#!/usr/bin/env bash
# Verify the declared, currently executable foundation toolchain.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

EXPECTED_CKB_VM="1ffba3977da9dcdef8092e9ab1fd2516b27ec939"
EXPECTED_SAIL_RISCV="27224ccb2290f022e46213c05b3e72e8a9ea635e"
EXPECTED_SAIL_VERSION="0.20.2"
MINIMUM_RUST_VERSION="1.95.0"
EXPECTED_CONFIG_HASH="41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024"
EXPECTED_ISA="rv64imcb_zca_zba_zbb_zbc_zbs"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

for command in awk cargo cmake git head jq rustc sail sed sha256sum sort; do
    require_command "$command"
done

actual_rust_version="$(rustc --version | awk '{print $2}')"
oldest_rust_version="$(printf '%s\n%s\n' "$MINIMUM_RUST_VERSION" "$actual_rust_version" | sort -V | head -n 1)"
if [ "$oldest_rust_version" != "$MINIMUM_RUST_VERSION" ]; then
    fail "Rust $actual_rust_version is older than required $MINIMUM_RUST_VERSION"
fi

actual_sail_version="$(sail --version | sed -n 's/^Sail \([^ ]*\).*/\1/p')"
if [ "$actual_sail_version" != "$EXPECTED_SAIL_VERSION" ]; then
    fail "Sail version is $actual_sail_version; expected $EXPECTED_SAIL_VERSION"
fi

read_submodule_commit() {
    local directory="$1"
    local name="$2"
    if [ ! -e "$directory/.git" ]; then
        fail "$name submodule is not initialized: $directory"
    fi
    git -C "$directory" rev-parse HEAD
}

actual_ckb_vm="$(read_submodule_commit "$PROJECT_DIR/deps/ckb-vm" ckb-vm)"
if [ "$actual_ckb_vm" != "$EXPECTED_CKB_VM" ]; then
    fail "ckb-vm commit is $actual_ckb_vm; expected $EXPECTED_CKB_VM"
fi

actual_sail_riscv="$(read_submodule_commit "$PROJECT_DIR/deps/sail-riscv" sail-riscv)"
if [ "$actual_sail_riscv" != "$EXPECTED_SAIL_RISCV" ]; then
    fail "sail-riscv commit is $actual_sail_riscv; expected $EXPECTED_SAIL_RISCV"
fi

SAIL_BIN="${SAIL_BIN:-$PROJECT_DIR/deps/sail-riscv/build/c_emulator/sail_riscv_sim}"
MATERIALIZED_CONFIG="${SAIL_CONFIG:-$PROJECT_DIR/sail-model/build/ckb_vm_config.json}"

if [ ! -x "$SAIL_BIN" ]; then
    fail "Sail emulator is missing; run make sail-config"
fi
if [ ! -f "$MATERIALIZED_CONFIG" ]; then
    fail "materialized Sail config is missing; run make sail-config"
fi

actual_config_hash="$(sha256sum "$MATERIALIZED_CONFIG" | awk '{print $1}')"
if [ "$actual_config_hash" != "$EXPECTED_CONFIG_HASH" ]; then
    fail "Sail config hash is $actual_config_hash; expected $EXPECTED_CONFIG_HASH"
fi

actual_isa="$("$SAIL_BIN" --config "$MATERIALIZED_CONFIG" --print-isa-string)"
if [ "$actual_isa" != "$EXPECTED_ISA" ]; then
    fail "Sail ISA is $actual_isa; expected $EXPECTED_ISA"
fi

if [ ! -f "$PROJECT_DIR/Cargo.lock" ]; then
    fail "Cargo.lock is missing"
fi
cargo metadata \
    --manifest-path "$PROJECT_DIR/Cargo.toml" \
    --locked \
    --format-version 1 \
    --no-deps >/dev/null

echo "Environment verified:"
echo "  Rust:       $actual_rust_version (minimum $MINIMUM_RUST_VERSION)"
echo "  Sail:       $actual_sail_version"
echo "  ckb-vm:     $actual_ckb_vm"
echo "  sail-riscv: $actual_sail_riscv"
echo "  ISA:        $actual_isa"
echo "  config:     $actual_config_hash"
