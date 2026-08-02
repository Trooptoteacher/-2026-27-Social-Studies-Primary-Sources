#!/usr/bin/env bash
# Resume command for the World History primary-source download pipeline.
#
# Safe to re-run any time: rows already in a terminal state (SUCCESS,
# HOLD_LICENSE, BROKEN_LINK, ACCESS_BLOCKED, UPLOADED) are skipped unless
# --force is added. State is tracked in download_state.sqlite.
#
# Usage:
#   ./resume.sh                # resume all units (skips terminal rows)
#   ./resume.sh --force        # re-attempt ALL rows, including terminal ones
#   ./resume.sh --only-row 5   # re-attempt a single manifest row (0-indexed, data rows only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${MANIFEST_PATH:-$SCRIPT_DIR/world_history_normalized_manifest.csv}"

echo "=== Resuming primary source download pipeline ==="
echo "Manifest: $MANIFEST"
echo "Pipeline dir: $SCRIPT_DIR"

if [[ " $* " == *" --unit "* ]] || [[ " $* " == *" --all-units "* ]]; then
  python3 "$SCRIPT_DIR/scripts/pipeline.py" --manifest "$MANIFEST" "$@"
else
  python3 "$SCRIPT_DIR/scripts/pipeline.py" --manifest "$MANIFEST" --all-units --batch-size 25 "$@"
fi

echo ""
echo "Done. See download_log.csv, exception_report.csv, and download_state.sqlite in $SCRIPT_DIR"
