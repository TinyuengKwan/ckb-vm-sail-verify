#!/usr/bin/env python3
"""Create or restore the exact source snapshot of one candidate using offline Git bundles.

The capsule carries complete Git bundles of the root and both submodules, a
byte-for-byte source payload (including the reviewed working-tree overlay) and
the self-digesting source snapshot.  Restoration uses the file transport only,
disables hooks and global configuration, and must reproduce the snapshot.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_common as common
import source_snapshot as source

require, sha = common.require, common.sha
BUNDLES = {".": "root.bundle", "deps/ckb-vm": "ckb.bundle", "deps/sail-riscv": "sail.bundle"}
MEMBER = "source/source-capsule.tar.gz"  # the capsule's name inside the release package


def environment():
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "file", "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
            "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"}


def new_path(path):
    path = Path(path).absolute()
    require(path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)) and not path.exists(),
            "new unaliased destination required: " + str(path))
    return path


def validate_snapshot(snapshot, candidate):
    common.fields(snapshot, {"schema_version", "identity_kind", "repositories", "ckb_source_baseline",
                             "ignored_build_and_evidence_files_included", "semantic_review_claimed", "snapshot_sha256"},
                  "source snapshot")
    require(snapshot["schema_version"] == 1 and snapshot["identity_kind"] == "HEAD-plus-byte-inventoried-working-tree-not-a-commit" and
            snapshot["ignored_build_and_evidence_files_included"] is False and snapshot["semantic_review_claimed"] is False,
            "source snapshot scope")
    body = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    require(source.digest(source.canonical(body)) == snapshot["snapshot_sha256"], "source snapshot self-digest differs")
    repos = snapshot["repositories"]
    common.fields(repos, set(BUNDLES), "source repository inventory")
    require(common.GIT_OID.fullmatch(candidate or "") and repos["."]["head"] == candidate, "source capsule candidate differs")
    require(repos["."]["gitlinks"] == {name: repos[name]["head"] for name in BUNDLES if name != "."}, "gitlinks differ")
    for repo, info in repos.items():
        common.fields(info, {"head", "gitlinks", "files", "changes_from_head"}, "source repository " + repo)
        require(common.GIT_OID.fullmatch(info["head"]) and (repo == "." or not info["gitlinks"]) and info["files"],
                "source repository head/nesting: " + repo)
        for name, row in info["files"].items():
            common.safe_name(name)
            require(".git" not in Path(name).parts and row["mode"] in ("100644", "100755") and
                    type(row["size"]) is int and common.SHA256.fullmatch(row["sha256"]), "source file identity: " + name)
    require(not repos["deps/sail-riscv"]["changes_from_head"], "unreviewed Sail overlay")
    return snapshot


def inspect(archive, candidate, expected_snapshot=None):
    archive = common.regular(archive)
    manifest = json.loads(common.archive_member_bytes(archive, "MANIFEST.json"))
    common.fields(manifest, {"schema_version", "kind", "candidate", "source_snapshot_sha256", "bundles", "members"}, "capsule manifest")
    require(manifest["schema_version"] == 1 and manifest["kind"] == "source-capsule-v1" and manifest["candidate"] == candidate,
            "source capsule identity")
    files, _ = common.tar_inventory(archive)
    members = manifest["members"]
    require(type(members) is dict and set(files) == set(members) | {"MANIFEST.json"}, "capsule member inventory differs")
    modes = {}
    with tarfile.open(archive, "r:gz") as tar:
        for item in tar:
            if item.isfile():
                modes[item.name] = item.mode
    snapshot = validate_snapshot(json.loads(common.archive_member_bytes(archive, "source-snapshot.json")), candidate)
    for name, row in members.items():
        common.fields(row, {"size", "sha256", "mode"}, "capsule member " + name)
        require(files[name] == {k: row[k] for k in ("size", "sha256")} and modes[name] == row["mode"] in (0o644, 0o755),
                "capsule member bytes/mode differ: " + name)
    require(snapshot["snapshot_sha256"] == manifest["source_snapshot_sha256"] and
            (expected_snapshot is None or snapshot == expected_snapshot), "capsule snapshot differs")
    expected = {"source-snapshot.json"} | set(BUNDLES.values())
    for repo, info in snapshot["repositories"].items():
        require(manifest["bundles"][repo] == {"path": BUNDLES[repo], "head": info["head"]}, "bundle binding differs")
        for name, row in info["files"].items():
            payload = "payload/" + (repo + "/" if repo != "." else "") + name
            expected.add(payload)
            require(members.get(payload) == {"size": row["size"], "sha256": row["sha256"], "mode": int(row["mode"], 8) & 0o777},
                    "payload differs from snapshot: " + name)
    require(set(members) == expected, "extra/missing payload or bundle")
    return snapshot, {name: {k: row[k] for k in ("size", "sha256")} for name, row in members.items()}


def command(out, name, argv, cwd):
    row = common.run_command(out, name, argv, cwd, env=environment(), timeout=600)
    require(row["exit_code"] == 0, "source capsule command failed: " + name)
    return row


def create(root, candidate, out):
    root, out = Path(root).resolve(), new_path(out)
    snapshot = validate_snapshot(source.capture(root), candidate)
    out.mkdir(parents=True)
    content = out / "content"
    content.mkdir()
    source.export(root, snapshot, content / "payload")
    common.write(content / "source-snapshot.json", snapshot)
    (content / "source-snapshot.json").chmod(0o644)
    stages = []
    for repo, filename in BUNDLES.items():
        stages.append(command(out, "create-" + filename, ["git", "bundle", "create", content / filename, "HEAD"], root / repo))
        stages.append(command(out, "verify-" + filename, ["git", "bundle", "verify", content / filename], root / repo))
        (content / filename).chmod(0o644)
    files = {p.relative_to(content).as_posix(): p for p in content.rglob("*") if p.is_file()}
    manifest = {"schema_version": 1, "kind": "source-capsule-v1", "candidate": candidate,
                "source_snapshot_sha256": snapshot["snapshot_sha256"],
                "bundles": {repo: {"path": f, "head": snapshot["repositories"][repo]["head"]} for repo, f in BUNDLES.items()},
                "members": {n: {"size": p.stat().st_size, "sha256": sha(p), "mode": p.stat().st_mode & 0o777}
                            for n, p in sorted(files.items())}}
    archive = out / "source-capsule.tar.gz"
    digest = common.write_tar_gz(archive, files, {"MANIFEST.json": common.json_bytes(manifest)})
    inspect(archive, candidate, snapshot)
    require(source.capture(root) == snapshot, "source changed during capsule creation")
    result = {"schema_version": 1, "kind": "source-capsule-result-v1", "status": "source_capsule_verified",
              "candidate": candidate, "source_snapshot_sha256": snapshot["snapshot_sha256"],
              "archive": {"path": archive.name, "sha256": digest}, "stages": stages}
    common.write(out / "report.json", result)
    return result


def restore(archive, digest, candidate, out, destination=None):
    out = new_path(out)
    destination = new_path(destination) if destination is not None else out / "checkout"
    require(not out.is_relative_to(destination), "report output overlaps checkout")
    archive = common.regular(archive)
    require(sha(archive) == digest, "source capsule trusted digest differs")
    snapshot, members = inspect(archive, candidate)
    out.mkdir(parents=True)
    unpacked = out / "unpacked"
    common.extract_verified(archive, unpacked, {**members, "MANIFEST.json": {"size": len(common.archive_member_bytes(archive, "MANIFEST.json")),
                                                                            "sha256": common.sha_bytes(common.archive_member_bytes(archive, "MANIFEST.json"))}})
    for repo, filename in BUNDLES.items():
        heads = subprocess.run(["git", "bundle", "list-heads", str(unpacked / filename)], env=environment(),
                               capture_output=True, text=True, timeout=300)
        require(heads.returncode == 0 and heads.stdout.strip() == snapshot["repositories"][repo]["head"] + " HEAD", "bundle heads differ")
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
    original = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(environment())
        source.restore(destination, unpacked / "payload", snapshot)
        require(source.capture(destination) == snapshot, "restored source identity differs")
    finally:
        os.environ.clear()
        os.environ.update(original)
    result = {"schema_version": 1, "kind": "source-restoration-v1", "status": "exact_source_restored", "candidate": candidate,
              "source_snapshot_sha256": snapshot["snapshot_sha256"], "checkout": str(destination), "stages": stages,
              "independent_git_objects": True, "file_only_git_transport": True}
    common.write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("create")
    build.add_argument("--root", type=Path, default=common.ROOT)
    build.add_argument("--candidate", required=True)
    build.add_argument("--out", type=Path, required=True)
    unpack = sub.add_parser("restore")
    unpack.add_argument("--archive", type=Path, required=True)
    unpack.add_argument("--archive-sha256", required=True)
    unpack.add_argument("--candidate", required=True)
    unpack.add_argument("--out", type=Path, required=True)
    unpack.add_argument("--destination", type=Path)
    args = parser.parse_args()
    result = (create(args.root, args.candidate, args.out) if args.command == "create" else
              restore(args.archive, args.archive_sha256, args.candidate, args.out, args.destination))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
