#!/usr/bin/env bash
# Build both models/imports, optionally checking the register or step theorem.
# --step still has explicit contracts; it is not the release proof-check gate.
set -euo pipefail

REGISTER_PROOF=false
STEP_PROOF=false
case "${1:-}" in
    "") [ "$#" = 0 ] || { echo "usage: $0 [--registers|--step]" >&2; exit 2; } ;;
    --registers) [ "$#" = 1 ] || { echo "usage: $0 [--registers|--step]" >&2; exit 2; }
        REGISTER_PROOF=true ;;
    --step) [ "$#" = 1 ] || { echo "usage: $0 [--registers|--step]" >&2; exit 2; }
        REGISTER_PROOF=true; STEP_PROOF=true ;;
    *) echo "usage: $0 [--registers|--step]" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
THEOREMS="$PROJECT_DIR/proof/lean/theorems"
AENEAS_LIB="${AENEAS_HOME:-$HOME/.local/share/aeneas}/backends/lean"
BUILD_TIMEOUT="${PROOF_BUILD_TIMEOUT:-3600}"
fail() { echo "ERROR: $*" >&2; exit 1; }

if ! command -v lake >/dev/null && [ -x "$HOME/.elan/bin/lake" ]; then
    export PATH="$HOME/.elan/bin:$PATH"
fi
for tool in lake python3 git patch timeout; do
    command -v "$tool" >/dev/null || fail "$tool is required"
done
for model in rust/CkbVmProduction.lean sail/LeanRV64D/Step.lean; do
    [ -s "$PROJECT_DIR/proof/lean/generated/$model" ] || \
        fail "missing generated/$model; run make proof-gen-rust and make proof-gen BACKEND=lean"
done
[ -s "$THEOREMS/lake-manifest.json" ] || fail "missing checked-in import dependency lock"
[ -d "$AENEAS_LIB/Aeneas" ] || fail "Aeneas library not found at $AENEAS_LIB"
"$SCRIPT_DIR/configure_lean_project.sh" rust
"$SCRIPT_DIR/configure_lean_project.sh" lean

# Keep the checked-in lock portable: Aeneas has a local installation, represented
# by this ignored link rather than an absolute home-directory path in the lock.
mkdir -p "$THEOREMS/.lake"
if [ -e "$THEOREMS/.lake/aeneas" ] && [ ! -L "$THEOREMS/.lake/aeneas" ]; then
    fail "$THEOREMS/.lake/aeneas must be a symlink, not an existing directory"
fi
ln -sfn "$(cd "$AENEAS_LIB" && pwd)" "$THEOREMS/.lake/aeneas"

LOCK_HASH="$(sha256sum "$THEOREMS/lake-manifest.json")"
cd "$THEOREMS"
export ELAN_TOOLCHAIN="$(tr -d '\n' < lean-toolchain)"
# Lean can print a compiler PANIC yet exit 0. Abort on fresh panics, and also
# inspect the log because Lake may replay a cached successful trace with one.
export LEAN_ABORT_ON_PANIC=1
ulimit -c 0
LEAN_VERSION="${ELAN_TOOLCHAIN##*:v}"
ACTUAL_VERSION="$(lake env lean --version)"
case "$ACTUAL_VERSION" in
    "Lean (version $LEAN_VERSION,"*) ;;
    *) fail "unexpected compiler: $ACTUAL_VERSION" ;;
esac
TARGETS=(LeanRV64D CkbVmProduction SmokeImports)
if "$REGISTER_PROOF"; then
    TARGETS+=(AddRegisterAxioms RegisterRegression)
fi
if "$STEP_PROOF"; then
    TARGETS+=(AddStepAxioms StepRegression ProductionAdd ProductionAddWitness)
fi
echo "==> Building ${TARGETS[*]} with $ACTUAL_VERSION"
# No lake update: use the committed revisions, including transitive dependencies.
LOG="$THEOREMS/.lake/import-build.log"
if "$REGISTER_PROOF"; then LOG="$THEOREMS/.lake/register-build.log"; fi
if "$STEP_PROOF"; then LOG="$THEOREMS/.lake/step-build.log"; fi
if ! timeout "$BUILD_TIMEOUT" lake build "${TARGETS[@]}" >"$LOG" 2>&1; then
    tail -n 30 "$LOG" >&2
    fail "shared import build failed or timed out; full log: $LOG"
fi
if ! timeout "$BUILD_TIMEOUT" lake env lean ../compat/EnumComputable.lean >>"$LOG" 2>&1; then
    tail -n 30 "$LOG" >&2
    fail "Sail enum compatibility regression probe failed; full log: $LOG"
fi
if grep -qE 'PANIC|uncaught exception|Stack overflow' "$LOG"; then
    fail "compiler panic/internal failure in build log (including cached traces): $LOG"
fi
tail -n 20 "$LOG"
[ "$(sha256sum lake-manifest.json | cut -d ' ' -f 1)" = "${LOCK_HASH%% *}" ] || \
    fail "Lake changed the import lock; review dependency changes before accepting this build"

# Check the actual checkouts, not just the revision strings in a manifest.
python3 - "$PROJECT_DIR/proof/lean/expected_build_status.txt" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

manifest = json.loads(Path("lake-manifest.json").read_text())
expected = dict(line.split("=", 1) for line in Path(sys.argv[1]).read_text().splitlines()
                if line and not line.startswith("#") and "=" in line)
packages = {package["name"]: package for package in manifest["packages"]}
if packages["Sail"]["rev"] != expected["lean_sail_rev"]:
    sys.exit("ERROR: import lock and recorded lean-sail revision differ")
if packages["Aeneas"].get("dir") != ".lake/aeneas":
    sys.exit("ERROR: Aeneas must resolve through the portable .lake/aeneas link")
for package in packages.values():
    if package["type"] != "git":
        continue
    directory = Path(manifest["packagesDir"]) / package["name"]
    head = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()
    if head != package["rev"]:
        sys.exit(f"ERROR: {package['name']} checkout differs from the lock")
    if subprocess.check_output(["git", "-C", str(directory), "status", "--porcelain"], text=True).strip():
        sys.exit(f"ERROR: {package['name']} checkout is dirty")
print("OK: all Git dependencies match the import lock.")
PY
if "$STEP_PROOF"; then
    echo "OK: conditional decoded ADD step theorem, exact axiom guards and regression lemmas checked."
    echo "Wrapper delegation and a concrete joint Sail witness are proved; the general theorem retains decoded-input/Sail premises."
    echo "The paired witness takes a Rust seed; it does not prove Nonempty Machine or raw-decoder correspondence."
elif "$REGISTER_PROOF"; then
    echo "OK: conditional ADD register theorem, exact axiom guards and regression lemmas checked."
    echo "Wrapper delegation remains a premise; this target does not check the PC/dispatch step theorem."
else
    echo "OK: both generated models import in one Lean environment. No ADD theorem is checked."
fi
