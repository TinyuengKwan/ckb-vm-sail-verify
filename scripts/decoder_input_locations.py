"""Resolve installed decoder inputs only after independent identity checks."""
import hashlib
import json
from pathlib import Path

import decoder_input_bundle as bundle
from decoder_public_source import check_reextraction


def load(directory):
    directory = Path(directory).resolve()
    payload = directory / "payload"
    manifest = bundle.verify_payload(payload)
    for name, commit in manifest["source_commits"].items():
        source = directory / "sources" / name
        objects = source / ".git/objects"
        bundle.require(not objects.is_symlink() and objects.is_dir() and
                       not (objects / "info/alternates").exists() and
                       not any(p.is_symlink() for p in objects.rglob("*")),
                       "installed Git objects are not independent")
        bundle.require(bundle.git(source, "rev-parse", "HEAD").decode().strip() == commit,
                       "installed tool source revision mismatch")
        digest = hashlib.sha256(bundle.git(source, "diff", "--")).hexdigest()
        bundle.require(digest == manifest["files"]["patches/" + name + ".patch"]["sha256"],
                       "installed source changes differ from the approved patch")
    return {"directory": str(directory), "payload": str(payload),
            "manifest_sha256": bundle.sha(payload / "package.json"),
            "source_commits": manifest["source_commits"]}


def _compare_metadata(archived, fresh, verified_sysroot):
    """Caller must have verified the actual std files. Only location metadata
    is remapped; extraction flags, types and source data are never rewritten."""
    root = str(Path(verified_sysroot).resolve())
    actual = fresh["translated"]["options"]["sysroot"]
    bundle.require(actual == root, "fresh extraction did not use the verified installed sysroot")
    normalized = dict(fresh)
    normalized["translated"] = dict(fresh["translated"])
    normalized["translated"]["options"] = dict(fresh["translated"]["options"])
    normalized["translated"]["options"]["sysroot"] = archived["translated"]["options"]["sysroot"]
    check_reextraction(archived, normalized)
    return {"archive_sysroot": archived["translated"]["options"]["sysroot"],
            "verified_installed_sysroot": root, "only_sysroot_location_and_output_path_vary": True}


def check_extraction(fresh, directory, name="OuterClosedDepsV3.llbc"):
    bundle.require(name in {"OuterClosedDepsV3.llbc", "FnPtrFullMir.llbc"}, "unknown extraction root")
    inputs = load(directory)  # Includes all 46 std library hashes, not a path-only assertion.
    payload = Path(inputs["payload"])
    archived = json.loads((payload / "llbc" / name).read_bytes())
    return _compare_metadata(archived, fresh, payload / "sysroot")
