#!/usr/bin/env bash
# Apply checked-in toolchain configuration and the documented Sail scope adapter.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOOLCHAIN="$PROJECT_DIR/proof/lean/theorems/lean-toolchain"
BACKEND="${1:?usage: configure_lean_project.sh lean|rust}"
fail() { echo "ERROR: $*" >&2; exit 1; }

case "$BACKEND" in
    lean)
        GENERATED="$PROJECT_DIR/proof/lean/generated/sail"
        EXPECTATION="$PROJECT_DIR/proof/lean/expected_build_status.txt"
        REV="$(sed -n 's/^lean_sail_rev=//p' "$EXPECTATION")"
        [[ "$REV" =~ ^[0-9a-f]{40}$ ]] || fail "invalid lean-sail revision in $EXPECTATION"
        [ -f "$GENERATED/lakefile.toml" ] || fail "generate the Sail model first"
        grep -q '^rev = ' "$GENERATED/lakefile.toml" || fail "Sail lakefile has no revision to pin"
        sed -i "s|^rev = .*|rev = \"$REV\"|" "$GENERATED/lakefile.toml"
        # Lean 4.31 panics when deriving enum BEq in a noncomputable section.
        # Defs contains computable types/helpers; function modules retain their
        # noncomputable scopes. Never alter generated instruction bodies.
        command -v patch >/dev/null || fail "patch is required for the Sail scope adapter"
        ADAPTER="$PROJECT_DIR/proof/lean/compat/sail-defs-computable.patch"
        if patch --batch --forward --fuzz=0 --dry-run -s -d "$GENERATED" -p0 < "$ADAPTER" >/dev/null 2>&1; then
            patch --batch --forward --fuzz=0 -s -d "$GENERATED" -p0 < "$ADAPTER"
        elif ! patch --batch --reverse --fuzz=0 --dry-run -s -d "$GENERATED" -p0 < "$ADAPTER" >/dev/null 2>&1; then
            fail "Sail Defs scope adapter does not apply; review the generated format"
        fi
        ;;
    rust)
        GENERATED="$PROJECT_DIR/proof/lean/generated/rust"
        AENEAS_LIB="${AENEAS_HOME:-$HOME/.local/share/aeneas}/backends/lean"
        [ -f "$GENERATED/lakefile.toml" ] || fail "generate the Rust model first"
        cmp -s "$TOOLCHAIN" "$AENEAS_LIB/lean-toolchain" || \
            fail "Aeneas support library must use $(tr -d '\n' < "$TOOLCHAIN")"
        ;;
    *) fail "backend must be lean or rust" ;;
esac

cp "$TOOLCHAIN" "$GENERATED/lean-toolchain"
