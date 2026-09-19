#!/usr/bin/env python3
"""Validate a downloaded Week6 archive and the intentional pre-publication audit boundary.

Extraction is restricted to new ignored evidence and replay paths; no archive
member may overwrite checkout source. This gate validates evidence but does
not claim that a CI run exists.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile


def project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts/audit_release.py").is_file():
            return parent
    raise RuntimeError("project root not found")


PROJECT = project_root()
sys.path.insert(0, str(PROJECT / "scripts"))
import audit_release
import release_external_evidence as external


SHA256 = re.compile(r"[0-9a-f]{64}")
OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
ALLOWED_PREFIXES = (
    "artifacts/boundary-check/week6-clean-room/",
    "cases/",
    "bin/",
    "config/",
)


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
            "unsafe archive name")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(part not in ("", ".", "..") for part in path.parts),
            "unsafe archive name")
    return value


def decode_json(data, label):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key in " + label)
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs)
    except Exception as error:
        raise RuntimeError("invalid JSON: " + label) from error


def expected_members(manifest, candidate):
    require(type(manifest) is dict and set(manifest) == {
        "schema_version", "kind", "candidate", "source_snapshot_sha256",
        "clean_room_report", "replay_case", "members"
    }, "CI manifest fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and
            manifest["kind"] == "ci-evidence-archive-manifest-v1" and
            manifest["candidate"] == candidate and
            SHA256.fullmatch(manifest["source_snapshot_sha256"] or ""),
            "CI manifest identity")
    clean = safe_name(manifest["clean_room_report"])
    replay = safe_name(manifest["replay_case"])
    require(clean.startswith(ALLOWED_PREFIXES[0]) and replay == "cases/add-signed-overflow.json",
            "CI manifest clean-room/replay paths")
    rows = manifest["members"]
    require(type(rows) is list and rows, "empty CI member inventory")
    result = {}
    for row in rows:
        require(type(row) is dict and set(row) == {"path", "size", "sha256"},
                "CI member fields")
        name = safe_name(row["path"])
        require(name != "MANIFEST.json" and any(name.startswith(prefix) for prefix in ALLOWED_PREFIXES),
                "CI member outside extraction allowlist")
        require(name not in result and type(row["size"]) is int and row["size"] >= 0 and
                SHA256.fullmatch(row["sha256"] or ""), "invalid/duplicate CI member")
        result[name] = {"size": row["size"], "sha256": row["sha256"]}
    require(clean in result and replay in result, "mandatory CI members absent")
    return result


# Replay members (bin/, cases/, config/) must not land at the checkout root:
# untracked files there would change the source snapshot the clean-room report
# is bound to.  They are extracted under an ignored evidence directory instead;
# the distinct download/replay job extracts the archive into its own directory.
REPLAY_ROOT = "artifacts/boundary-check/week6-ci-replay"


def member_target(destination, name):
    if name.startswith(ALLOWED_PREFIXES[0]):
        return Path(destination) / name
    return Path(destination) / REPLAY_ROOT / name


def extract_and_validate(archive_path, destination, candidate):
    archive_path = Path(archive_path).absolute()
    destination = Path(destination).absolute()
    require(archive_path.is_file() and not archive_path.is_symlink(), "missing/linked CI archive")
    require(destination.is_dir() and not destination.is_symlink(), "missing/linked checkout root")
    archive_before = sha(archive_path)
    observed, manifest_bytes = {}, None
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            name = safe_name(member.name)
            require(member.isfile() and not member.linkname and not member.sparse and
                    member.uid == member.gid == member.mtime == 0 and not member.uname and not member.gname and
                    not member.mode & 0o7000, "unsafe CI archive metadata")
            stream = archive.extractfile(member)
            require(stream is not None, "unreadable CI archive member")
            if name == "MANIFEST.json":
                require(manifest_bytes is None and member.size <= 64 * 1024 * 1024,
                        "duplicate/oversized CI manifest")
                manifest_bytes = stream.read()
                require(len(manifest_bytes) == member.size, "truncated CI manifest")
                continue
            require(any(name.startswith(prefix) for prefix in ALLOWED_PREFIXES) and name not in observed,
                    "extra/duplicate CI member")
            target = member_target(destination, name)
            require(target.resolve(strict=False) == target and not target.exists() and not target.is_symlink(),
                    "CI member target occupied/aliased")
            target.parent.mkdir(parents=True, exist_ok=True)
            require(all(not parent.is_symlink() for parent in (target, *target.parents)),
                    "linked CI member ancestor")
            digest, size = hashlib.sha256(), 0
            with target.open("xb") as output:
                while block := stream.read(1024 * 1024):
                    output.write(block)
                    digest.update(block)
                    size += len(block)
            require(size == member.size, "truncated CI archive member")
            target.chmod(member.mode & 0o777)
            observed[name] = {"size": size, "sha256": digest.hexdigest()}
    require(manifest_bytes is not None, "CI manifest absent")
    manifest = decode_json(manifest_bytes, "MANIFEST.json")
    expected = expected_members(manifest, candidate)
    require(observed == expected, "CI archive member inventory differs")
    for name, row in observed.items():
        path = member_target(destination, name)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == row["size"] and
                sha(path) == row["sha256"], "extracted CI member differs")
    require(sha(archive_path) == archive_before, "CI archive changed during extraction")
    return manifest, archive_before


def validate_archived_aggregate(root, audit_manifest, archived_report, expected, clean_report):
    """Accept the aggregate the guest recorded instead of recomputing it.

    The intake runner has none of the fixed toolchains, so the local components
    (runtime, Rust tests, mismatches) cannot be re-probed here.  The guest's own
    final aggregate is bound to the extracted audit manifest by hash, every slot
    it verified must reference a file present in the archive with the recorded
    digest, the only clean-room shortfall it may report is the host provenance
    record that is written after extraction, and that record is validated here
    against the same clean-room report.
    """
    report = decode_json(archived_report.read_bytes(), "archived aggregate")
    manifest = decode_json(audit_manifest.read_bytes(), "audit manifest")
    require(type(manifest) is dict and type(manifest.get("evidence")) is dict, "audit manifest evidence rows")
    require(type(report) is dict and report.get("status") == "incomplete" and
            report.get("manifest_sha256") == sha(audit_manifest), "archived aggregate identity")
    require(report.get("release_claimed") is False and report.get("week6_closed") is False and
            report.get("fresh_execution_claimed") is False, "archived aggregate boundary")
    require(report.get("outstanding") == expected, "archived aggregate boundary differs")
    checks = report.get("checks")
    require(type(checks) is dict and set(checks) == set(audit_release.SLOTS), "archived aggregate slots")
    verified = 0
    for name, row in checks.items():
        status = row.get("status")
        if name in expected:
            require(status in ("missing", "incomplete"), "outstanding slot is not merely open: " + name)
            if name == "clean_room":
                require(status == "incomplete" and "provenance record absent" in str(row.get("reason")),
                        "guest clean-room shortfall is not the deferred host record")
            continue
        require(status == "verified_existing_evidence", "archived slot not verified: " + name)
        reference = row.get("reference")
        require(type(reference) is dict and set(reference) == {"path", "sha256"} and
                SHA256.fullmatch(reference["sha256"] or ""), "archived slot reference")
        safe_name(reference["path"])
        # The CI archive carries the clean-room record, not every evidence tree; the
        # intake job validated the complete bundle.  Here the aggregate's verified
        # references must be exactly the manifest rows it was computed from, and any
        # referenced file that is present must still carry the recorded digest.
        require(manifest["evidence"].get(name) == reference, "archived slot reference differs from manifest: " + name)
        present = root / reference["path"]
        if present.exists():
            audit_release.evidence.linked(root, reference["path"], reference["sha256"])
        verified += 1
    provenance = external.check_vm_provenance(clean_report)
    return {"archived_aggregate_sha256": sha(archived_report), "verified_slots": verified,
            "outstanding": expected, "vm_provenance": provenance}


def run(args):
    root = Path(args.root).resolve()
    require(root == PROJECT.resolve(), "gate must run against its own checkout")
    require(OID.fullmatch(args.candidate), "candidate must be a full Git OID")
    require(SHA256.fullmatch(args.archive_sha256), "archive SHA-256 absent")
    require(sha(args.archive) == args.archive_sha256, "downloaded archive SHA-256 differs")
    manifest, archive_sha = extract_and_validate(args.archive, root, args.candidate)
    clean = root / manifest["clean_room_report"]
    clean_result = external.check_clean_room(clean, args.candidate, root=root)
    require(clean_result["source_snapshot_sha256"] == manifest["source_snapshot_sha256"],
            "archive/clean-room source snapshot differs")
    audit_manifest = root / safe_name(args.audit_manifest)
    require(audit_manifest.is_file() and not audit_manifest.is_symlink(), "pre-CI audit manifest absent")
    expected = args.expected_outstanding.split(",")
    if args.archived_aggregate:
        archived = root / safe_name(args.archived_aggregate)
        require(archived.is_file() and not archived.is_symlink(), "archived aggregate absent")
        archived_result = validate_archived_aggregate(root, audit_manifest, archived, expected, clean)
        return {"status": "downloaded_clean_room_host_provenance_and_archived_boundary_verified",
                "candidate": args.candidate, "archive_sha256": archive_sha,
                "source_snapshot_sha256": manifest["source_snapshot_sha256"],
                "clean_room": clean_result, "archived_aggregate": archived_result,
                "audit_outstanding": expected, "release_claimed": False, "week6_closed": False}
    result, code = audit_release.aggregate(audit_release.evidence.read(audit_manifest))
    require(code == 2 and result["status"] == "incomplete" and result["outstanding"] == expected and
            result["release_claimed"] is False and result["week6_closed"] is False,
            "pre-publication audit boundary differs")
    return {"status": "downloaded_clean_room_and_pre_publication_boundary_verified",
            "candidate": args.candidate, "archive_sha256": archive_sha,
            "source_snapshot_sha256": manifest["source_snapshot_sha256"],
            "clean_room": clean_result, "audit_outstanding": expected,
            "release_claimed": False, "week6_closed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--audit-manifest", required=True)
    parser.add_argument("--expected-outstanding", required=True)
    parser.add_argument("--archived-aggregate", default=None,
                        help="root-relative path of the guest's final aggregate report; validated instead of recomputed")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
