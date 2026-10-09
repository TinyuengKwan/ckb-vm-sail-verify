#!/usr/bin/env python3
"""Pack or unpack the evidence tree of one ephemeral-VM clean-room run.

``pack`` writes a deterministic gzip tar of ``artifacts/boundary-check/clean-room``
from the checkout the launcher extracted into (fixed inputs and build caches
excluded).  ``unpack`` is the CI intake counterpart: it verifies the expected
SHA-256, extracts regular files only into a fresh candidate checkout without
overwriting anything, then runs the clean-room validator.  The same bundle
bytes are attested by CI and re-downloaded by the collector, so there is one
evidence container from the guest to the final aggregate.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_common as common

require, sha = common.require, common.sha
CLEAN = "artifacts/boundary-check/clean-room"
EXCLUDED = {"fixed-inputs", "cargo-target", "rust-tests-cargo-home", "runtime-cargo-home"}
VM_RECORD = "vm-provenance.json"


def candidate_root(path, commit):
    root = Path(path).resolve()
    require(root.is_dir() and (root / ".git").exists(), "candidate root is not a git checkout")
    require(common.GIT_OID.fullmatch(commit or ""), "candidate must be a full commit OID")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(head.returncode == 0 and head.stdout.decode().strip() == commit, "candidate root is not at the candidate commit")
    return root


def safe_member(name):
    common.safe_name(name)
    require(name.startswith(CLEAN + "/"), "member outside the clean-room evidence prefix: " + name)
    require(not any(part in EXCLUDED for part in name.split("/")), "excluded member: " + name)
    return name


def tree_files(root):
    base = root / CLEAN
    require(base.is_dir() and not base.is_symlink(), "clean-room evidence directory missing")
    files = {}
    for directory, names, filenames in os.walk(base, followlinks=False):
        directory = Path(directory)
        names[:] = [n for n in names if n not in EXCLUDED]
        for name in names:
            require(not (directory / name).is_symlink(), "linked evidence directory")
        for name in filenames:
            path = directory / name
            require(path.is_file() and not path.is_symlink(), "special/link evidence file: " + str(path))
            mode = path.stat().st_mode
            require(stat.S_ISREG(mode) and not mode & 0o7000, "special evidence mode: " + str(path))
            files[safe_member(path.relative_to(root).as_posix())] = path
    require(CLEAN + "/report.json" in files and CLEAN + "/" + VM_RECORD in files,
            "evidence tree lacks the clean-room report or its VM provenance record")
    return files


def pack(root, out):
    files = tree_files(Path(root).resolve())
    out = Path(out).absolute()
    digest = common.write_tar_gz(out, files)
    return {"status": "packed", "bundle": str(out), "sha256": digest, "members": len(files),
            "clean_room_report_sha256": sha(files[CLEAN + "/report.json"]),
            "vm_provenance_sha256": sha(files[CLEAN + "/" + VM_RECORD])}


def extract(bundle, expected, destination):
    """Strictly extract the bundle below destination; files only, nothing overwritten."""
    bundle, destination = Path(bundle), Path(destination).resolve()
    common.digest(expected, "expected bundle SHA-256")
    require(sha(bundle) == expected, "bundle SHA-256 differs")
    targets = {}
    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar:
            name = safe_member(member.name)
            require(member.isfile() and not member.linkname, "special/link bundle member: " + name)
            require(name not in targets, "duplicate bundle member")
            path = destination / name
            require(not path.exists() and not path.is_symlink(), "bundle target occupied: " + name)
            require(not any(p.is_symlink() for p in path.parents if p.is_relative_to(destination)), "linked bundle target ancestor")
            targets[name] = member.mode
    require(CLEAN + "/report.json" in targets and CLEAN + "/" + VM_RECORD in targets,
            "bundle lacks the clean-room report or its VM provenance record")
    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar:
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            require(stream is not None, "unreadable bundle member")
            with path.open("xb") as output:
                while block := stream.read(1024 * 1024):
                    output.write(block)
            path.chmod(0o755 if member.mode & 0o100 else 0o644)
    require(sha(bundle) == expected, "bundle changed during extraction")
    return sorted(targets)


def unpack(bundle, expected, root, commit):
    import audit_release
    root = candidate_root(root, commit)
    members = extract(bundle, expected, root)
    report = root / CLEAN / "report.json"
    summary = audit_release.check_vm_report(report, commit, root)
    return {"status": "unpacked_and_clean_room_validated", "bundle_sha256": expected, "members": len(members),
            "clean_room": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    packer = sub.add_parser("pack")
    packer.add_argument("--root", required=True, type=Path)
    packer.add_argument("--out", required=True, type=Path)
    unpacker = sub.add_parser("unpack")
    unpacker.add_argument("--bundle", required=True, type=Path)
    unpacker.add_argument("--bundle-sha256", required=True)
    unpacker.add_argument("--root", required=True, type=Path)
    unpacker.add_argument("--candidate", required=True)
    args = parser.parse_args()
    try:
        result = pack(args.root, args.out) if args.mode == "pack" else unpack(args.bundle, args.bundle_sha256, args.root, args.candidate)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print("evidence bundle rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
