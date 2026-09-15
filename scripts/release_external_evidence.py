"""Fail-closed Week6 validators for clean-room, CI, package and third-party records.

The validators execute no recorded build or replay command.  They may execute
``gh attestation verify`` for CI provenance, a validator-constructed read-only
``gh api`` query for the immutable release, and ``ssh-keygen -Y verify`` for
release/third-party signatures, always against repository-pinned identities or
allowed-signers files.  A report cannot introduce its own trust key.
"""

import json
import hashlib
from pathlib import Path
import re
import subprocess
import tarfile

import release_evidence as common
import source_snapshot as source

ROOT = common.ROOT
POLICY = Path("docs/release/external-acceptance-policy-v1.json")
FALSE_BOUNDARIES = {"release_claimed", "week6_closed"}
SHA256 = re.compile(r"[0-9a-f]{64}")
GIT_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
IMAGE = re.compile(r"sha256:[0-9a-f]{64}")


def require(value, message):
    common.require(value, message)


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " fields")


def text(value, label):
    require(type(value) is str and value.strip(), label)
    return value


def integer(value, label):
    require(type(value) is int and value > 0, label)
    return value


def digest(value, label):
    require(type(value) is str and SHA256.fullmatch(value), label)
    return value


def load_policy(root=None):
    root = ROOT if root is None else Path(root)
    value = common.read(root / POLICY)
    fields(value, {"schema_version", "kind", "repository", "clean_room", "ci_download",
                   "release_package", "third_party"}, "external policy")
    require(common.same(value["schema_version"], 1) and
            value["kind"] == "week6-external-acceptance-policy-v1", "external policy version")
    text(value["repository"], "external repository")
    fields(value["clean_room"], {"allowed_providers", "required_stages", "required_tools"},
           "clean-room policy")
    fields(value["ci_download"], {"provider", "workflow", "signer_workflow", "artifact_name_prefix", "required_jobs",
                                  "require_external_download", "require_provenance_attestation"},
           "CI policy")
    fields(value["release_package"], {"approved_version", "approved_delivery_profile",
                                      "approved_signer_identity", "allowed_signers_path", "signature_namespace",
                                      "required_members", "require_immutable_publication"},
           "package policy")
    fields(value["third_party"], {"allowed_signers_path", "require_signature_namespace",
                                  "required_stages"}, "third-party policy")
    for key in ["allowed_providers", "required_stages", "required_tools"]:
        rows = value["clean_room"][key]
        require(type(rows) is list and rows and len(rows) == len(set(rows)) and
                all(type(row) is str and row for row in rows), "invalid clean-room policy " + key)
    for key in ["required_jobs"]:
        rows = value["ci_download"][key]
        require(type(rows) is list and rows and len(rows) == len(set(rows)), "invalid CI jobs")
    require(value["ci_download"]["require_external_download"] is True and
            value["ci_download"]["require_provenance_attestation"] is True,
            "CI policy weakened")
    require(value["release_package"]["require_immutable_publication"] is True,
            "package publication policy weakened")
    return value


def reference(directory, row, label):
    fields(row, {"path", "sha256"}, label + " reference")
    return common.linked(directory, text(row["path"], label + " path"), digest(row["sha256"], label + " hash"))


def safe_archive_name(name):
    require(type(name) is str and name and not Path(name).is_absolute() and
            all(part not in ["", ".", ".."] for part in name.rstrip("/").split("/")),
            "unsafe archive member")
    return name


def tar_inventory(path):
    """Read a gzip tar without extracting; reject links, devices and duplicate names."""
    files, directories, seen = {}, set(), set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = safe_archive_name(member.name)
            require(name not in seen, "duplicate archive member")
            seen.add(name)
            if member.isdir():
                directories.add(name.rstrip("/") + "/")
                continue
            require(member.isfile(), "special/link archive member")
            stream = archive.extractfile(member)
            require(stream is not None, "unreadable archive member")
            size, hasher = 0, hashlib.sha256()
            while block := stream.read(1024 * 1024):
                size += len(block)
                hasher.update(block)
            require(size == member.size, "archive member size differs")
            # Release/CI archives may contain multi-gigabyte nested tool
            # packages. Validators need member size and digest only; retaining
            # every member body made otherwise valid Week6 evidence OOM-prone.
            files[name] = {"size": size, "sha256": hasher.hexdigest()}
    require(files, "empty evidence archive")
    return files, directories


def manifest_members(rows, label):
    require(type(rows) is list and rows, "empty " + label + " members")
    result = {}
    for row in rows:
        fields(row, {"path", "size", "sha256"}, label + " member")
        name = safe_archive_name(row["path"])
        require(name not in result and type(row["size"]) is int and row["size"] >= 0,
                "duplicate/invalid " + label + " member")
        result[name] = {"size": row["size"], "sha256": digest(row["sha256"], label + " member hash")}
    return result


