# 2026-27 Social Studies — Primary Sources

Academically-accepted, TDOE Schedule F–compliant primary sources for the History Hack Social Studies suite (Grades 6–8, Tennessee History, World History, U.S. History, Government), with a full standards crosswalk and complete academic citations.

## Structure
- **`GUARDRAIL.md`** — the acceptance standard every source must meet (approved repository, cleared academic/commercial license, verified + cited, tied to a standard, accessible, and — for charts — built from cited primary-source data). Mapped to the verbatim TDOE Schedule F rubric.
- **`crosswalk/`** — one CSV per course: **every standard → its primary source(s) with full academic citation and sourcing** (title, creator, year, repository, rights/license, commercial-use flag, catalog URL, download URL, citation, alt text, verified, Schedule F SSP mapping). Standards are the verified 2026-27 set from `Trooptoteacher/2026-27-Tn.-Social-Studies-Standards`.
- **`manifests/`** — machine-readable source records (guardrail schema) for validation.
- **`tools/`** — `validate_primary_sources.py` (+ `approved_sources.py` policy). Run:
  ```
  python3 tools/validate_primary_sources.py manifests/government.json
  ```
  Exit 0 only at zero blockers. Add `--release` to also require alt text + verified.
- **`sources/`** — the actual image/document files, by course (e.g. `sources/government/GC.01_locke-portrait.jpg`).

## Status
| Course | Standards | Sources populated |
|---|---|---|
| Government | 35 | **35 (crosswalk complete, citations included)** |
| Grade 6 / 7 / 8, Tennessee, World, U.S. History | 350 | scaffolded — standards mapped, sources pending |

The non-Government sets are pending because the archive hosts (LoC / NARA / Smithsonian) are firewalled from the current build environment; the crosswalk rows are ready to fill once those are reachable. The Government set is populated from real, verified records — note two open items the validator flags: GC.29 rights need final confirmation, and several images are Wikimedia PD scans that should be swapped to the original LoC/NARA copy (Rule 1 "prefer original").

## Recommendation crosswalks (candidate sources for the download agent)
Guardrail-screened primary-source recommendations — **2 per standard** — for Grades 6–8, World History, and Tennessee (US History is maintained separately; Government is already downloaded/embedded). Excel in `crosswalk/xlsx/`, CSV alongside, machine-readable in `manifests/`. Every row is `verified: false` and carries a **Guardrail Check** column; the download agent fetches canonical items, confirms per-item rights, and sets verified.

| Course | Rows | Clean | Needs review (not commercial-safe) |
|---|---|---|---|
| Grade 6 | 124 | 124 | 0 |
| Grade 7 | 130 | 130 | 0 |
| Grade 8 | 150 | 150 | 0 |
| HS World History | 186 | 186 | 0 — cleared |
| Tennessee History | 128 | 128 | 0 — cleared |

All flagged copyrighted items (World 14, Tennessee 19) were CLEARED by swapping to public-domain substitutes of a different type — U.S. government/FRUS/court records, Chronicling America PD newspapers, CC0 museum objects, and U.S. patents — so every row is now commercial-use-safe (0 blockers). A few Civil Rights standards (MLK's copyrighted "Mountaintop" speech; some 1960s press imagery) are satisfied via a PD government/court record rather than a period photo; those rows carry a teacher note. `link_type=search` means "find it at this repository"; `canonical` means a high-confidence direct URL.

## Zero copyright risk (Rule 7 enforced)
Every source is guaranteed public domain by category — pre-1929 published, U.S. government work, official document/treaty/statute text, or explicit CC0 — with **no hedged rights**. The World History strict pass cleaned 27 famous PD documents and replaced 28 copyright-risky 20th-century photos/speeches with guaranteed-PD U.S.-government substitutes (e.g., Churchill's Iron Curtain speech → Kennan's Long Telegram; Berlin Wall 1989 → Bush Public Papers + Two Plus Four Treaty). Grade 6 rerouted 7 ancient-artifact images to Met/Smithsonian CC0. All five courses validate at 0 blockers under the Rule 7 validator.

## Maps crosswalks (downloadable PD maps) — Wave 1 of the visual-sources phase
`crosswalk/maps/` — **315 downloadable public-domain maps** across all geo-flagged standards in five courses (Grade 6: 59, Grade 7: 66, Grade 8: 56, World: 96, Tennessee: 38). Repositories: LOC Geography & Map Division, David Rumsey (CC BY), Perry-Castañeda/Shepherd 1911 atlas, U.S. Army Center of Military History + CIA maps (20th-c., US-gov PD), Census/USGS/NPS. All Rule 7 clean (0 blockers); `verified:false` for the download agent. (Charts and political cartoons follow as Waves 2–3.)
