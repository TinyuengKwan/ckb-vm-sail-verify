#!/usr/bin/env python3
"""Export/install the pinned public-decoder inputs, not proof or release evidence.

Only explicit policy-bound files are copied. Sysroot links are materialized;
tool source history is exported as self-contained Git bundles, never .git/config
or local alternates. Installation needs an externally supplied archive SHA-256.
No existing output is overwritten and no proof policy is modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import sys

import check_proof as proof

ROOT = Path(__file__).resolve().parents[1]
SYSROOT_REPORT_SHA = "69ea312f2e816dd9575d508f4226dc01ba654d253a9b69afd4c7029f8728f9a8"
ITERATOR_SHA = "ec90aafd39b3a6154f98b73b12d99d7e8a567e2461d1c5baec113b20ac699ee4"
LOWER = {
    "LocalFields.lean": ("raw-fields-6zf2keby/models/LocalFields.lean", "3657ae25ac3b2c690e27a8e520663d64d7996bf7397eb1f182f905a4183f6868"),
    "FactoryScoped.lean": ("raw-add-0__trc1y/models/FactoryScoped.lean", "c5fe992b8979f1cffea74d733f06b7441311aadf2ff224306184e434a2dd3dbf"),
    "MiniComplete.lean": ("raw-add-0__trc1y/models/MiniComplete.lean", "d83df99cd1ec4617c9738e03405acde8158756251ab74dfe689d210ce12aad3d"),
}
MAX_BYTES = 2 * 1024 ** 3
UPSTREAM = {"aeneas": "https://github.com/AeneasVerif/aeneas.git",
            "charon": "https://github.com/AeneasVerif/charon.git"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_env():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return env


def git(cwd, *args):
    try:
        return subprocess.check_output(["git", "-c", "core.hooksPath=" + os.devnull, *map(str, args)],
                                       cwd=cwd, env=git_env(), stderr=subprocess.PIPE, timeout=300)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("git failed: " + error.stderr.decode(errors="replace").strip()) from error


def policies():
    policy = json.loads((ROOT / "proof/lean/decoder/public-policy.json").read_text())
    config = json.loads((ROOT / "proof/lean/decoder/toolchain/full-entry/extraction.json").read_text())
    require(policy["status"] == "adopted-rv64-add-public-v1", "public tools are not adopted")
    return policy, config


def catalogue(sysroot_report):
    """Approval comes from repository policy and the pinned sysroot report,
    never from arbitrary hashes supplied by the archive's own manifest."""
    policy, config = policies()
    require(sha(sysroot_report) == SYSROOT_REPORT_SHA, "sysroot qualification identity changed")
    files = {
        "bin/aeneas": config["aeneas_binary_sha256"],
        "bin/charon": config["charon_binary_sha256"],
        "bin/charon-driver": config["charon_driver_sha256"],
        "patches/aeneas.patch": config["aeneas_patch_sha256"],
        "patches/charon.patch": config["charon_patch_sha256"],
        "llbc/OuterClosedDepsV3.llbc": config["llbc_sha256"],
        "llbc/FnPtrFullMir.llbc": ITERATOR_SHA,
        "harness/lib.rs": config["outer_root_source_sha256"],
        "harness/Cargo.lock": config["outer_cargo_lock_sha256"],
        "qualification/sysroot.json": SYSROOT_REPORT_SHA,
    }
    for name, (_, digest) in LOWER.items():
        files["models/" + name] = digest
    for label, item in policy["qualification"].items():
        files["qualification/" + label + Path(item["path"]).suffix] = item["sha256"]
    libraries = json.loads(Path(sysroot_report).read_text())["sysroot_libraries"]
    for name, digest in libraries.items():
        require(Path(name).name == name and name.endswith((".rlib", ".rmeta")), "invalid sysroot library name")
        files["sysroot/lib/rustlib/x86_64-unknown-linux-gnu/lib/" + name] = digest
    return files, {"aeneas": config["aeneas_commit"], "charon": config["charon_commit"]}


