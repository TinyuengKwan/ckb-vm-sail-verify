#!/usr/bin/env bash
# Generate and transactionally install a fresh Sail theorem-prover model.
# Rust/Aeneas extraction and its production connection are separate Week 4–5 gates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="${1:-lean}"
[ "$#" -le 1 ] || { echo "usage: $0 [lean|rocq]" >&2; exit 2; }
python3 "$SCRIPT_DIR/sail_model_transaction.py" "$BACKEND"

if [ "$BACKEND" = coq ]; then
    BACKEND=rocq
fi

echo "Generated Sail $BACKEND definitions; previous directories retained in the reported backups."
echo "NOTE: generating these files says nothing about whether they compile."
echo "      Run scripts/check_proof_model.sh $BACKEND for that; it is what"
echo "      separates a reproducible generation from a usable model."
echo "NOTE: this does not extract Rust and does not establish an equivalence theorem."
