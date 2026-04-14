#!/usr/bin/env bash
# Build the Sail RISC-V C++ emulator for differential testing.
#
# Usage: ./scripts/build_sail_emulator.sh <sail-riscv-dir>
#
# This builds the sail_riscv_sim binary that can be used for:
# 1. Direct ELF execution with --trace flag
# 2. RVFI-DII protocol for instruction-level comparison

set -euo pipefail

SAIL_RISCV_DIR="${1:?Usage: $0 <sail-riscv-dir>}"

if [ ! -f "$SAIL_RISCV_DIR/CMakeLists.txt" ]; then
    echo "ERROR: sail-riscv not found at $SAIL_RISCV_DIR"
    exit 1
fi

echo "==> Building Sail RISC-V emulator..."
echo "    Source: $SAIL_RISCV_DIR"

# Configure if needed
if [ ! -d "$SAIL_RISCV_DIR/build" ]; then
    echo "==> Configuring cmake..."
    cmake -S "$SAIL_RISCV_DIR" -B "$SAIL_RISCV_DIR/build" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DDOWNLOAD_GMP=TRUE
fi

# Build
cmake --build "$SAIL_RISCV_DIR/build" -j"$(nproc)" --target sail_riscv_sim

SAIL_BIN="$SAIL_RISCV_DIR/build/c_emulator/sail_riscv_sim"
if [ -f "$SAIL_BIN" ]; then
    echo ""
    echo "==> Build successful!"
    echo "    Binary: $SAIL_BIN"
    echo ""
    echo "    Test with: $SAIL_BIN --help"
else
    echo "ERROR: Build completed but binary not found at $SAIL_BIN"
    exit 1
fi
