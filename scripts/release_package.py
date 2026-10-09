#!/usr/bin/env python3
"""Build, record and restore the signed release package.

``build`` assembles the primary archive from the current candidate checkout:
the source capsule, the pinned installation inputs, the user-facing documents
and the evidence directory you name.  It is deterministic and unsigned.
``record`` is read-only: after the owner has signed the archive, tagged the
candidate and published the immutable GitHub release, it fetches the tag,
queries the release, downloads every asset and runs the release validator.
``restore`` authenticates a downloaded release with this checkout's trusted
signer and restores the source and the fixed tools offline.  Nothing here
creates a release, uploads, chooses a version or signs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixed_inputs
import release_common as common
import source_capsule
import source_snapshot

ROOT = common.ROOT
require, sha, read = common.require, common.sha, common.read
PREFIXES = ("source/", "install/", "evidence/", "docs/")
INSTALL_MEMBERS = {"install/manifest.json": "manifest.json",
                   "install/rebuilt-decoder-candidate.tar.gz": "rebuilt-decoder-candidate.tar.gz",
                   "install/cmake-downloads.tar.gz": "cmake-downloads.tar.gz",
                   "install/cmake-downloads-manifest.json": "cmake-downloads-manifest.json"}


def archive_name(version):
    return f"ckb-vm-sail-verify-{version}.tar.gz"


def copy_tree(source, target, files, prefix):
    for path in sorted(Path(source).rglob("*")):
        if path.is_file() and not path.is_symlink():
            name = prefix + path.relative_to(source).as_posix()
            common.safe_name(name)
            require(name not in files, "duplicate package member: " + name)
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            destination.chmod(0o755 if path.stat().st_mode & 0o100 else 0o644)
            files[name] = destination


def build(args, root=ROOT):
    policy = common.load_policy(root)
    pkg, pins = policy["package"], policy["fixed_inputs"]
    candidate, version = args.candidate, policy["version"]
    require(common.GIT_OID.fullmatch(candidate or ""), "candidate must be a full commit OID")
    out = Path(args.out).absolute()
    require(not out.exists() and not out.is_symlink(), "new package output required")
    inputs = Path(args.inputs).resolve()
    for name in INSTALL_MEMBERS.values():
        local = inputs / name
        require(local.is_file() and sha(local) == pins[name]["sha256"], "pinned input missing/differs: " + name)
    tool_name = pkg["tool_asset"]
    tool = inputs / tool_name
    require(tool.is_file() and tool.stat().st_size == pins[tool_name]["size"] and sha(tool) == pins[tool_name]["sha256"],
            "tool asset missing/differs")
    evidence = Path(args.evidence).resolve()
    require(evidence.is_dir(), "evidence directory missing")
    snapshot = source_snapshot.capture(root)
    require(snapshot["repositories"]["."]["head"] == candidate, "checkout head is not the candidate")
    out.mkdir(parents=True)
    built = out / "built"
    built.mkdir()
    capsule = source_capsule.create(root, candidate, out / "source-capsule")
    files = {}
    (built / "source").mkdir()
    shutil.copyfile(out / "source-capsule" / capsule["archive"]["path"], built / source_capsule.MEMBER)
    files[source_capsule.MEMBER] = built / source_capsule.MEMBER
    (built / "install").mkdir()
    for member, name in INSTALL_MEMBERS.items():
        shutil.copyfile(inputs / name, built / member)
        files[member] = built / member
    (built / "docs").mkdir()
    docs = []
    for name in pkg["docs"]:
        member = "docs/" + Path(name).name
        shutil.copyfile(root / name, built / member)
        files[member] = built / member
        docs.append(member)
    copy_tree(evidence, built, files, "evidence/")
    require(any(n.startswith("evidence/") for n in files), "evidence directory is empty")
    sums = "".join(f"{sha(path)}  {name}\n" for name, path in sorted(files.items())).encode()
    (built / "SHA256SUMS").write_bytes(sums)
    files["SHA256SUMS"] = built / "SHA256SUMS"
    manifest = {"schema_version": 3, "kind": "release-package-manifest-v3", "candidate": candidate, "version": version,
                "source_snapshot_sha256": snapshot["snapshot_sha256"],
                "tool_asset": {"name": tool_name, **pins[tool_name]}, "docs": docs,
                "members": [{"path": n, "size": p.stat().st_size, "sha256": sha(p)} for n, p in sorted(files.items())]}
    manifest_bytes = common.json_bytes(manifest)
    (built / "MANIFEST.json").write_bytes(manifest_bytes)
    archive = built / archive_name(version)
    digest = common.write_tar_gz(archive, files, {"MANIFEST.json": manifest_bytes}, directories=[p.rstrip("/") for p in PREFIXES])
    common.size_ok(archive.stat().st_size)
    inventory, _ = common.tar_inventory(archive)
    require({n: r for n, r in inventory.items() if n != "MANIFEST.json"} ==
            {n: {"size": p.stat().st_size, "sha256": sha(p)} for n, p in files.items()}, "built archive differs from inputs")
    shutil.copyfile(tool, built / tool_name)
    require(source_snapshot.capture(root) == snapshot, "source changed during the build")
    result = {"schema_version": 3, "kind": "release-package-build-v3", "status": "built_not_signed_or_published",
              "candidate": candidate, "version": version, "source_snapshot_sha256": snapshot["snapshot_sha256"],
              "archive": {"path": "built/" + archive.name, "sha256": digest, "size": archive.stat().st_size},
              "manifest": {"path": "built/MANIFEST.json", "sha256": sha(built / "MANIFEST.json")},
              "tool_asset": {"path": "built/" + tool_name, "sha256": pins[tool_name]["sha256"]}, "members": len(files),
              "next": ["owner: ssh-keygen -Y sign -f <key> -n " + policy["signer"]["namespace"] + " " + str(archive),
                       "owner: git tag -s " + version + " " + candidate + " && git push origin " + version,
                       "owner: draft release for tag " + version + ", upload archive, .sig and " + tool_name + ", publish",
                       "then: release_package.py record --package-dir " + str(out) + " --release-id <id>"]}
    common.write(out / "build-result.json", result)
    return result


def record(args, root=ROOT):
    policy = common.load_policy(root)
    signer, pkg, pins = policy["signer"], policy["package"], policy["fixed_inputs"]
    directory = Path(args.package_dir).absolute()
    build_result = read(directory / "build-result.json")
    require(build_result.get("kind") == "release-package-build-v3", "not a v3 package build")
    require(not (directory / "report.json").exists(), "release record already exists")
    candidate, version = build_result["candidate"], build_result["version"]
    require(version == policy["version"], "built version is not the policy version")
    archive = common.regular(directory / build_result["archive"]["path"])
    require(sha(archive) == build_result["archive"]["sha256"], "built archive changed")
    signature = common.regular(Path(str(archive) + ".sig"))
    tool_name = pkg["tool_asset"]
    tool = common.regular(directory / build_result["tool_asset"]["path"])
    allowed = Path(root) / signer["allowed_signers"]
    common.verify_ssh_signature(allowed, signer["identity"], signer["namespace"], signature, archive, "release package")
    fetch = common.run_command(directory, "fetch-tag", ["git", "fetch", "origin", "tag", version, "--no-tags"], root)
    require(fetch["exit_code"] == 0, "tag fetch failed: " + version)
    tag = common.verify_tag(root, version, allowed, signer["identity"], candidate)
    release_id = args.release_id
    query = common.run_command(directory, "release-query",
                               ["gh", "api", "--hostname", "github.com", f"repos/{policy['repository']}/releases/{release_id}"], root)
    require(query["exit_code"] == 0, "release query failed")
    remote = read(directory / query["stdout"]["path"])
    require(remote.get("id") == release_id and remote.get("tag_name") == version and remote.get("draft") is False and
            remote.get("immutable") is True, "release is not the published immutable release for this tag")
    assets = {row["name"]: row for row in remote.get("assets", []) if type(row) is dict}
    local = {archive.name: archive, signature.name: signature, tool_name: tool}
    require(set(assets) == set(local), "release assets differ from the expected three")
    publication_assets, downloads = {}, {}
    downloaded = directory / "downloaded"
    downloaded.mkdir()
    for name, path in local.items():
        row = assets[name]
        require(row.get("state") == "uploaded" and row.get("size") == path.stat().st_size and
                row.get("digest") == "sha256:" + sha(path), "release asset bytes/state differ: " + name)
        publication_assets[name] = {"id": row["id"], "size": row["size"], "digest": row["digest"], "url": row["browser_download_url"]}
        target = downloaded / name
        got = common.run_command(directory, "download-" + name, ["curl", "--fail", "--location", "--output", str(target),
                                                                  row["browser_download_url"]], directory)
        require(got["exit_code"] == 0 and sha(target) == sha(path), "download differs: " + name)
        downloads[name] = {**got, "archive": common.ref(directory, target)}
    report = {"schema_version": 3, "kind": "release-evidence-v3", "status": "passed", "candidate": candidate, "version": version,
              "source_snapshot_sha256": build_result["source_snapshot_sha256"],
              "archive": common.ref(directory, archive), "signature": common.ref(directory, signature),
              "manifest": common.ref(directory, directory / build_result["manifest"]["path"]),
              "tool_asset": common.ref(directory, tool), "tag": tag,
              "publication": {"release_id": release_id, "tag": version, "url": remote["html_url"],
                              "published_at": remote["published_at"], "immutable": True, "assets": publication_assets,
                              "query": {k: query[k] for k in ("argv", "exit_code", "stdout", "stderr")}},
              "downloads": downloads, "boundaries": {"release_claimed": False, "week6_closed": False}}
    common.write(directory / "report.json", report)
    import audit_release
    return audit_release.check_release(directory / "report.json", candidate, root)


def authenticate(archive, signature, tool, candidate, root):
    policy = common.load_policy(root)
    signer, pkg, pins = policy["signer"], policy["package"], policy["fixed_inputs"]
    archive, signature, tool = common.regular(archive), common.regular(signature), common.regular(tool)
    common.size_ok(archive.stat().st_size)
    before = (sha(archive), sha(signature))
    common.verify_ssh_signature(Path(root) / signer["allowed_signers"], signer["identity"], signer["namespace"], signature, archive,
                                "release restoration")
    manifest = json.loads(common.archive_member_bytes(archive, "MANIFEST.json"))
    require(manifest["kind"] == "release-package-manifest-v3" and manifest["candidate"] == candidate and
            manifest["version"] == policy["version"], "restoration candidate/version differs")
    members = common.manifest_members(manifest["members"], "restoration")
    files, _ = common.tar_inventory(archive)
    require({n: r for n, r in files.items() if n != "MANIFEST.json"} == members, "primary inventory differs")
    tool_name = pkg["tool_asset"]
    require(manifest["tool_asset"] == {"name": tool_name, **pins[tool_name]} and tool.stat().st_size == pins[tool_name]["size"] and
            sha(tool) == pins[tool_name]["sha256"], "tool asset is not the signed binding")
    for member, name in INSTALL_MEMBERS.items():
        require(members.get(member, {}).get("sha256") == pins[name]["sha256"], "pinned install member differs: " + member)
    require(source_capsule.MEMBER in members, "source capsule missing")
    require((sha(archive), sha(signature)) == before, "signed inputs changed")
    return manifest, members, {**members, "MANIFEST.json": files["MANIFEST.json"]}


def restore(archive, signature, tool, candidate, out, mode="staging", root=ROOT):
    require(mode in ("staging", "canonical"), "unknown restoration mode")
    policy = common.load_policy(root)
    out = source_capsule.new_path(out)
    destination = source_capsule.new_path(policy["canonical_checkout"]) if mode == "canonical" else out / "checkout"
    require(not out.is_relative_to(destination), "restoration report overlaps checkout")
    manifest, members, archived = authenticate(archive, signature, tool, candidate, root)
    out.mkdir(parents=True)
    primary = out / "primary"
    common.extract_verified(archive, primary, archived, directories=[p.rstrip("/") for p in PREFIXES])
    capsule = primary / source_capsule.MEMBER
    source_result = source_capsule.restore(capsule, members[source_capsule.MEMBER]["sha256"], candidate, out / "source-restoration",
                                           destination)
    require(source_snapshot.capture(destination)["snapshot_sha256"] == manifest["source_snapshot_sha256"], "restored source differs")
    install_manifest = primary / "install/manifest.json"
    installations = fixed_inputs.load_manifest(install_manifest, policy["fixed_inputs"]["manifest.json"]["sha256"])
    require(installations["canonical_checkout"] == policy["canonical_checkout"], "fixed prefix differs")
    staged = out / "tool-staging"
    fixed_inputs.stage(tool, install_manifest, policy["fixed_inputs"]["manifest.json"]["sha256"], staged)
    roots = fixed_inputs.install_staged_roots(staged, destination, installations["entries"])
    shutil.rmtree(staged)
    stages = []
    env = source_capsule.environment()

    def command(label, argv):
        row = common.run_command(out, label, argv, destination, env=env)
        require(row["exit_code"] == 0, "restoration command failed: " + label)
        stages.append(row)
    decoder = destination / "artifacts/boundary-check/release-decoder-inputs"
    command("decoder-install", [sys.executable, "-O", destination / "scripts/decoder_rebuilt_inputs.py", "--install",
                                primary / "install/rebuilt-decoder-candidate.tar.gz", "--destination", decoder])
    command("decoder-verify", [sys.executable, "-O", destination / "scripts/decoder_rebuilt_inputs.py", "--verify", decoder])
    cmake = destination / "artifacts/boundary-check/release-cmake-inputs"
    command("cmake-stage", [sys.executable, "-O", destination / "scripts/fixed_inputs.py", "cmake-stage", "--archive",
                            primary / "install/cmake-downloads.tar.gz", "--manifest", primary / "install/cmake-downloads-manifest.json",
                            "--out", cmake])
    require(source_snapshot.capture(destination)["snapshot_sha256"] == manifest["source_snapshot_sha256"],
            "source changed during input restoration")
    result = {"schema_version": 2, "kind": "release-restoration-v2", "status": "inputs_restored", "candidate": candidate,
              "version": manifest["version"], "mode": mode, "checkout": str(destination),
              "source_snapshot_sha256": manifest["source_snapshot_sha256"], "primary_sha256": sha(archive),
              "signature_verified": True, "installation_roots": roots, "decoder_inputs": str(decoder), "cmake_inputs": str(cmake),
              "source_restoration": source_result["status"], "stages": stages,
              "operational_toolchain_claimed": False, "proofs_executed": False}
    common.write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    builder = sub.add_parser("build")
    builder.add_argument("--candidate", required=True)
    builder.add_argument("--inputs", required=True, type=Path, help="directory holding the five pinned input files")
    builder.add_argument("--evidence", required=True, type=Path, help="directory copied into evidence/")
    builder.add_argument("--out", required=True, type=Path)
    recorder = sub.add_parser("record")
    recorder.add_argument("--package-dir", required=True, type=Path)
    recorder.add_argument("--release-id", required=True, type=int)
    restorer = sub.add_parser("restore")
    restorer.add_argument("--archive", required=True, type=Path)
    restorer.add_argument("--signature", required=True, type=Path)
    restorer.add_argument("--tool-archive", required=True, type=Path)
    restorer.add_argument("--candidate", required=True)
    restorer.add_argument("--out", required=True, type=Path)
    restorer.add_argument("--mode", choices=("staging", "canonical"), default="staging")
    args = parser.parse_args()
    if args.command == "build":
        result = build(args)
    elif args.command == "record":
        result = record(args)
    else:
        result = restore(args.archive, args.signature, args.tool_archive, args.candidate, args.out, args.mode)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
