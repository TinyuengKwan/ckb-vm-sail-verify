#!/usr/bin/env bash
# Reproduce the Rocq/Coq compatibility spike.
#
# Runs both halves and reports what each does. The verdict and its evidence are
# in proof/rocq/SPIKE.md; this script is what makes that document checkable
# rather than a claim. It exits non-zero if a half *succeeds*, because the
# recorded verdict is NO-GO and a success would mean the record is stale --
# the same two-directional contract as scripts/check_proof_model.sh.
#
# Needs the `rocq-spike` opam switch; see proof/rocq/SPIKE.md for its contents.
#
# Usage: ./scripts/rocq_spike.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SWITCH="${ROCQ_SPIKE_SWITCH:-rocq-spike}"
WORK="${ROCQ_SPIKE_WORK:-$PROJECT_DIR/target/rocq-spike}"

fail() { echo "ERROR: $*" >&2; exit 1; }

command -v opam >/dev/null 2>&1 || fail "opam is required"
opam switch list --short 2>/dev/null | grep -qx "$SWITCH" || \
    fail "opam switch '$SWITCH' not found. Create it as proof/rocq/SPIKE.md records:
       opam switch create $SWITCH ocaml-base-compiler.5.2.1 --no-switch
       opam repo add --yes rocq-released https://rocq-prover.org/opam/released
       opam install -y rocq-core=9.1.1 rocq-stdlib=9.0.0 \\
           rocq-stdpp-bitvector=1.13.0 rocq-sail-stdpp=0.20.2"

eval "$(opam env --switch="$SWITCH" --set-switch)"
command -v rocq >/dev/null 2>&1 || fail "rocq not found in switch $SWITCH"

rm -rf "$WORK"
mkdir -p "$WORK/rust" "$WORK/sail"
failures=0

echo "=== Rocq: $(rocq --version | head -n 1)"
echo
echo "=== Half 1: Rust to Rocq (Aeneas) ==="
LLBC="$PROJECT_DIR/target/CkbVmProduction.llbc"
if [ ! -f "$LLBC" ]; then
    echo "SKIP: no $LLBC; run make proof-gen-rust first"
else
    AENEAS="${AENEAS:-$HOME/.local/share/aeneas/aeneas}"
    [ -x "$AENEAS" ] || fail "aeneas not found at $AENEAS"
    "$AENEAS" -backend rocq -dest "$WORK/rust" "$LLBC" > "$WORK/rust/generate.log" 2>&1
    if grep -q 'Recursive trait implementations are not supported' "$WORK/rust/generate.log"; then
        echo "  generation warns: recursive trait impl will not type-check (as recorded)"
    fi
    (cd "$WORK/rust" && rocq compile -Q . "" Primitives.v) > "$WORK/rust/prim.log" 2>&1 \
        || { echo "  UNEXPECTED: Aeneas Primitives.v itself failed to compile"; failures=$((failures+1)); }
    if (cd "$WORK/rust" && rocq compile -Q . "" CkbVmProduction.v) > "$WORK/rust/compile.log" 2>&1; then
        echo "  UNEXPECTED PASS: the Rust-side Rocq model now type-checks."
        echo "  proof/rocq/SPIKE.md records NO-GO and is now stale."
        failures=$((failures+1))
    else
        echo "  NO-GO, as recorded. First error:"
        grep -A4 '^Error' "$WORK/rust/compile.log" | head -n 6 | sed 's/^/    /'
    fi

    # The minimal reproduction, compiled against the Primitives.v just
    # generated rather than a checked-in copy of it, so it cannot go stale
    # when the pinned Aeneas moves.
    REPRO="$PROJECT_DIR/proof/rocq/spike/result_shadowing.v"
    if [ -f "$REPRO" ]; then
        cp "$REPRO" "$WORK/rust/"
        if (cd "$WORK/rust" && rocq compile -Q . "" result_shadowing.v) > "$WORK/rust/repro.log" 2>&1; then
            echo "  minimal reproduction still shows the shadowing:"
            grep -E 'Expands to|^result :' "$WORK/rust/repro.log" | head -n 2 | sed 's/^/    /'
        else
            echo "  UNEXPECTED: proof/rocq/spike/result_shadowing.v no longer reproduces."
            echo "  It asserts the shadowing with Fail Check; that assertion did not hold."
            failures=$((failures+1))
        fi
    fi
fi

echo
echo "=== Half 2: Sail to Rocq ==="
GEN="$PROJECT_DIR/proof/rocq/generated/sail"
EXTRAS="$PROJECT_DIR/deps/sail-riscv/handwritten_support/riscv_extras.v"
if [ ! -f "$GEN/rv64d.v" ]; then
    echo "SKIP: no $GEN/rv64d.v; run make proof-gen BACKEND=rocq first"
else
    cp "$GEN/rv64d_types.v" "$GEN/rv64d.v" "$EXTRAS" "$WORK/sail/"
    (cd "$WORK/sail" && rocq compile -Q . "" riscv_extras.v && rocq compile -Q . "" rv64d_types.v) \
        > "$WORK/sail/types.log" 2>&1 \
        || { echo "  UNEXPECTED: the support file or the generated types failed"; failures=$((failures+1)); }
    if (cd "$WORK/sail" && rocq compile -Q . "" rv64d.v) > "$WORK/sail/compile.log" 2>&1; then
        echo "  UNEXPECTED PASS: the Sail-side Rocq model now type-checks."
        echo "  proof/rocq/SPIKE.md records NO-GO and is now stale."
        failures=$((failures+1))
    else
        echo "  NO-GO, as recorded. First error:"
        grep '^Error' "$WORK/sail/compile.log" | head -n 2 | sed 's/^/    /'
    fi
fi

echo
if [ "$failures" -ne 0 ]; then
    echo "The recorded NO-GO no longer matches reality; update proof/rocq/SPIKE.md."
    exit 1
fi
echo "Both halves fail as recorded in proof/rocq/SPIKE.md. Verdict stands: NO-GO."
echo "The mandatory Lean 4 backend is unaffected: make proof-build BACKEND=lean|rust."
