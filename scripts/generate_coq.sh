#!/usr/bin/env bash
# Generate Coq definitions from Sail RISC-V model for CKB-VM subset.
#
# Usage: ./scripts/generate_coq.sh [sail-riscv-dir] [output-dir]
#
# Defaults:
#   sail-riscv-dir = deps/sail-riscv
#   output-dir     = coq/generated

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SAIL_RISCV_DIR="${1:-$PROJECT_DIR/deps/sail-riscv}"
OUTPUT_DIR="${2:-$PROJECT_DIR/coq/generated}"

# Validate
if [ ! -f "$SAIL_RISCV_DIR/model/riscv.sail_project" ]; then
    echo "ERROR: sail-riscv model not found at $SAIL_RISCV_DIR"
    echo "Run: git submodule update --init --recursive"
    exit 1
fi

if ! command -v sail &> /dev/null; then
    echo "ERROR: sail compiler not found. Install with: opam install sail"
    exit 1
fi

echo "Sail RISC-V: $SAIL_RISCV_DIR"
echo "Output:      $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Configure cmake if needed
if [ ! -d "$SAIL_RISCV_DIR/build" ]; then
    echo "==> Configuring sail-riscv..."
    cmake -S "$SAIL_RISCV_DIR" -B "$SAIL_RISCV_DIR/build" \
        -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -5
fi

# Generate Coq
echo "==> Generating Coq for RV64..."
cmake --build "$SAIL_RISCV_DIR/build" --target generated_rocq_rv64d 2>&1 | tail -10

# Copy
echo "==> Copying..."
cp "$SAIL_RISCV_DIR/build/rocq/rv64d.v" "$OUTPUT_DIR/CkbVmSpec.v"
cp "$SAIL_RISCV_DIR/build/rocq/rv64d_types.v" "$OUTPUT_DIR/CkbVmSpec_types.v"

if [ -f "$SAIL_RISCV_DIR/handwritten_support/riscv_extras.v" ]; then
    cp "$SAIL_RISCV_DIR/handwritten_support/riscv_extras.v" "$OUTPUT_DIR/riscv_extras.v"
fi

echo ""
echo "==> Done. Files:"
ls -la "$OUTPUT_DIR"/*.v
