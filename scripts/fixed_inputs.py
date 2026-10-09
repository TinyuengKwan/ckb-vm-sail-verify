#!/usr/bin/env python3
"""Verify, stage and install the hash-pinned fixed inputs: the fixed-prefix tool
package (Rust, Sail, Aeneas/Charon, Lean, Rocq), and the CMake download package
for an offline Sail emulator configure.

The manifest binds member identity, not the container.  Staging restores bytes
into a NEW directory; the five installation roots are then moved below the
canonical checkout.  The tools are not relocatable and nothing here is a
clean-room claim.  The decoder input package has its own installer
(decoder_rebuilt_inputs.py) because it is also a proof input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import stat
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_common as common

require, sha = common.require, common.sha
COMPRESSION_MAGIC = {"gz": b"\x1f\x8b", "xz": b"\xfd7zXZ\x00"}
INSTALL_ROOTS = ["aeneas-opam-finalize-mj9dgb4h", "aeneas-opam-qhtaephh", "isolated-rocq-ac54t6f8",
                 "isolated-rust-lean-ad7o1fsn", "isolated-sail-nrdi23ds"]
CMAKE_FILES = {"CLI11.hpp", "gmp-6.3.0.tar.xz", "v1.8.1.tar.gz", "asio-1.36.0.tar.bz2"}


def identity(path):
    path = Path(path)
    require(all(not parent.is_symlink() for parent in path.parents), "linked source ancestor")
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return {"kind": "symlink", "target": os.readlink(path)}
    if stat.S_ISDIR(info.st_mode):
        require(not info.st_mode & 0o7000, "special directory permission bits")
        return {"kind": "directory", "mode": info.st_mode & 0o777}
    require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o7000, "special source or permission bits")
    return {"kind": "file", "sha256": sha(path), "bytes": info.st_size, "mode": info.st_mode & 0o777}


def entries_valid(entries):
    require(type(entries) is dict and entries, "empty entry inventory")
    for name, row in entries.items():
        common.safe_name(name)
        for parent in PurePosixPath(name).parents:
            require(str(parent) not in entries or entries[str(parent)].get("kind") == "directory", "entry overlaps a file parent")
        if row.get("kind") == "file":
            require(set(row) == {"kind", "sha256", "bytes", "mode"} and common.SHA256.fullmatch(row["sha256"]) and
                    type(row["bytes"]) is int and 0 <= row["mode"] <= 0o777, "invalid regular entry")
        elif row.get("kind") == "directory":
            require(set(row) == {"kind", "mode"} and 0 <= row["mode"] <= 0o777, "invalid directory entry")
        else:
            require(row.get("kind") == "symlink" and set(row) == {"kind", "target"} and type(row["target"]) is str and
                    row["target"] and not row["target"].startswith("/") and "\0" not in row["target"], "invalid symbolic link")
    for name, row in entries.items():
        if row["kind"] != "symlink":
            continue
        current, visited = name, set()
        while entries.get(current, {}).get("kind") == "symlink":
            require(current not in visited, "symbolic link cycle")
            visited.add(current)
            current = common.safe_name(posixpath.normpath(posixpath.join(posixpath.dirname(current), entries[current]["target"])))
        require(entries.get(current, {}).get("kind") == "file", "link chain does not end at a recorded regular file")


def load_manifest(path, expected_sha):
    common.digest(expected_sha, "trusted manifest digest")
    require(sha(path) == expected_sha, "manifest digest differs")
    manifest = common.read(path)
    require(manifest.get("schema_version") == 1 and manifest.get("kind") == "extra-fixed-prefix-installations-v1",
            "unknown installation package")
    require(set(manifest) == {"schema_version", "kind", "canonical_checkout", "inputs", "required_external", "boundaries", "entries"},
            "manifest fields differ")
    require(Path(manifest["canonical_checkout"]).is_absolute(), "canonical checkout absent")
    require(manifest["boundaries"] == {key: False for key in ["clean_room", "release", "kernel_execution", "relocatable",
                                                               "host_closure_complete"]}, "package assurance differs")
    entries_valid(manifest["entries"])
    return manifest


def compression_of(path):
    with Path(path).open("rb") as stream:
        head = stream.read(6)
    for name, magic in COMPRESSION_MAGIC.items():
        if head.startswith(magic):
            return name
    raise RuntimeError("unsupported archive compression")


def open_archive(path):
    return tarfile.open(path, "r|" + compression_of(path))


def validate_member(member, entries, seen):
    name = common.safe_name(member.name)
    require(name in entries and name not in seen, "extra or repeated archive entry: " + name)
    seen.add(name)
    row = entries[name]
    require(member.uid == member.gid == 0 and not member.uname and not member.gname and member.mtime == 0,
            "unreviewed ownership/timestamp metadata")
    if row["kind"] == "file":
        require(member.isreg() and member.size == row["bytes"] and member.mode == row["mode"] and not member.linkname and
                not member.sparse, "regular archive metadata differs: " + name)
    elif row["kind"] == "directory":
        require(member.isdir() and member.size == 0 and member.mode == row["mode"] and not member.linkname, "directory metadata differs")
    else:
        require(member.issym() and member.linkname == row["target"] and member.size == 0 and member.mode == 0o777,
                "symbolic archive metadata differs")
    return name, row


def verify_archive(archive_path, manifest_path, manifest_sha):
    manifest = load_manifest(manifest_path, manifest_sha)
    entries, seen = manifest["entries"], set()
    before = sha(archive_path)
    with open_archive(archive_path) as archive:
        for member in archive:
            name, row = validate_member(member, entries, seen)
            if row["kind"] == "file":
                stream = archive.extractfile(member)
                digest = hashlib.sha256()
                while block := stream.read(1024 * 1024):
                    digest.update(block)
                require(digest.hexdigest() == row["sha256"], "archived bytes differ: " + name)
    require(seen == set(entries), "missing archive entries")
    require(sha(archive_path) == before and sha(manifest_path) == manifest_sha, "archive/manifest changed during verification")
    return {"archive_sha256": before, "manifest_sha256": manifest_sha, "entries": len(entries),
            "compression": compression_of(archive_path),
            "regular_bytes": sum(row.get("bytes", 0) for row in entries.values())}


def verify_staged(destination, entries):
    destination = Path(destination)
    implied = {str(parent) for name in entries for parent in PurePosixPath(name).parents if str(parent) != "."}
    observed = {}
    for path in destination.rglob("*"):
        name = str(path.relative_to(destination))
        if path.is_dir() and not path.is_symlink() and name not in entries:
            require(name in implied, "unexpected staged directory: " + name)
            continue
        observed[name] = identity(path)
        if path.is_file() and not path.is_symlink():
            require(path.stat().st_nlink == 1, "hardlinked staged file")
    require(observed == entries, "staged inventory differs")


def stage(archive_path, manifest_path, manifest_sha, destination):
    """Restore the package bytes into a new directory; never tar.extract."""
    destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink() and
            not any(p.is_symlink() for p in destination.parents), "staging destination exists/linked")
    checked = verify_archive(archive_path, manifest_path, manifest_sha)
    manifest = load_manifest(manifest_path, manifest_sha)
    entries, seen, links, directories = manifest["entries"], set(), [], []
    destination.mkdir(parents=True)
    with open_archive(archive_path) as archive:
        for member in archive:
            name, row = validate_member(member, entries, seen)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            require(not any(p.is_symlink() for p in (target, *target.parents)), "linked staging member")
            if row["kind"] == "symlink":
                links.append((target, row["target"]))
            elif row["kind"] == "directory":
                target.mkdir(exist_ok=True)
                directories.append((target, row["mode"]))
            else:
                with target.open("xb") as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream, 1024 * 1024)
                target.chmod(row["mode"])
    require(seen == set(entries), "missing staged entries")
    for target, link in links:
        target.symlink_to(link)
    for target, mode in sorted(directories, key=lambda row: len(row[0].parts), reverse=True):
        target.chmod(mode)
    verify_staged(destination, entries)
    require(sha(archive_path) == checked["archive_sha256"] and sha(manifest_path) == manifest_sha, "inputs changed during staging")
    return {**checked, "staged_at": str(destination)}


def installation_roots(entries):
    roots = set()
    for name in entries:
        parts = Path(common.safe_name(name)).parts
        require(len(parts) >= 3 and parts[:2] == ("artifacts", "boundary-check") and parts[2] in INSTALL_ROOTS,
                "installation entry outside fixed roots: " + name)
        roots.add(parts[2])
    require(roots == set(INSTALL_ROOTS), "incomplete installation root inventory")
    return sorted(roots)


def install_staged_roots(staged, checkout, entries):
    """Move the five verified, disjoint installation roots into a checkout."""
    roots = installation_roots(entries)
    parent = Path(checkout) / "artifacts/boundary-check"
    require(not any(p.is_symlink() for p in (parent, *parent.parents)), "linked installation destination")
    for name in roots:
        require(not (parent / name).exists() and not (parent / name).is_symlink(), "installation destination occupied: " + name)
        require((Path(staged) / "artifacts/boundary-check" / name).is_dir(), "staged installation root missing: " + name)
    parent.mkdir(parents=True, exist_ok=True)
    for name in roots:
        shutil.move(str(Path(staged) / "artifacts/boundary-check" / name), parent / name)
    for name, expected in entries.items():
        require(identity(Path(checkout) / name) == expected, "installed member differs: " + name)
    return roots


# ---- CMake download package ----------------------------------------------------

def cmake_configure_options(out):
    out = Path(out).absolute()
    return ["-DFETCHCONTENT_FULLY_DISCONNECTED:BOOL=ON", "-DFETCHCONTENT_UPDATES_DISCONNECTED:BOOL=ON",
            "-DFETCHCONTENT_SOURCE_DIR_CLI11_HPP:PATH=" + str(out / "sources/cli11_hpp"),
            "-DFETCHCONTENT_SOURCE_DIR_JSONCONS:PATH=" + str(out / "sources/jsoncons/jsoncons-1.8.1"),
            "-DFETCHCONTENT_SOURCE_DIR_ASIO:PATH=" + str(out / "sources/asio/asio-1.36.0"),
            "-DDOWNLOAD_GMP:BOOL=TRUE"]


def unpack_source(archive_path, destination, top):
    destination = Path(destination).absolute()
    require(not destination.exists(), "output already exists")
    destination.mkdir(parents=True)
    seen, directories = set(), []
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            name = common.safe_name(member.name.rstrip("/") if member.isdir() else member.name)
            require((name == top or name.startswith(top + "/")) and name not in seen and (member.isfile() or member.isdir()) and
                    not member.mode & ~0o777, "unexpected upstream archive entry: " + name)
            seen.add(name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                target.mkdir(exist_ok=True)
                directories.append((target, member.mode))
            else:
                with target.open("xb") as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream)
                target.chmod(member.mode)
    for target, mode in sorted(directories, key=lambda row: len(row[0].parts), reverse=True):
        target.chmod(mode)
    return len(seen)


def stage_cmake(archive_path, manifest_path, out, policy):
    """Unpack the reviewed CMake download package into NEW input directories."""
    out = Path(out).absolute()
    require(not out.exists() and not any(p.is_symlink() for p in (out, *out.parents)), "output exists/linked")
    pins = policy["fixed_inputs"]
    require(sha(manifest_path) == pins["cmake-downloads-manifest.json"]["sha256"] and
            sha(archive_path) == pins["cmake-downloads.tar.gz"]["sha256"], "unreviewed CMake input package")
    manifest = common.read(manifest_path)
    require(manifest["kind"] == "fixed-cmake-download-inputs-v1" and set(manifest["files"]) == CMAKE_FILES, "CMake package scope")
    contents = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            require(member.name in CMAKE_FILES and member.name not in contents and member.isfile(), "invalid download member")
            row = manifest["files"][member.name]
            data = archive.extractfile(member).read()
            require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"], "download payload differs")
            algorithm = {"SHA256": "sha256", "SHA3_256": "sha3_256"}[row["declaration"]["hash_algorithm"]]
            require(hashlib.new(algorithm, data).hexdigest() == row["declaration"]["digest"], "CMake download hash differs")
            contents[member.name] = data
    require(set(contents) == CMAKE_FILES, "download omitted")
    out.mkdir(parents=True)
    downloads = out / "downloads"
    downloads.mkdir()
    for name, data in contents.items():
        (downloads / name).write_bytes(data)
    sources = out / "sources"
    sources.mkdir()
    unpack_source(downloads / "v1.8.1.tar.gz", sources / "jsoncons", "jsoncons-1.8.1")
    unpack_source(downloads / "asio-1.36.0.tar.bz2", sources / "asio", "asio-1.36.0")
    (sources / "cli11_hpp").mkdir()
    shutil.copyfile(downloads / "CLI11.hpp", sources / "cli11_hpp/CLI11.hpp")
    gmp = out / "build/gmp-prefix/src/gmp-6.3.0.tar.xz"
    gmp.parent.mkdir(parents=True)
    shutil.copyfile(downloads / gmp.name, gmp)
    result = {"schema_version": 1, "kind": "fixed-cmake-inputs-staged-v1", "status": "staged", "out": str(out),
              "build": str(out / "build"), "configure_options": cmake_configure_options(out),
              "archive_sha256": sha(archive_path), "manifest_sha256": sha(manifest_path)}
    common.write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "stage"):
        p = sub.add_parser(name)
        p.add_argument("--archive", type=Path, required=True)
        p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--manifest-sha256", required=True)
        if name == "stage":
            p.add_argument("--out", type=Path, required=True, help="NEW directory; byte staging, not tool deployment")
    cmake = sub.add_parser("cmake-stage")
    cmake.add_argument("--archive", type=Path, required=True)
    cmake.add_argument("--manifest", type=Path, required=True)
    cmake.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        result = verify_archive(args.archive, args.manifest, args.manifest_sha256)
    elif args.command == "stage":
        result = stage(args.archive, args.manifest, args.manifest_sha256, args.out)
    else:
        result = stage_cmake(args.archive, args.manifest, args.out, common.load_policy())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