def boundaries(value, true_fields=()):
    expected = FALSE_BOUNDARIES | set(true_fields)
    fields(value, expected, "external boundary")
    require(all(value[name] is False for name in FALSE_BOUNDARIES) and
            all(value[name] is True for name in true_fields), "external assurance boundary changed")


def verify_ssh_signature(allowed, identity, namespace, signature, payload, label):
    """Verify a file without copying a potentially multi-gigabyte archive into memory."""
    with Path(payload).open("rb") as stream:
        result = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", identity,
                                 "-n", namespace, "-s", str(signature)], stdin=stream,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(result.returncode == 0, label + " signature verification failed")


def query_json(argv, label):
    """Run one validator-constructed, read-only query and require JSON output."""
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(result.returncode == 0, label + " query failed")
    try:
        return json.loads(result.stdout)
    except Exception as error:
        raise RuntimeError(label + " query did not return JSON") from error


def release_remote_facts(value, report, archive, signature):
    require(type(value) is dict, "release remote payload")
    require(value.get("id") == report["publication"]["release_id"] and
            value.get("tag_name") == report["publication"]["tag"] and
            value.get("html_url") == report["publication"]["url"] and
            value.get("published_at") == report["publication"]["published_at"] and
            value.get("immutable") is True and value.get("draft") is False,
            "release remote metadata differs")
    assets = value.get("assets")
    require(type(assets) is list, "release remote asset payload")
    def published_asset(url, path, label):
        matches = [item for item in assets if type(item) is dict and
                   item.get("browser_download_url") == url]
        require(len(matches) == 1, label + " asset URL is absent or ambiguous")
        asset = matches[0]
        require(type(asset.get("id")) is int and asset["id"] > 0 and
                asset.get("state") == "uploaded" and asset.get("size") == path.stat().st_size and
                asset.get("digest") == "sha256:" + common.sha(path),
                label + " asset state/size/digest differs")
        return asset

    asset = published_asset(report["publication"]["asset_url"], archive, "release")
    signature_asset = published_asset(
        report["publication"]["signature_asset_url"], signature, "release signature")
    return {"release_id": value["id"], "tag": value["tag_name"], "url": value["html_url"],
            "published_at": value["published_at"], "immutable": value["immutable"],
            "asset_id": asset["id"], "asset_url": asset["browser_download_url"],
            "asset_size": asset["size"], "asset_digest": asset["digest"],
            "signature_asset_id": signature_asset["id"],
            "signature_asset_url": signature_asset["browser_download_url"],
            "signature_asset_size": signature_asset["size"],
            "signature_asset_digest": signature_asset["digest"]}


def stages(directory, rows, expected):
    require(type(rows) is list and [row.get("name") for row in rows] == expected,
            "external stage inventory")
    for row in rows:
        fields(row, {"name", "argv", "cwd", "exit_code", "stdout", "stderr"},
               "external stage")
        require(type(row["argv"]) is list and row["argv"] and
                all(type(item) is str and item for item in row["argv"]), "external stage argv")
        cwd = text(row["cwd"], "external stage cwd")
        require(not Path(cwd).is_absolute() and ".." not in Path(cwd).parts, "unsafe external stage cwd")
        require(common.same(row["exit_code"], 0), "external stage failed")
        reference(directory, row["stdout"], row["name"] + " stdout")
        reference(directory, row["stderr"], row["name"] + " stderr")


def current_snapshot(directory, row, root):
    path = reference(directory, row, "source snapshot")
    recorded = common.read(path)
    current = source.capture(root)
    require(recorded == current, "external evidence source snapshot is not current")
    return current


def result_counts(value):
    fields(value, {"runtime_cases", "instruction_families", "mutations_applied", "rust_tests",
                   "lean_stages", "lean_tests", "lean_public_theorems", "rocq_stages",
                   "rocq_verdict", "unexpected_mismatches", "worktree_reviewed",
                   "public_claims_reviewed"}, "external result")
    require(value["runtime_cases"] == 33 and
            value["instruction_families"] == {"ADD": 13, "ADDI": 10, "BEQ": 10} and
            value["mutations_applied"] == 194 and value["rust_tests"] == 78 and
            value["lean_stages"] == 28 and value["lean_tests"] == 287 and
            value["lean_public_theorems"] == 68 and value["rocq_stages"] == 11 and
            value["rocq_verdict"] == "NO-GO" and value["unexpected_mismatches"] == 0 and
            value["worktree_reviewed"] is True and value["public_claims_reviewed"] is True,
            "external result counts/boundaries changed")


VM_PROVIDER = "independent-ephemeral-vm"
VM_RECORD = "vm-provenance.json"
VM_RECORD_KIND = "week6-ephemeral-vm-provenance-v1"
VM_RECORD_STATUS = "guest_completed_evidence_extracted_overlay_destroyed"
VM_SHARED_FILESYSTEM = ("-virtfs", "-fsdev", "virtio-9p", "virtiofs", "vhost-user-fs")


