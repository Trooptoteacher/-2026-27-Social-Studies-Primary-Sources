"""
Deterministic repository resolvers.

Each resolver takes a manifest row and attempts to identify the EXACT
supplied work within its named repository using title / creator / date.
It must return a dict:
    {
        "ok": True/False,
        "download_url": str or None,
        "extension_hint": str or None,
        "status": one of ACCESS_BLOCKED / BROKEN_LINK / None (None if ok),
        "error": str or None,
        "resolution_note": str  (how it was matched, for citation/audit trail)
    }

No open-web research. No guessing. If ambiguous -> ACCESS_BLOCKED / BROKEN_LINK.
"""
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def _http_get(url, headers=None, timeout=30, max_retries=3):
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                return resp.status, dict(resp.getheaders()), data
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 401, 410):
                # Could be a hard permanent error OR a transient rate limit (Met API uses 403
                # for throttling). Back off once or twice before giving up, but do not loop forever.
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)
                    last_exc = e
                    continue
                raise
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(1.5 * attempt)
                last_exc = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                last_exc = e
                continue
            raise
    raise last_exc

def _norm(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokens(s):
    return set(_norm(s).split())

def _title_key_tokens(title):
    """Remove stopwords/common words to focus match on distinctive terms."""
    stop = {"the", "of", "a", "an", "and", "or", "in", "on", "at", "to", "for",
            "portrait", "print", "engraving", "painting", "view", "map"}
    return {t for t in _tokens(title) if t not in stop and len(t) > 2}


# ---------------------------------------------------------------------------
# The Metropolitan Museum of Art  -- public Collection API, no key required
# ---------------------------------------------------------------------------
def resolve_met(row):
    title = row["title"]
    creator = row["creator_or_institution"]
    # Build search query from source_page_url q param if present, else title
    parsed = urllib.parse.urlparse(row["source_page_url"])
    qs = urllib.parse.parse_qs(parsed.query)
    url_query = qs.get("q", [title])[0]

    object_ids = []
    query = url_query
    for candidate_query in [url_query, title]:
        search_url = f"https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&q={urllib.parse.quote(candidate_query)}"
        try:
            status, _, data = _http_get(search_url)
            result = json.loads(data)
        except Exception as e:
            return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"Met search request failed: {e}"}
        ids = result.get("objectIDs") or []
        if ids:
            object_ids = ids
            query = candidate_query
            break

    if not object_ids:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"No Met objects found for queries tried: {[url_query, title]}."}

    title_key = _title_key_tokens(title)
    creator_key = _tokens(creator)
    # strip qualifiers like "after", "various" that never appear literally on museum records
    creator_key = {t for t in creator_key if t not in {"after", "various", "the"}}
    # A creator surname is "distinctive" if it's a proper-noun-like token (len>3), used to
    # require a creator match when the manifest supplies a specific artist attribution.
    distinctive_creator_tokens = {t for t in creator_key if len(t) > 3}

    candidates = []
    probes = 0
    max_probes = 25
    for oid in object_ids:
        if probes >= max_probes:
            break
        try:
            _, _, obj_data = _http_get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
            obj = json.loads(obj_data)
        except Exception:
            continue
        probes += 1
        time.sleep(0.15)
        obj_title_key = _title_key_tokens(obj.get("title", ""))
        artist = obj.get("artistDisplayName", "") or ""
        artist_key = _tokens(artist)
        title_overlap = len(title_key & obj_title_key)
        creator_overlap = len(distinctive_creator_tokens & artist_key)
        has_image = bool(obj.get("primaryImage"))
        is_pd = obj.get("isPublicDomain", False)
        # Require substantial title overlap (majority of distinctive title tokens) AND,
        # when the manifest specifies a distinctive creator, require that creator to match.
        title_ok = len(title_key) > 0 and title_overlap >= max(2, (len(title_key) + 1) // 2)
        creator_required = len(distinctive_creator_tokens) > 0
        creator_ok = (creator_overlap == len(distinctive_creator_tokens)) if creator_required else True
        if title_ok and creator_ok and has_image:
            candidates.append({
                "objectID": oid,
                "title": obj.get("title"),
                "artist": artist,
                "primaryImage": obj.get("primaryImage"),
                "isPublicDomain": is_pd,
                "objectURL": obj.get("objectURL"),
                "title_overlap": title_overlap,
                "creator_overlap": creator_overlap,
                "objectDate": obj.get("objectDate"),
            })

    if not candidates:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": (f"No Met object matched required title tokens {sorted(title_key)} "
                          f"AND creator tokens {sorted(distinctive_creator_tokens)} for query '{query}' "
                          f"within first {probes} probed candidates (out of {len(object_ids)} total search hits).")}

    candidates.sort(key=lambda c: (c["title_overlap"], c["creator_overlap"]), reverse=True)
    best = candidates[0]
    # Detect real ambiguity: multiple top-scoring distinct candidates
    top_score = (best["title_overlap"], best["creator_overlap"])
    tied = [c for c in candidates if (c["title_overlap"], c["creator_overlap"]) == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous Met match: {len(tied)} objects tie on title/creator overlap for '{title}'. IDs: {[c['objectID'] for c in tied]}"}

    if not best["isPublicDomain"]:
        return {"ok": False, "status": "HOLD_LICENSE",
                "error": f"Met object {best['objectID']} ('{best['title']}') is not flagged isPublicDomain."}

    return {
        "ok": True,
        "download_url": best["primaryImage"],
        "extension_hint": "jpg",
        "status": None,
        "error": None,
        "resolution_note": f"Met Collection API object {best['objectID']} matched title tokens {sorted(title_key & _title_key_tokens(best['title']))}; artist='{best['artist']}'; objectURL={best['objectURL']}",
    }


# ---------------------------------------------------------------------------
# Avalon Project, Yale Law School  -- canonical direct page, text/html document
# ---------------------------------------------------------------------------
def resolve_avalon(row):
    url = row["source_page_url"]
    if not url or "avalon.law.yale.edu" not in url:
        return {"ok": False, "status": "BROKEN_LINK", "error": "No canonical Avalon URL supplied."}
    try:
        status, headers, data = _http_get(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return {"ok": False, "status": "ACCESS_BLOCKED" if e.code == 403 else "BROKEN_LINK",
                    "error": f"Avalon page returned HTTP {e.code} for {url}."}
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Avalon page request failed: {e}"}
    except Exception as e:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Avalon page request failed: {e}"}

    if status != 200:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Avalon page returned HTTP {status}."}

    # Confirm the title text appears on the page (basic sanity, not open-web research).
    html_text = data.decode("utf-8", errors="ignore")
    title_key_terms = [t for t in _title_key_tokens(row["title"]) if len(t) > 3]
    matched = sum(1 for t in title_key_terms if t in html_text.lower())
    if title_key_terms and matched < max(1, len(title_key_terms) // 3):
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"Avalon page at {url} did not contain expected title terms {title_key_terms}."}

    return {
        "ok": True,
        "download_url": url,
        "extension_hint": "html",
        "status": None,
        "error": None,
        "resolution_note": f"Avalon canonical URL {url} verified to contain title terms {title_key_terms}.",
    }


# ---------------------------------------------------------------------------
# U.S. National Archives (NARA) -- canonical direct page
# ---------------------------------------------------------------------------
def resolve_nara(row):
    url = row["source_page_url"]
    if not url or "archives.gov" not in url:
        return {"ok": False, "status": "BROKEN_LINK", "error": "No canonical NARA URL supplied."}
    try:
        status, headers, data = _http_get(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return {"ok": False, "status": "ACCESS_BLOCKED" if e.code == 403 else "BROKEN_LINK",
                    "error": f"NARA page returned HTTP {e.code} for {url}."}
        return {"ok": False, "status": "BROKEN_LINK", "error": f"NARA page request failed: {e}"}
    except Exception as e:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"NARA page request failed: {e}"}

    if status != 200:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"NARA page returned HTTP {status}."}

    html_text = data.decode("utf-8", errors="ignore")
    title_key_terms = [t for t in _title_key_tokens(row["title"]) if len(t) > 3]
    matched = sum(1 for t in title_key_terms if t in html_text.lower())
    if title_key_terms and matched < max(1, len(title_key_terms) // 3):
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"NARA page at {url} did not contain expected title terms {title_key_terms}."}

    return {
        "ok": True,
        "download_url": url,
        "extension_hint": "html",
        "status": None,
        "error": None,
        "resolution_note": f"NARA canonical URL {url} verified to contain title terms {title_key_terms}.",
    }


# ---------------------------------------------------------------------------
# Library of Congress -- JSON search API (loc.gov/search/?fo=json)
# ---------------------------------------------------------------------------
def _loc_search_once(query, title_key):
    search_url = f"https://www.loc.gov/search/?q={urllib.parse.quote(query)}&fo=json"
    status, _, data = _http_get(search_url)
    result = json.loads(data)
    results = result.get("results") or []

    candidates = []
    for r in results:
        if r.get("access_restricted"):
            continue
        item_title = r.get("title") or ""
        item_key = _title_key_tokens(item_title)
        overlap = len(title_key & item_key)
        image_urls = r.get("image_url") or []
        original_format = r.get("original_format") or []
        is_webpage = "web page" in original_format
        if overlap >= max(1, len(title_key) // 2) and image_urls and not is_webpage:
            candidates.append({
                "title": item_title,
                "id": r.get("id"),
                "url": r.get("url"),
                "image_url": image_urls[-1] if image_urls else None,
                "overlap": overlap,
                "date": r.get("date"),
            })
    return candidates


def _extract_quoted_or_bare_title(title):
    """If the title contains a quoted primary phrase, extract it (drop parenthetical
    English gloss) -- e.g. '"A faut ... bentot" (The Third Estate)' -> 'A faut ... bentot'.
    This is a deterministic string transform of the manifest's own supplied title, not
    open-web research."""
    m = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', title)
    if m:
        return m.group(1)
    # Strip trailing parenthetical, e.g. "Title (1215)" -> "Title"
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def resolve_loc(row):
    parsed = urllib.parse.urlparse(row["source_page_url"])
    qs = urllib.parse.parse_qs(parsed.query)
    url_query = qs.get("q", [row["title"]])[0]
    title_key = _title_key_tokens(row["title"])
    extracted_title = _extract_quoted_or_bare_title(row["title"])

    # Strategy: try (1) the exact supplied title text, (2) a deterministic extraction of the
    # quoted/primary phrase from that same title (dropping bracketed glosses), then (3) fall
    # back to the manifest's source_page_url query param. Do not broaden further (no open-web
    # research) -- if none yield an unambiguous match, report clearly.
    queries_tried = []
    all_candidates_by_query = {}
    for query in [row["title"], extracted_title, url_query]:
        if query in queries_tried:
            continue
        queries_tried.append(query)
        try:
            cands = _loc_search_once(query, title_key)
        except Exception as e:
            return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"LOC search request failed for query '{query}': {e}"}
        all_candidates_by_query[query] = cands
        if cands:
            candidates = cands
            matched_query = query
            break
    else:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"No LOC results matched title tokens {sorted(title_key)} for queries tried: {queries_tried}."}

    candidates.sort(key=lambda c: c["overlap"], reverse=True)
    top_score = candidates[0]["overlap"]
    tied = [c for c in candidates if c["overlap"] == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous LOC match: {len(tied)} items tie on title overlap for '{row['title']}' (query='{matched_query}'). URLs: {[c['url'] for c in tied]}"}

    best = tied[0]
    if not best["image_url"]:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"LOC item {best['url']} has no image_url."}

    return {
        "ok": True,
        "download_url": best["image_url"],
        "extension_hint": "jpg",
        "status": None,
        "error": None,
        "resolution_note": f"LOC search (query='{matched_query}') matched item '{best['title']}' ({best['url']}) via title overlap {sorted(title_key)}",
    }


