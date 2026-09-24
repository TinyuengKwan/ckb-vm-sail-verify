"""Shared, non-executing contract for the approved profile-A two-asset layout.

The SSH-signed primary archive binds the tool archive through its manifest.
Transport URLs are never trust roots: publication evidence must also bind both
archives to the same immutable GitHub release. No download or signing here.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

ASSET_NAME = "extra-installations.tar.xz"
MAX_ASSET_BYTES = 2 * 1024**3  # Exclusive GitHub release-asset limit.
SHA256 = re.compile(r"[0-9a-f]{64}")
SCHEMA = 2
SOURCE_CAPSULE = "source/source-capsule.tar.gz"
RESTORE_PINS = {
    "install/rebuilt-decoder-candidate.tar.gz": "1a81921b12215a87106ac2080c05de3f2bf9d51b9bb14bdb80a90ac8c05c58d5",
    "install/cmake-downloads.tar.gz": "51589032e8adc0aa6db1420633630e5d83cbbb0e094990d0484dd9f6fc8199c9",
    "install/cmake-downloads-manifest.json": "792223f4b9773e647805edc4b0b9e1a2064d1a2c498866d14c1a748f405217dd",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fields(value, expected, message):
    require(type(value) is dict and set(value) == set(expected), message)


def safe_name(name):
    require(type(name) is str and name and not any(c in name for c in "\\\0\r\n"), "unsafe delivery path")
    p = PurePosixPath(name)
    require(not p.is_absolute() and p.as_posix() == name and
            all(part not in ("", ".", "..") for part in p.parts), "unsafe delivery path")
    return name


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(),
            "missing/linked delivery input")
    require(stat.S_ISREG(path.stat().st_mode) and not path.stat().st_mode & 0o7000,
            "special delivery input")
    return path


def sha(path):
    h = hashlib.sha256()
    with regular(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def size_ok(size):
    require(type(size) is int and 0 < size < MAX_ASSET_BYTES, "release asset must be under 2 GiB")


def policy_assets(cfg):
    value = cfg["external_assets"]
    fields(value, {ASSET_NAME}, "profile A requires exactly the approved tool asset")
    row = value[ASSET_NAME]
    fields(row, {"size", "sha256", "manifest"}, "tool asset policy fields")
    size_ok(row["size"])
    require(type(row["sha256"]) is str and SHA256.fullmatch(row["sha256"]), "tool asset policy digest")
    fields(row["manifest"], {"path", "sha256"}, "tool manifest policy fields")
    require(row["manifest"]["path"] == "install/manifest.json" and
            type(row["manifest"]["sha256"]) is str and SHA256.fullmatch(row["manifest"]["sha256"]),
            "tool manifest policy identity")
    return value


def local_asset(path, row):
    path = regular(path)
    size_ok(path.stat().st_size)
    require(path.stat().st_size == row["size"] and sha(path) == row["sha256"],
            "external tool asset bytes differ")
    return path


def bind_manifest(manifest, cfg, members):
    """Called only after the manifest/member inventory has been verified."""
    expected = policy_assets(cfg)
    require(manifest["external_assets"] == expected, "signed external asset binding differs from policy")
    for name, row in expected.items():
        reference = row["manifest"]
        require(reference["path"] in members and
                members[reference["path"]]["sha256"] == reference["sha256"],
                "signed installation manifest binding differs")
        require(name not in members and "install/" + name not in members,
                "standalone tool asset duplicated inside primary archive")


def restoration_members(members):
    require(SOURCE_CAPSULE in members and "docs/RESTORE.md" in members,
            "current source capsule/restoration guide missing")
    for name, digest in RESTORE_PINS.items():
        require(name in members and members[name]["sha256"] == digest,
                "restoration input missing or unreviewed: " + name)


def json_data(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate delivery JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def primary_manifest(archive):
    """Bounded manifest read; does not establish signature or member integrity."""
    size_ok(regular(archive).stat().st_size)
    with tarfile.open(archive, "r:gz") as tar:
        matches = [m for m in tar if m.name == "MANIFEST.json"]
        require(len(matches) == 1 and matches[0].isfile() and
                0 < matches[0].size <= 16 * 1024**2, "primary manifest missing/ambiguous/oversized")
        return json_data(tar.extractfile(matches[0]).read())


def extract_verified(archive, destination, members):
    """Extract only a fully known inventory into a new directory, without links.

    Callers authenticate the primary archive before this operation. Each output
    is rehashed while writing, and unexpected/duplicate/missing nodes fail closed.
    """
    destination = Path(destination).absolute()
    require(not destination.exists() and not any(p.is_symlink() for p in (destination, *destination.parents)),
            "new unaliased extraction destination required")
    for name, row in members.items():
        safe_name(name)
        fields(row, {"size", "sha256"}, "extraction member fields")
        require(type(row["size"]) is int and row["size"] >= 0 and
                type(row["sha256"]) is str and SHA256.fullmatch(row["sha256"]), "extraction member identity")
        require(not any(str(p) in members for p in PurePosixPath(name).parents), "file is archive parent")
    allowed_dirs = {str(p) for n in members for p in PurePosixPath(n).parents if str(p) != "."}
    # These explicit empty roots are part of the release/capsule archive format.
    allowed_dirs |= {"source", "install", "evidence", "docs"}
    destination.mkdir(parents=True)
    seen, files = set(), set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = safe_name(member.name.rstrip("/") if member.isdir() else member.name)
            require(name not in seen and not member.mode & ~0o777, "duplicate/special extraction entry")
            seen.add(name)
            target = destination / name
            require(not any(p.is_symlink() for p in (target, *target.parents)), "linked extraction ancestor")
            if member.isdir():
                require(name in allowed_dirs and name not in members, "unexpected extraction directory")
                target.mkdir(parents=True, exist_ok=True)
                continue
            require(member.isfile() and name in members and member.size == members[name]["size"],
                    "unexpected/special/incorrect-size extraction member")
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with tar.extractfile(member) as incoming, target.open("xb") as outgoing:
                while block := incoming.read(1024 * 1024):
                    h.update(block)
                    outgoing.write(block)
            require(h.hexdigest() == members[name]["sha256"] and target.stat().st_size == member.size,
                    "extracted bytes differ")
            target.chmod(member.mode)
            files.add(name)
    require(files == set(members), "missing extraction members")
