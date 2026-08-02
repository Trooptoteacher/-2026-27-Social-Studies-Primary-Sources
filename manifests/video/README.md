# Video source manifests

Video is a first-class asset type here, validated by the same guardrail as maps,
charts, cartoons, and images (`tools/validate_primary_sources.py`). Records use the
standard manifest schema plus two video-specific rules.

## Two extra rules for video
1. **No YouTube, no third-party player.** Every accepted clip is **downloaded and
   self-hosted** so there is no external navigation surface and no ads — a core
   district-safety promise. Records carry `"hosting": "self-hosted-pd"`.
2. **Cite the institution, not the aggregator.** Same provenance rule as everything
   else: Wikimedia Commons / bare Internet Archive / DPLA are discovery tools, never
   the cited source. `repository` names a Tier-1/2 authority (NARA, LoC, C-SPAN
   floor, etc.). `approved_sources.py` now includes `c-span.org` (House/Senate floor
   proceedings are public domain; C-SPAN-produced programming is not — the `rights`
   field must reflect that per record).

## Schema (per record)
Same fields as the image/map manifests: `standard, title, type:"video", creator,
year, repository, rights, commercial_use_ok, catalog_url, download_url, citation,
alt_text, verified, schedule_f{table1_standard, table3_ssp}` — plus `hosting`.

- `catalog_url` may be a repository **search/landing URL** ("find it here") while
  `verified:false`; the download agent then fetches the canonical item, confirms
  per-item rights, sets `download_url` + `verified:true`.
- `rights` must be an **un-hedged** cleared basis (public domain / U.S. government
  work / pre-1929 / CC0 / CC BY). "Verify per item" phrasing is a Rule 7 blocker, so
  per-item-verify sources (Prelinger, TeVA) are only added once an individual item's
  PD basis is confirmed.

## Status
- `government.video.json` — seed set across units where authentic public-domain
  footage exists (legislative floor, executive, citizen participation, civil
  liberties, TN/TVA). Passes the validator at **0 blockers** (non-release).
- Other courses — pending the per-standard sourcing pass, done course-by-course so
  each URL is individually confirmed (not bulk-guessed). Grade 6–7 (ancient/medieval)
  and pure-philosophy standards have little/no authentic video by nature; carry those
  with the image/primary-source bank.

## Validate
```
python3 tools/validate_primary_sources.py manifests/video/government.video.json
# add --release to also require alt_text + verified
```
