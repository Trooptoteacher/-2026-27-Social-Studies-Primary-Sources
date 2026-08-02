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
