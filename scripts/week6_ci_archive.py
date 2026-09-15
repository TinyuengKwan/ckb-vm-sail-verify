#!/usr/bin/env python3
"""Build one deterministic, manifest-bound Week6 CI evidence tarball.

This production helper packages an already completed clean-room record and
the exact four files needed for the distinct download/replay job. It does not
execute a clean-room run or upgrade any verification claim.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile


OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def safe_name(value):
    require(type(value) is str and value and "\\" not in value and "\0" not in value,
            "unsafe member name")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(part not in ("", ".", "..") for part in path.parts),
            "unsafe member name")
    return value


def regular(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), "missing/non-regular input: " + str(path))
    require(all(not parent.is_symlink() for parent in path.parents),
            "linked input ancestor: " + str(path))
    mode = path.stat().st_mode
    require(stat.S_ISREG(mode) and not mode & 0o7000, "special input mode: " + str(path))
    return path


def read_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(regular(path).read_bytes(), object_pairs_hook=pairs)


def clean_tree(directory, root):
    directory = Path(directory).absolute()
    root = Path(root).absolute()
    require(directory.is_dir() and not directory.is_symlink(), "missing clean-room directory")
    require(root.is_dir() and not root.is_symlink() and directory.is_relative_to(root),
            "clean-room directory is outside candidate root")
    require(all(not parent.is_symlink() for parent in directory.parents), "linked clean-room ancestor")
    prefix = directory.relative_to(root).as_posix()
    result = {}
    for base, directories, files in os.walk(directory, followlinks=False):
        base = Path(base)
        for name in sorted(directories):
            require(not (base / name).is_symlink(), "linked clean-room directory")
        for name in sorted(files):
            path = regular(base / name)
            relative = path.relative_to(directory).as_posix()
            member = safe_name(prefix + "/" + relative)
            require(member not in result, "duplicate clean-room member")
            result[member] = path
    report_name = safe_name(prefix + "/report.json")
    require(report_name in result, "clean-room report is outside tree")
    return result, report_name


def member_row(path):
    path = regular(path)
    return {"path": None, "size": path.stat().st_size, "sha256": sha(path)}


def manifest(candidate, source_snapshot_sha256, files, clean_report, replay_case):
    rows = []
    for name, path in sorted(files.items()):
        row = member_row(path)
        row["path"] = name
        rows.append(row)
    return {
        "schema_version": 1,
        "kind": "ci-evidence-archive-manifest-v1",
        "candidate": candidate,
        "source_snapshot_sha256": source_snapshot_sha256,
        "clean_room_report": clean_report,
        "replay_case": replay_case,
        "members": rows,
    }


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def tar_info(name, size, mode):
    info = tarfile.TarInfo(safe_name(name))
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    info.mode = mode & 0o777
    info.size = size
    return info


def write_archive(output, files, manifest_data):
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), "archive output already exists")
    require(output.parent.is_dir() and not output.parent.is_symlink(), "archive parent missing/linked")
    with output.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=1, mtime=0, fileobj=raw) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name, path in sorted(files.items()):
                    path = regular(path)
                    before = sha(path)
                    with path.open("rb") as stream:
                        archive.addfile(tar_info(name, path.stat().st_size, path.stat().st_mode), stream)
                    require(sha(path) == before, "input changed during archive: " + name)
                archive.addfile(tar_info("MANIFEST.json", len(manifest_data), 0o644),
                                _BytesReader(manifest_data))
    return sha(output)


class _BytesReader:
    def __init__(self, value):
        self.value = value
        self.offset = 0

    def read(self, size=-1):
        if size < 0:
            size = len(self.value) - self.offset
        result = self.value[self.offset:self.offset + size]
        self.offset += len(result)
        return result


def verify_archive(path, expected_files, expected_manifest):
    observed, seen_manifest = {}, None
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = safe_name(member.name)
            require(name not in observed and name != "MANIFEST.json" or
                    name == "MANIFEST.json" and seen_manifest is None, "duplicate archive member")
            require(member.isfile() and not member.linkname and member.uid == member.gid == member.mtime == 0,
                    "unsafe archive metadata: " + name)
            stream = archive.extractfile(member)
            require(stream is not None, "unreadable archive member")
            digest = hashlib.sha256()
            size = 0
            chunks = [] if name == "MANIFEST.json" else None
            while block := stream.read(1024 * 1024):
                size += len(block)
                digest.update(block)
                if chunks is not None:
                    chunks.append(block)
            require(size == member.size, "archive member size changed")
            if name == "MANIFEST.json":
                seen_manifest = b"".join(chunks)
            else:
                observed[name] = {"size": size, "sha256": digest.hexdigest()}
    expected = {name: {"size": regular(path).stat().st_size, "sha256": sha(path)}
                for name, path in expected_files.items()}
    require(observed == expected, "archive member inventory differs")
    require(seen_manifest == expected_manifest, "archived manifest bytes differ")


def create(args):
    require(OID.fullmatch(args.candidate), "candidate must be a full Git OID")
    clean_report = regular(args.clean_room)
    clean_value = read_json(clean_report)
    require(clean_value.get("schema_version") == 1 and
            clean_value.get("kind") == "clean-room-evidence-v1" and
            clean_value.get("status") == "passed" and
            clean_value.get("candidate") == args.candidate,
            "clean-room report identity/status differs")
    snapshot_ref = clean_value.get("source_snapshot")
    require(type(snapshot_ref) is dict and set(snapshot_ref) == {"path", "sha256"},
            "clean-room source snapshot reference")
    require(re.fullmatch(r"[0-9a-f]{64}", snapshot_ref["sha256"] or ""),
            "source snapshot reference hash")
    snapshot_path = regular(clean_report.parent / safe_name(snapshot_ref["path"]))
    require(sha(snapshot_path) == snapshot_ref["sha256"], "source snapshot file differs")
    snapshot = read_json(snapshot_path)
    snapshot_identity = snapshot.get("snapshot_sha256")
    require(re.fullmatch(r"[0-9a-f]{64}", snapshot_identity or ""), "source snapshot identity")

    files, clean_report_name = clean_tree(clean_report.parent, args.root)
    replay_name = safe_name("cases/" + args.replay_case + ".json")
    additions = {
        replay_name: regular(args.replay_case_file),
        "bin/ckb-vm-sail-diff": regular(args.diff_binary),
        "bin/sail_riscv_sim": regular(args.sail_binary),
        "config/ckb_vm_config.json": regular(args.sail_config),
    }
    require(not set(files) & set(additions), "archive member collision")
    files.update(additions)
    value = manifest(args.candidate, snapshot_identity, files, clean_report_name, replay_name)
    data = json_bytes(value)
    manifest_out = Path(args.manifest_out).absolute()
    require(not manifest_out.exists() and not manifest_out.is_symlink(), "manifest output already exists")
    require(manifest_out.parent.is_dir() and not manifest_out.parent.is_symlink(), "manifest parent missing/linked")
    with manifest_out.open("xb") as stream:
        stream.write(data)
    archive_sha = write_archive(args.out, files, data)
    verify_archive(args.out, files, data)
    require(regular(manifest_out).read_bytes() == data, "external manifest changed")
    return {"status": "created_and_independently_stream_verified",
            "archive": str(Path(args.out).absolute()), "archive_sha256": archive_sha,
            "manifest": str(manifest_out), "manifest_sha256": sha(manifest_out),
            "members": len(files), "candidate": args.candidate,
            "source_snapshot_sha256": snapshot_identity,
            "release_claimed": False, "week6_closed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("--root", required=True, type=Path)
    create_parser.add_argument("--clean-room", required=True, type=Path)
    create_parser.add_argument("--candidate", required=True)
    create_parser.add_argument("--replay-case", required=True)
    create_parser.add_argument("--replay-case-file", required=True, type=Path)
    create_parser.add_argument("--diff-binary", required=True, type=Path)
    create_parser.add_argument("--sail-binary", required=True, type=Path)
    create_parser.add_argument("--sail-config", required=True, type=Path)
    create_parser.add_argument("--out", required=True, type=Path)
    create_parser.add_argument("--manifest-out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(create(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
