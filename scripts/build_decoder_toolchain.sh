#!/usr/bin/env bash
# Build a new isolated candidate. This does NOT accept its binary into policy.
set -euo pipefail
decoder_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
decoder_build=$(mktemp -d "$decoder_repo/artifacts/boundary-check/decoder-build-XXXXXX")
decoder_source="$decoder_build/aeneas-src"
decoder_switch="$decoder_build/ocaml-switch"
printf 'Isolated build: %s\n' "$decoder_build"
git clone --filter=blob:none --no-checkout https://github.com/AeneasVerif/aeneas.git "$decoder_source"
git -C "$decoder_source" switch --detach 379890b54b4961dc7729e314c6eefdc09fe50981
git clone --filter=blob:none --no-checkout https://github.com/AeneasVerif/charon.git "$decoder_source/charon"
git -C "$decoder_source/charon" switch --detach 89ac118194b978d8cf753222c19f313521377aa0
git -C "$decoder_source" apply --check "$decoder_repo/proof/lean/decoder/toolchain/aeneas-join-recovery.patch"
git -C "$decoder_source" apply "$decoder_repo/proof/lean/decoder/toolchain/aeneas-join-recovery.patch"
opam switch create "$decoder_switch" ocaml-base-compiler.5.2.1 --no-switch --yes --jobs=8
mapfile -t decoder_packages < "$decoder_repo/proof/lean/decoder/toolchain/opam-packages.txt"
opam install --switch "$decoder_switch" --yes --jobs=8 "${decoder_packages[@]}"
(
  cd "$decoder_source/src"
  opam exec --switch "$decoder_switch" -- dune build main.exe -j 8
)
decoder_binary="$decoder_source/src/_build/default/main.exe"
"$decoder_binary" -version
sha256sum "$decoder_binary"
printf 'Candidate only. Review source, tool regression and binary identity before changing raw-policy.json.\n'
printf 'AENEAS_DECODER_BIN=%s\n' "$decoder_binary"
