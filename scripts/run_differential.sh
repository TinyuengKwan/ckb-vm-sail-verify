#!/usr/bin/env bash
# Run differential tests between CKB-VM and Sail RISC-V emulator.
#
# Usage: ./scripts/run_differential.sh [options]
#
# Options:
#   --test-dir <dir>   Directory containing test ELF binaries
#   --sail-bin <path>  Path to Sail emulator (default: auto-detect)
#   --verbose          Enable verbose output

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default paths
SAIL_RISCV_DIR="${SAIL_RISCV_DIR:-$HOME/workplace/sail-riscv}"
SAIL_BIN="${SAIL_RISCV_DIR}/build/c_emulator/sail_riscv_sim"

# CKB-VM test artifacts (if ckb-vm is cloned nearby)
CKB_VM_TESTS=""
if [ -d "$HOME/workplace/ckb-vm/tests/artifact/spec" ]; then
    CKB_VM_TESTS="$HOME/workplace/ckb-vm/tests/artifact/spec"
fi

# Parse arguments
VERBOSE=""
TEST_DIR=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --test-dir) TEST_DIR="$2"; shift 2 ;;
        --sail-bin) SAIL_BIN="$2"; shift 2 ;;
        --verbose)  VERBOSE="--verbose"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Default test directory
if [ -z "$TEST_DIR" ] && [ -n "$CKB_VM_TESTS" ]; then
    TEST_DIR="$CKB_VM_TESTS"
fi

if [ -z "$TEST_DIR" ]; then
    echo "ERROR: No test directory specified."
    echo "Usage: $0 --test-dir <path/to/elf/tests>"
    echo ""
    echo "You can use CKB-VM's test artifacts:"
    echo "  git clone https://github.com/nervosnetwork/ckb-vm ~/workplace/ckb-vm"
    echo "  $0 --test-dir ~/workplace/ckb-vm/tests/artifact/spec"
    exit 1
fi

# Check Sail emulator
if [ ! -f "$SAIL_BIN" ]; then
    echo "WARNING: Sail emulator not found at $SAIL_BIN"
    echo "Build it with: ./scripts/build_sail_emulator.sh $SAIL_RISCV_DIR"
    echo ""
    echo "Running CKB-VM side only (no comparison)..."
fi

echo "=== CKB-VM Differential Test ==="
echo "Test directory: $TEST_DIR"
echo "Sail emulator:  $SAIL_BIN"
echo ""

# Build differential test binary
cargo build --release --manifest-path "$PROJECT_DIR/differential-test/Cargo.toml"

# Run tests
cargo run --release --manifest-path "$PROJECT_DIR/differential-test/Cargo.toml" -- \
    --test-dir "$TEST_DIR" \
    --sail-bin "$SAIL_BIN" \
    $VERBOSE