class VmProvenanceAbsent(RuntimeError):
    """The clean-room report names an independent ephemeral VM but no host record exists yet."""


def check_vm_provenance(report_path):
    """Validate the operator-attested host record binding a VM run to its clean-room report.

    The record is produced by the host launcher after the guest has powered off and the
    evidence was extracted, so it cannot exist while the guest self-checks its own report.
    It is required by the aggregator, not by ``check_clean_room``.  It never upgrades the
    provider to platform-signed provenance; the aggregator reports it as operator-attested.
    """
    report_path = Path(report_path)
    directory = report_path.parent
    report = common.read(report_path)
    provider = report["provider"]
    require(provider["kind"] == VM_PROVIDER, "VM provenance applies only to independent ephemeral VM reports")
    path = directory / VM_RECORD
    if not path.exists() and not path.is_symlink():
        raise VmProvenanceAbsent("independent ephemeral VM host provenance record absent")
    require(path.is_file() and not path.is_symlink(), "VM provenance record is not a regular file")
    initial = common.sha(path)
    record = common.read(path)
    fields(record, {"schema_version", "kind", "status", "provider", "hypervisor", "disks", "seed",
                    "launch", "guest", "report", "boundaries"}, "VM provenance")
    require(common.same(record["schema_version"], 1) and record["kind"] == VM_RECORD_KIND and
            record["status"] == VM_RECORD_STATUS, "VM provenance identity/status")
    fields(record["provider"], {"kind", "environment_id", "image", "image_digest"}, "VM provenance provider")
    require(record["provider"] == {key: provider[key] for key in ["kind", "environment_id", "image",
                                                                    "image_digest"]},
            "VM provenance provider differs from the clean-room report")
    fields(record["hypervisor"], {"executable", "executable_sha256", "version", "accelerator"},
           "VM provenance hypervisor")
    text(record["hypervisor"]["executable"], "VM hypervisor executable")
    digest(record["hypervisor"]["executable_sha256"], "VM hypervisor hash")
    text(record["hypervisor"]["version"], "VM hypervisor version")
    require(record["hypervisor"]["accelerator"] == "kvm", "VM provenance accelerator")
    fields(record["disks"], {"base_image_sha256", "overlay", "evidence", "secrets"}, "VM provenance disks")
    require("sha256:" + digest(record["disks"]["base_image_sha256"], "VM base image hash") ==
            provider["image_digest"], "VM base image differs from the provider image digest")
    fields(record["disks"]["overlay"], {"created_at", "virtual_size_bytes", "destroyed"}, "VM overlay")
    fields(record["disks"]["evidence"], {"virtual_size_bytes", "archive_sha256", "destroyed"}, "VM evidence disk")
    fields(record["disks"]["secrets"], {"destroyed"}, "VM secrets disk")
    text(record["disks"]["overlay"]["created_at"], "VM overlay creation time")
    integer(record["disks"]["overlay"]["virtual_size_bytes"], "VM overlay size")
    integer(record["disks"]["evidence"]["virtual_size_bytes"], "VM evidence disk size")
    digest(record["disks"]["evidence"]["archive_sha256"], "VM evidence archive hash")
    require(record["disks"]["overlay"]["destroyed"] is True and record["disks"]["evidence"]["destroyed"] is True
            and record["disks"]["secrets"]["destroyed"] is True, "VM disks were not destroyed")
    fields(record["seed"], {"user_data_sha256", "meta_data_sha256"}, "VM seed")
    digest(record["seed"]["user_data_sha256"], "VM user-data hash")
    digest(record["seed"]["meta_data_sha256"], "VM meta-data hash")
    fields(record["launch"], {"argv", "started_at", "finished_at", "exit_code", "console_log"}, "VM launch")
    argv = record["launch"]["argv"]
    require(type(argv) is list and argv and all(type(item) is str and item for item in argv), "VM launch argv")
    require(not any(flag in item for item in argv for flag in VM_SHARED_FILESYSTEM),
            "VM launch shared a host filesystem")
    require("accel=kvm" in " ".join(argv), "VM launch did not use KVM")
    text(record["launch"]["started_at"], "VM start time")
    text(record["launch"]["finished_at"], "VM finish time")
    require(common.same(record["launch"]["exit_code"], 0), "VM hypervisor exit code")
    reference(directory, record["launch"]["console_log"], "VM console log")
    fields(record["guest"], {"controller_exit_code", "controller_stdout", "controller_stderr", "packages",
                             "extracted_members"}, "VM guest")
    require(common.same(record["guest"]["controller_exit_code"], 0), "VM guest controller exit code")
    reference(directory, record["guest"]["controller_stdout"], "VM guest controller stdout")
    reference(directory, record["guest"]["controller_stderr"], "VM guest controller stderr")
    require(type(record["guest"]["packages"]) is list and record["guest"]["packages"], "VM guest packages")
    integer(record["guest"]["extracted_members"], "VM extracted member count")
    fields(record["report"], {"path", "sha256"}, "VM provenance report")
    require(record["report"]["path"] == report_path.name and
            record["report"]["sha256"] == common.sha(report_path),
            "VM provenance record is bound to a different clean-room report")
    fields(record["boundaries"], {"release_claimed", "week6_closed", "clean_room_claimed",
                                  "platform_signed_identity", "operator_attested", "overlay_destroyed",
                                  "secrets_destroyed", "shared_filesystem_absent"}, "VM provenance boundary")
    require(all(record["boundaries"][name] is False for name in
                ["release_claimed", "week6_closed", "clean_room_claimed", "platform_signed_identity"]) and
            all(record["boundaries"][name] is True for name in
                ["operator_attested", "overlay_destroyed", "secrets_destroyed", "shared_filesystem_absent"]),
            "VM provenance assurance boundary changed")
    require(common.sha(path) == initial, "VM provenance record changed during validation")
    return {"record_sha256": initial, "environment_id": record["provider"]["environment_id"],
            "image_digest": record["provider"]["image_digest"], "operator_attested": True,
            "platform_signed_identity": False, "release_claimed": False, "week6_closed": False}


