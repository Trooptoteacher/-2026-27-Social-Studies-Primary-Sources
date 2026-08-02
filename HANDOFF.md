# Agent Handoff — Primary-Source Manifests & Spreadsheets

This repo is the **single source of truth** for the 2026-27 TN Social Studies
primary-source library. Another agent (or a human) can pick it up from here to
**download the actual source files, confirm per-item rights, and mark records
verified.** Nothing here is fabricated; every record is guaranteed public domain
by category (see `GUARDRAIL.md`, Rule 7).

---

## What's here (what to consume)

### Manifests — machine-readable, one JSON record per source
| Path | Contents |
|---|---|
| `manifests/*.json` | Primary sources — one file per course (`government`, `grade-06/07/08`, `hs-world-history`, `tennessee-history`) |
| `manifests/maps/*.json` | Wave 1 — 315 public-domain maps |
| `manifests/charts/*.json` | Wave 2 — 101 chart opportunities (build FROM cited data) |
| `manifests/cartoons/*.json` | Wave 3 — 52 public-domain political cartoons |

### Spreadsheets — the same data, human-readable
| Path | Contents |
|---|---|
| `crosswalk/xlsx/*.xlsx` + `crosswalk/*.csv` | Primary sources, per course |
| `crosswalk/{maps,charts,cartoons}/xlsx/*.xlsx` | Visual sources, per wave |

**The JSON manifests are the machine interface. The `.xlsx`/`.csv` are the same
records for human review — treat the JSON as authoritative if they ever differ.**

---

## Record schema (each manifest entry)
```json
{
  "standard": "US.28",
  "title": "...", "type": "photo|document|map|cartoon|artifact|chart|graph",
  "creator": "...", "year": "1920",
  "repository": "Library of Congress",
  "rights": "Public domain — no known restrictions",
  "commercial_use_ok": true,
  "catalog_url": "https://www.loc.gov/item/...",   // the item's page at the archive
  "download_url": "https://tile.loc.gov/...full.jpg", // direct file
  "citation": "...", "alt_text": "...",
  "verified": false,                                // <- YOUR JOB: flip to true
  "data_source": null, "data_source_url": null      // required for chart/graph
}
```

## The consuming agent's job
Most records are **`verified: false`** — they were screened and cited, but the
actual files were **not** downloaded here (this build environment is firewalled
from LOC / NARA / Smithsonian / tn.gov, which 403). To finish:

1. For each `verified: false` record, open `catalog_url` and `download_url` and
   confirm they resolve to the stated item.
2. Confirm the item's rights match `rights` (public domain / CC0 / CC BY / U.S.
   government work). If an item turns out to be in copyright, **replace it** with
   a guaranteed-PD substitute — do **not** ship it (Rule 7). There is plenty of
   safe content.
3. Save the file (suggested: `sources/<course>/<STANDARD>_<slug>.<ext>`), then set
   `verified: true`.
4. **Charts/graphs are not downloaded — they are built.** Generate the graphic
   from the cited `data_source_url` (facts aren't copyrightable, so the chart is
   an original, copyright-clean work). Show the data source on-figure.

## Validate before you ship
Every change must still pass the guardrail — exit 0 only at zero blockers:
```bash
python3 tools/validate_primary_sources.py manifests/<course>.json \
    --standards <path-to>/2026-27-standards/index.json
# add --release to also require alt text + verified:true
```
Rules live in `GUARDRAIL.md`; the repository allowlist is `tools/approved_sources.py`
(the one place a new host is vetted and added).

## Status at handoff
- **Government** — files already downloaded/embedded (`sources/government/`).
- **All other courses + all visual waves** — screened, cited, `verified: false`;
  pending the download/verify pass above.
- Everything validates at **0 guardrail blockers** as-is.
