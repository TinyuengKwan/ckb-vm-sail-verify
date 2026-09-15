#!/usr/bin/env python3
"""Build or record one approved Week6 profile-A release package.

The build command is local and deterministic. The record command is read-only:
it records an already published immutable GitHub release, downloads the asset,
and invokes the repository's strict release-package validator. This script does
not create releases, upload assets, choose a version, or create a signature.
"""

import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile


def project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts/release_external_evidence.py").is_file():
            return parent
    raise RuntimeError("project root not found")


ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts"))
import release_external_evidence as external
import release_evidence as common
import source_snapshot


OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
SHA256 = re.compile(r"[0-9a-f]{64}")
PREFIXES = ("source/", "install/", "evidence/", "docs/")


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
            "unsafe package path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(part not in ("", ".", "..") for part in path.parts), "unsafe package path")
    return value


def regular(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink() and
            all(not parent.is_symlink() for parent in path.parents), "missing/linked package input")
    mode = path.stat().st_mode
    require(stat.S_ISREG(mode) and not mode & 0o7000, "special package input")
    return path


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(regular(path).read_bytes(), object_pairs_hook=pairs)


def write(path, data):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(data)


def ref(directory, path):
    directory, path = Path(directory).absolute(), regular(path)
    require(path.is_relative_to(directory), "release reference outside package directory")
    return {"path": path.relative_to(directory).as_posix(), "sha256": sha(path)}


def run_command(directory, label, argv):
    stdout, stderr = directory / (label + ".stdout"), directory / (label + ".stderr")
    with stdout.open("xb") as a, stderr.open("xb") as b:
        result = subprocess.run(list(map(str, argv)), cwd=directory, env=os.environ.copy(),
                                stdout=a, stderr=b, timeout=1800)
    return {"argv": list(map(str, argv)), "exit_code": result.returncode,
            "stdout": ref(directory, stdout), "stderr": ref(directory, stderr)}


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def descriptor(path, input_root, candidate, version, profile):
    value = read(path)
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "candidate", "version", "delivery_profile",
        "source_snapshot", "coverage", "non_goals", "members"
    }, "package input descriptor fields")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and
            value["kind"] == "release-package-inputs-v1" and value["candidate"] == candidate and
            value["version"] == version and value["delivery_profile"] == profile,
            "package input descriptor identity")
    snapshot = value["source_snapshot"]
    require(type(snapshot) is dict and set(snapshot) == {"path", "sha256"} and
            SHA256.fullmatch(snapshot["sha256"] or ""), "package source snapshot reference")
    input_root = Path(input_root).absolute()
    snapshot_path = regular(input_root / safe_name(snapshot["path"]))
    require(sha(snapshot_path) == snapshot["sha256"], "package source snapshot bytes")
    snapshot_value = read(snapshot_path)
    require(SHA256.fullmatch(snapshot_value.get("snapshot_sha256", "")), "source snapshot identity")
    rows, files = value["members"], {}
    require(type(rows) is list and rows, "empty package input inventory")
    for row in rows:
        require(type(row) is dict and set(row) == {"path", "source", "sha256"},
                "package input row fields")
        name, source = safe_name(row["path"]), safe_name(row["source"])
        require(any(name.startswith(prefix) for prefix in PREFIXES) and name not in files and
                name not in ("SHA256SUMS", "MANIFEST.json") and SHA256.fullmatch(row["sha256"] or ""),
                "invalid/duplicate package member")
        source_path = regular(input_root / source)
        require(sha(source_path) == row["sha256"], "package input hash differs: " + name)
        files[name] = source_path
    coverage, non_goals = safe_name(value["coverage"]), safe_name(value["non_goals"])
    require(coverage in files and non_goals in files and coverage.startswith("docs/") and
            non_goals.startswith("docs/"), "coverage/non-goals package members")
    require(all(any(name.startswith(prefix) for name in files) for prefix in PREFIXES),
            "required package prefix absent")
    return value, snapshot_value, snapshot_path, files


def copy_payload(built, files):
    result = {}
    for name, source in sorted(files.items()):
        target = built / name
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists() and not target.is_symlink(), "package build target occupied")
        with regular(source).open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        target.chmod(source.stat().st_mode & 0o777)
        require(sha(target) == sha(source), "package copy changed bytes")
        result[name] = target
    return result


def checksum_bytes(files):
    return "".join(f"{sha(path)}  {name}\n" for name, path in sorted(files.items())).encode()


def tar_info(name, size=0, mode=0o644, directory=False):
    info = tarfile.TarInfo(name.rstrip("/") + "/" if directory else safe_name(name))
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    info.mode = mode & 0o777
    info.size = size
    if directory:
        info.type = tarfile.DIRTYPE
    return info


