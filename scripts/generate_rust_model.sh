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
#   MachineRuntime           The reviewed source patch contains the dynamic
#                            callbacks in a private container. DefaultMachine
#                            and its five register/PC delegates are included;
#                            only the dynamic container remains opaque.
#   Register<u64>::{eq,lt,lt_s,logical_not}
#                            All four are `bool -> u64` via `.into()`, and
#                            Aeneas emits `core.convert.FromU64Bool`, which its
#                            Lean library does not define -- the generated file
#                            does not compile with them in. ADD uses none of
#                            them, but BEQ does, so a comparison theorem will
#                            have to resolve this first.
#
# The selections above do not enumerate every generated axiom. The two reached
# external constants are explicitly included below so Charon retains their
# source initializers: register count (ADD) and RA (other dispatch branches).
# See proof/lean/ADD_AUDIT.md for remaining dependencies and method premises.
#
# Usage: ./scripts/generate_rust_model.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Reject the original checkout, unreviewed edits, or extraction-config drift.
# A source baseline is upstream commit PLUS patch, never the commit alone.
SOURCE_IDENTITY="$(python3 "$SCRIPT_DIR/ckb_source_baseline.py")"
EXTRACTION_CONFIG="$PROJECT_DIR/proof/lean/extraction/ckb-vm.json"

# Pinned toolchain. VERIFICATION.md section 1 requires these to be fixed before
# any Rust-side definition is generated.
EXPECTED_CHARON="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["charon"])' "$EXTRACTION_CONFIG")"
EXPECTED_AENEAS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["aeneas"])' "$EXTRACTION_CONFIG")"

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
mapfile -t CHARON_ARGS < <(python3 - "$EXTRACTION_CONFIG" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
print('--preset=' + c['preset'])
print('--start-from\n' + c['root'])
for key in ('include', 'opaque'):
    for name in c[key]:
        print('--' + key + '\n' + name)
PY
)
(cd "$PROJECT_DIR/crates/proof-extract" && "$CHARON" cargo "${CHARON_ARGS[@]}" \
    --dest-file "$LLBC" -- --lib)

echo "==> Translating to Lean 4"
mapfile -t AENEAS_ARGS < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["aeneas_args"]))' "$EXTRACTION_CONFIG")
"$AENEAS" "${AENEAS_ARGS[@]}" -dest "$DESTINATION" "$LLBC"
# Bind provenance to the model just generated and reject mid-run source drift.
[ "$(python3 "$SCRIPT_DIR/ckb_source_baseline.py")" = "$SOURCE_IDENTITY" ] || fail "source identity changed during extraction"
python3 - "$DESTINATION" "$SOURCE_IDENTITY" "$LLBC" <<'PY'
import hashlib, json, pathlib, sys
dest = pathlib.Path(sys.argv[1])
evidence = json.loads(sys.argv[2])
evidence['generated_lean_sha256'] = hashlib.sha256((dest/'CkbVmProduction.lean').read_bytes()).hexdigest()
evidence['llbc_sha256'] = hashlib.sha256(pathlib.Path(sys.argv[3]).read_bytes()).hexdigest()
(dest/'SOURCE_BASELINE.json').write_text(json.dumps(evidence, indent=2) + '\n')
PY

# A lake project so the generated definitions can be compiled. Written here
# rather than by hand: the exit gate requires that regenerating needs no edits
# to anything under the generated directory.
AENEAS_LEAN_LIB="$AENEAS_HOME/backends/lean"
cat >"$DESTINATION/lakefile.toml" <<EOF
name = "CkbVmProduction"
defaultTargets = ["CkbVmProduction"]

[[require]]
name = "Aeneas"
path = "$AENEAS_LEAN_LIB"

[[lean_lib]]
name = "CkbVmProduction"
EOF
"$SCRIPT_DIR/configure_lean_project.sh" rust
cat >"$DESTINATION/TOOLCHAIN.txt" <<EOF
charon=$actual_charon
aeneas=$actual_aeneas
roots=ckb_vm_sail_extract::execute_production
lean_toolchain=$(cat "$DESTINATION/lean-toolchain")
EOF

echo
echo "Generated Rust-side Lean definitions: $DESTINATION"
echo "NOTE: generating these files says nothing about whether they compile,"
echo "      and compiling alone checks no theorem. Run make proof-check BACKEND=lean"
echo "      to audit the existing conditional ADD step theorem and its boundaries."
