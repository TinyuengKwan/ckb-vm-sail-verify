#!/usr/bin/env bash
# Run differential tests: CKB-VM vs Sail RISC-V emulator.
#
# Usage: ./scripts/run_differential.sh [options]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SAIL_BIN="$PROJECT_DIR/deps/sail-riscv/build/c_emulator/sail_riscv_sim"

# Find CKB-VM test artifacts
CKB_VM_TESTS=""
for d in "$PROJECT_DIR/deps/ckb-vm" "$HOME/workplace/ckb-vm" "/tmp/ckb-vm-ref"; do
    if [ -d "$d/tests/artifact/spec" ]; then
        CKB_VM_TESTS="$d/tests/artifact/spec"
        break
    fi
done

VERBOSE=""
TEST_DIR=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --test-dir) TEST_DIR="$2"; shift 2 ;;
        --sail-bin) SAIL_BIN="$2"; shift 2 ;;
        --verbose)  VERBOSE="--verbose"; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

[ -z "$TEST_DIR" ] && [ -n "$CKB_VM_TESTS" ] && TEST_DIR="$CKB_VM_TESTS"

if [ -z "$TEST_DIR" ]; then
    echo "ERROR: No test directory. Use --test-dir <path>"
    echo "  or: git clone --depth=1 https://github.com/nervosnetwork/ckb-vm /tmp/ckb-vm-ref"
    exit 1
fi

if [ ! -f "$SAIL_BIN" ]; then
    echo "WARNING: Sail emulator not found at $SAIL_BIN"
    echo "Build: make sail-emu"
fi

echo "=== CKB-VM Differential Test ==="
echo "Tests: $TEST_DIR"
echo "Sail:  $SAIL_BIN"
echo ""

cargo run --release -p ckb-vm-diff-test -- \
    --test-dir "$TEST_DIR" \
    --sail-bin "$SAIL_BIN" \
    $VERBOSE