# ---------------------------------------------------------------------------
# Rijksmuseum -- API requires a registered API key we do not have. The public
# search UI is JS-rendered and its search endpoint is disallowed by robots.txt
# for automated access. Deterministic resolution is not possible without
# credentials -> ACCESS_BLOCKED.
# ---------------------------------------------------------------------------
def resolve_rijksmuseum(row):
    return {
        "ok": False,
        "status": "ACCESS_BLOCKED",
        "error": ("Rijksmuseum Collection API requires a registered Rijksstudio API key "
                  "(none available in this environment); the public web search UI is "
                  "JavaScript-rendered and its search endpoint is disallowed by "
                  "rijksmuseum.nl/robots.txt for automated/API access, so the exact "
                  "object cannot be deterministically resolved without credentials."),
    }


# ---------------------------------------------------------------------------
# HathiTrust Digital Library -- catalog and full-text access are behind a
# Cloudflare bot-challenge (verified via direct HTTP probe); no key-based API
# is available for anonymous full-volume PDF download of arbitrary public
# domain works without passing the interactive challenge. -> ACCESS_BLOCKED
# ---------------------------------------------------------------------------
def resolve_hathitrust(row):
    return {
        "ok": False,
        "status": "ACCESS_BLOCKED",
        "error": ("HathiTrust catalog and full-text search endpoints are behind an "
                  "interactive Cloudflare bot-challenge (verified via direct HTTP probe "
                  "returning a JS challenge page), which blocks deterministic automated "
                  "resolution and full-volume download without a browser session/credentials."),
    }