def check_clean_room(path, candidate, root=None):
    root = ROOT if root is None else Path(root)
    path, directory = Path(path), Path(path).parent
    initial, report, policy = common.sha(path), common.read(path), load_policy(root)
    fields(report, {"schema_version", "kind", "status", "candidate", "provider", "checkout", "tools",
                    "source_snapshot", "stages", "result", "boundaries"}, "clean-room report")
    require(common.same(report["schema_version"], 1) and report["kind"] == "clean-room-evidence-v1" and
            report["status"] == "passed" and report["candidate"] == candidate, "clean-room identity/status")
    fields(report["provider"], {"kind", "environment_id", "image", "image_digest", "created_at",
                                "ephemeral", "original_workspace_mounted"}, "clean-room provider")
    require(report["provider"]["kind"] in policy["clean_room"]["allowed_providers"] and
            report["provider"]["ephemeral"] is True and
            report["provider"]["original_workspace_mounted"] is False and
            IMAGE.fullmatch(report["provider"]["image_digest"]), "clean-room provider is not fresh/allowed")
    for key in ["environment_id", "image", "created_at"]:
        text(report["provider"][key], "clean-room provider " + key)
    snapshot = current_snapshot(directory, report["source_snapshot"], root)
    fields(report["checkout"], {"repository", "head", "recursive_submodules", "submodules",
                                "overlay_applied", "worktree_status", "log"}, "clean-room checkout")
    require(report["checkout"]["repository"] == policy["repository"] and
            report["checkout"]["head"] == snapshot["repositories"]["."]["head"] and
            report["checkout"]["recursive_submodules"] is True and
            report["checkout"]["overlay_applied"] is True and
            report["checkout"]["submodules"] == {
                name: snapshot["repositories"][name]["head"] for name in source.REPOS[1:]},
            "clean-room recursive checkout differs")
    require(type(report["checkout"]["worktree_status"]) is str, "clean-room worktree status")
    reference(directory, report["checkout"]["log"], "clean-room checkout log")
    required_tools = policy["clean_room"]["required_tools"]
    require(type(report["tools"]) is dict and set(report["tools"]) == set(required_tools),
            "clean-room tool inventory")
    for name, row in report["tools"].items():
        fields(row, {"version", "executable_sha256", "install_log"}, "clean-room tool " + name)
        text(row["version"], "clean-room tool version")
        digest(row["executable_sha256"], "clean-room executable hash")
        reference(directory, row["install_log"], "clean-room install log")
    stages(directory, report["stages"], policy["clean_room"]["required_stages"])
    result_counts(report["result"])
    boundaries(report["boundaries"], {"fresh_execution_claimed", "clean_room_verified"})
    require(common.sha(path) == initial, "clean-room report changed during validation")
    return {"scope": "fresh_recursive_checkout_pinned_install_regeneration_and_full_execution",
            "provider": report["provider"]["kind"], "source_snapshot_sha256": snapshot["snapshot_sha256"],
            "stages": len(report["stages"]), "fresh_execution_claimed": True,
            "clean_room_verified": True, "release_claimed": False, "week6_closed": False}


