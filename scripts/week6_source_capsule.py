#!/usr/bin/env python3
"""Create/restore the exact current source snapshot using offline Git bundles.

Unlike the historical handoff CLI this format is not tied to a 2026-09-13
snapshot. The caller supplies the expected commit and trusted archive digest;
release restoration obtains that digest from the verified signed primary.
No installation, proof, publication or semantic approval is claimed here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import source_snapshot as source
import week6_release_assets as assets
import release_external_evidence as external

BUNDLES = {".": "root.bundle", "deps/ckb-vm": "ckb.bundle", "deps/sail-riscv": "sail.bundle"}
require = assets.require


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write(path, value):
    with Path(path).open("xb") as stream:
        stream.write(json_bytes(value))


def environment():
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "file",
            "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
            "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}


def new_path(path):
    path = Path(path).absolute()
    require(path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)) and
            not path.exists(), "new unaliased source destination required")
    return path


def validate_snapshot(snapshot, candidate):
    assets.fields(snapshot, {"schema_version", "identity_kind", "repositories", "ckb_source_baseline",
                  "ignored_build_and_evidence_files_included", "semantic_review_claimed", "snapshot_sha256"},
                  "source capsule snapshot fields")
    require(type(snapshot["schema_version"]) is int and snapshot["schema_version"] == 1 and
            snapshot["identity_kind"] == "HEAD-plus-byte-inventoried-working-tree-not-a-commit" and
            snapshot["ignored_build_and_evidence_files_included"] is False and
            snapshot["semantic_review_claimed"] is False, "source capsule snapshot scope")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    require(source.digest(source.canonical(body)) == snapshot["snapshot_sha256"], "source snapshot self-digest differs")
    assets.fields(snapshot["repositories"], set(BUNDLES), "source capsule repository inventory")
    repos = snapshot["repositories"]
    require(type(candidate) is str and external.GIT_OID.fullmatch(candidate) and repos["."]["head"] == candidate,
            "source capsule candidate differs")
    require(repos["."]["gitlinks"] == {name: repos[name]["head"] for name in BUNDLES if name != "."},
            "source capsule gitlinks differ")
    for repo, info in repos.items():
        assets.fields(info, {"head", "gitlinks", "files", "changes_from_head"}, "source repository fields")
        require(type(info["head"]) is str and external.GIT_OID.fullmatch(info["head"]) and
                (repo == "." or not info["gitlinks"]), "invalid source repository head/nesting")
        require(type(info["files"]) is dict and info["files"], "empty source file inventory")
        for name, row in info["files"].items():
            assets.safe_name(name)
            require(".git" not in Path(name).parts, "Git metadata in source payload")
            assets.fields(row, {"mode", "sha256", "size"}, "source file fields")
            require(row["mode"] in ("100644", "100755") and type(row["size"]) is int and row["size"] >= 0 and
                    type(row["sha256"]) is str and assets.SHA256.fullmatch(row["sha256"]), "source file identity")
    require(not repos["deps/sail-riscv"]["changes_from_head"], "unreviewed Sail overlay")
    return snapshot


def inspect(archive, candidate, expected_snapshot=None):
    archive = assets.regular(archive)
    manifest = assets.primary_manifest(archive)
    assets.fields(manifest, {"schema_version", "kind", "candidate", "source_snapshot_sha256", "bundles", "members"},
                  "source capsule manifest fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and
            manifest["kind"] == "week6-source-capsule-v1" and manifest["candidate"] == candidate,
            "source capsule identity")
    assets.fields(manifest["bundles"], set(BUNDLES), "source bundle inventory")
    files, _ = external.tar_inventory(archive)
    members = manifest["members"]
    require(type(members) is dict and "MANIFEST.json" not in members and
            set(files) == set(members) | {"MANIFEST.json"}, "source capsule member inventory differs")
    modes = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if member.isfile():
                modes[member.name] = member.mode
        snap = tar.getmember("source-snapshot.json")
        require(snap.isfile() and snap.size <= 16 * 1024**2, "source snapshot missing/oversized")
        snapshot = validate_snapshot(assets.json_data(tar.extractfile(snap).read()), candidate)
    for name, row in members.items():
        assets.safe_name(name)
        assets.fields(row, {"size", "sha256", "mode"}, "source capsule member fields")
        require(files[name] == {k: row[k] for k in ("size", "sha256")} and
                row["mode"] in (0o644, 0o755) and modes[name] == row["mode"], "source capsule member bytes/mode differ: " + name)
    require(snapshot["snapshot_sha256"] == manifest["source_snapshot_sha256"] and
            (expected_snapshot is None or snapshot == expected_snapshot), "source capsule snapshot differs")
    expected_names = {"source-snapshot.json"} | set(BUNDLES.values())
    for repo, info in snapshot["repositories"].items():
        require(manifest["bundles"][repo] == {"path": BUNDLES[repo], "head": info["head"]}, "source bundle binding differs")
        for name, row in info["files"].items():
            payload = "payload/" + (repo + "/" if repo != "." else "") + name
            expected_names.add(payload)
            require(members.get(payload) == {"size": row["size"], "sha256": row["sha256"],
                                            "mode": int(row["mode"], 8) & 0o777}, "source payload differs from snapshot")
    require(set(members) == expected_names, "extra/missing source payload or bundle")
    return snapshot, files


def command(out, name, argv, cwd):
    stdout, stderr = out / (name + ".stdout"), out / (name + ".stderr")
    with stdout.open("xb") as a, stderr.open("xb") as b:
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env=environment(),
                                stdin=subprocess.DEVNULL, stdout=a, stderr=b, timeout=300)
    require(result.returncode == 0, "source capsule command failed: " + name + "; inspect " + str(stderr))
    return {"name": name, "argv": list(map(str, argv)), "cwd": str(cwd), "exit_code": result.returncode,
            "stdout": {"path": stdout.name, "sha256": assets.sha(stdout)},
            "stderr": {"path": stderr.name, "sha256": assets.sha(stderr)}}


def create(root, candidate, out):
    import week6_release_package as package
    root, out = Path(root).resolve(), new_path(out)
    snapshot = validate_snapshot(source.capture(root), candidate)
    out.mkdir(parents=True)
    content = out / "content"
    content.mkdir()
    source.export(root, snapshot, content / "payload")
    write(content / "source-snapshot.json", snapshot)
    (content / "source-snapshot.json").chmod(0o644)
    stages = []
    for repo, filename in BUNDLES.items():
        stages.append(command(out, "create-" + filename, ["git", "bundle", "create", content / filename, "HEAD"], root / repo))
        stages.append(command(out, "verify-" + filename, ["git", "bundle", "verify", content / filename], root / repo))
        (content / filename).chmod(0o644)
    files = {p.relative_to(content).as_posix(): p for p in content.rglob("*") if p.is_file()}
    manifest = {"schema_version": 1, "kind": "week6-source-capsule-v1", "candidate": candidate,
        "source_snapshot_sha256": snapshot["snapshot_sha256"],
        "bundles": {repo: {"path": filename, "head": snapshot["repositories"][repo]["head"]} for repo, filename in BUNDLES.items()},
        "members": {n: {"size": p.stat().st_size, "sha256": assets.sha(p), "mode": p.stat().st_mode & 0o777}
                    for n, p in sorted(files.items())}}
    archive = out / "source-capsule.tar.gz"
    digest = package.archive(archive, files, json_bytes(manifest))
    inspect(archive, candidate, snapshot)
    require(source.capture(root) == snapshot, "source changed during capsule creation")
    result = {"schema_version": 1, "kind": "week6-source-capsule-result-v1", "status": "source_capsule_verified",
        "candidate": candidate, "source_snapshot_sha256": snapshot["snapshot_sha256"],
        "archive": {"path": archive.name, "sha256": digest}, "stages": stages,
        "semantic_approval_claimed": False, "release_claimed": False, "week6_closed": False}
    write(out / "report.json", result)
    return result


def restore(archive, digest, candidate, out, destination=None):
    out = new_path(out)
    destination = new_path(destination) if destination is not None else out / "checkout"
    require(not out.is_relative_to(destination), "source report output overlaps checkout")
    archive = assets.regular(archive)
    require(assets.sha(archive) == digest, "source capsule trusted digest differs")
    snapshot, members = inspect(archive, candidate)
    out.mkdir(parents=True)
    unpacked = out / "unpacked"
    assets.extract_verified(archive, unpacked, members)
    require(assets.sha(archive) == digest, "source capsule changed during extraction")
    for repo, filename in BUNDLES.items():
        heads = subprocess.run(["git", "bundle", "list-heads", str(unpacked / filename)],
            env=environment(), capture_output=True, text=True, timeout=300)
        require(heads.returncode == 0 and heads.stdout.strip() == snapshot["repositories"][repo]["head"] + " HEAD",
                "source bundle heads differ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stages = [command(out, "clone-root", ["git", "clone", "--no-hardlinks", "--no-checkout", unpacked / BUNDLES["."], destination], out),
              command(out, "checkout-root", ["git", "checkout", "--detach", candidate], destination)]
    for repo, filename in BUNDLES.items():
        if repo != ".":
            stages.append(command(out, "configure-" + filename, ["git", "config", "submodule." + repo + ".url", unpacked / filename], destination))
    stages.append(command(out, "recursive-submodules", ["git", "submodule", "update", "--init", "--recursive"], destination))
    for repo, filename in BUNDLES.items():
        stages.append(command(out, "fsck-" + filename, ["git", "fsck", "--full", "--strict"], destination / repo))
        source.independent(destination / repo)
    # Source helpers use Git too; keep them in the same file-only environment.
    original = dict(os.environ)
    try:
        os.environ.clear(); os.environ.update(environment())
        source.restore(destination, unpacked / "payload", snapshot)
        require(source.capture(destination) == snapshot, "restored source identity differs")
    finally:
        os.environ.clear(); os.environ.update(original)
    result = {"schema_version": 1, "kind": "week6-source-restoration-v1", "status": "exact_source_restored",
        "candidate": candidate, "source_snapshot_sha256": snapshot["snapshot_sha256"], "checkout": str(destination),
        "stages": stages, "independent_git_objects": True, "file_only_git_transport": True,
        "os_sandboxed": False, "toolchain_installed": False, "release_claimed": False, "week6_closed": False}
    write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("create")
    build.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    build.add_argument("--candidate", required=True)
    build.add_argument("--out", type=Path, required=True)
    unpack = sub.add_parser("restore")
    unpack.add_argument("--archive", type=Path, required=True)
    unpack.add_argument("--archive-sha256", required=True)
    unpack.add_argument("--candidate", required=True)
    unpack.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = create(args.root, args.candidate, args.out) if args.command == "create" else restore(
        args.archive, args.archive_sha256, args.candidate, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