# ---------------------------------------------------------------------------
# Documenting the American South, UNC-Chapel Hill -- canonical direct page.
# Reuses the same canonical-page-fetch + title-term-verify pattern as Avalon/NARA.
# ---------------------------------------------------------------------------
def resolve_docsouth(row):
    url = row["source_page_url"]
    if not url or "docsouth.unc.edu" not in url:
        return {"ok": False, "status": "BROKEN_LINK", "error": "No canonical Documenting the American South URL supplied."}
    try:
        status, headers, data = _http_get(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return {"ok": False, "status": "ACCESS_BLOCKED" if e.code == 403 else "BROKEN_LINK",
                    "error": f"Documenting the American South page returned HTTP {e.code} for {url}."}
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Documenting the American South page request failed: {e}"}
    except Exception as e:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Documenting the American South page request failed: {e}"}

    if status != 200:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Documenting the American South page returned HTTP {status}."}

    html_text = data.decode("utf-8", errors="ignore")
    title_key_terms = [t for t in _title_key_tokens(row["title"]) if len(t) > 3]
    matched = sum(1 for t in title_key_terms if t in html_text.lower())
    if title_key_terms and matched < max(1, len(title_key_terms) // 3):
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"Documenting the American South page at {url} did not contain expected title terms {title_key_terms}."}

    return {
        "ok": True,
        "download_url": url,
        "extension_hint": "html",
        "status": None,
        "error": None,
        "resolution_note": f"Documenting the American South canonical URL {url} verified to contain title terms {title_key_terms}.",
    }


# ---------------------------------------------------------------------------
# Office of the Historian, U.S. Department of State (history.state.gov) --
# canonical FRUS volume/document pages only (verified: /historicaldocuments/search
# and bare /search both return HTTP 404 -- no deterministic search API without a
# browser session, so 'search' link_type rows for this repository are ACCESS_BLOCKED).
# 'canonical' link_type rows use the documented stable URL pattern
# https://history.state.gov/historicaldocuments/{VOLUME_ID}/{ELEMENT_ID} and are
# fetched + title-verified directly, same pattern as Avalon/NARA/docsouth.
# ---------------------------------------------------------------------------
def resolve_history_state_gov(row):
    url = row["source_page_url"]
    link_type = (row.get("link_type") or "").strip().lower()
    if not url or "history.state.gov" not in url:
        return {"ok": False, "status": "BROKEN_LINK", "error": "No history.state.gov URL supplied."}

    if link_type == "search" or "/search" in urllib.parse.urlparse(url).path:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": ("history.state.gov has no deterministic search API: both "
                          "/historicaldocuments/search and bare /search return HTTP 404 "
                          f"(verified) for {url}; the Office of the Historian's only public, "
                          "key-free API is the FRUS ebook-catalog OPDS feed (distinct ebook "
                          "volumes, not individual documents/images), which cannot deterministically "
                          "locate this row's exact supplied work.")}

    try:
        status, headers, data = _http_get(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return {"ok": False, "status": "ACCESS_BLOCKED" if e.code == 403 else "BROKEN_LINK",
                    "error": f"history.state.gov page returned HTTP {e.code} for {url}."}
        return {"ok": False, "status": "BROKEN_LINK", "error": f"history.state.gov page request failed: {e}"}
    except Exception as e:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"history.state.gov page request failed: {e}"}

    if status != 200:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"history.state.gov page returned HTTP {status}."}

    html_text = data.decode("utf-8", errors="ignore")
    title_key_terms = [t for t in _title_key_tokens(row["title"]) if len(t) > 3]
    matched = sum(1 for t in title_key_terms if t in html_text.lower())
    if title_key_terms and matched < max(1, len(title_key_terms) // 3):
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"history.state.gov page at {url} did not contain expected title terms {title_key_terms}."}

    return {
        "ok": True,
        "download_url": url,
        "extension_hint": "html",
        "status": None,
        "error": None,
        "resolution_note": f"history.state.gov canonical URL {url} verified to contain title terms {title_key_terms}.",
    }