def archive(path, files, manifest_data):
    require(not path.exists() and not path.is_symlink(), "package archive output occupied")
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=1, mtime=0, fileobj=raw) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for prefix in PREFIXES:
                    tar.addfile(tar_info(prefix, directory=True, mode=0o755))
                for name, source in sorted(files.items()):
                    source = regular(source)
                    before = sha(source)
                    with source.open("rb") as stream:
                        tar.addfile(tar_info(name, source.stat().st_size, source.stat().st_mode), stream)
                    require(sha(source) == before, "package input changed during archive")
                tar.addfile(tar_info("MANIFEST.json", len(manifest_data)), _Reader(manifest_data))
    return sha(path)


class _Reader:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def read(self, size=-1):
        if size < 0:
            size = len(self.data) - self.offset
        result = self.data[self.offset:self.offset + size]
        self.offset += len(result)
        return result


def build(args, policy=None, verify_current=True):
    policy = external.load_policy(ROOT) if policy is None else policy
    cfg = policy["release_package"]
    require(OID.fullmatch(args.candidate), "candidate must be a full Git OID")
    require(cfg["approved_version"] is not None and cfg["approved_delivery_profile"] == "A" and
            cfg["approved_signer_identity"] is not None, "release policy approvals incomplete")
    require(args.version == cfg["approved_version"] and args.delivery_profile == "A",
            "requested package identity is not approved")
    out = Path(args.out).absolute()
    require(not out.exists() and not out.is_symlink() and out.parent.is_dir(), "new package output required")
    value, snapshot, snapshot_path, sources = descriptor(
        args.inputs, args.input_root, args.candidate, args.version, args.delivery_profile)
    if verify_current:
        require(source_snapshot.capture(ROOT) == snapshot, "package source snapshot is not current")
    out.mkdir()
    built = out / "built"
    built.mkdir()
    shutil.copyfile(snapshot_path, built / "source-snapshot.json")
    require(sha(built / "source-snapshot.json") == sha(snapshot_path), "source snapshot copy changed")
    files = copy_payload(built, sources)
    sums = checksum_bytes(files)
    write(built / "SHA256SUMS", sums)
    files["SHA256SUMS"] = built / "SHA256SUMS"
    manifest = {
        "schema_version": 1, "kind": "release-package-manifest-v1",
        "candidate": args.candidate, "version": args.version,
        "delivery_profile": args.delivery_profile,
        "source_snapshot_sha256": snapshot["snapshot_sha256"],
        "coverage": value["coverage"], "non_goals": value["non_goals"],
        "members": [{"path": name, "size": path.stat().st_size, "sha256": sha(path)}
                    for name, path in sorted(files.items())],
    }
    manifest_data = json_bytes(manifest)
    write(built / "MANIFEST.json", manifest_data)
    name = f"ckb-vm-sail-verify-{args.version}.tar.gz"
    archive_path = built / name
    archive_sha = archive(archive_path, files, manifest_data)
    inventory, directories = external.tar_inventory(archive_path)
    expected = {name: {"size": path.stat().st_size, "sha256": sha(path)} for name, path in files.items()}
    require({name: row for name, row in inventory.items() if name != "MANIFEST.json"} == expected and
            inventory["MANIFEST.json"]["sha256"] == sha(built / "MANIFEST.json") and
            set(PREFIXES) <= directories, "built package independent stream verification failed")
    result = {"schema_version": 1, "kind": "release-package-build-result-v1",
              "status": "approved_identity_package_built_not_signed_or_published",
              "candidate": args.candidate, "version": args.version, "delivery_profile": "A",
              "source_snapshot": ref(out, built / "source-snapshot.json"),
              "archive": {"path": "built/" + name, "sha256": archive_sha},
              "manifest": {"path": "built/MANIFEST.json", "sha256": sha(built / "MANIFEST.json")},
              "members": len(files),
              "boundaries": {"signed": False, "published": False, "download_verified": False,
                             "release_claimed": False, "week6_closed": False}}
    write(out / "build-result.json", json_bytes(result))
    return result


