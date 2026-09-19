#!/usr/bin/env python3
"""Pack or unpack the evidence tree of one independent ephemeral VM clean-room run.

``pack`` writes a deterministic gzip tar of ``artifacts/boundary-check/week6-*``
from the checkout the launcher extracted into; the tree must already contain
``week6-clean-room/report.json`` and its ``vm-provenance.json``.  ``unpack``
is the CI intake counterpart: it verifies the expected SHA-256, extracts only
regular files under that prefix into a fresh candidate checkout without
overwriting anything, then runs the same clean-room and VM provenance
validators the aggregator uses.  Neither mode executes a clean-room, uploads,
signs or approves; ``unpack`` succeeding means the archived evidence is
internally consistent with the checkout it was unpacked into, nothing more.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_external_evidence as external

PREFIX = "artifacts/boundary-check"
CLEAN = PREFIX + "/week6-clean-room"
OID = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def candidate_root(path, commit):
    root = Path(path).resolve()
    require(root.is_dir() and (root / ".git").exists(), "candidate root is not a git checkout")
    require(OID.fullmatch(commit or ""), "candidate must be a full Git OID")
    import subprocess
    head = subprocess.run(["/usr/bin/git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=30)
    require(head.returncode == 0 and head.stdout.decode().strip() == commit,
            "candidate root is not at the candidate commit")
    return root


def safe_member(name):
    require(type(name) is str and name and "\\" not in name and "\0" not in name, "unsafe member name")
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and
            all(part not in ("", ".", "..") for part in path.parts), "unsafe member name: " + name)
    require(name.startswith(PREFIX + "/week6-"), "member outside the Week6 evidence prefix: " + name)
    return name


def tree_files(root):
    base = root / PREFIX
    require(base.is_dir() and not base.is_symlink(), "evidence prefix missing")
    files = {}
    for entry in sorted(base.iterdir()):
        if not entry.name.startswith("week6-"):
            continue
        require(entry.is_dir() and not entry.is_symlink(), "linked/non-directory evidence root: " + entry.name)
        for directory, names, filenames in os.walk(entry, followlinks=False):
            directory = Path(directory)
            if directory == root / CLEAN:
                # The downloaded fixed inputs are hash-pinned public inputs; the
                # bundle carries evidence, not a second copy of 2 GB of inputs.
                names[:] = [name for name in names if name != "fixed-inputs"]
            for name in names:
                require(not (directory / name).is_symlink(), "linked evidence directory")
            for name in filenames:
                path = directory / name
                require(path.is_file() and not path.is_symlink(), "special/link evidence file: " + str(path))
                mode = path.stat().st_mode
                require(stat.S_ISREG(mode) and not mode & 0o7000, "special evidence mode: " + str(path))
                member = safe_member(path.relative_to(root).as_posix())
                files[member] = path
    require(CLEAN + "/report.json" in files and CLEAN + "/" + external.VM_RECORD in files,
            "evidence tree lacks the clean-room report or its VM provenance record")
    return files


def pack(root, out):
    files = tree_files(root)
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), "bundle output exists")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(files):
            path = files[name]
            info = tarfile.TarInfo(name)
            info.size = path.stat().st_size
            info.mtime = 0
            info.mode = 0o755 if path.stat().st_mode & 0o100 else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with path.open("rb") as stream:
                tar.addfile(info, stream)
    with out.open("xb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as compressed:
        compressed.write(buffer.getvalue())
    return {"status": "packed", "bundle": str(out), "sha256": sha(out), "members": len(files),
            "clean_room_report_sha256": sha(files[CLEAN + "/report.json"]),
            "vm_provenance_sha256": sha(files[CLEAN + "/" + external.VM_RECORD]),
            "boundaries": {"clean_room_claimed": False, "release_claimed": False, "week6_closed": False}}


def unpack(bundle, expected, root, commit):
    bundle = Path(bundle)
    require(SHA256.fullmatch(expected or ""), "expected bundle SHA-256 absent")
    require(sha(bundle) == expected, "bundle SHA-256 differs")
    root = candidate_root(root, commit)
    targets = {}
    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar:
            name = safe_member(member.name)
            require(member.isfile(), "special/link bundle member: " + name)
            require(name not in targets, "duplicate bundle member")
            path = root / name
            require(not path.exists() and not path.is_symlink(), "bundle target occupied: " + name)
            require(not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(root)),
                    "linked bundle target ancestor: " + name)
            targets[name] = member.mode
    require(CLEAN + "/report.json" in targets and CLEAN + "/" + external.VM_RECORD in targets,
            "bundle lacks the clean-room report or its VM provenance record")
    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar:
            path = root / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            require(stream is not None, "unreadable bundle member")
            with path.open("xb") as output:
                while block := stream.read(1024 * 1024):
                    output.write(block)
            path.chmod(0o755 if member.mode & 0o100 else 0o644)
    require(sha(bundle) == expected, "bundle changed during extraction")
    report = root / CLEAN / "report.json"
    clean = external.check_clean_room(report, commit, root=root)
    require(clean["provider"] == external.VM_PROVIDER, "unpacked clean-room report is not an ephemeral VM run")
    provenance = external.check_vm_provenance(report)
    return {"status": "unpacked_clean_room_and_vm_provenance_validated", "bundle_sha256": expected,
            "members": len(targets), "clean_room": clean, "vm_provenance": provenance,
            "boundaries": {"clean_room_claimed": False, "ci_download_verified": False,
                           "release_claimed": False, "week6_closed": False}}


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
        if args.mode == "pack":
            result = pack(args.root, args.out)
        else:
            result = unpack(args.bundle, args.bundle_sha256, args.root, args.candidate)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print("Week6 VM evidence bundle rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