def check_ci_download(path, candidate, root=None):
    root = ROOT if root is None else Path(root)
    path, directory = Path(path), Path(path).parent
    initial, report, policy = common.sha(path), common.read(path), load_policy(root)
    cfg = policy["ci_download"]
    fields(report, {"schema_version", "kind", "status", "candidate", "provider", "workflow",
                    "source_snapshot", "clean_room", "jobs", "artifact", "external_download", "replay",
                    "remote_query", "jobs_query", "boundaries"},
           "CI download report")
    require(common.same(report["schema_version"], 1) and report["kind"] == "ci-download-evidence-v1" and
            report["status"] == "passed" and report["candidate"] == candidate, "CI identity/status")
    fields(report["provider"], {"kind", "repository", "run_id", "run_attempt", "event", "head_sha",
                                "conclusion", "html_url"}, "CI provider")
    require(report["provider"]["kind"] == cfg["provider"] and
            report["provider"]["repository"] == policy["repository"] and
            report["provider"]["conclusion"] == "success" and
            report["provider"]["event"] in ["push", "workflow_dispatch"], "CI provider/result")
    integer(report["provider"]["run_id"], "CI run id")
    integer(report["provider"]["run_attempt"], "CI run attempt")
    require(type(report["provider"]["head_sha"]) is str and
            GIT_OID.fullmatch(report["provider"]["head_sha"]), "CI head commit identity")
    text(report["provider"]["html_url"], "CI URL")
    snapshot = current_snapshot(directory, report["source_snapshot"], root)
    require(report["provider"]["head_sha"] == snapshot["repositories"]["."]["head"],
            "CI head does not match current source base commit")
    clean_room = reference(directory, report["clean_room"], "CI clean-room report")
    fields(report["workflow"], {"path", "sha256"}, "CI workflow")
    require(report["workflow"]["path"] == cfg["workflow"] and
            report["workflow"]["sha256"] == common.sha(root / cfg["workflow"]), "CI workflow differs")
    require(type(report["jobs"]) is dict and set(report["jobs"]) == set(cfg["required_jobs"]),
            "CI job inventory")
    for name, row in report["jobs"].items():
        fields(row, {"job_id", "conclusion", "log"}, "CI job")
        integer(row["job_id"], "CI job id")
        require(row["conclusion"] == "success", "CI job did not succeed")
        reference(directory, row["log"], "CI job log " + name)
    fields(report["artifact"], {"name", "artifact_id", "format", "sha256", "upload_archive",
                                "download_archive", "manifest", "attestation", "expired"}, "CI artifact")
    require(report["artifact"]["name"].startswith(cfg["artifact_name_prefix"]) and
            report["artifact"]["format"] == "tar.gz" and report["artifact"]["expired"] is False,
            "CI artifact identity/format/expiry")
    integer(report["artifact"]["artifact_id"], "CI artifact id")
    expected = digest(report["artifact"]["sha256"], "CI artifact hash")
    uploaded = reference(directory, report["artifact"]["upload_archive"], "CI uploaded archive")
    downloaded = reference(directory, report["artifact"]["download_archive"], "CI downloaded archive")
    require(uploaded != downloaded and common.sha(uploaded) == common.sha(downloaded) == expected,
            "CI downloaded bytes differ from upload")
    files, _ = tar_inventory(downloaded)
    manifest_path = reference(directory, report["artifact"]["manifest"], "CI artifact manifest")
    require("MANIFEST.json" in files and common.sha(manifest_path) == files["MANIFEST.json"]["sha256"],
            "CI artifact manifest is not the archived manifest")
    artifact_manifest = common.read(manifest_path)
    fields(artifact_manifest, {"schema_version", "kind", "candidate", "source_snapshot_sha256",
                               "clean_room_report", "replay_case", "members"}, "CI artifact manifest")
    require(common.same(artifact_manifest["schema_version"], 1) and
            artifact_manifest["kind"] == "ci-evidence-archive-manifest-v1" and
            artifact_manifest["candidate"] == candidate and
            artifact_manifest["source_snapshot_sha256"] == snapshot["snapshot_sha256"],
            "CI artifact manifest identity")
    members = manifest_members(artifact_manifest["members"], "CI artifact")
    actual = {name: {"size": row["size"], "sha256": row["sha256"]}
              for name, row in files.items() if name != "MANIFEST.json"}
    require(actual == members, "CI artifact member inventory differs")
    clean_name = safe_archive_name(artifact_manifest["clean_room_report"])
    replay_name = safe_archive_name(artifact_manifest["replay_case"])
    require(clean_name in members and replay_name in members and
            report["clean_room"]["path"] == "downloaded/" + clean_name and
            report["clean_room"]["sha256"] == members[clean_name]["sha256"],
            "CI archive does not contain the linked clean-room report")
    archived_provider = common.read(clean_room).get("provider")
    if type(archived_provider) is dict and archived_provider.get("kind") == VM_PROVIDER:
        record_name = safe_archive_name(clean_name.rsplit("/", 1)[0] + "/" + VM_RECORD)
        require(record_name in members and
                common.sha(common.member(directory, "downloaded/" + record_name)) == members[record_name]["sha256"],
                "CI archive lacks the independent ephemeral VM provenance record")
        check_vm_provenance(clean_room)
    attestation = reference(directory, report["artifact"]["attestation"], "CI attestation bundle")
    verified = subprocess.run([
        "gh", "attestation", "verify", str(downloaded), "--repo", policy["repository"],
        "--bundle", str(attestation), "--signer-workflow", cfg["signer_workflow"],
        "--source-digest", report["provider"]["head_sha"], "--deny-self-hosted-runners", "--format", "json",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(verified.returncode == 0, "CI provenance attestation verification failed")
    try:
        verified_result = json.loads(verified.stdout)
    except Exception as error:
        raise RuntimeError("CI attestation verifier did not return JSON") from error
    require(type(verified_result) is list and verified_result, "CI attestation verifier returned no result")
    fields(report["external_download"], {"argv", "exit_code", "stdout", "stderr", "destination_initially_absent"},
           "external download")
    require(report["external_download"]["destination_initially_absent"] is True,
            "CI external download reused destination")
    require(report["external_download"]["argv"] == [
        "gh", "run", "download", str(report["provider"]["run_id"]), "--repo", policy["repository"],
        "--name", report["artifact"]["name"], "--dir", "downloaded",
    ], "CI external download command differs")
    stages(directory, [{"name": "external-download", "cwd": ".",
                        "argv": report["external_download"]["argv"],
                        "exit_code": report["external_download"]["exit_code"],
                        "stdout": report["external_download"]["stdout"],
                        "stderr": report["external_download"]["stderr"]}], ["external-download"])
    fields(report["replay"], {"case", "source", "argv", "exit_code", "stdout", "stderr"}, "CI replay")
    require(report["replay"]["case"] == "add-signed-overflow" and
            report["replay"]["source"] == "downloaded/" + replay_name and
            common.same(report["replay"]["exit_code"], 0), "CI downloaded replay differs")
    replay_source = common.member(directory, report["replay"]["source"])
    require(common.sha(replay_source) == members[replay_name]["sha256"], "CI replay file differs from archive")
    require(type(report["replay"]["argv"]) is list and report["replay"]["argv"], "CI replay argv")
    reference(directory, report["replay"]["stdout"], "CI replay stdout")
    reference(directory, report["replay"]["stderr"], "CI replay stderr")
    fields(report["remote_query"], {"argv", "exit_code", "stdout", "stderr"}, "CI remote query")
    require(common.same(report["remote_query"]["exit_code"], 0) and
            report["remote_query"]["argv"] == ["gh", "api",
                f"repos/{policy['repository']}/actions/runs/{report['provider']['run_id']}"],
            "CI remote state was not queried")
    remote_path = reference(directory, report["remote_query"]["stdout"], "CI remote query stdout")
    reference(directory, report["remote_query"]["stderr"], "CI remote query stderr")
    remote = common.read(remote_path)
    for key, expected_remote in {
        "id": report["provider"]["run_id"], "run_attempt": report["provider"]["run_attempt"],
        "event": report["provider"]["event"], "head_sha": report["provider"]["head_sha"],
        "conclusion": "success", "path": cfg["workflow"],
    }.items():
        require(remote.get(key) == expected_remote, "CI remote run metadata differs: " + key)
    fields(report["jobs_query"], {"argv", "exit_code", "stdout", "stderr"}, "CI jobs query")
    require(common.same(report["jobs_query"]["exit_code"], 0) and
            report["jobs_query"]["argv"] == ["gh", "api",
                f"repos/{policy['repository']}/actions/runs/{report['provider']['run_id']}/jobs"],
            "CI remote jobs were not queried")
    jobs_path = reference(directory, report["jobs_query"]["stdout"], "CI jobs query stdout")
    reference(directory, report["jobs_query"]["stderr"], "CI jobs query stderr")
    remote_jobs = common.read(jobs_path)
    require(type(remote_jobs.get("jobs")) is list, "CI remote jobs payload")
    observed_jobs = {row.get("name"): {"job_id": row.get("id"), "conclusion": row.get("conclusion")}
                     for row in remote_jobs["jobs"]}
    require(observed_jobs == {name: {"job_id": row["job_id"], "conclusion": row["conclusion"]}
                              for name, row in report["jobs"].items()}, "CI remote job metadata differs")
    boundaries(report["boundaries"], {"remote_state_queried", "ci_download_verified"})
    require(common.sha(path) == initial, "CI report changed during validation")
    return {"scope": "successful_current_CI_and_external_artifact_download_replay",
            "run_id": report["provider"]["run_id"], "artifact_sha256": expected,
            "source_snapshot_sha256": snapshot["snapshot_sha256"],
            "clean_room_report_sha256": common.sha(clean_room),
            "jobs": len(report["jobs"]), "remote_state_queried": True,
            "ci_download_verified": True, "release_claimed": False, "week6_closed": False}


def check_release_package(path, candidate, root=None):
    root = ROOT if root is None else Path(root)
    path, directory = Path(path), Path(path).parent
    initial, report, policy = common.sha(path), common.read(path), load_policy(root)
    cfg = policy["release_package"]
    require(cfg["approved_version"] is not None and cfg["approved_delivery_profile"] is not None and
            cfg["approved_signer_identity"] is not None,
            "release version/delivery profile/signer not approved in policy")
    fields(report, {"schema_version", "kind", "status", "candidate", "version", "delivery_profile",
                    "source_snapshot", "archive_format", "archive", "manifest", "coverage", "non_goals", "publication",
                    "download", "signing_identity", "signature", "boundaries"}, "release package report")
    require(common.same(report["schema_version"], 1) and report["kind"] == "release-package-evidence-v1" and
            report["status"] == "passed" and report["candidate"] == candidate and
            report["version"] == cfg["approved_version"] and
            report["delivery_profile"] == cfg["approved_delivery_profile"] and
            report["archive_format"] == "tar.gz", "package identity/status/format")
    snapshot = current_snapshot(directory, report["source_snapshot"], root)
    archive = reference(directory, report["archive"], "built release archive")
    archive_files, archive_directories = tar_inventory(archive)
    manifest_path = reference(directory, report["manifest"], "release package manifest")
    require("MANIFEST.json" in archive_files and
            archive_files["MANIFEST.json"]["sha256"] == common.sha(manifest_path),
            "release package manifest is not the archived manifest")
    package_manifest = common.read(manifest_path)
    fields(package_manifest, {"schema_version", "kind", "candidate", "version", "delivery_profile",
                              "source_snapshot_sha256", "coverage", "non_goals", "members"},
           "release package manifest")
    require(common.same(package_manifest["schema_version"], 1) and
            package_manifest["kind"] == "release-package-manifest-v1" and
            package_manifest["candidate"] == candidate and package_manifest["version"] == report["version"] and
            package_manifest["delivery_profile"] == report["delivery_profile"] and
            package_manifest["source_snapshot_sha256"] == snapshot["snapshot_sha256"],
            "release package manifest identity")
    members = manifest_members(package_manifest["members"], "release package")
    actual = {name: {"size": row["size"], "sha256": row["sha256"]}
              for name, row in archive_files.items() if name != "MANIFEST.json"}
    require(actual == members, "release package member inventory differs")
    names = set(archive_files) | archive_directories
    for required in cfg["required_members"]:
        require(required in names or (required.endswith("/") and any(name.startswith(required) for name in names)),
                "missing required package member: " + required)
    coverage_name = safe_archive_name(package_manifest["coverage"])
    non_goals_name = safe_archive_name(package_manifest["non_goals"])
    coverage = reference(directory, report["coverage"], "release coverage")
    non_goals = reference(directory, report["non_goals"], "release non-goals")
    require(coverage_name in members and non_goals_name in members and
            report["coverage"] == {"path": "built/" + coverage_name,
                                    "sha256": members[coverage_name]["sha256"]} and
            report["non_goals"] == {"path": "built/" + non_goals_name,
                                     "sha256": members[non_goals_name]["sha256"]} and
            common.sha(coverage) == members[coverage_name]["sha256"] and
            common.sha(non_goals) == members[non_goals_name]["sha256"],
            "release coverage/non-goals are not archived members")
    signature = reference(directory, report["signature"], "release package signature")
    fields(report["publication"], {"provider", "repository", "release_id", "tag", "url", "asset_url",
                                   "signature_asset_url", "published_at", "immutable", "remote_query"},
           "release publication")
    require(report["publication"]["provider"] == "github-releases" and
            report["publication"]["repository"] == policy["repository"] and
            report["publication"]["tag"] == report["version"] and
            report["publication"]["immutable"] is True, "release publication identity/mutability")
    integer(report["publication"]["release_id"], "release id")
    text(report["publication"]["url"], "release URL")
    text(report["publication"]["asset_url"], "release asset URL")
    text(report["publication"]["signature_asset_url"], "release signature asset URL")
    require(report["publication"]["signature_asset_url"] != report["publication"]["asset_url"],
            "release signature asset is not distinct")
    text(report["publication"]["published_at"], "release publish time")
    fields(report["publication"]["remote_query"], {"argv", "exit_code", "stdout", "stderr"},
           "release remote query")
    query_argv = ["gh", "api", "--hostname", "github.com",
                  f"repos/{policy['repository']}/releases/{report['publication']['release_id']}"]
    require(common.same(report["publication"]["remote_query"]["exit_code"], 0) and
            report["publication"]["remote_query"]["argv"] == query_argv,
            "release remote state was not queried")
    remote_path = reference(directory, report["publication"]["remote_query"]["stdout"],
                            "release remote query stdout")
    reference(directory, report["publication"]["remote_query"]["stderr"], "release remote query stderr")
    recorded_remote = release_remote_facts(common.read(remote_path), report, archive, signature)
    live_remote = release_remote_facts(query_json(query_argv, "release remote"), report, archive, signature)
    require(recorded_remote == live_remote, "release remote state changed after recording")
    fields(report["download"], {"url", "archive", "destination_initially_absent", "argv",
                                "exit_code", "stdout", "stderr"}, "release download")
    require(report["download"]["url"] == report["publication"]["asset_url"] and
            report["download"]["destination_initially_absent"] is True, "release download source/destination")
    require(common.same(report["download"]["exit_code"], 0) and report["download"]["argv"] == [
        "curl", "--fail", "--location", "--output", report["download"]["archive"]["path"],
        report["download"]["url"]], "release download command differs")
    reference(directory, report["download"]["stdout"], "release download stdout")
    reference(directory, report["download"]["stderr"], "release download stderr")
    downloaded = reference(directory, report["download"]["archive"], "downloaded release archive")
    require(downloaded != archive and common.sha(downloaded) == common.sha(archive),
            "published package download differs")
    require(report["signing_identity"] == cfg["approved_signer_identity"], "package signer differs from policy")
    allowed = root / cfg["allowed_signers_path"]
    require(allowed.is_file() and not allowed.is_symlink(), "release allowed signers missing/unsafe")
    allowed_text = allowed.read_text()
    require(any(line.split(maxsplit=1)[0] == report["signing_identity"] for line in allowed_text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")), "release signer is not approved")
    verify_ssh_signature(allowed, report["signing_identity"], cfg["signature_namespace"],
                         signature, archive, "release package")
    boundaries(report["boundaries"], {"release_package_built", "publication_verified",
                                      "download_verified", "remote_state_queried"})
    require(common.sha(path) == initial, "release package report changed during validation")
    return {"scope": "approved_versioned_package_with_immutable_publication_and_download",
            "version": report["version"], "delivery_profile": report["delivery_profile"],
            "archive_sha256": common.sha(archive), "source_snapshot_sha256": snapshot["snapshot_sha256"],
            "release_package_built": True, "publication_verified": True, "download_verified": True,
            "remote_state_queried": True, "release_claimed": False, "week6_closed": False}


def check_third_party(path, candidate, root=None):
    root = ROOT if root is None else Path(root)
    path, directory = Path(path), Path(path).parent
    initial, report, policy = common.sha(path), common.read(path), load_policy(root)
    cfg = policy["third_party"]
    fields(report, {"schema_version", "kind", "status", "candidate", "performer", "source_snapshot",
                    "release_package", "stages", "result", "statement", "signature", "boundaries"},
           "third-party report")
    require(common.same(report["schema_version"], 1) and report["kind"] == "third-party-reproduction-v1" and
            report["status"] == "passed" and report["candidate"] == candidate, "third-party identity/status")
    fields(report["performer"], {"identity", "name", "affiliation", "independent", "maintainer",
                                 "assistant"}, "third-party performer")
    identity = text(report["performer"]["identity"], "third-party signer identity")
    require(report["performer"]["independent"] is True and report["performer"]["maintainer"] is False and
            report["performer"]["assistant"] is False and report["performer"]["name"] != "Codex",
            "third-party performer is not independent")
    text(report["performer"]["name"], "third-party performer name")
    text(report["performer"]["affiliation"], "third-party affiliation")
    snapshot = current_snapshot(directory, report["source_snapshot"], root)
    reference(directory, report["release_package"], "third-party release package report")
    stages(directory, report["stages"], cfg["required_stages"])
    result_counts(report["result"])
    statement = reference(directory, report["statement"], "third-party statement")
    signature = reference(directory, report["signature"], "third-party signature")
    allowed = root / cfg["allowed_signers_path"]
    require(allowed.is_file() and not allowed.is_symlink(), "third-party allowed signers missing/unsafe")
    allowed_text = allowed.read_text()
    require(any(line.split(maxsplit=1)[0] == identity for line in allowed_text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")),
            "third-party identity is not approved")
    statement_value = common.read(statement)
    fields(statement_value, {"schema_version", "kind", "candidate", "performer", "source_snapshot_sha256",
                             "release_package", "result"}, "third-party signed statement")
    require(common.same(statement_value["schema_version"], 1) and
            statement_value["kind"] == "third-party-reproduction-statement-v1" and
            statement_value["candidate"] == candidate and statement_value["performer"] == report["performer"] and
            statement_value["source_snapshot_sha256"] == snapshot["snapshot_sha256"] and
            statement_value["release_package"] == report["release_package"] and
            statement_value["result"] == report["result"], "third-party signed statement differs")
    verify_ssh_signature(allowed, identity, cfg["require_signature_namespace"],
                         signature, statement, "third-party")
    boundaries(report["boundaries"], {"independent_third_party", "third_party_reproduced"})
    require(common.sha(path) == initial, "third-party report changed during validation")
    return {"scope": "signed_independent_document_only_release_reproduction",
            "performer": report["performer"], "source_snapshot_sha256": snapshot["snapshot_sha256"],
            "stages": len(report["stages"]), "independent_third_party": True,
            "third_party_reproduced": True, "release_claimed": False, "week6_closed": False}
