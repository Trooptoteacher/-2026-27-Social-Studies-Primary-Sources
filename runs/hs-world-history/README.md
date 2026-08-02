# World History Primary-Source Download Pipeline

Deterministic, checkpointed downloader for the 186 World History manifest rows.
It resolves only the supplied repository records, preserves original bytes,
limits concurrency to four, checkpoints after every asset, and never creates
substitute sources.

## Contents

- `world_history_normalized_manifest.csv`: normalized working manifest.
- `download_state.sqlite`: authoritative per-row checkpoint state.
- `download_log.csv`: append-only event log.
- `exception_report.csv`: blocked, broken, license, and validation exceptions.
- `resume.sh`: idempotent restart command.
- `scripts/pipeline.py`: batch orchestrator.
- `scripts/resolvers.py`: repository-specific deterministic resolvers.
- `scripts/downloader.py`: HTTP download, signature validation, dimensions,
  SHA-256, and citation generation.
- `scripts/stage_to_repo.py`: stages validated assets and checkpoints into this
  primary-sources repository.

## Status model

`PENDING → DOWNLOADING → DOWNLOADED → UPLOADED → SUCCESS`

Terminal exceptions are `HOLD_LICENSE`, `BROKEN_LINK`, `ACCESS_BLOCKED`, and
`FAILED_VALIDATION`. Normal resumes skip every terminal status unless
`--force` is explicitly supplied.

## Resume

From this directory:

```bash
./resume.sh
```

Specific unit:

```bash
./resume.sh --unit "Cold War (1945-1991)" --batch-size 25
```

Specific manifest row:

```bash
./resume.sh --only-row 25 --force
```

## Current World History checkpoint

- Manifest rows: 186
- Successful repository assets: 14
- Access blocked: 130
- Broken links or unresolved exact matches: 37
- Failed exactness/content validation: 5
- License holds: 0
- Successful asset bytes: 495,124

Five downloaded candidates were rejected during final exactness validation:
three Library of Congress results did not match the specified item type/title,
and two Avalon pages were navigation menus rather than the source text.

Validated files live under `sources/hs-world-history/<STANDARD>/`, each with a
matching `.citation.md` sidecar. The authoritative JSON manifest is
`manifests/hs-world-history.json`.

## Validation

```bash
python3 tools/validate_primary_sources.py manifests/hs-world-history.json \
  --standards /path/to/2026-27-Tn.-Social-Studies-Standards/index.json
```

The full manifest passes the normal guardrail. The 14 verified records also
pass `--release` with zero blockers and zero warnings.
