#!/usr/bin/env bash
# Generate Lean 4 definitions of the production CKB-VM execution path.
#
# The roots are `crates/proof-extract`, which is ordinary Rust calling the
# production interpreter at the very type `ckb-runner` drives. Charon extracts
# the call graph from there and Aeneas translates it, so `common::add` appears
# because production reaches it, not because this script names it.
#
# What is deliberately left opaque, and why:
#
#   ckb_vm::memory::_        ADD touches no memory. SparseMemory::load also
#                            uses Iterator::skip, which the Aeneas Lean library
#                            has no model for, so including it fails outright.
#   DefaultMachine           It carries `Box<dyn Syscalls>`, `Box<dyn Debugger>`
#                            and a `dyn Fn` cycle hook. Aeneas reports
#                            "Dynamic trait types are not supported yet". None
#                            of the three is touched by ADD, but the type
#                            cannot be translated while they are in it, so the
#                            wrapper's delegation to DefaultCoreMachine stays an
#                            axiom. This is recorded in docs/semantic-gaps.md;
#                            it is the one link in the chain that extraction
#                            does not cover.
#   Register<u64>::{eq,lt,lt_s,logical_not}
#                            All four are `bool -> u64` via `.into()`, and
#                            Aeneas emits `core.convert.FromU64Bool`, which its
#                            Lean library does not define -- the generated file
#                            does not compile with them in. ADD uses none of
#                            them, but BEQ does, so a comparison theorem will
#                            have to resolve this first.
#
# Usage: ./scripts/generate_rust_model.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Pinned toolchain. VERIFICATION.md section 1 requires these to be fixed before
# any Rust-side definition is generated.
EXPECTED_CHARON="0.1.247 (89ac118194b978d8cf753222c19f313521377aa0)"
EXPECTED_AENEAS="aeneas nightly-2026.09.01-379890b"

AENEAS_HOME="${AENEAS_HOME:-$HOME/.local/share/aeneas}"
CHARON="${CHARON:-$AENEAS_HOME/charon}"
AENEAS="${AENEAS:-$AENEAS_HOME/aeneas}"
DESTINATION="$PROJECT_DIR/proof/lean/generated/rust"

fail() { echo "ERROR: $*" >&2; exit 1; }

[ -x "$CHARON" ] || fail "charon not found at $CHARON; see README.md"
[ -x "$AENEAS" ] || fail "aeneas not found at $AENEAS; see README.md"

actual_charon="$("$CHARON" version)"
actual_aeneas="$("$AENEAS" -version)"
[ "$actual_charon" = "$EXPECTED_CHARON" ] || \
    fail "charon is '$actual_charon'; expected '$EXPECTED_CHARON'"
[ "$actual_aeneas" = "$EXPECTED_AENEAS" ] || \
    fail "aeneas is '$actual_aeneas'; expected '$EXPECTED_AENEAS'"

# The file name becomes the generated module name, so it has to be a valid
# identifier in every backend: Rocq rejects `Module Proof-extract.`
LLBC="$PROJECT_DIR/target/CkbVmProduction.llbc"
mkdir -p "$(dirname "$LLBC")" "$DESTINATION"

echo "==> Extracting the production call graph"
(cd "$PROJECT_DIR/crates/proof-extract" && "$CHARON" cargo --preset=aeneas \
    --start-from 'ckb_vm_sail_extract::execute_production' \
    --include 'ckb_vm::instructions::_' \
    --include 'ckb_vm::machine::DefaultCoreMachine' \
    --include 'ckb_vm::machine::{impl ckb_vm::machine::CoreMachine for ckb_vm::machine::DefaultCoreMachine}::_' \
    --opaque 'ckb_vm::machine::DefaultMachine' \
    --opaque 'ckb_vm::memory::_' \
    --opaque 'ckb_vm::instructions::register::{ckb_vm::instructions::register::Register<u64>}::eq' \
    --opaque 'ckb_vm::instructions::register::{ckb_vm::instructions::register::Register<u64>}::lt' \
    --opaque 'ckb_vm::instructions::register::{ckb_vm::instructions::register::Register<u64>}::lt_s' \
    --opaque 'ckb_vm::instructions::register::{ckb_vm::instructions::register::Register<u64>}::logical_not' \
    --dest-file "$LLBC" -- --lib)

echo "==> Translating to Lean 4"
"$AENEAS" -backend lean -dest "$DESTINATION" "$LLBC"

# A lake project so the generated definitions can be compiled. Written here
# rather than by hand: the exit gate requires that regenerating needs no edits
# to anything under the generated directory.
AENEAS_LEAN_LIB="$AENEAS_HOME/backends/lean"
cat >"$DESTINATION/lean-toolchain" <<EOF
$(cat "$AENEAS_LEAN_LIB/lean-toolchain")
EOF
cat >"$DESTINATION/lakefile.toml" <<EOF
name = "CkbVmProduction"
defaultTargets = ["CkbVmProduction"]

[[require]]
name = "Aeneas"
path = "$AENEAS_LEAN_LIB"

[[lean_lib]]
name = "CkbVmProduction"
EOF
cat >"$DESTINATION/TOOLCHAIN.txt" <<EOF
charon=$actual_charon
aeneas=$actual_aeneas
roots=ckb_vm_sail_extract::execute_production
lean_toolchain=$(cat "$AENEAS_LEAN_LIB/lean-toolchain")
EOF

echo
echo "Generated Rust-side Lean definitions: $DESTINATION"
echo "NOTE: generating these files says nothing about whether they compile,"
echo "      and compiling says nothing about any theorem. Neither a Rust-side"
echo "      to Sail-side state bridge nor an ADD refinement theorem exists yet."
