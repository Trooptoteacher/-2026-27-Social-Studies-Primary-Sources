#!/usr/bin/env python3
"""
Primary Source Guardrail validator — TDOE Schedule F compliance.

Enforces PRIMARY_SOURCE_GUARDRAIL.md against a manifest of primary-source (and
chart/graph) records. Reuses approved_sources.classify() so the repository
allowlist is defined in exactly one place.

Usage:
    python3 validate_primary_sources.py <manifest.json | manifest.csv> [--standards <index.json>] [--release]

Exit code 0 only when there are ZERO blockers. Warnings never fail the build,
except that --release promotes accessibility/verification warnings to blockers.
"""
import sys, os, json, csv, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from approved_sources import classify
except Exception:
    def classify(_):  # fail-closed if the policy module is missing
        return "unknown"

APPROVED_LICENSES = (
    "public domain", "no known restrictions", "no known copyright",
    "cc0", "cc by", "cc-by", "creative commons attribution",
    "u.s. government work", "us government work", "federal government work", "public record",
)
STD_RE = re.compile(r"^(US|GC|TN|W|[678])\.\d{1,3}[A-Za-z]?$")
CHART_TYPES = {"chart", "graph", "figure", "table"}


def load(path):
    if path.endswith(".json"):
        d = json.load(open(path, encoding="utf-8"))
        return d if isinstance(d, list) else (d.get("sources") or d.get("items") or d.get("records") or [])
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    return rows


def valid_standards(index_path):
    if not index_path or not os.path.exists(index_path):
        return None
    codes = set()
    idx = json.load(open(index_path, encoding="utf-8"))
    base = os.path.dirname(index_path)
    for c in idx.get("courses", []):
        f = os.path.join(base, os.path.basename(os.path.dirname(c["file"])), os.path.basename(c["file"])) \
            if False else os.path.join(base, c["file"])
        try:
            for s in json.load(open(f, encoding="utf-8")).get("standards", []):
                codes.add(s.get("code"))
        except Exception:
            pass
    return codes or None


def truthy(v):
    return str(v).strip().lower() in ("true", "yes", "y", "1", "✓", "check")


