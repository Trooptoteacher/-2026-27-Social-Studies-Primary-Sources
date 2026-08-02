# Primary Source Guardrail — TDOE Schedule F Compliance

**Every primary source (and every chart/graph built from primary-source data) used in a History Hack deck, workbook, or web edition MUST pass this guardrail before release.** It exists so that all sourced material is academically accepted and defensible as a *primary resource* under the TDOE Social Studies Instructional Materials rubric (Schedule F). Enforced by `validate_primary_sources.py` (which reuses `approved_sources.py`, the single source of truth for repositories).

Rubric source of truth: `courses/*/06_COMPLIANCE_INTERNAL/schedule-f-rubric-source.md`.

---

## Rule 1 — Approved repository only (accuracy / Schedule F C5)
The source must come from an **authoritative, academically-accepted repository**, classified by `approved_sources.classify()`:

- **approved** — `*.gov` / `*.edu` and the named list: Library of Congress, National Archives (NARA) & DocsTeach, Office of the Historian, NPS, Smithsonian (incl. NMAAHC), U.S. Census, Congress.gov, GovInfo, Supreme Court, presidential libraries (incl. FDR Library), Army/Navy history commands, **Tennessee Encyclopedia**, **TeVA**, **Tennessee State Museum**, State of Tennessee; **open-access museums & libraries** with public-domain / CC0 programs — The Met, Cleveland Museum of Art, National Gallery of Art, Getty, Rijksmuseum, NYPL Digital Collections, HathiTrust; **Gilder Lehrman**; and **authoritative data sources** for charts — Census, BLS, BEA, USGS, NOAA, NASA, FRED (Federal Reserve), Our World in Data (CC BY). ✅ pass. *(Repository trust only — per-item rights are still enforced by Rule 2, so a copyrighted item on an approved host still fails Rule 2.)*
- **prefer_original** — Wikimedia Commons / DPLA / Internet Archive / Flickr Commons / PICRYL / GetArchive hosting a genuinely public-domain work. ⚠️ allowed, but a warning: swap to the ORIGINAL repository (LoC/NARA/TN State/originating museum) when the same item exists there.
- **blocked** — Wikipedia, Britannica, or any general/tertiary encyclopedia or study-aid site (History.com, Study.com, Ducksters, Quizlet, SparkNotes, CliffsNotes, IXL). ❌ **BLOCKER** — never a cited primary source (fact-check aid only).
- **unknown** — unrecognized host. ❌ **BLOCKER** until vetted and added to `approved_sources.py`.

## Rule 2 — Academic / commercial use cleared (approved for use as a primary resource)
Rights must be one of: **Public Domain**, **CC0**, **CC BY**, or **U.S. Government Work** (and, for TN items, TeVA/State terms that permit educational + commercial use). `commercial_use_ok` must be `true`, with the exact rights statement recorded. Anything "no known copyright" must cite the hosting repository's rights page. ❌ BLOCKER if rights are missing, unclear, or non-commercial/ND.

## Rule 3 — Verified, retrievable, cited
Each source must carry a **complete citation**, a working **catalog URL** (the item's page at the repository) **and** a **direct download URL**, and `verified: true` — meaning both URLs were actually opened and confirmed to resolve to the stated item. ❌ BLOCKER: missing citation, missing catalog URL, or `verified` not true at release. ⚠️ WARN: missing direct download URL.

## Rule 4 — Tied to a standard + serves the SSPs (Schedule F Tables 1 & 3)
Every source maps to a specific standard code (`US.xx`, `8.xx`, `6.xx`, `7.xx`, `W.xx`, `GC.xx`, `TN.xx`) that exists in the **2026-27 standards source of truth** (`Trooptoteacher/2026-27-Tn.-Social-Studies-Standards`). It must enable authentic **source analysis** (SSP.01 collect · SSP.02 examine · SSP.03 synthesize) and evidence-based writing — i.e., a usable primary document/image, not decoration. ❌ BLOCKER: no valid standard code.

## Rule 5 — Accessibility (Schedule F Table 4)
Every image/source ships with **alt text** and is deliverable in **print + digital**. ⚠️ WARN (BLOCKER at final release): missing alt text.

## Rule 6 — Charts & graphs are built FROM cited primary-source data
Any chart or graph is a **derived primary resource** and is held to the same bar:
- It must be generated from an **actual primary-source dataset** (e.g., U.S. Census, BLS, NARA/GovInfo statistical series, Congressional record) — **never fabricated, estimated, or "representative" numbers.**
- The record must include `data_source` (the dataset), `data_source_url` (classified **approved** by Rule 1), the **year/series**, and a citation. The rendered chart must show the data source on-figure.
- ❌ BLOCKER: a chart with no cited primary-source dataset, or a `data_source_url` that is blocked/unknown, or any value not traceable to the cited dataset.

---

## Required record schema (per source)
```json
{
  "standard": "US.28",
  "title": "…", "type": "photo|document|map|cartoon|artifact|chart|graph",
  "creator": "…", "year": "1920",
  "repository": "Library of Congress",
  "rights": "Public domain — no known restrictions",
  "commercial_use_ok": true,
  "catalog_url": "https://www.loc.gov/item/…",
  "download_url": "https://tile.loc.gov/…full.jpg",
  "citation": "Formatted citation string",
  "alt_text": "…",
  "verified": true,
  "schedule_f": {"table1_standard": true, "table3_ssp": ["SSP.01","SSP.02"]},
  "data_source": null, "data_source_url": null
}
```
For `type: chart|graph`, `data_source`, `data_source_url`, and `year` are **required** (Rule 6).

## Gate
`validate_primary_sources.py <manifest.json|csv>` → **exit 0 only when zero BLOCKERs.** Warnings are printed but do not fail. Run it in preflight and in CI before any primary-source set is merged or embedded.
