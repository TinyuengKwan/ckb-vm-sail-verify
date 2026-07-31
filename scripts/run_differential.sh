#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ELF="${1:?usage: run_differential.sh path/to/test.elf}"

cd "$PROJECT_DIR"
cargo run --locked -p ckb-vm-sail-diff -- \
    --elf "$ELF" \
    --sail-bin "${SAIL_BIN:-deps/sail-riscv/build/c_emulator/sail_riscv_sim}" \
    --sail-config "${SAIL_CONFIG:-sail-model/build/ckb_vm_config.json}"
