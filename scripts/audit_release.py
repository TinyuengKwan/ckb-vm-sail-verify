#!/usr/bin/env python3
"""Aggregate the six evidence slots of one release candidate.

Slots: runtime, lean, rocq, clean_room, release, third_party.  Each slot is one
report file; each validator reopens the files it names and recomputes what it
can.  Validators execute no recorded build or replay command; they may run
read-only remote queries (``gh api``, ``gh attestation verify``) and signature
checks (``ssh-keygen -Y verify``, ``git verify-tag``) against identities pinned
in docs/release/policy.json and the repository's allowed-signers files.

Exit 0: every slot verified, or third_party explicitly deferred.  Exit 2: a
slot is missing or incomplete.  Exit 1: a supplied report is invalid.  The
aggregator never publishes, signs, approves or reruns proofs.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_proof as proof
import public_claims
import release_common as common
import rocq_spike as rocq
import runtime_evidence
import source_capsule
import source_snapshot

ROOT = common.ROOT
require, same, sha, read = common.require, common.same, common.sha, common.read
SLOTS = ["runtime", "lean", "rocq", "clean_room", "release", "third_party"]
STEP_POLICY = "proof/lean/audit/step-policy.json"
VM_PROVIDER = "independent-ephemeral-vm"
VM_RECORD = "vm-provenance.json"
VM_RECORD_KIND = "ephemeral-vm-provenance-v2"
VM_RECORD_STATUS = "guest_completed_evidence_extracted_overlay_destroyed"
VM_SHARED_FILESYSTEM = ("-virtfs", "-fsdev", "virtio-9p", "virtiofs", "vhost-user-fs")
ROCQ_REJECTIONS = {"rust-model": "rust", "sail-model": "sail", "sail-repro": "sail"}
ROCQ_TRACKED_MODELS = {"rust/result_shadowing.v": "proof/rocq/spike/result_shadowing.v",
                       "sail/missing_e_div.v": "proof/rocq/spike/missing_e_div.v",
                       "sail/riscv_extras.v": "deps/sail-riscv/handwritten_support/riscv_extras.v"}


class Incomplete(RuntimeError):
    """Valid so far, but a required companion record does not exist yet."""


def current_snapshot(root):
    return source_snapshot.capture(Path(root))


# ---- runtime / lean / rocq ---------------------------------------------------

def check_runtime(path, candidate, root):
    return runtime_evidence.check(path)


def check_lean(path, candidate, root):
    path = Path(path)
    out, report = path.parent, read(path)
    policy_path = Path(root) / STEP_POLICY
    policy = read(policy_path)
    require(same(report["schema_version"], 1) and report["status"] == "passed" and report["assurance"] == "conditional" and
            report["coverage"] == "runtime-only" and report["release_audit"] is False, "Lean status/assurance")
    require(report["policy_sha256"] == sha(policy_path), "Lean report was produced under a different proof policy")
    require(same(report["theorem"], policy["theorem"]), "Lean theorem differs from policy")
    logs = {}
    for row in report["stages"]:
        require(row["status"] == "passed" and same(row["exit_code"], 0) and row["log"] == row["name"] + ".log",
                "Lean stage failed: " + str(row.get("name")))
        logs[row["name"]] = common.linked(out, row["log"], row["sha256"]).read_text()
    for name in ("sail-config", "generate-rust", "generate-sail", "kernel-step", "theorem-audit", "public-decoder"):
        require(name in logs, "Lean stage missing: " + name)
    audit = proof.parse_audit(logs["theorem-audit"])
    require(audit == read(common.member(out, "lean-audit.json")), "Lean audit record/log disagree")
    proof.check_audit(audit, policy)
    require(report["boundary_sha256"] == proof.boundary_hashes(audit), "Lean boundary hashes differ")
    public = report["public_decoder"]
    require(type(public) is dict and common.text(public["theorem"], "public theorem") and
            type(public["public_theorem_count"]) is int and public["clean_dependency_build"] is True, "public decoder record")
    return {"theorem": audit["theorem"], "axioms": len(audit["axioms"]), "sorry_free": True, "stages": len(report["stages"]),
            "public_theorem": public["theorem"], "public_theorems": public["public_theorem_count"],
            "assurance": "conditional", "coverage": "runtime-only"}


def check_rocq(path, candidate, root):
    path = Path(path)
    out, report = path.parent, read(path)
    require(same(report["schema_version"], 1) and report["status"] == "passed" and report["verdict"] == "NO-GO" and
            report["extra_proof_coverage"] is False and report["clean_room_claimed"] is False, "Rocq status/verdict")
    require(report["policy_sha256"] == sha(Path(root) / STEP_POLICY), "Rocq report was produced under a different proof policy")
    names = []
    for row in report["stages"]:
        name = row["name"]
        names.append(name)
        log = common.linked(out, row["log"], row["log_sha256"]).read_text()
        if name in ROCQ_REJECTIONS:
            require(row["status"] == "expected_rejection", "Rocq stage status: " + name)
            rocq.check_failure(ROCQ_REJECTIONS[name], row["exit_code"], log)
        else:
            require(row["status"] == "passed" and same(row["exit_code"], 0) and not rocq.INFRA_FAILURE.search(log),
                    "Rocq stage failed: " + name)
    require(set(ROCQ_REJECTIONS) | {"packages", "version", "rust-generate", "rust-repro", "sail-support", "sail-types"} <= set(names),
            "Rocq stage inventory")
    for name, digest in report["model_sha256"].items():
        common.linked(out, name, digest)
        if name in ROCQ_TRACKED_MODELS:
            require(digest == sha(Path(root) / ROCQ_TRACKED_MODELS[name]), "Rocq reproduction source differs: " + name)
    return {"verdict": "NO-GO", "stages": len(names), "rocq_version": report["rocq_version"].splitlines()[0],
            "extra_proof_coverage": False}


# ---- clean room -----------------------------------------------------------------

def check_vm_provenance(report_path):
    report_path = Path(report_path)
    directory, report = report_path.parent, read(report_path)
    provider = report["provider"]
    path = directory / VM_RECORD
    if not path.exists() and not path.is_symlink():
        raise Incomplete("independent ephemeral VM host provenance record absent")
    record = read(common.regular(path))
    common.fields(record, {"schema_version", "kind", "status", "provider", "hypervisor", "disks", "seed", "launch", "guest",
                           "report", "boundaries"}, "VM provenance")
    require(same(record["schema_version"], 2) and record["kind"] == VM_RECORD_KIND and record["status"] == VM_RECORD_STATUS,
            "VM provenance identity/status")
    require(record["provider"] == {k: provider[k] for k in ("kind", "environment_id", "image", "image_digest")},
            "VM provenance provider differs from the clean-room report")
    common.fields(record["hypervisor"], {"executable", "executable_sha256", "version", "accelerator"}, "VM hypervisor")
    require(record["hypervisor"]["accelerator"] == "kvm", "VM accelerator")
    disks = record["disks"]
    require("sha256:" + common.digest(disks["base_image_sha256"], "base image") == provider["image_digest"], "VM base image differs")
    require(disks["overlay"]["destroyed"] is True and disks["evidence"]["destroyed"] is True and
            disks["secrets"]["destroyed"] is True, "VM disks were not destroyed")
    argv = record["launch"]["argv"]
    require(type(argv) is list and argv and "accel=kvm" in " ".join(argv) and
            not any(flag in item for item in argv for flag in VM_SHARED_FILESYSTEM), "VM launch argv")
    require(same(record["launch"]["exit_code"], 0) and same(record["guest"]["controller_exit_code"], 0), "VM exit codes")
    common.reference(directory, record["launch"]["console_log"], "VM console log")
    require(record["report"] == {"path": report_path.name, "sha256": sha(report_path)},
            "VM provenance record is bound to a different clean-room report")
    b = record["boundaries"]
    require(b["operator_attested"] is True and b["platform_signed_identity"] is False and b["release_claimed"] is False and
            b["week6_closed"] is False, "VM provenance boundary")
    return {"record_sha256": sha(path), "environment_id": provider["environment_id"], "hypervisor": record["hypervisor"]["version"],
            "operator_attested": True, "platform_signed_identity": False}


def check_vm_report(path, candidate, root):
    """The clean-room report the guest wrote plus the host's provenance record."""
    path = Path(path)
    directory, report, policy = path.parent, read(path), common.load_policy(root)
    cfg = policy["clean_room"]
    common.fields(report, {"schema_version", "kind", "status", "candidate", "provider", "checkout", "tools", "source_snapshot",
                           "stages", "generated_roots", "slots", "boundaries"}, "clean-room report")
    require(same(report["schema_version"], 2) and report["kind"] == "clean-room-evidence-v2" and report["status"] == "passed" and
            report["candidate"] == candidate, "clean-room identity/status")
    provider = report["provider"]
    require(provider["kind"] in cfg["providers"] and provider["ephemeral"] is True and
            provider["original_workspace_mounted"] is False and provider["image_digest"] == "sha256:" + cfg["image"]["sha256"],
            "clean-room provider is not the pinned fresh image")
    snapshot = read(common.reference(directory, report["source_snapshot"], "clean-room source snapshot"))
    require(snapshot == current_snapshot(root), "clean-room source snapshot is not the current checkout")
    checkout = report["checkout"]
    require(checkout["repository"] == policy["repository"] and checkout["head"] == candidate ==
            snapshot["repositories"]["."]["head"] and checkout["overlay_applied"] is True and
            checkout["worktree_status"] == "" and checkout["submodules"] ==
            {name: snapshot["repositories"][name]["head"] for name in source_snapshot.REPOS[1:]}, "clean-room checkout")
    common.reference(directory, checkout["log"], "clean-room checkout log")
    require(set(report["tools"]) == set(cfg["tools"]), "clean-room tool inventory")
    for name, row in report["tools"].items():
        common.text(row["version"], "tool version " + name)
        common.digest(row["executable_sha256"], "tool hash " + name)
    common.check_stages(directory, report["stages"], cfg["stages"])
    require(set(report["generated_roots"]) == set(cfg["generated_roots"]) and
            all(common.digest(v, "generated root hash") for v in report["generated_roots"].values()), "generated roots")
    for name in ("runtime", "lean", "rocq", "public_claims"):
        common.reference(directory, report["slots"][name], "clean-room slot " + name)
    b = report["boundaries"]
    require(b["fresh_execution_claimed"] is True and b["release_claimed"] is False and b["week6_closed"] is False,
            "clean-room boundary")
    provenance = check_vm_provenance(path)
    return {"provider": provider["kind"], "environment_id": provider["environment_id"], "image": provider["image_digest"],
            "source_snapshot_sha256": snapshot["snapshot_sha256"], "stages": len(report["stages"]),
            "tools": {name: row["version"].splitlines()[0] for name, row in report["tools"].items()},
            "generated_roots": report["generated_roots"], "host_provenance": provenance}


