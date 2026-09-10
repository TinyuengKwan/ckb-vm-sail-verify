#!/usr/bin/env python3
"""Verify or explicitly apply the reviewed upstream-plus-patch source baseline.

No refresh mode. This identifies source contents, not a running binary or proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path("proof/lean/extraction/ckb-source-baseline.json")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def require(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f"{label} differs from reviewed CKB source baseline; review required")


def tree(repo, added, *, upstream=False):
    entries = {}
    for row in git(repo, "ls-tree", "-rz", "HEAD").split(b"\0"):
        if not row:
            continue
        meta, raw_name = row.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError("unsupported source tree entry: " + raw_name.decode())
        entries[raw_name.decode()] = (mode, oid)
    if not upstream:
        untracked = set(filter(None, git(repo, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")))
        # Added files may already be staged; HEAD, not the index, defines the base.
        indexed = set(filter(None, git(repo, "ls-files", "-z").decode().split("\0")))
        require((untracked | indexed) - entries.keys(), set(added), "additional source paths")
        for name in added:
            if name in entries:
                raise RuntimeError("added path already exists upstream: " + name)
            entries[name] = ("100644", None)
    hashes = {}
    for name, (mode, oid) in sorted(entries.items()):
        if upstream:
            data = git(repo, "cat-file", "blob", oid)
            actual_mode = mode
        else:
            path = repo / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("missing or non-regular source: " + name)
            data = path.read_bytes()
            actual_mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        hashes[name] = {"mode": actual_mode, "sha256": sha(data)}
    return sha(canonical(hashes))


def check(root=ROOT, *, apply=False):
    manifest_bytes = (root / MANIFEST).read_bytes()
    manifest = json.loads(manifest_bytes)
    require(manifest["schema_version"], 1, "manifest schema")
    repo = root / "deps/ckb-vm"
    require(git(repo, "rev-parse", "HEAD").decode().strip(), manifest["upstream_commit"], "upstream commit")
    patch = root / manifest["patch"]
    require(sha(patch.read_bytes()), manifest["patch_sha256"], "patch hash")
    for name, expected in manifest["extraction_inputs"].items():
        require(sha((root / name).read_bytes()), expected, name)
    if apply:
        # Idempotent only for an already exact baseline; never repair partial edits.
        try:
            require(tree(repo, manifest["added_files"]), manifest["source_tree_sha256"], "source tree")
        except (RuntimeError, FileNotFoundError):
            require(git(repo, "status", "--porcelain", "--untracked-files=all"), b"", "clean upstream checkout")
            require(tree(repo, []), manifest["upstream_tree_sha256"], "upstream tree")
            git(repo, "apply", "--check", str(patch))
            git(repo, "apply", str(patch))
    require(tree(repo, manifest["added_files"]), manifest["source_tree_sha256"], "source tree")
    git(repo, "apply", "--reverse", "--check", str(patch))
    return {"baseline_id": manifest["baseline_id"],
            "upstream_commit": manifest["upstream_commit"],
            "patch_sha256": manifest["patch_sha256"],
            "source_tree_sha256": manifest["source_tree_sha256"],
            "manifest_sha256": sha(manifest_bytes),
            "identity_kind": "verified-source-checkout-not-binary-attestation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply reviewed patch only to exact clean upstream")
    args = parser.parse_args()
    try:
        print(json.dumps(check(apply=args.apply), sort_keys=True))
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