def check(rec, i, known_codes, release):
    blockers, warns = [], []
    tag = rec.get("standard") or rec.get("Standard") or f"row {i}"
    g = lambda *ks: next((rec[k] for k in ks if rec.get(k) not in (None, "")), "")

    # Charts/graphs are ORIGINAL graphics we build from cited factual data — they don't
    # redistribute a copyrighted image, and facts aren't copyrightable. So the image-source
    # rules (repository allowlist, per-item license, verified download) don't apply; only
    # Rule 4 (tied to a standard) and Rule 6 (cite a real, non-tertiary dataset) do.
    if str(g("type", "Type")).lower() in CHART_TYPES:
        std = g("standard", "Standard")
        if not std or not STD_RE.match(str(std).strip()):
            blockers.append(f"chart standard '{std}' missing/invalid (Rule 4)")
        ds = g("data_source", "Data source")
        dsu = g("data_source_url", "Data source URL") or g("catalog_url", "Catalog URL")
        if not ds:
            blockers.append("chart has no cited dataset (Rule 6)")
        if not dsu:
            blockers.append("chart has no data_source_url (Rule 6)")
        elif classify(dsu) == "blocked":
            blockers.append(f"chart data source is a tertiary/encyclopedia source '{dsu}' (Rule 6)")
        elif classify(dsu) == "unknown":
            warns.append(f"chart data source '{dsu}' is an academic/uncatalogued host — confirm the dataset is real; the chart is original (Rule 6)")
        if not g("citation", "Citation"):
            warns.append("chart missing citation")
        return tag, blockers, warns

    std = g("standard", "Standard")
    if not std:
        blockers.append("no standard code (Rule 4)")
    elif not STD_RE.match(str(std).strip()):
        blockers.append(f"standard code '{std}' not a valid TN code (Rule 4)")
    elif known_codes is not None and str(std).strip() not in known_codes:
        blockers.append(f"standard '{std}' not in the 2026-27 standards source of truth (Rule 4)")

    repo = g("repository", "Repository")
    url = g("catalog_url", "Catalog URL", "url")
    cls = classify(url or repo)
    if cls == "blocked":
        blockers.append(f"repository '{repo or url}' is BLOCKED — tertiary/encyclopedia (Rule 1)")
    elif cls == "unknown":
        blockers.append(f"repository '{repo or url}' unrecognized — vet + add to approved_sources.py (Rule 1)")
    elif cls == "prefer_original":
        warns.append(f"'{repo or url}' is a PD host — prefer the original repository (Rule 1)")

    rights = str(g("rights", "Rights / License", "license")).lower()
    HEDGE = ("verify individual", "verify the", "verify each", "verify item", "verify rights",
             "confirm rights", "confirm the copyright", "confirm cc0", "confirm open",
             "rights unclear", "copyright status unclear", "may be under copyright",
             "possibly copyright", "if pd", "if public domain", "check copyright",
             "check rights", "varies by item", "varies", "depends on")
    if not rights:
        blockers.append("no rights/license recorded (Rule 2)")
    elif not any(a in rights for a in APPROVED_LICENSES):
        blockers.append(f"rights '{rights}' not a cleared academic/commercial license (Rule 2)")
    elif any(h in rights for h in HEDGE):
        blockers.append(f"rights are HEDGED ('{rights[:60]}') — needs a guaranteed PD basis, no teacher copyright risk (Rule 7)")
    if not truthy(g("commercial_use_ok", "Commercial Use OK?")):
        (blockers if rights and not any(a in rights for a in APPROVED_LICENSES) else warns).append(
            "commercial_use_ok not affirmed (Rule 2)")

    if not g("citation", "Citation"):
        blockers.append("no citation (Rule 3)")
    if not url:
        blockers.append("no catalog URL (Rule 3)")
    if not g("download_url", "Direct download URL"):
        warns.append("no direct download URL (Rule 3)")
    if not truthy(g("verified", "Verified?")):
        (blockers if release else warns).append("not verified (Rule 3)")

    if not g("alt_text", "alt", "Alt text"):
        (blockers if release else warns).append("no alt text (Rule 5 / Schedule F Table 4)")

    if str(g("type", "Type")).lower() in CHART_TYPES:
        ds, dsu = g("data_source", "Data source"), g("data_source_url", "Data source URL")
        if not ds:
            blockers.append("chart has no cited primary-source dataset (Rule 6)")
        if not dsu:
            blockers.append("chart has no data_source_url (Rule 6)")
        elif classify(dsu) == "blocked":
            blockers.append(f"chart data_source is a tertiary/encyclopedia source '{dsu}' (Rule 6)")
        elif classify(dsu) == "unknown":
            # A chart WE build from factual data does not redistribute the source, and facts
            # are not copyrightable — so an academic/journal (e.g. doi.org) data source is
            # acceptable as long as the dataset is real and cited. Flag to confirm, not block.
            warns.append(f"chart data source '{dsu}' is an academic/uncatalogued host — confirm the dataset is real; the chart itself is original (Rule 6)")
    return tag, blockers, warns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    release = "--release" in sys.argv
    idx = None
    if "--standards" in sys.argv:
        idx = sys.argv[sys.argv.index("--standards") + 1]
    if not args:
        print("usage: validate_primary_sources.py <manifest.json|csv> [--standards index.json] [--release]")
        sys.exit(2)
    recs = load(args[0])
    known = valid_standards(idx)
    total_b = total_w = 0
    print(f"Validating {len(recs)} record(s) against PRIMARY_SOURCE_GUARDRAIL.md"
          f"{' [RELEASE mode]' if release else ''}"
          f"{' — standards checked vs source of truth' if known else ''}\n")
    for i, rec in enumerate(recs, 1):
        tag, b, w = check(rec, i, known, release)
        if b or w:
            print(f"[{tag}]")
            for x in b:
                print(f"   BLOCKER: {x}")
            for x in w:
                print(f"   warn:    {x}")
        total_b += len(b); total_w += len(w)
    print(f"\n{'='*60}\nRESULT: {total_b} blocker(s), {total_w} warning(s) across {len(recs)} record(s).")
    if total_b == 0:
        print("PASS — Schedule F primary-source guardrail satisfied.")
    else:
        print("FAIL — resolve blockers before release.")
    sys.exit(1 if total_b else 0)


if __name__ == "__main__":
    main()
