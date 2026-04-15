#!/usr/bin/env bash
# Build the Sail RISC-V C++ emulator for differential testing.
#
# Usage: ./scripts/build_sail_emulator.sh [sail-riscv-dir]
# Default: deps/sail-riscv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SAIL_RISCV_DIR="${1:-$PROJECT_DIR/deps/sail-riscv}"

if [ ! -f "$SAIL_RISCV_DIR/CMakeLists.txt" ]; then
    echo "ERROR: sail-riscv not found at $SAIL_RISCV_DIR"
    echo "Run: git submodule update --init --recursive"
    exit 1
fi

echo "==> Building Sail RISC-V emulator..."
echo "    Source: $SAIL_RISCV_DIR"

if [ ! -d "$SAIL_RISCV_DIR/build" ]; then
    echo "==> Configuring cmake..."
    cmake -S "$SAIL_RISCV_DIR" -B "$SAIL_RISCV_DIR/build" \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DDOWNLOAD_GMP=TRUE
fi

cmake --build "$SAIL_RISCV_DIR/build" -j"$(nproc)" --target sail_riscv_sim

SAIL_BIN="$SAIL_RISCV_DIR/build/c_emulator/sail_riscv_sim"
if [ -f "$SAIL_BIN" ]; then
    echo "==> Build successful: $SAIL_BIN"
else
    echo "ERROR: Binary not found at $SAIL_BIN"
    exit 1
fi
