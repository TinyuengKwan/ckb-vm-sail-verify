#!/usr/bin/env bash
# Stable entry: missing inputs and unrelated failures never count as NO-GO.
# Every run preserves a new evidence directory; existing outputs are not removed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/rocq_spike.py" "$@"
