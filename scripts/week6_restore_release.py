#!/usr/bin/env python3
"""Authenticate and restore the current profile-A two-asset delivery, offline.

Trust comes from this checkout's approved SSH signer, not from downloaded code
or a manifest-supplied key. Local authentication is distinct from publication:
week6_release_package.py record checks the same immutable GitHub release.
Staging is byte restoration only; fixed-prefix tools are NOT relocatable.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

import fixed_install_bundle as bundle
import release_external_evidence as external
import restore_fixed_inputs as fixed
import source_snapshot
import week6_release_assets as assets
import week6_source_capsule as capsule

ROOT = Path(__file__).resolve().parents[1]
require = assets.require


def validate_sources(files, candidate, snapshot):
    """Build-time semantic check, in addition to the ordinary member hashes."""
    members = {name: {"size": p.stat().st_size, "sha256": assets.sha(p)} for name, p in files.items()}
    assets.restoration_members(members)
    capsule.inspect(files[assets.SOURCE_CAPSULE], candidate, snapshot)


def check_archived_source(archive, candidate, snapshot):
    # Authenticate before calling this helper on a downloaded release.
    with tempfile.TemporaryDirectory(prefix="week6-source-check-") as name:
        target = Path(name) / "capsule.tar.gz"
        with tarfile.open(archive, "r:gz") as tar, target.open("xb") as output:
            member = tar.getmember(assets.SOURCE_CAPSULE)
            require(member.isfile(), "source capsule is not regular")
            with tar.extractfile(member) as incoming:
                while block := incoming.read(1024 * 1024):
                    output.write(block)
        return capsule.inspect(target, candidate, snapshot)[0]


def authenticate(archive, signature, tool, candidate, root=ROOT):
    cfg = external.load_policy(root)["release_package"]
    require(cfg["approved_version"] and cfg["approved_delivery_profile"] == "A" and
            cfg["approved_signer_identity"], "release identity not approved")
    archive, signature = assets.regular(archive), assets.regular(signature)
    assets.size_ok(archive.stat().st_size)
    before = {"archive": assets.sha(archive), "signature": assets.sha(signature)}
    external.verify_ssh_signature(assets.regular(Path(root) / cfg["allowed_signers_path"]),
        cfg["approved_signer_identity"], cfg["signature_namespace"], signature, archive, "release restoration")
    manifest = assets.primary_manifest(archive)
    assets.fields(manifest, {"schema_version", "kind", "candidate", "version", "delivery_profile",
        "source_snapshot_sha256", "coverage", "non_goals", "members", "external_assets"}, "primary manifest fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 2 and
            manifest["kind"] == "release-package-manifest-v2" and manifest["candidate"] == candidate and
            manifest["version"] == cfg["approved_version"] and manifest["delivery_profile"] == "A",
            "restoration candidate/version/profile differs")
    members = external.manifest_members(manifest["members"], "restoration")
    actual, directories = external.tar_inventory(archive)
    require({k: v for k, v in actual.items() if k != "MANIFEST.json"} == members, "primary inventory differs")
    for name in actual:
        assets.safe_name(name)
    for name in cfg["required_members"]:
        require(name in actual or name in directories or
                (name.endswith("/") and any(n.startswith(name) for n in actual)), "required primary member missing")
    require(manifest["coverage"] in members and manifest["non_goals"] in members, "coverage/non-goals missing")
    assets.bind_manifest(manifest, cfg, members)
    assets.restoration_members(members)
    tool = assets.local_asset(tool, cfg["external_assets"][assets.ASSET_NAME])
    snapshot = check_archived_source(archive, candidate, None)
    require(snapshot["snapshot_sha256"] == manifest["source_snapshot_sha256"], "source capsule identity differs")
    require(before == {"archive": assets.sha(archive), "signature": assets.sha(signature)}, "signed inputs changed")
    return cfg, manifest, actual, snapshot, before


def restore(archive, signature, tool, candidate, out, mode="staging", root=ROOT):
    require(mode in ("staging", "canonical"), "unknown restoration mode")
    out = capsule.new_path(out)
    destination = capsule.new_path(fixed.CANONICAL) if mode == "canonical" else out / "checkout"
    require(not out.is_relative_to(destination), "restoration report overlaps checkout")
    cfg, manifest, members, snapshot, before = authenticate(archive, signature, tool, candidate, root)
    out.mkdir(parents=True)
    primary = out / "primary"
    assets.extract_verified(archive, primary, members)
    require(assets.sha(archive) == before["archive"], "primary changed during extraction")
    source_result = capsule.restore(primary / assets.SOURCE_CAPSULE, members[assets.SOURCE_CAPSULE]["sha256"],
                                    candidate, out / "source-restoration", destination)
    require(source_snapshot.capture(destination) == snapshot, "restored source identity differs")
    install = cfg["external_assets"][assets.ASSET_NAME]["manifest"]
    installations = bundle.load_manifest(primary / install["path"], install["sha256"])
    require(installations["canonical_checkout"] == str(fixed.CANONICAL), "fixed prefix differs")
    fixed.installation_roots(installations["entries"])
    print("Restoring verified fixed installations (large archive).", flush=True)
    staged = out / "tool-staging"
    bundle.stage(tool, primary / install["path"], install["sha256"], staged)
    assets.local_asset(tool, cfg["external_assets"][assets.ASSET_NAME])
    roots = fixed.install_staged_roots(staged, destination, installations["entries"])
    for name, expected in installations["entries"].items():
        require(bundle.identity(destination / name) == expected, "installed tool member differs: " + name)
    stages = []
    def command(label, args):
        stdout, stderr = out / (label + ".stdout"), out / (label + ".stderr")
        with stdout.open("xb") as a, stderr.open("xb") as b:
            result = subprocess.run(list(map(str, args)), cwd=destination, env=capsule.environment(),
                stdin=subprocess.DEVNULL, stdout=a, stderr=b, timeout=1800)
        require(result.returncode == 0, "restoration command failed: " + label + "; inspect " + str(stderr))
        stages.append({"name": label, "argv": list(map(str, args)), "exit_code": result.returncode,
            "stdout": {"path": stdout.name, "sha256": assets.sha(stdout)},
            "stderr": {"path": stderr.name, "sha256": assets.sha(stderr)}})
    decoder = destination / "artifacts/boundary-check/week6-release-decoder-inputs"
    command("decoder-install", [sys.executable, "-O", destination / "scripts/decoder_rebuilt_inputs.py", "--install",
        primary / "install/rebuilt-decoder-candidate.tar.gz", "--destination", decoder])
    command("decoder-verify", [sys.executable, "-O", destination / "scripts/decoder_rebuilt_inputs.py", "--verify", decoder])
    cmake = destination / "artifacts/boundary-check/week6-release-cmake-inputs"
    command("cmake-stage", [sys.executable, "-O", destination / "scripts/stage_fixed_cmake_inputs.py",
        "--archive", primary / "install/cmake-downloads.tar.gz", "--manifest",
        primary / "install/cmake-downloads-manifest.json", "--out", cmake])
    require(source_snapshot.capture(destination) == snapshot, "source changed during input restoration")
    result = {"schema_version": 1, "kind": "week6-authenticated-release-restoration-v1", "status": "inputs_restored",
        "candidate": candidate, "version": manifest["version"], "mode": mode, "checkout": str(destination),
        "source_snapshot_sha256": snapshot["snapshot_sha256"], "primary_sha256": before["archive"],
        "tool_sha256": cfg["external_assets"][assets.ASSET_NAME]["sha256"], "signature_verified": True,
        "source_restoration": "source-restoration/report.json", "independent_git_objects": source_result["independent_git_objects"],
        "installation_roots": roots, "decoder_inputs": str(decoder), "cmake_inputs": str(cmake), "stages": stages,
        "publication_verified": False, "host_dependencies_installed": False, "operational_toolchain_claimed": False,
        "proofs_executed": False, "clean_room_closed": False, "third_party_reproduced": False,
        "os_sandboxed": False, "release_claimed": False, "week6_closed": False}
    capsule.write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--tool-archive", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--mode", choices=("staging", "canonical"), default="staging")
    args = parser.parse_args()
    print(json.dumps(restore(args.archive, args.signature, args.tool_archive, args.candidate, args.out, args.mode), indent=2))


if __name__ == "__main__":
    main()