# ---------------------------------------------------------------------------
# U.S. National Archives (NARA) -- 'search' link_type rows against
# catalog.archives.gov/search. Verified: both the search UI and the Catalog
# API v2 (catalog.archives.gov/api/v2/records/search) now require a
# registered x-api-key (per archives.gov API docs); none is available in
# this environment, and the search UI itself renders no server-side results
# (pure JS shell, verified via direct HTTP probe). Deterministic resolution
# without credentials is not possible -> ACCESS_BLOCKED. 'canonical' rows
# (direct archives.gov/... pages) continue to use resolve_nara() above.
# ---------------------------------------------------------------------------
def resolve_nara_catalog_search(row):
    url = row["source_page_url"]
    return {
        "ok": False,
        "status": "ACCESS_BLOCKED",
        "error": ("NARA Catalog search (catalog.archives.gov/search and the Catalog API v2 "
                  "records/search endpoint) requires a registered x-api-key (verified via direct "
                  "HTTP probe: both the search UI and the unauthenticated API call return a bare "
                  "JS-shell/empty response, not server-rendered results or data), which is not "
                  f"available in this environment; cannot deterministically resolve {url}."),
    }


def resolve_nara_dispatch(row):
    """NARA rows may be 'canonical' (direct archives.gov page) or 'search'
    (catalog.archives.gov/search, API-key gated). Dispatch on link_type/URL."""
    url = row["source_page_url"] or ""
    link_type = (row.get("link_type") or "").strip().lower()
    if link_type == "search" or "catalog.archives.gov/search" in url:
        return resolve_nara_catalog_search(row)
    return resolve_nara(row)


