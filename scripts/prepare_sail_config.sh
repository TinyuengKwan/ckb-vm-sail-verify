#!/usr/bin/env bash
# Materialize and validate the exact Sail configuration used by runtime and proofs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SAIL_BIN="${SAIL_BIN:-$PROJECT_DIR/deps/sail-riscv/build/c_emulator/sail_riscv_sim}"
OVERRIDE="${SAIL_CONFIG_OVERRIDE:-$PROJECT_DIR/sail-model/ckb_vm_config.json}"
OUTPUT_DIR="$PROJECT_DIR/sail-model/build"
OUTPUT="$OUTPUT_DIR/ckb_vm_config.json"

if [ ! -x "$SAIL_BIN" ]; then
    echo "ERROR: Sail emulator not found at $SAIL_BIN" >&2
    echo "Run: make sail-emu" >&2
    exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required for recursive JSON merge" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

"$SAIL_BIN" --print-default-config |
    sed '/^[[:space:]]*\/\//d' >"$TEMP_DIR/default.json"
jq -s '
    .[0] as $default
    | .[1] as $override
    | (
        $default
        | .extensions |= walk(if type == "object" and has("supported") then .supported = false else . end)
      ) * $override
' "$TEMP_DIR/default.json" "$OVERRIDE" >"$OUTPUT"
"$SAIL_BIN" --config "$OUTPUT" --print-isa-string >/dev/null
sha256sum "$OUTPUT" >"$OUTPUT.sha256"

echo "Materialized Sail config: $OUTPUT"
cat "$OUTPUT.sha256"