def record(args):
    directory = Path(args.package_dir).absolute()
    require(directory.is_dir() and not directory.is_symlink() and
            all(not parent.is_symlink() for parent in directory.parents), "package directory missing/linked")
    require(not (directory / "report.json").exists() and not (directory / "report.candidate.json").exists(),
            "release report already exists")
    build_result = read(directory / "build-result.json")
    require(build_result.get("schema_version") == 1 and
            build_result.get("kind") == "release-package-build-result-v1" and
            build_result.get("status") == "approved_identity_package_built_not_signed_or_published",
            "release build result incomplete")
    candidate, version = build_result["candidate"], build_result["version"]
    require(OID.fullmatch(candidate) and type(args.release_id) is int and args.release_id > 0,
            "release identity absent")
    policy = external.load_policy(ROOT)
    cfg = policy["release_package"]
    require(version == cfg["approved_version"] and build_result["delivery_profile"] ==
            cfg["approved_delivery_profile"] == "A" and cfg["approved_signer_identity"] is not None,
            "release build no longer matches approved policy")
    archive_path = regular(directory / build_result["archive"]["path"])
    require(sha(archive_path) == build_result["archive"]["sha256"], "built archive changed")
    signature = regular(Path(str(archive_path) + ".sig"))
    manifest_path = regular(directory / build_result["manifest"]["path"])
    source_path = regular(directory / build_result["source_snapshot"]["path"])
    manifest = read(manifest_path)
    coverage = regular(directory / "built" / safe_name(manifest["coverage"]))
    non_goals = regular(directory / "built" / safe_name(manifest["non_goals"]))

    remote_argv = ["gh", "api", "--hostname", "github.com",
                   f"repos/{policy['repository']}/releases/{args.release_id}"]
    remote_record = run_command(directory, "release-remote-query", remote_argv)
    require(remote_record["exit_code"] == 0, "release remote query failed")
    remote = read(directory / remote_record["stdout"]["path"])
    require(remote.get("id") == args.release_id and remote.get("tag_name") == version and
            remote.get("draft") is False and remote.get("immutable") is True and
            type(remote.get("html_url")) is str and type(remote.get("published_at")) is str,
            "release is not the approved immutable publication")
    assets = remote.get("assets")
    require(type(assets) is list, "release asset list absent")
    archive_assets = [row for row in assets if type(row) is dict and row.get("name") == archive_path.name]
    signature_assets = [row for row in assets if type(row) is dict and row.get("name") == signature.name]
    require(len(archive_assets) == len(signature_assets) == 1, "release archive/signature asset ambiguity")
    asset, signature_asset = archive_assets[0], signature_assets[0]
    for row, path in [(asset, archive_path), (signature_asset, signature)]:
        require(type(row.get("id")) is int and row["id"] > 0 and row.get("state") == "uploaded" and
                row.get("size") == path.stat().st_size and row.get("digest") == "sha256:" + sha(path) and
                type(row.get("browser_download_url")) is str and row["browser_download_url"],
                "release asset bytes/state differ")

    downloaded = directory / "downloaded"
    initially_absent = not downloaded.exists() and not downloaded.is_symlink()
    require(initially_absent, "release download destination reused")
    downloaded.mkdir()
    downloaded_archive = downloaded / archive_path.name
    download_argv = ["curl", "--fail", "--location", "--output",
                     downloaded_archive.relative_to(directory).as_posix(), asset["browser_download_url"]]
    download_record = run_command(directory, "release-download", download_argv)
    require(download_record["exit_code"] == 0 and regular(downloaded_archive) and
            sha(downloaded_archive) == sha(archive_path), "published release download differs")

    report = {
        "schema_version": 1, "kind": "release-package-evidence-v1", "status": "passed",
        "candidate": candidate, "version": version, "delivery_profile": "A",
        "source_snapshot": ref(directory, source_path), "archive_format": "tar.gz",
        "archive": ref(directory, archive_path), "manifest": ref(directory, manifest_path),
        "coverage": ref(directory, coverage), "non_goals": ref(directory, non_goals),
        "publication": {"provider": "github-releases", "repository": policy["repository"],
                        "release_id": args.release_id, "tag": version, "url": remote["html_url"],
                        "asset_url": asset["browser_download_url"],
                        "signature_asset_url": signature_asset["browser_download_url"],
                        "published_at": remote["published_at"],
                        "immutable": True, "remote_query": remote_record},
        "download": {"url": asset["browser_download_url"], "archive": ref(directory, downloaded_archive),
                     "destination_initially_absent": initially_absent, **download_record},
        "signing_identity": cfg["approved_signer_identity"], "signature": ref(directory, signature),
        "boundaries": {"release_package_built": True, "publication_verified": True,
                       "download_verified": True, "remote_state_queried": True,
                       "release_claimed": False, "week6_closed": False},
    }
    candidate_path = directory / "report.candidate.json"
    write(candidate_path, json_bytes(report))
    checked = external.check_release_package(candidate_path, candidate, root=ROOT)
    require(checked["publication_verified"] is True and checked["download_verified"] is True,
            "release package validator did not close its slot")
    candidate_path.rename(directory / "report.json")
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    builder = sub.add_parser("build")
    builder.add_argument("--candidate", required=True)
    builder.add_argument("--version", required=True)
    builder.add_argument("--delivery-profile", required=True, choices=["A"])
    builder.add_argument("--input-root", required=True, type=Path)
    builder.add_argument("--inputs", required=True, type=Path)
    builder.add_argument("--out", required=True, type=Path)
    recorder = sub.add_parser("record")
    recorder.add_argument("--package-dir", required=True, type=Path)
    recorder.add_argument("--release-id", required=True, type=int)
    args = parser.parse_args()
    if args.command == "build":
        print(json.dumps(build(args), indent=2, sort_keys=True))
    else:
        print(json.dumps(record(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