def source_files():
    policy, config = policies()
    parent = ROOT / "artifacts/boundary-check"
    inputs = ROOT / policy["inputs"]
    full = parent / "decoder-sysroot-q8nI9W"
    sources = {
        "bin/aeneas": inputs / "candidate-v2-bin/aeneas",
        "bin/charon": parent / "charon-cfg-OYcaoK/candidate-bin/charon",
        "bin/charon-driver": parent / "charon-cfg-OYcaoK/candidate-bin/charon-driver",
        "patches/aeneas.patch": ROOT / "proof/lean/decoder/toolchain/branch-experimental/aeneas-branch-v2.patch",
        "patches/charon.patch": ROOT / "proof/lean/decoder/toolchain/cfg-experimental/charon-cleanup-suffix.patch",
        "llbc/OuterClosedDepsV3.llbc": inputs / "OuterClosedDepsV3.llbc",
        "llbc/FnPtrFullMir.llbc": full / "FnPtrFullMir.llbc",
        "harness/lib.rs": ROOT / "proof/lean/decoder/toolchain/full-mir/OuterRoot.rs",
        "harness/Cargo.lock": ROOT / "proof/lean/decoder/toolchain/public-harness/Cargo.lock",
        "qualification/sysroot.json": parent / "full-mir-check-ykre555d/report.json",
    }
    expected, commits = catalogue(sources["qualification/sysroot.json"])
    for name, (relative, _) in LOWER.items():
        sources["models/" + name] = parent / relative
    for label, item in policy["qualification"].items():
        sources["qualification/" + label + Path(item["path"]).suffix] = ROOT / item["path"]
    for name in expected:
        if name.startswith("sysroot/"):
            sources[name] = full / name
    repos = {"aeneas": inputs / "aeneas-src", "charon": parent / "charon-cfg-OYcaoK/charon-src"}
    return sources, expected, commits, repos


def regular_files(root):
    result = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "package contains a symlink: " + str(path))
        if path.is_file():
            result.add(path.relative_to(root).as_posix())
        else:
            require(path.is_dir(), "package contains a non-regular entry")
    return result


def check_files(root, expected, metadata):
    require(set(metadata) == set(expected), "manifest file set differs from approved catalogue")
    require(regular_files(root) == set(expected) | {"package.json"}, "unexpected or missing package file")
    for name, digest in expected.items():
        path = root / name
        mode = 0o755 if name.startswith("bin/") else 0o644
        require(sha(path) == digest == metadata[name]["sha256"], "input hash mismatch: " + name)
        require(path.stat().st_size == metadata[name]["bytes"], "input size mismatch: " + name)
        require(path.stat().st_mode & 0o777 == mode == metadata[name]["mode"], "input mode mismatch: " + name)


def verify_payload(root):
    root = Path(root).resolve()
    require(not (root / "package.json").is_symlink(), "linked package manifest")
    require((root / "package.json").stat().st_mode & 0o777 == 0o644, "package manifest mode must be 0644")
    manifest = json.loads((root / "package.json").read_text())
    require(manifest["schema_version"] == 1 and manifest["kind"] == "public-decoder-inputs", "unknown input package schema")
    require(manifest["proof_check_claimed"] is False and manifest["clean_room_claimed"] is False,
            "input package cannot claim proof or clean-room success")
    expected, commits = catalogue(root / "qualification/sysroot.json")
    policy, _ = policies()
    require(manifest["production_baseline"] == policy["production_baseline"] and
            manifest["tool_ids"] == policy["tool_ids"], "package tool or production identity mismatch")
    require(manifest["source_commits"] == commits, "tool source revisions changed")
    for name, commit in commits.items():
        filename = "sources/" + name + ".bundle"
        # Bundle bytes vary with Git pack encoding. The trusted identity is the
        # one approved commit; installation in an empty clone proves closure.
        expected[filename] = manifest["files"][filename]["sha256"]
        heads = git(root, "bundle", "list-heads", root / filename).decode().splitlines()
        require(heads == [commit + " HEAD"], "source bundle has unapproved refs: " + name)
    check_files(root, expected, manifest["files"])
    return manifest