# ---------------------------------------------------------------------------
# Library of Congress -- Chronicling America sub-collection. Reuses the main
# LOC JSON search API pattern, scoped to the chronicling-america collection
# path (loc.gov/collections/chronicling-america/?q=...&fo=json).
# ---------------------------------------------------------------------------
def _loc_chronicling_america_search_once(query, title_key):
    search_url = f"https://www.loc.gov/collections/chronicling-america/?q={urllib.parse.quote(query)}&fo=json"
    status, _, data = _http_get(search_url)
    result = json.loads(data)
    results = result.get("results") or []

    candidates = []
    for r in results:
        if r.get("access_restricted"):
            continue
        item_title = r.get("title") or ""
        item_key = _title_key_tokens(item_title)
        overlap = len(title_key & item_key)
        image_urls = r.get("image_url") or []
        if overlap >= max(1, len(title_key) // 2) and image_urls:
            candidates.append({
                "title": item_title,
                "id": r.get("id"),
                "url": r.get("url"),
                "image_url": image_urls[-1] if image_urls else None,
                "overlap": overlap,
                "date": r.get("date"),
            })
    return candidates


def resolve_chronicling_america(row):
    parsed = urllib.parse.urlparse(row["source_page_url"])
    qs = urllib.parse.parse_qs(parsed.query)
    url_query = qs.get("q", [row["title"]])[0]
    title_key = _title_key_tokens(row["title"])

    try:
        candidates = _loc_chronicling_america_search_once(url_query, title_key)
    except Exception as e:
        return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"Chronicling America search request failed for query '{url_query}': {e}"}

    if not candidates:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"No Chronicling America results matched title tokens {sorted(title_key)} for query '{url_query}'."}

    candidates.sort(key=lambda c: c["overlap"], reverse=True)
    top_score = candidates[0]["overlap"]
    tied = [c for c in candidates if c["overlap"] == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous Chronicling America match: {len(tied)} items tie on title overlap for '{row['title']}' (query='{url_query}'). URLs: {[c['url'] for c in tied]}"}

    best = tied[0]
    if not best["image_url"]:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Chronicling America item {best['url']} has no image_url."}

    return {
        "ok": True,
        "download_url": best["image_url"],
        "extension_hint": "jpg",
        "status": None,
        "error": None,
        "resolution_note": f"Chronicling America search (query='{url_query}') matched item '{best['title']}' ({best['url']}) via title overlap {sorted(title_key)}",
    }


# ---------------------------------------------------------------------------
# NASA Image and Video Library -- public images-api.nasa.gov, no key required.
# ---------------------------------------------------------------------------
def resolve_nasa_images(row):
    parsed = urllib.parse.urlparse(row["source_page_url"])
    qs = urllib.parse.parse_qs(parsed.query)
    url_query = qs.get("q", [row["title"]])[0]
    title_key = _title_key_tokens(row["title"])

    search_url = f"https://images-api.nasa.gov/search?q={urllib.parse.quote(url_query)}&media_type=image"
    try:
        status, _, data = _http_get(search_url)
        result = json.loads(data)
    except Exception as e:
        return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"NASA Images API search request failed for '{url_query}': {e}"}

    items = (result.get("collection") or {}).get("items") or []
    candidates = []
    for it in items:
        data_list = it.get("data") or []
        if not data_list:
            continue
        item_meta = data_list[0]
        item_title = item_meta.get("title", "") or ""
        item_key = _title_key_tokens(item_title)
        overlap = len(title_key & item_key)
        if overlap >= max(2, (len(title_key) + 1) // 2):
            candidates.append({
                "title": item_title,
                "nasa_id": item_meta.get("nasa_id"),
                "href": it.get("href"),
                "overlap": overlap,
                "date_created": item_meta.get("date_created"),
            })

    if not candidates:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"No NASA Images result matched required title tokens {sorted(title_key)} for query '{url_query}' (out of {len(items)} search hits)."}

    candidates.sort(key=lambda c: c["overlap"], reverse=True)
    top_score = candidates[0]["overlap"]
    tied = [c for c in candidates if c["overlap"] == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous NASA Images match: {len(tied)} items tie on title overlap for '{row['title']}'. IDs: {[c['nasa_id'] for c in tied]}"}

    best = tied[0]
    # The 'href' points to a collection.json manifest listing actual asset URLs; fetch it
    # and pick the largest available original/orig image.
    try:
        _, _, manifest_data = _http_get(best["href"])
        asset_urls = json.loads(manifest_data)
    except Exception as e:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"NASA Images asset manifest fetch failed for {best['nasa_id']}: {e}"}

    orig_urls = [u for u in asset_urls if isinstance(u, str) and ("~orig" in u or "~large" in u)]
    if not orig_urls:
        image_urls = [u for u in asset_urls if isinstance(u, str) and u.lower().endswith((".jpg", ".jpeg", ".png"))]
        if not image_urls:
            return {"ok": False, "status": "BROKEN_LINK", "error": f"NASA Images item {best['nasa_id']} has no downloadable image asset in its manifest."}
        orig_urls = image_urls

    return {
        "ok": True,
        "download_url": orig_urls[0],
        "extension_hint": "jpg",
        "status": None,
        "error": None,
        "resolution_note": f"NASA Images API matched nasa_id={best['nasa_id']} title='{best['title']}' via title overlap {sorted(title_key)}; asset manifest {best['href']}",
    }


