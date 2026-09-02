#!/usr/bin/env bash
# Generate Sail definitions in the selected theorem-prover backend.
# Rust/Aeneas extraction and its production connection are separate Week 4–5 gates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SAIL_RISCV_DIR="${SAIL_RISCV_DIR:-$PROJECT_DIR/deps/sail-riscv}"
SAIL_BUILD="$SAIL_RISCV_DIR/build"
BACKEND="${1:-lean}"
MATERIALIZED_CONFIG="$PROJECT_DIR/sail-model/build/ckb_vm_config.json"

case "$BACKEND" in
    lean)
        TARGET="generated_lean_rv64d"
        SOURCE="$SAIL_BUILD/model/Lean_RV64D"
        DESTINATION="$PROJECT_DIR/proof/lean/generated/sail"
        ;;
    rocq|coq)
        BACKEND="rocq"
        TARGET="generated_rocq_rv64d"
        SOURCE="$SAIL_BUILD/rocq"
        DESTINATION="$PROJECT_DIR/proof/rocq/generated/sail"
        ;;
    *)
        echo "ERROR: backend must be lean or rocq" >&2
        exit 2
        ;;
esac

if [ ! -f "$MATERIALIZED_CONFIG" ]; then
    "$SCRIPT_DIR/prepare_sail_config.sh"
fi
if [ ! -d "$SAIL_BUILD/config" ]; then
    echo "ERROR: Sail CMake build is not configured; run make sail-emu" >&2
    exit 1
fi

cp "$MATERIALIZED_CONFIG" "$SAIL_BUILD/config/rv64d_v256_e64.json"
cmake --build "$SAIL_BUILD" --target "$TARGET"

mkdir -p "$DESTINATION"
cp -R "$SOURCE"/. "$DESTINATION"/
cp "$MATERIALIZED_CONFIG" "$DESTINATION/ckb_vm_config.json"
sha256sum "$DESTINATION/ckb_vm_config.json" >"$DESTINATION/ckb_vm_config.json.sha256"

echo "Generated Sail $BACKEND definitions: $DESTINATION"
echo "NOTE: generating these files says nothing about whether they compile."
echo "      Run scripts/check_proof_model.sh $BACKEND for that; it is what"
echo "      separates a reproducible generation from a usable model."
echo "NOTE: this does not extract Rust and does not establish an equivalence theorem."
