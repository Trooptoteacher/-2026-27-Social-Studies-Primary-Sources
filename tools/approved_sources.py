#!/usr/bin/env python3
"""
Approved-source policy for the Social Studies Hack suite (TDOE Schedule F, C5).

Single source of truth for which repositories may be CITED in adoption-grade
content. Imported by geo_review_audit.py and asset_standards_crosswalk.py so the
same rule is enforced everywhere.

classify(url_or_text) -> one of:
  "approved"        — authoritative government / archival / scholarly repository
  "prefer_original" — acceptable host for a genuinely public-domain work, but a
                      reviewer prefers the ORIGINAL repository (e.g. Wikimedia
                      Commons hosting a LoC/NARA image); allowed, warned
  "blocked"         — tertiary/general encyclopedia; never a cited source
  "unknown"         — not recognized; treat as a failure until vetted
"""

# Authoritative, academically-accepted repositories (domain -> label).
APPROVED = {
    "loc.gov": "Library of Congress",
    "archives.gov": "U.S. National Archives (NARA)",
    "docsteach.org": "NARA DocsTeach",
    "history.state.gov": "U.S. Dept. of State, Office of the Historian",
    "nps.gov": "National Park Service",
    "energy.gov": "U.S. Department of Energy",
    "fhwa.dot.gov": "Federal Highway Administration",
    "history.army.mil": "U.S. Army Center of Military History",
    "history.navy.mil": "U.S. Navy History & Heritage Command",
    "si.edu": "Smithsonian Institution",
    "nmaahc.si.edu": "Smithsonian NMAAHC",
    "census.gov": "U.S. Census Bureau",
    "congress.gov": "U.S. Congress",
    "govinfo.gov": "U.S. Government Publishing Office",
    "supremecourt.gov": "Supreme Court of the United States",
    "jfklibrary.org": "JFK Presidential Library",
    "hoover.archives.gov": "Hoover Presidential Library (NARA)",
    "911memorial.org": "National September 11 Memorial & Museum",
    "tennesseeencyclopedia.net": "Tennessee Encyclopedia",
    "tn.gov": "State of Tennessee",
    "sos.tn.gov": "Tennessee Secretary of State",
    "teva.contentdm.oclc.org": "Tennessee Virtual Archive (TeVA)",
}
# Any *.gov and *.edu host is treated as approved even if not listed above.
APPROVED_TLDS = (".gov", ".edu")

# Acceptable HOST for a public-domain work, but prefer the original repository.
PREFER_ORIGINAL = {
    "commons.wikimedia.org": "Wikimedia Commons (media repository)",
    "dp.la": "Digital Public Library of America",
}

# Tertiary/general encyclopedias — never a cited source (fact-check aid only).
BLOCKED = {
    "britannica.com": "Encyclopaedia Britannica",
    "wikipedia.org": "Wikipedia",
    "en.wikipedia.org": "Wikipedia",
}


def _host(s):
    s = str(s or "").lower()
    if "://" in s:
        s = s.split("://", 1)[1]
    # citations often read "... — Library of Congress: https://www.loc.gov/..."
    if " http" in s:
        s = s.split(" http", 1)[1]
    s = s.split("/", 1)[0].split()[-1] if s else s
    return s.lstrip("www.")


# Repository-name fallbacks (when a row gives a name, not a URL).
NAME_APPROVED = ("library of congress", "national archives", "office of the historian",
                 "national park service", "smithsonian", "census", "army center of military",
                 "navy history", "tennessee encyclopedia", "presidential library",
                 "department of energy", "federal highway", "supreme court", "9/11 memorial",
                 "september 11 memorial")
NAME_PREFER = ("wikimedia commons", "wikimedia", "digital public library", "dpla")
NAME_BLOCKED = ("britannica", "wikipedia")


def classify(url_or_text):
    h = _host(url_or_text)
    for dom in BLOCKED:
        if h == dom or h.endswith("." + dom):
            return "blocked"
    for dom in PREFER_ORIGINAL:
        if h == dom or h.endswith("." + dom):
            return "prefer_original"
    for dom in APPROVED:
        if h == dom or h.endswith("." + dom):
            return "approved"
    if h.endswith(APPROVED_TLDS):
        return "approved"
    # name-based fallback (repository column may be a label, not a URL).
    # Check Wikimedia (Commons/CDN) BEFORE the "wikipedia" substring so that
    # upload.wikimedia.org storage paths (which contain "/wikipedia/") are not
    # mistaken for the encyclopedia.
    t = str(url_or_text or "").lower()
    if "wikimedia" in h or any(n in t for n in NAME_PREFER):
        return "prefer_original"
    if any(n in t for n in NAME_BLOCKED):
        return "blocked"
    if any(n in t for n in NAME_APPROVED):
        return "approved"
    return "unknown"


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(f"{classify(arg):15} {arg}")