def check_ci(path, candidate, root):
    """The externally collected CI record: attested bundle, two downloads, replay."""
    path = Path(path)
    directory, report, policy = path.parent, read(path), common.load_policy(root)
    cfg = policy["ci"]
    common.fields(report, {"schema_version", "kind", "status", "candidate", "repository", "run", "jobs", "artifact", "attestation",
                           "clean_room", "replay", "queries", "boundaries"}, "CI record")
    require(same(report["schema_version"], 2) and report["kind"] == "ci-evidence-v2" and report["status"] == "passed" and
            report["candidate"] == candidate and report["repository"] == policy["repository"], "CI identity/status")
    run = report["run"]
    require(run["head_sha"] == candidate and run["conclusion"] == "success" and run["event"] in ("push", "workflow_dispatch") and
            run["workflow_path"] == cfg["workflow"] and common.integer(run["run_id"], "run id"), "CI run")
    require(set(report["jobs"]) == set(cfg["jobs"]), "CI job inventory")
    for name, row in report["jobs"].items():
        require(row["conclusion"] == "success" and common.integer(row["job_id"], "job id"), "CI job failed: " + name)
        common.reference(directory, row["log"], "CI job log " + name)
    artifact = report["artifact"]
    require(artifact["name"] == cfg["artifact_name_prefix"] + candidate and artifact["expired"] is False, "CI artifact identity")
    first = common.reference(directory, artifact["first_download"], "first download")
    second = common.reference(directory, artifact["second_download"], "second download")
    require(first != second and sha(first) == sha(second) == common.digest(artifact["sha256"], "artifact hash"),
            "independent downloads differ")
    attestation = common.reference(directory, artifact["attestation"], "attestation bundle")
    verify = subprocess.run(["gh", "attestation", "verify", str(second), "--repo", policy["repository"], "--bundle", str(attestation),
                             "--signer-workflow", policy["repository"] + "/" + cfg["workflow"], "--source-digest", candidate,
                             "--deny-self-hosted-runners", "--format", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=120)
    require(verify.returncode == 0, "CI provenance attestation verification failed")
    require(same(report["attestation"]["exit_code"], 0), "recorded attestation verification failed")
    local = common.reference(root, report["clean_room"]["report"], "CI clean-room report")
    require(report["clean_room"]["bundle_sha256"] == artifact["sha256"] and
            report["clean_room"]["archived_report_sha256"] == sha(local), "CI bundle does not carry the local clean-room report")
    replay = report["replay"]
    require(replay["case"] == cfg["replay_case"] and same(replay["exit_code"], 0), "CI downloaded replay")
    for key in ("stdout", "stderr"):
        common.reference(directory, replay[key], "replay " + key)
    for name in ("run", "jobs", "artifacts"):
        require(same(report["queries"][name]["exit_code"], 0), "remote query failed: " + name)
    vm = check_vm_report(local, candidate, root)
    return {**vm, "ci_run_id": run["run_id"], "ci_url": run["html_url"], "bundle_sha256": artifact["sha256"],
            "attestation_verified": True, "external_downloads": 2, "replayed_case": replay["case"]}


def check_clean_room(path, candidate, root):
    kind = read(path).get("kind")
    if kind == "ci-evidence-v2":
        return check_ci(path, candidate, root)
    if kind == "clean-room-evidence-v2":
        check_vm_report(path, candidate, root)
        raise Incomplete("VM report validated; the externally collected CI record is absent")
    raise RuntimeError("unknown clean-room record kind: " + str(kind))


# ---- release / third party ------------------------------------------------------

def check_release(path, candidate, root):
    path = Path(path)
    directory, report, policy = path.parent, read(path), common.load_policy(root)
    signer, pkg = policy["signer"], policy["package"]
    common.fields(report, {"schema_version", "kind", "status", "candidate", "version", "source_snapshot_sha256", "archive",
                           "signature", "manifest", "tool_asset", "tag", "publication", "downloads", "boundaries"}, "release record")
    require(same(report["schema_version"], 3) and report["kind"] == "release-evidence-v3" and report["status"] == "passed" and
            report["candidate"] == candidate and report["version"] == policy["version"], "release identity/status")
    archive = common.reference(directory, report["archive"], "release archive")
    common.size_ok(archive.stat().st_size)
    files, directories = common.tar_inventory(archive)
    manifest_path = common.reference(directory, report["manifest"], "release manifest")
    require(files["MANIFEST.json"]["sha256"] == sha(manifest_path), "release manifest is not the archived manifest")
    manifest = read(manifest_path)
    common.fields(manifest, {"schema_version", "kind", "candidate", "version", "source_snapshot_sha256", "tool_asset", "docs",
                             "members"}, "release manifest")
    require(same(manifest["schema_version"], 3) and manifest["kind"] == "release-package-manifest-v3" and
            manifest["candidate"] == candidate and manifest["version"] == report["version"] and
            manifest["source_snapshot_sha256"] == report["source_snapshot_sha256"], "release manifest identity")
    members = common.manifest_members(manifest["members"], "release package")
    require({n: r for n, r in files.items() if n != "MANIFEST.json"} == members, "release member inventory differs")
    names = set(files) | directories
    for required in pkg["required_members"]:
        require(required in names or (required.endswith("/") and any(n.startswith(required) for n in names)),
                "missing required package member: " + required)
    require(manifest["docs"] == ["docs/" + Path(d).name for d in pkg["docs"]] and all(d in members for d in manifest["docs"]),
            "release docs inventory")
    tool_name = pkg["tool_asset"]
    expected_tool = policy["fixed_inputs"][tool_name]
    require(manifest["tool_asset"] == {"name": tool_name, **expected_tool}, "release manifest tool asset binding")
    tool = common.reference(directory, report["tool_asset"], "tool asset")
    require(tool.stat().st_size == expected_tool["size"] and sha(tool) == expected_tool["sha256"], "tool asset bytes differ")
    signature = common.reference(directory, report["signature"], "release signature")
    allowed = Path(root) / signer["allowed_signers"]
    common.verify_ssh_signature(allowed, signer["identity"], signer["namespace"], signature, archive, "release package")
    tag = common.verify_tag(root, report["version"], allowed, signer["identity"], candidate)
    require(report["tag"] == tag, "recorded tag verification differs")
    publication = report["publication"]
    live = common.query_json(["gh", "api", "--hostname", "github.com", f"repos/{policy['repository']}/releases/{publication['release_id']}"],
                             "release")
    require(live.get("id") == publication["release_id"] and live.get("tag_name") == report["version"] and
            live.get("draft") is False and live.get("immutable") is True and live.get("published_at") == publication["published_at"],
            "release is not the recorded immutable publication")
    assets = {row["name"]: row for row in live.get("assets", []) if type(row) is dict}
    expected_assets = {archive.name: archive, signature.name: signature, tool_name: tool}
    require(set(publication["assets"]) == set(expected_assets) == set(assets), "release asset inventory")
    for name, local in expected_assets.items():
        row = assets[name]
        require(row.get("state") == "uploaded" and row.get("size") == local.stat().st_size and
                row.get("digest") == "sha256:" + sha(local) and publication["assets"][name] ==
                {"id": row["id"], "size": row["size"], "digest": row["digest"], "url": row["browser_download_url"]},
                "release asset differs: " + name)
    for name, local in expected_assets.items():
        downloaded = common.reference(directory, report["downloads"][name]["archive"], "download " + name)
        require(downloaded != local and sha(downloaded) == sha(local) and same(report["downloads"][name]["exit_code"], 0),
                "download differs: " + name)
    with tempfile.TemporaryDirectory(prefix="release-source-") as temporary:
        capsule = Path(temporary) / "capsule.tar.gz"
        capsule.write_bytes(common.archive_member_bytes(archive, source_capsule.MEMBER, limit=512 * 1024 ** 2))
        snapshot, _ = source_capsule.inspect(capsule, candidate, current_snapshot(root))
    require(snapshot["snapshot_sha256"] == report["source_snapshot_sha256"], "release source capsule is not the current source")
    b = report["boundaries"]
    require(b["release_claimed"] is False and b["week6_closed"] is False, "release record boundary")
    return {"version": report["version"], "release_id": publication["release_id"], "url": publication["url"], "tag": tag,
            "archive_sha256": sha(archive), "source_snapshot_sha256": snapshot["snapshot_sha256"], "immutable": True,
            "assets": sorted(expected_assets), "signer": signer["identity"]}


def check_third_party(path, candidate, root):
    path = Path(path)
    directory, report, policy = path.parent, read(path), common.load_policy(root)
    cfg = policy["third_party"]
    common.fields(report, {"schema_version", "kind", "status", "candidate", "performer", "source_snapshot_sha256", "release_id",
                           "stages", "statement", "signature", "boundaries"}, "third-party report")
    require(same(report["schema_version"], 2) and report["kind"] == "third-party-reproduction-v2" and
            report["status"] == "passed" and report["candidate"] == candidate, "third-party identity/status")
    performer = report["performer"]
    common.fields(performer, {"identity", "name", "affiliation", "independent", "maintainer"}, "performer")
    require(performer["independent"] is True and performer["maintainer"] is False and
            performer["identity"] != policy["signer"]["identity"], "third party is not independent of the maintainer")
    require(report["source_snapshot_sha256"] == current_snapshot(root)["snapshot_sha256"], "third party reproduced another source")
    common.check_stages(directory, report["stages"], cfg["stages"])
    statement = common.reference(directory, report["statement"], "third-party statement")
    value = read(statement)
    require(value == {"schema_version": 2, "kind": "third-party-reproduction-statement-v2", "candidate": candidate,
                      "performer": performer, "source_snapshot_sha256": report["source_snapshot_sha256"],
                      "release_id": report["release_id"], "result": "passed"}, "third-party statement differs")
    signature = common.reference(directory, report["signature"], "third-party signature")
    common.verify_ssh_signature(Path(root) / cfg["allowed_signers"], performer["identity"], cfg["namespace"], signature,
                                statement, "third-party")
    return {"performer": performer, "stages": len(report["stages"]), "release_id": report["release_id"],
            "source_snapshot_sha256": report["source_snapshot_sha256"], "independent": True}


VALIDATORS = {"runtime": check_runtime, "lean": check_lean, "rocq": check_rocq, "clean_room": check_clean_room,
              "release": check_release, "third_party": check_third_party}


# ---- aggregation -----------------------------------------------------------------

def load_manifest(path):
    manifest = read(path)
    common.fields(manifest, {"schema_version", "kind", "candidate", "slots"}, "audit manifest")
    require(same(manifest["schema_version"], 2) and manifest["kind"] == "release-audit-manifest-v2" and
            common.GIT_OID.fullmatch(manifest["candidate"] or ""), "audit manifest identity")
    require(type(manifest["slots"]) is dict and set(manifest["slots"]) == set(SLOTS), "audit manifest slot inventory")
    return manifest


def aggregate(manifest, root=ROOT):
    root = Path(root).resolve()
    candidate = manifest["candidate"]
    slots = {}
    for name in SLOTS:
        row = manifest["slots"][name]
        if row is None:
            slots[name] = ({"status": "deferred", "reason": "third-party reproduction is performed by the recipient after delivery"}
                           if name == "third_party" else {"status": "missing", "reason": "report absent"})
            continue
        try:
            path = common.reference(root, row, name)
            summary = VALIDATORS[name](path, candidate, root)
            require(sha(path) == row["sha256"], "report changed during validation")
            slots[name] = {"status": "verified", "reference": row, "summary": summary}
        except Incomplete as error:
            slots[name] = {"status": "incomplete", "reference": row, "reason": str(error)}
        except Exception as error:
            slots[name] = {"status": "invalid", "reference": row, "reason": str(error), "error_type": type(error).__name__}
    claims = {"status": "passed"}
    try:
        claims = public_claims.check(root)
    except Exception as error:
        claims = {"status": "invalid", "reason": str(error)}
    snapshots = {name: row["summary"]["source_snapshot_sha256"] for name, row in slots.items()
                 if row["status"] == "verified" and "source_snapshot_sha256" in row["summary"]}
    current = current_snapshot(root)["snapshot_sha256"]
    invalid = [name for name, row in slots.items() if row["status"] == "invalid"] + (["public_claims"] if claims["status"] != "passed" else [])
    if snapshots and set(snapshots.values()) != {current}:
        invalid.append("source_snapshot")
    outstanding = [name for name, row in slots.items() if row["status"] in ("missing", "incomplete")]
    deferred = [name for name, row in slots.items() if row["status"] == "deferred"]
    status = "invalid" if invalid else "incomplete" if outstanding else "passed"
    code = {"invalid": 1, "incomplete": 2, "passed": 0}[status]
    return {"schema_version": 2, "kind": "release-audit-v2", "candidate": candidate, "status": status,
            "source_snapshot_sha256": current, "slots": slots, "invalid": invalid, "outstanding": outstanding,
            "deferred": deferred, "public_claims": claims,
            "boundaries": {"release_claimed": status == "passed", "week6_closed": status == "passed",
                           "third_party_reproduced": slots["third_party"]["status"] == "verified"}}, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="release-audit-manifest-v2 JSON")
    parser.add_argument("--candidate", help="full commit OID (when composing the manifest from --<slot> paths)")
    for name in SLOTS:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, help="report file for the slot")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", required=True, type=Path, help="new report directory")
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "started_at": common.stamp()}
    try:
        if args.manifest:
            manifest = load_manifest(args.manifest)
        else:
            require(common.GIT_OID.fullmatch(args.candidate or ""), "--candidate must be a full commit OID")
            manifest = {"schema_version": 2, "kind": "release-audit-manifest-v2", "candidate": args.candidate,
                        "slots": {name: (common.ref(root, getattr(args, name)) if getattr(args, name) else None) for name in SLOTS}}
        common.write(out / "manifest.json", manifest)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        report["project_head"] = head.stdout.decode().strip() if head.returncode == 0 else None
        report["candidate"] = manifest["candidate"]
        result, code = aggregate(manifest, root)
        report.update(result)
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="invalid", error=str(error), error_type=type(error).__name__,
                      boundaries={"release_claimed": False, "week6_closed": False, "third_party_reproduced": False})
        code = 1
    report["finished_at"] = common.stamp()
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(out / "report.json"),
                      "invalid": report.get("invalid", []), "outstanding": report.get("outstanding", []),
                      "deferred": report.get("deferred", [])}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
