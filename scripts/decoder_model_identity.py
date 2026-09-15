"""Compare public Lean output across checkout locations without editing it.

The legacy approved hash includes absolute Rust source paths in generated doc
comments. Only the checkout prefix of an entire, specifically shaped Source:
line can be mapped to that legacy namespace for comparison. Every other byte,
including the source filename, line/column positions and all Lean code, remains
in the hash. The legacy prefix is an identity namespace, never a file to load.
"""
import hashlib
import os
from pathlib import Path
import re

LEGACY_CHECKOUT = "/home/clair/tinyueng_workplace/ckb-vm-sail-verify"
APPROVED_SHA256 = "b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061"
ITERATOR_SHA256 = "3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3"
ITERATOR_RELATIVE = "proof/lean/decoder/toolchain/fnptr-experimental/fnptr_cases.rs"


def canonicalize(data, checkout):
    prefix = str(Path(checkout).resolve()).encode() + b"/deps/ckb-vm/"
    pattern = re.compile(rb"(?m)^(    Source: ')" + re.escape(prefix) +
                         rb"([^'\r\n]+', lines [0-9]+:[0-9]+-[0-9]+:[0-9]+)$")
    legacy = LEGACY_CHECKOUT.encode() + b"/deps/ckb-vm/"
    return pattern.subn(lambda match: match[1] + legacy + match[2], data)


def check(path, checkout):
    data = Path(path).read_bytes()
    canonical, count = canonicalize(data, checkout)
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != APPROVED_SHA256:
        raise RuntimeError("public model differs beyond the reviewed source-comment prefix")
    return {"raw_sha256": hashlib.sha256(data).hexdigest(), "canonical_sha256": digest,
            "normalization": "generated-source-comment-checkout-prefix-v1",
            "source_comment_count": count, "actual_checkout": str(Path(checkout).resolve()),
            "legacy_identity_namespace": LEGACY_CHECKOUT, "generated_file_edited": False}


def canonicalize_iterator(data, checkout, extraction_cwd):
    """Map only this fixture's exact Source line, preserving the suffix.

    Charon may render sources relative to its working directory. Both spellings
    are derived from the actual checkout/cwd, never taken from generated text.
    The optional closing comment delimiter is retained verbatim in the hash.
    """
    source = Path(checkout).resolve() / ITERATOR_RELATIVE
    spellings = {str(source), os.path.relpath(source, Path(extraction_cwd).resolve())}
    names = b"|".join(re.escape(name.encode()) for name in sorted(spellings))
    pattern = re.compile(rb"(?m)^(    Source: ')(?:" + names +
                         rb")(', lines [0-9]+:[0-9]+-[0-9]+:[0-9]+(?: -/)?)$")
    legacy = (LEGACY_CHECKOUT + "/" + ITERATOR_RELATIVE).encode()
    return pattern.subn(lambda match: match[1] + legacy + match[2], data)


def check_iterator(path, checkout, extraction_cwd):
    data = Path(path).read_bytes()
    canonical, count = canonicalize_iterator(data, checkout, extraction_cwd)
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != ITERATOR_SHA256:
        raise RuntimeError("iterator model differs beyond the reviewed fixture-source location")
    return {"raw_sha256": hashlib.sha256(data).hexdigest(), "canonical_sha256": digest,
            "normalization": "generated-iterator-source-location-v1", "source_comment_count": count,
            "actual_checkout": str(Path(checkout).resolve()),
            "extraction_cwd": str(Path(extraction_cwd).resolve()),
            "legacy_identity_namespace": LEGACY_CHECKOUT, "generated_file_edited": False}