# ---------------------------------------------------------------------------
# Smithsonian Institution -- Open Access API (api.si.edu), works with the
# public DEMO_KEY (verified). Requires strict title match AND presence of an
# online_media image asset in the record (many SI catalog records are
# metadata-only with no digitized image, which is a real, non-guessable gap).
# ---------------------------------------------------------------------------
def resolve_smithsonian(row):
    parsed = urllib.parse.urlparse(row["source_page_url"])
    qs = urllib.parse.parse_qs(parsed.query)
    url_query = qs.get("edan_q", [row["title"]])[0]
    title_key = _title_key_tokens(row["title"])

    search_url = f"https://api.si.edu/openaccess/api/v1.0/search?q={urllib.parse.quote(url_query)}&api_key=DEMO_KEY&rows=50"
    try:
        status, _, data = _http_get(search_url)
        result = json.loads(data)
    except Exception as e:
        return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"Smithsonian Open Access API search request failed for '{url_query}': {e}"}

    rows_ = (result.get("response") or {}).get("rows") or []
    candidates = []
    for r in rows_:
        item_title = r.get("title", "") or ""
        item_key = _title_key_tokens(item_title)
        overlap = len(title_key & item_key)
        content = r.get("content") or {}
        descriptive = content.get("descriptiveNonRepeating") or {}
        online_media = descriptive.get("online_media") or {}
        media = online_media.get("media") or []
        image_media = [m for m in media if m.get("type") == "Images" and m.get("content")]
        if overlap >= max(2, (len(title_key) + 1) // 2) and image_media:
            candidates.append({
                "title": item_title,
                "id": r.get("id"),
                "overlap": overlap,
                "image_url": image_media[0]["content"],
            })

    if not candidates:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"No Smithsonian record matched title tokens {sorted(title_key)} AND had a digitized online image for query '{url_query}' (out of {len(rows_)} search hits)."}

    candidates.sort(key=lambda c: c["overlap"], reverse=True)
    top_score = candidates[0]["overlap"]
    tied = [c for c in candidates if c["overlap"] == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous Smithsonian match: {len(tied)} records tie on title overlap for '{row['title']}'. IDs: {[c['id'] for c in tied]}"}

    best = tied[0]
    return {
        "ok": True,
        "download_url": best["image_url"],
        "extension_hint": "jpg",
        "status": None,
        "error": None,
        "resolution_note": f"Smithsonian Open Access API matched id={best['id']} title='{best['title']}' via title overlap {sorted(title_key)}",
    }


# ---------------------------------------------------------------------------
# U.S. Government Publishing Office (govinfo.gov) -- the public site's
# /app/search/{json} URL is a client-side SPA route, but the underlying
# search API it calls (POST www.govinfo.gov/wssearch/search) is reachable
# without a key (verified). We extract the same 'query' the manifest's URL
# encodes and issue that POST directly. Requires strict title-token match
# against the messy free-text 'line1' result field (title-cased document
# titles), since govinfo's own 'title' metadata field is not reliably present.
# ---------------------------------------------------------------------------
def _govinfo_extract_query(source_page_url):
    parsed = urllib.parse.urlparse(source_page_url)
    marker = "/app/search/"
    if marker in parsed.path:
        raw_json = urllib.parse.unquote(parsed.path.split(marker, 1)[1])
        try:
            return json.loads(raw_json).get("query")
        except Exception:
            return None
    return None


def resolve_govinfo(row):
    url = row["source_page_url"]
    query = _govinfo_extract_query(url)
    if not query:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"Could not extract a search query from govinfo.gov URL {url}."}

    title_key = _title_key_tokens(row["title"])

    try:
        req = urllib.request.Request(
            "https://www.govinfo.gov/wssearch/search",
            data=json.dumps({"query": query, "offset": 0, "pageSize": 20}).encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        result = json.loads(data)
    except Exception as e:
        return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"govinfo.gov search API request failed for query '{query}': {e}"}

    result_set = result.get("resultSet") or []
    candidates = []
    for r in result_set:
        line1 = re.sub(r"<[^>]+>", "", r.get("line1") or "")
        field_map = r.get("fieldMap") or {}
        item_key = _title_key_tokens(line1)
        overlap = len(title_key & item_key)
        pdf_file = field_map.get("pdffile")
        package_id = field_map.get("packageid")
        doc_url = field_map.get("url")
        if overlap >= max(2, (len(title_key) + 1) // 2) and (pdf_file or doc_url):
            candidates.append({
                "title": line1,
                "package_id": package_id,
                "overlap": overlap,
                "url": doc_url,
            })

    if not candidates:
        return {"ok": False, "status": "BROKEN_LINK",
                "error": f"No govinfo.gov result matched title tokens {sorted(title_key)} for query '{query}' (out of {len(result_set)} search hits)."}

    candidates.sort(key=lambda c: c["overlap"], reverse=True)
    top_score = candidates[0]["overlap"]
    tied = [c for c in candidates if c["overlap"] == top_score]
    if len(tied) > 1:
        return {"ok": False, "status": "ACCESS_BLOCKED",
                "error": f"Ambiguous govinfo.gov match: {len(tied)} results tie on title overlap for '{row['title']}' (query='{query}'). Package IDs: {[c['package_id'] for c in tied]}"}

    best = tied[0]
    if not best["url"]:
        return {"ok": False, "status": "BROKEN_LINK", "error": f"govinfo.gov result {best['package_id']} has no direct document URL."}

    return {
        "ok": True,
        "download_url": best["url"],
        "extension_hint": "pdf" if best["url"].lower().endswith(".pdf") else "html",
        "status": None,
        "error": None,
        "resolution_note": f"govinfo.gov search API (query='{query}') matched package {best['package_id']} title='{best['title']}' via title overlap {sorted(title_key)}",
    }


RESOLVERS = {
    "The Metropolitan Museum of Art": resolve_met,
    "Avalon Project, Yale Law School": resolve_avalon,
    "U.S. National Archives (NARA)": resolve_nara_dispatch,
    "U.S. National Archives (archives.gov)": resolve_nara_dispatch,
    "Library of Congress": resolve_loc,
    "Rijksmuseum": resolve_rijksmuseum,
    "HathiTrust Digital Library": resolve_hathitrust,
    "Documenting the American South, UNC-Chapel Hill": resolve_docsouth,
    "Office of the Historian, U.S. Department of State (history.state.gov)": resolve_history_state_gov,
    "Chronicling America, Library of Congress (loc.gov/chroniclingamerica)": resolve_chronicling_america,
    "NASA Image and Video Library": resolve_nasa_images,
    "Smithsonian Institution": resolve_smithsonian,
    "U.S. Government Publishing Office (govinfo.gov)": resolve_govinfo,
}

def resolve(row):
    repo = row["repository"]
    fn = RESOLVERS.get(repo)
    if not fn:
        return {"ok": False, "status": "ACCESS_BLOCKED", "error": f"No resolver implemented for repository '{repo}'."}
    return fn(row)
