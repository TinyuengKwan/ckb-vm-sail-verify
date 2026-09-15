"""Materialize the reviewed public Rust root against a verified local checkout.

Only Cargo's dependency location varies. Rust source and dependency lock retain
their existing identities. This helper does not adopt a tool or change policy.
"""
import json
import os
from pathlib import Path
import shutil

import ckb_source_baseline as baseline
import check_proof as proof

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("proof/lean/decoder/toolchain/full-mir/OuterRoot.rs")
LOCK = Path("proof/lean/decoder/toolchain/public-harness/Cargo.lock")
SOURCE_SHA256 = "ce89211f2d139f2a7a3f4f5d69e6fe362ad2fd0b8bcf19e8e185cb589a15972c"
LOCK_SHA256 = "023588c4dac3bf3489f629bfd7eef67fa202a76918c737ad8ab1816d9ddfc2c3"


def manifest(directory, checkout):
    relative = os.path.relpath(Path(checkout).resolve() / "deps/ckb-vm", Path(directory).resolve())
    # JSON string escaping is valid for the ordinary paths supported here by
    # TOML basic strings; no interpolated shell commands or ambient root path.
    return ('[package]\nname = "outer-decoder-probe"\nversion = "0.0.0"\n'
            'edition = "2024"\n[workspace]\n[dependencies]\n'
            'ckb-vm = { path = ' + json.dumps(relative, ensure_ascii=False) + ' }\n'
            '[lib]\npath = "lib.rs"\n')


def verify(directory, checkout):
    directory = Path(directory).resolve()
    checkout = Path(checkout).resolve()
    identity = baseline.check(checkout)
    expected = {"lib.rs": SOURCE_SHA256, "Cargo.lock": LOCK_SHA256}
    for name, digest in expected.items():
        proof.require_equal(proof.file_hash(directory / name), digest, "portable harness " + name)
    proof.require_equal((directory / "Cargo.toml").read_text(), manifest(directory, checkout),
                        "portable harness Cargo manifest")
    return {"directory": str(directory), "checkout": str(checkout), "production_baseline": identity,
            "files": {name: proof.file_hash(directory / name)
                      for name in ["lib.rs", "Cargo.lock", "Cargo.toml"]}}


def prepare(directory, checkout):
    directory = Path(directory).resolve()
    checkout = Path(checkout).resolve()
    # Check inputs before creating anything. Never reuse or overwrite a caller's
    # existing directory; Cargo target placement belongs to the fresh-run caller.
    baseline.check(checkout)
    proof.require_equal(proof.file_hash(ROOT / SOURCE), SOURCE_SHA256, "public Rust root")
    proof.require_equal(proof.file_hash(ROOT / LOCK), LOCK_SHA256, "public Rust dependency lock")
    directory.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT / SOURCE, directory / "lib.rs")
    shutil.copyfile(ROOT / LOCK, directory / "Cargo.lock")
    (directory / "Cargo.toml").write_text(manifest(directory, checkout))
    return verify(directory, checkout)