def build(destination):
    destination = Path(destination).resolve()
    sources, expected, commits, repos = source_files()
    for name, path in sources.items():
        require(sha(path) == expected[name], "unapproved source input: " + name)
    destination.mkdir(parents=True, exist_ok=False)
    payload = destination / "payload"
    payload.mkdir()
    for name, source in sources.items():
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target, follow_symlinks=True)
        target.chmod(0o755 if name.startswith("bin/") else 0o644)
    for name, repo in repos.items():
        print("==> input bundle: source " + name, flush=True)
        require(git(repo, "rev-parse", "HEAD").decode().strip() == commits[name], "tool source commit mismatch")
        prefix = "src" if name == "aeneas" else "charon/src"
        require(hashlib.sha256(git(repo, "diff", "--", prefix)).hexdigest() == expected["patches/" + name + ".patch"],
                "tool source patch mismatch")
        target = payload / "sources" / (name + ".bundle")
        target.parent.mkdir(exist_ok=True)
        # Existing experimental checkouts can have incomplete historical objects
        # behind their alternates. Fetch in a NEW standalone repository instead
        # of repairing those checkouts or exporting a thin, host-dependent pack.
        export = destination / "source-export" / name
        export.mkdir(parents=True)
        git(export, "init", "--quiet")
        git(export, "fetch", "--no-tags", UPSTREAM[name], commits[name])
        git(export, "checkout", "--detach", commits[name])
        require(git(export, "rev-parse", "--is-shallow-repository").strip() == b"false",
                "source export must not be shallow")
        git(export, "fsck", "--full", "--strict")
        git(export, "bundle", "create", target, "HEAD")
        target.chmod(0o644)
    policy, _ = policies()
    manifest = {"schema_version": 1, "kind": "public-decoder-inputs", "source_commits": commits,
                "production_baseline": policy["production_baseline"], "tool_ids": policy["tool_ids"],
                "proof_check_claimed": False, "clean_room_claimed": False,
                "requirements": ["Linux x86_64", "pinned nightly-2026-08-18 including rustc-dev",
                                 "system GMP/zstd/libc", "main Sail/Aeneas/Lean/Rocq installations remain separate"],
                "files": {}}
    for name in sorted(regular_files(payload)):
        path = payload / name
        manifest["files"][name] = {"sha256": sha(path), "bytes": path.stat().st_size,
                                   "mode": path.stat().st_mode & 0o777}
    proof.write_json(payload / "package.json", manifest)
    (payload / "package.json").chmod(0o644)
    verify_payload(payload)
    archive = destination / "public-decoder-inputs.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=3) as tar:
        for name in sorted(regular_files(payload)):
            path = payload / name
            info = tar.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            with path.open("rb") as stream:
                tar.addfile(info, stream)
    report = {"status": "input_bundle_created", "archive": str(archive), "archive_sha256": sha(archive),
              "manifest_sha256": sha(payload / "package.json"), "files": len(manifest["files"]),
              "payload_bytes": sum(row["bytes"] for row in manifest["files"].values()),
              "proof_check_claimed": False, "clean_room_claimed": False}
    proof.write_json(destination / "build-report.json", report)
    return report


def check_members(members):
    require(len(members) <= 256, "too many package entries")
    names = set()
    total = 0
    for member in members:
        path = PurePosixPath(member.name)
        require(member.isfile() and not path.is_absolute() and ".." not in path.parts and
                path.as_posix() == member.name and member.name not in ("", ".") and
                "\\" not in member.name, "unsafe package entry: " + member.name)
        require(member.name not in names, "duplicate package entry: " + member.name)
        require(member.mode in (0o644, 0o755), "unsafe file mode")
        names.add(member.name)
        total += member.size
        require(0 <= member.size <= MAX_BYTES and total <= MAX_BYTES, "package exceeds size limit")
    require("package.json" in names, "package manifest missing")


def unpack(archive, digest, destination):
    require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "explicit SHA-256 required")
    require(sha(archive) == digest, "archive checksum mismatch")
    destination = Path(destination).resolve()
    # Validation occurs before output creation; extract only ordinary files and
    # use exclusive creation. No tar.extractall, symlinks, hardlinks or deletion.
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        check_members(members)
        destination.mkdir(parents=True, exist_ok=False)
        for member in members:
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode)
    return verify_payload(destination)


def install(archive, digest, destination):
    destination = Path(destination).resolve()
    require(not destination.exists(), "installation destination already exists")
    payload = destination / "payload"
    manifest = unpack(archive, digest, payload)
    for name, commit in manifest["source_commits"].items():
        print("==> input install: independent source " + name, flush=True)
        checkout = destination / "sources" / name
        checkout.parent.mkdir(exist_ok=True)
        git(destination, "clone", "--no-checkout", payload / "sources" / (name + ".bundle"), checkout)
        git(checkout, "checkout", "--detach", commit)
        require(not (checkout / ".git/objects/info/alternates").exists(), "source clone is not independent")
        git(checkout, "fsck", "--full", "--strict")
        git(checkout, "apply", "--check", payload / "patches" / (name + ".patch"))
        git(checkout, "apply", payload / "patches" / (name + ".patch"))
        prefix = "src" if name == "aeneas" else "charon/src"
        require(hashlib.sha256(git(checkout, "diff", "--", prefix)).hexdigest() ==
                manifest["files"]["patches/" + name + ".patch"]["sha256"], "installed patch mismatch")
    verify_payload(payload)
    report = {"status": "input_bundle_installed", "directory": str(destination), "archive_sha256": digest,
              "manifest_sha256": sha(payload / "package.json"), "independent_git_sources": True,
              "materialized_sysroot": True, "proof_check_claimed": False, "clean_room_claimed": False}
    proof.write_json(destination / "install-report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("build")
    create.add_argument("--output", required=True, type=Path)
    load = sub.add_parser("install")
    load.add_argument("--archive", required=True, type=Path)
    load.add_argument("--sha256", required=True)
    load.add_argument("--output", required=True, type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("payload", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        result = build(args.output)
    elif args.action == "install":
        result = install(args.archive, args.sha256, args.output)
    else:
        verify_payload(args.payload)
        result = {"status": "input_payload_verified", "proof_check_claimed": False}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print("ERROR: " + (str(error) or type(error).__name__), file=sys.stderr)
        sys.exit(1)
