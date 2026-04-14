#!/usr/bin/env bash
# Generate Coq definitions from Sail RISC-V model for CKB-VM subset.
#
# Usage: ./scripts/generate_coq.sh <sail-riscv-dir> <output-dir>
#
# Prerequisites:
#   - sail compiler installed (opam install sail)
#   - coq-sail-stdpp installed (opam install coq-sail-stdpp)
#   - sail-riscv repository cloned

set -euo pipefail

SAIL_RISCV_DIR="${1:?Usage: $0 <sail-riscv-dir> <output-dir>}"
OUTPUT_DIR="${2:?Usage: $0 <sail-riscv-dir> <output-dir>}"

# Validate sail-riscv directory
if [ ! -f "$SAIL_RISCV_DIR/model/riscv.sail_project" ]; then
    echo "ERROR: sail-riscv model not found at $SAIL_RISCV_DIR"
    echo "Expected: $SAIL_RISCV_DIR/model/riscv.sail_project"
    exit 1
fi

# Check for sail compiler
if ! command -v sail &> /dev/null; then
    echo "ERROR: sail compiler not found. Install with: opam install sail"
    exit 1
fi

echo "Sail RISC-V model: $SAIL_RISCV_DIR"
echo "Output directory:  $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Step 1: Build the sail-riscv project if not already built
if [ ! -d "$SAIL_RISCV_DIR/build" ]; then
    echo "==> Configuring sail-riscv build..."
    cmake -S "$SAIL_RISCV_DIR" -B "$SAIL_RISCV_DIR/build" \
        -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -5
fi

# Step 2: Generate Coq using sail-riscv's CMake target
echo "==> Generating Coq for RV64..."
cmake --build "$SAIL_RISCV_DIR/build" --target generated_rocq_rv64d 2>&1 | tail -10

# Step 3: Copy generated files to our output directory
echo "==> Copying generated Coq files..."
cp "$SAIL_RISCV_DIR/build/rocq/rv64d.v" "$OUTPUT_DIR/CkbVmSpec.v"
cp "$SAIL_RISCV_DIR/build/rocq/rv64d_types.v" "$OUTPUT_DIR/CkbVmSpec_types.v"

# Step 4: Copy handwritten support
if [ -f "$SAIL_RISCV_DIR/handwritten_support/riscv_extras.v" ]; then
    cp "$SAIL_RISCV_DIR/handwritten_support/riscv_extras.v" "$OUTPUT_DIR/riscv_extras.v"
fi

echo ""
echo "==> Coq generation complete. Files:"
ls -la "$OUTPUT_DIR"/*.v
echo ""
echo "Next steps:"
echo "  1. cd coq && make   # to compile proofs"
