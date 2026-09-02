#!/usr/bin/env bash
# Build and install the pinned Sail compiler from source.
#
# sail-riscv's Lean target needs a Sail newer than any release: at the pinned
# sail-riscv commit the handwritten Lean support expects a module namespace
# that release 0.20.2 does not emit. Upstream has the same split -- its
# compile-lean.yml builds Sail from source while cmake/sail_required_version.txt
# pins 0.20.2 for the C emulator. This project uses one Sail for both targets
# and pins it by commit, because a source build and the release both report the
# version number 0.20.2 and only the full version string tells them apart.
#
# Installs outside the opam switch so a release install can coexist and the
# choice is made by PATH.
#
# Usage: ./scripts/build_sail.sh [install-prefix]

set -euo pipefail

SAIL_COMMIT="8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1"
SAIL_REPO="https://github.com/rems-project/sail.git"
PREFIX="${1:-$HOME/.local/share/sail-src}"
SOURCE_DIR="${SAIL_SOURCE_DIR:-$HOME/.local/src/sail}"

command -v opam >/dev/null 2>&1 || { echo "ERROR: opam is required" >&2; exit 1; }

if [ ! -d "$SOURCE_DIR/.git" ]; then
    echo "==> Cloning Sail into $SOURCE_DIR"
    mkdir -p "$(dirname "$SOURCE_DIR")"
    git clone "$SAIL_REPO" "$SOURCE_DIR"
fi

echo "==> Checking out $SAIL_COMMIT"
git -C "$SOURCE_DIR" fetch --quiet origin
git -C "$SOURCE_DIR" checkout --quiet "$SAIL_COMMIT"

eval "$(opam env)"

echo "==> Installing build dependencies"
(cd "$SOURCE_DIR" && opam install . --deps-only --yes)

# Only the install targets: the test target needs alcotest, which is not
# required to produce the compiler.
echo "==> Building"
(cd "$SOURCE_DIR" && dune build @install)

echo "==> Installing to $PREFIX"
(cd "$SOURCE_DIR" && dune install --prefix="$PREFIX")

INSTALLED="$("$PREFIX/bin/sail" --version)"
EXPECTED="Sail 0.20.2 (HEAD @ $SAIL_COMMIT)"
if [ "$INSTALLED" != "$EXPECTED" ]; then
    echo "ERROR: installed Sail reports '$INSTALLED'; expected '$EXPECTED'" >&2
    exit 1
fi

cat <<EOF

Installed: $INSTALLED

Put it ahead of any release install on PATH:

    export PATH="$PREFIX/bin:\$PATH"

scripts/verify_environment.sh checks this exact version string, so a release
build of the same version number will be rejected.
EOF
