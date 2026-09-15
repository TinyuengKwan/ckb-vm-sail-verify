"""Fail-closed tests for Week6 external evidence validators."""

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_external_evidence as external


class ExternalEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="external-evidence-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.out = self.root / "evidence"
        self.out.mkdir()
        self.candidate = "fixture-candidate"
        self.snapshot = {
            "schema_version": 1,
            "snapshot_sha256": "f" * 64,
            "repositories": {
                ".": {"head": "1" * 40},
                "deps/ckb-vm": {"head": "2" * 40},
                "deps/sail-riscv": {"head": "3" * 40},
            },
        }
        policy_source = Path(__file__).resolve().parents[2] / external.POLICY
        self.policy = json.loads(policy_source.read_text())
        self.write_policy()
        allowed = self.root / self.policy["third_party"]["allowed_signers_path"]
        allowed.parent.mkdir(parents=True, exist_ok=True)
        allowed.write_text("# no fixture signer yet\n")
        workflow = self.root / self.policy["ci_download"]["workflow"]
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("name: fixture Week6\n")
        self.log = self.make_file("stage.log", b"fixture log\n")
        self.snapshot_ref = self.make_json("source-snapshot.json", self.snapshot)
        self.result = {
            "runtime_cases": 33,
            "instruction_families": {"ADD": 13, "ADDI": 10, "BEQ": 10},
            "mutations_applied": 194,
            "rust_tests": 78,
            "lean_stages": 28,
            "lean_tests": 287,
            "lean_public_theorems": 68,
            "rocq_stages": 11,
            "rocq_verdict": "NO-GO",
            "unexpected_mismatches": 0,
            "worktree_reviewed": True,
            "public_claims_reviewed": True,
        }

    def write_policy(self):
        path = self.root / external.POLICY
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.policy))

    def make_file(self, name, body=b"fixture\n"):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return {"path": name, "sha256": external.common.sha(path)}

    def make_json(self, name, value):
        return self.make_file(name, (json.dumps(value, sort_keys=True) + "\n").encode())

    def make_tar(self, name, members):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "w:gz") as archive:
            for member_name, data in members.items():
                info = tarfile.TarInfo(member_name)
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
        return {"path": name, "sha256": external.common.sha(path)}

    def test_tar_inventory_streams_without_retaining_member_bytes(self):
        data = b"streamed member" * 100

        class GuardedStream(io.BytesIO):
            def read(self, size=-1):
                if size < 0:
                    raise AssertionError("unbounded archive member read")
                return super().read(size)

        class Member:
            name = "evidence/member.bin"
            size = len(data)

            @staticmethod
            def isdir():
                return False

            @staticmethod
            def isfile():
                return True

        class Archive:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def __iter__(self):
                return iter([Member()])

            @staticmethod
            def extractfile(_):
                return GuardedStream(data)

        with patch.object(external.tarfile, "open", return_value=Archive()):
            files, directories = external.tar_inventory(self.out / "unused.tar.gz")
        self.assertEqual(directories, set())
        self.assertEqual(files, {"evidence/member.bin": {
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}})

    def write_report(self, name, value):
        path = self.out / name
        path.write_text(json.dumps(value))
        return path

    def signer(self, identity, allowed_path, stem):
        key = self.root / stem
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        allowed = self.root / allowed_path
        allowed.parent.mkdir(parents=True, exist_ok=True)
        allowed.write_text(identity + " " + (self.root / (stem + ".pub")).read_text())
        return key

    def sign(self, key, namespace, reference):
        target = self.out / reference["path"]
        signature = Path(str(target) + ".sig")
        if signature.exists():
            signature.unlink()
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", namespace, str(target)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return {"path": signature.relative_to(self.out).as_posix(),
                "sha256": external.common.sha(signature)}

    def stage_rows(self, names):
        return [{"name": name, "argv": ["fixture", name], "cwd": ".", "exit_code": 0,
                 "stdout": self.log, "stderr": self.log} for name in names]

    def check_snapshot(self):
        return patch.object(external.source, "capture", return_value=copy.deepcopy(self.snapshot))

    def clean_report(self):
        cfg = self.policy["clean_room"]
        return {
            "schema_version": 1,
            "kind": "clean-room-evidence-v1",
            "status": "passed",
            "candidate": self.candidate,
            "provider": {
                "kind": cfg["allowed_providers"][0],
                "environment_id": "fixture-environment",
                "image": "ubuntu-24.04",
                "image_digest": "sha256:" + "4" * 64,
                "created_at": "2026-09-14T00:00:00Z",
                "ephemeral": True,
                "original_workspace_mounted": False,
            },
            "checkout": {
                "repository": self.policy["repository"],
                "head": self.snapshot["repositories"]["."]["head"],
                "recursive_submodules": True,
                "submodules": {name: self.snapshot["repositories"][name]["head"]
                               for name in external.source.REPOS[1:]},
                "overlay_applied": True,
                "worktree_status": "fixture reviewed overlay",
                "log": self.log,
            },
            "tools": {name: {"version": "fixture " + name, "executable_sha256": "5" * 64,
                              "install_log": self.log} for name in cfg["required_tools"]},
            "source_snapshot": self.snapshot_ref,
            "stages": self.stage_rows(cfg["required_stages"]),
            "result": copy.deepcopy(self.result),
            "boundaries": {"release_claimed": False, "week6_closed": False,
                           "fresh_execution_claimed": True, "clean_room_verified": True},
        }

    def test_clean_room_accepts_exact_fresh_full_chain(self):
        path = self.write_report("clean.json", self.clean_report())
        with self.check_snapshot():
            result = external.check_clean_room(path, self.candidate, root=self.root)
        self.assertTrue(result["clean_room_verified"])
        self.assertEqual(result["stages"], 16)

    def test_clean_room_rejects_mounted_workspace_or_missing_stage(self):
        for mutate, pattern in [
            (lambda r: r["provider"].update(original_workspace_mounted=True), "not fresh"),
            (lambda r: r["stages"].pop(), "stage inventory"),
        ]:
            report = self.clean_report()
            mutate(report)
            path = self.write_report("clean.json", report)
            with self.subTest(pattern=pattern), self.check_snapshot(), \
                    self.assertRaisesRegex(RuntimeError, pattern):
                external.check_clean_room(path, self.candidate, root=self.root)

    def vm_record(self, clean_path, mutate=None):
        report = json.loads(clean_path.read_text())
        directory = clean_path.parent
        host = directory / "host"
        host.mkdir(exist_ok=True)
        logs = {}
        for name in ["console.log", "guest-controller.stdout", "guest-controller.stderr"]:
            (host / name).write_bytes(b"fixture " + name.encode() + b"\n")
            logs[name] = {"path": "host/" + name, "sha256": external.common.sha(host / name)}
        record = {
            "schema_version": 1, "kind": external.VM_RECORD_KIND, "status": external.VM_RECORD_STATUS,
            "provider": {key: report["provider"][key] for key in ["kind", "environment_id", "image", "image_digest"]},
            "hypervisor": {"executable": "/usr/bin/qemu-system-x86_64", "executable_sha256": "6" * 64,
                           "version": "QEMU emulator version 8.2.2", "accelerator": "kvm"},
            "disks": {"base_image_sha256": report["provider"]["image_digest"][len("sha256:"):],
                      "overlay": {"created_at": "2026-09-14T00:00:00+00:00", "virtual_size_bytes": 96 * 1024 ** 3,
                                  "destroyed": True},
                      "evidence": {"virtual_size_bytes": 24 * 1024 ** 3, "archive_sha256": "7" * 64,
                                   "destroyed": True},
                      "secrets": {"destroyed": True}},
            "seed": {"user_data_sha256": "8" * 64, "meta_data_sha256": "9" * 64},
            "launch": {"argv": ["/usr/bin/qemu-system-x86_64", "-machine", "q35,accel=kvm", "-drive",
                                "file=overlay.qcow2,if=virtio"],
                       "started_at": "2026-09-14T00:00:00+00:00", "finished_at": "2026-09-14T04:00:00+00:00",
                       "exit_code": 0, "console_log": logs["console.log"]},
            "guest": {"controller_exit_code": 0, "controller_stdout": logs["guest-controller.stdout"],
                      "controller_stderr": logs["guest-controller.stderr"], "packages": ["git"],
                      "extracted_members": 12},
            "report": {"path": clean_path.name, "sha256": external.common.sha(clean_path)},
            "boundaries": {"release_claimed": False, "week6_closed": False, "clean_room_claimed": False,
                           "platform_signed_identity": False, "operator_attested": True,
                           "overlay_destroyed": True, "secrets_destroyed": True,
                           "shared_filesystem_absent": True},
        }
        if mutate:
            mutate(record)
        path = directory / external.VM_RECORD
        path.write_text(json.dumps(record))
        return path

    def test_vm_provider_report_is_self_described_until_the_host_record_binds_it(self):
        report = self.clean_report()
        report["provider"].update(kind=external.VM_PROVIDER, environment_id="0b6c0f4e-vm",
                                  image="ubuntu-24.04-server-cloudimg-amd64.img")
        path = self.write_report("clean.json", report)
        with self.check_snapshot():
            result = external.check_clean_room(path, self.candidate, root=self.root)
        self.assertEqual(result["provider"], external.VM_PROVIDER)
        with self.assertRaises(external.VmProvenanceAbsent):
            external.check_vm_provenance(path)
        self.vm_record(path)
        verified = external.check_vm_provenance(path)
        self.assertTrue(verified["operator_attested"])
        self.assertFalse(verified["platform_signed_identity"])
        self.assertEqual(verified["environment_id"], "0b6c0f4e-vm")
        for mutate, pattern in [
            (lambda r: r["provider"].update(environment_id="other"), "provider differs"),
            (lambda r: r["report"].update(sha256="0" * 64), "different clean-room report"),
            (lambda r: r["launch"]["argv"].append("-virtfs"), "shared a host filesystem"),
            (lambda r: r["launch"].update(argv=["qemu", "-machine", "q35,accel=tcg"]), "did not use KVM"),
            (lambda r: r["disks"]["overlay"].update(destroyed=False), "not destroyed"),
            (lambda r: r["boundaries"].update(platform_signed_identity=True), "boundary changed"),
            (lambda r: r["hypervisor"].update(accelerator="tcg"), "accelerator"),
            (lambda r: r["disks"].update(base_image_sha256="1" * 64), "base image differs"),
            (lambda r: r.update(status="guest_running"), "identity/status"),
        ]:
            self.vm_record(path, mutate)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                external.check_vm_provenance(path)
        github = self.clean_report()
        github_path = self.write_report("github.json", github)
        with self.assertRaisesRegex(RuntimeError, "applies only"):
            external.check_vm_provenance(github_path)

    def test_ci_archive_with_vm_clean_room_must_carry_the_host_record(self):
        clean_report = self.clean_report()
        clean_report["provider"].update(kind=external.VM_PROVIDER, environment_id="vm-1",
                                        image="ubuntu-24.04-server-cloudimg-amd64.img")
        clean_bytes = (json.dumps(clean_report, sort_keys=True) + "\n").encode()
        clean_path = self.out / "downloaded/clean-room/report.json"
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.write_bytes(clean_bytes)
        record_path = self.vm_record(clean_path)
        extra = {"clean-room/report.json": clean_bytes,
                 "clean-room/vm-provenance.json": record_path.read_bytes()}
        for name in ["console.log", "guest-controller.stdout", "guest-controller.stderr"]:
            extra["clean-room/host/" + name] = (clean_path.parent / "host" / name).read_bytes()
        report = self.ci_report(extra)
        verified = SimpleNamespace(returncode=0, stdout=b'[{"verificationResult": {}}]', stderr=b"")
        path = self.write_report("ci-vm.json", report)
        with self.check_snapshot(), patch.object(external.subprocess, "run", return_value=verified):
            result = external.check_ci_download(path, self.candidate, root=self.root)
        self.assertTrue(result["ci_download_verified"])
        without = {name: data for name, data in extra.items() if name != "clean-room/vm-provenance.json"}
        path = self.write_report("ci-vm-missing.json", self.ci_report(without))
        with self.check_snapshot(), patch.object(external.subprocess, "run", return_value=verified), \
                self.assertRaisesRegex(RuntimeError, "lacks the independent ephemeral VM provenance record"):
            external.check_ci_download(path, self.candidate, root=self.root)

    def ci_report(self, extra_payload=None):
        cfg = self.policy["ci_download"]
        clean_name = "clean-room/report.json"
        replay_name = "corpus/add-signed-overflow.json"
        payload = {
            clean_name: b'{"fixture":"clean-room"}\n',
            replay_name: b'{"fixture":"replay"}\n',
        }
        if extra_payload:
            payload.update(extra_payload)
        member_rows = [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                       for name, data in payload.items()]
        artifact_manifest = {
            "schema_version": 1,
            "kind": "ci-evidence-archive-manifest-v1",
            "candidate": self.candidate,
            "source_snapshot_sha256": self.snapshot["snapshot_sha256"],
            "clean_room_report": clean_name,
            "replay_case": replay_name,
            "members": member_rows,
        }
        manifest_bytes = (json.dumps(artifact_manifest, sort_keys=True) + "\n").encode()
        uploaded = self.make_tar("uploaded.tar.gz", {**payload, "MANIFEST.json": manifest_bytes})
        downloaded = self.make_file("downloaded.tar.gz", (self.out / uploaded["path"]).read_bytes())
        manifest_ref = self.make_file("downloaded/MANIFEST.json", manifest_bytes)
        clean_room = self.make_file("downloaded/" + clean_name, payload[clean_name])
        self.make_file("downloaded/" + replay_name, payload[replay_name])
        for name, data in payload.items():
            if name not in (clean_name, replay_name):
                self.make_file("downloaded/" + name, data)
        artifact_hash = uploaded["sha256"]
        run_id = 123
        head = self.snapshot["repositories"]["."]["head"]
        attestation = self.make_file("attestation.jsonl", b"fixture sigstore bundle\n")
        jobs = {name: {"job_id": i + 1, "conclusion": "success", "log": self.log}
                for i, name in enumerate(cfg["required_jobs"])}
        run_query = self.make_json("run-query.json", {
            "id": run_id,
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "head_sha": head,
            "conclusion": "success",
            "path": cfg["workflow"],
        })
        jobs_query = self.make_json("jobs-query.json", {"jobs": [
            {"name": name, "id": row["job_id"], "conclusion": row["conclusion"]}
            for name, row in jobs.items()
        ]})
        return {
            "schema_version": 1,
            "kind": "ci-download-evidence-v1",
            "status": "passed",
            "candidate": self.candidate,
            "provider": {"kind": cfg["provider"], "repository": self.policy["repository"],
                         "run_id": run_id, "run_attempt": 1, "event": "workflow_dispatch",
                         "head_sha": head, "conclusion": "success",
                         "html_url": "https://example.invalid/actions/runs/123"},
            "workflow": {"path": cfg["workflow"],
                         "sha256": external.common.sha(self.root / cfg["workflow"])},
            "source_snapshot": self.snapshot_ref,
            "clean_room": clean_room,
            "jobs": jobs,
            "artifact": {"name": cfg["artifact_name_prefix"] + "123", "artifact_id": 77,
                         "format": "tar.gz",
                         "sha256": artifact_hash, "upload_archive": uploaded,
                         "download_archive": downloaded, "manifest": manifest_ref,
                         "attestation": attestation, "expired": False},
            "external_download": {"argv": ["gh", "run", "download", "123", "--repo",
                                                    self.policy["repository"], "--name",
                                                    cfg["artifact_name_prefix"] + "123", "--dir", "downloaded"],
                                  "exit_code": 0,
                                  "stdout": self.log, "stderr": self.log,
                                  "destination_initially_absent": True},
            "replay": {"case": "add-signed-overflow", "source": "downloaded/" + replay_name,
                       "argv": ["ckb-vm-sail-diff", "--replay", "downloaded/" + replay_name],
                       "exit_code": 0, "stdout": self.log, "stderr": self.log},
            "remote_query": {"argv": ["gh", "api", "repos/" + self.policy["repository"] +
                                       "/actions/runs/123"], "exit_code": 0,
                             "stdout": run_query, "stderr": self.log},
            "jobs_query": {"argv": ["gh", "api", "repos/" + self.policy["repository"] +
                                     "/actions/runs/123/jobs"], "exit_code": 0,
                           "stdout": jobs_query, "stderr": self.log},
            "boundaries": {"release_claimed": False, "week6_closed": False,
                           "remote_state_queried": True, "ci_download_verified": True},
        }

    def test_ci_accepts_current_workflow_upload_download_and_replay(self):
        path = self.write_report("ci.json", self.ci_report())
        verified = SimpleNamespace(returncode=0, stdout=b'[{"verificationResult": {}}]', stderr=b"")
        with self.check_snapshot(), patch.object(external.subprocess, "run", return_value=verified) as run:
            result = external.check_ci_download(path, self.candidate, root=self.root)
        self.assertTrue(result["ci_download_verified"])
        self.assertEqual(result["jobs"], 5)
        self.assertEqual(run.call_args.args[0][:3], ["gh", "attestation", "verify"])

    def test_ci_rejects_missing_job_or_same_archive_path(self):
        for mutate, pattern in [
            (lambda r: r["jobs"].pop(next(iter(r["jobs"]))), "job inventory"),
            (lambda r: r["artifact"].update(download_archive=r["artifact"]["upload_archive"]),
             "downloaded bytes"),
        ]:
            report = self.ci_report()
            mutate(report)
            path = self.write_report("ci.json", report)
            with self.subTest(pattern=pattern), self.check_snapshot(), \
                    self.assertRaisesRegex(RuntimeError, pattern):
                external.check_ci_download(path, self.candidate, root=self.root)

    def test_ci_rejects_failed_or_non_json_provenance_verification(self):
        for verifier, pattern in [
            (SimpleNamespace(returncode=1, stdout=b"", stderr=b"bad signature"), "verification failed"),
            (SimpleNamespace(returncode=0, stdout=b"not json", stderr=b""), "did not return JSON"),
        ]:
            path = self.write_report("ci.json", self.ci_report())
            with self.subTest(pattern=pattern), self.check_snapshot(), \
                    patch.object(external.subprocess, "run", return_value=verifier), \
                    self.assertRaisesRegex(RuntimeError, pattern):
                external.check_ci_download(path, self.candidate, root=self.root)

    def package_report(self):
        payload = {
            "source/file.txt": b"source\n",
            "install/file.txt": b"install\n",
            "evidence/file.txt": b"evidence\n",
            "docs/coverage.md": b"coverage\n",
            "docs/non-goals.md": b"non-goals\n",
            "SHA256SUMS": b"fixture sums\n",
        }
        members = [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                   for name, data in payload.items()]
        package_manifest = {
            "schema_version": 1,
            "kind": "release-package-manifest-v1",
            "candidate": self.candidate,
            "version": self.policy["release_package"]["approved_version"],
            "delivery_profile": self.policy["release_package"]["approved_delivery_profile"],
            "source_snapshot_sha256": self.snapshot["snapshot_sha256"],
            "coverage": "docs/coverage.md",
            "non_goals": "docs/non-goals.md",
            "members": members,
        }
        manifest_bytes = (json.dumps(package_manifest, sort_keys=True) + "\n").encode()
        archive = self.make_tar("release.tar.gz", {**payload, "MANIFEST.json": manifest_bytes})
        downloaded = self.make_file("download/release.tar.gz", (self.out / archive["path"]).read_bytes())
        manifest = self.make_file("built/MANIFEST.json", manifest_bytes)
        coverage = self.make_file("built/docs/coverage.md", payload["docs/coverage.md"])
        non_goals = self.make_file("built/docs/non-goals.md", payload["docs/non-goals.md"])
        asset_url = "https://example.invalid/releases/v1/download/release.tar.gz"
        signature = self.make_file("release.tar.gz.sig", b"fixture release signature")
        signature_url = "https://example.invalid/releases/v1/download/release.tar.gz.sig"
        remote = {
            "id": 88,
            "tag_name": self.policy["release_package"]["approved_version"],
            "html_url": "https://example.invalid/releases/v1",
            "published_at": "2026-09-14T00:00:00Z",
            "immutable": True,
            "draft": False,
            "assets": [{"id": 99, "browser_download_url": asset_url, "state": "uploaded",
                        "size": (self.out / archive["path"]).stat().st_size,
                        "digest": "sha256:" + archive["sha256"]},
                       {"id": 100, "browser_download_url": signature_url, "state": "uploaded",
                        "size": (self.out / signature["path"]).stat().st_size,
                        "digest": "sha256:" + signature["sha256"]}],
        }
        remote_ref = self.make_json("release-query.json", remote)
        query_argv = ["gh", "api", "--hostname", "github.com",
                      "repos/" + self.policy["repository"] + "/releases/88"]
        return {
            "schema_version": 1,
            "kind": "release-package-evidence-v1",
            "status": "passed",
            "candidate": self.candidate,
            "version": self.policy["release_package"]["approved_version"],
            "delivery_profile": self.policy["release_package"]["approved_delivery_profile"],
            "source_snapshot": self.snapshot_ref,
            "archive_format": "tar.gz",
            "archive": archive,
            "manifest": manifest,
            "coverage": coverage,
            "non_goals": non_goals,
            "publication": {"provider": "github-releases", "repository": self.policy["repository"],
                            "release_id": 88, "tag": self.policy["release_package"]["approved_version"],
                            "url": "https://example.invalid/releases/v1",
                            "asset_url": asset_url, "signature_asset_url": signature_url,
                            "published_at": "2026-09-14T00:00:00Z", "immutable": True,
                            "remote_query": {"argv": query_argv, "exit_code": 0,
                                             "stdout": remote_ref, "stderr": self.log}},
            "download": {"url": asset_url, "archive": downloaded, "destination_initially_absent": True,
                         "argv": ["curl", "--fail", "--location", "--output", downloaded["path"], asset_url],
                         "exit_code": 0, "stdout": self.log, "stderr": self.log},
            "signing_identity": self.policy["release_package"]["approved_signer_identity"],
            "signature": signature,
            "boundaries": {"release_claimed": False, "week6_closed": False,
                           "release_package_built": True, "publication_verified": True,
                           "download_verified": True, "remote_state_queried": True},
        }

    def test_package_requires_policy_approval_then_accepts_publication_download(self):
        path = self.write_report("package.json", {"status": "PASS"})
        with self.assertRaisesRegex(RuntimeError, "not approved"):
            external.check_release_package(path, self.candidate, root=self.root)
        self.policy["release_package"].update(approved_version="v1.0.0", approved_delivery_profile="A",
                                              approved_signer_identity="release@example")
        self.write_policy()
        allowed = self.root / self.policy["release_package"]["allowed_signers_path"]
        allowed.parent.mkdir(parents=True, exist_ok=True)
        allowed.write_text("release@example ssh-ed25519 AAAAfixture\n")
        report = self.package_report()
        path = self.write_report("package.json", report)
        remote = json.loads((self.out / report["publication"]["remote_query"]["stdout"]["path"]).read_text())
        with self.check_snapshot(), patch.object(external, "query_json", return_value=remote), \
                patch.object(external.subprocess, "run",
                return_value=SimpleNamespace(returncode=0, stdout=b"Good", stderr=b"")):
            result = external.check_release_package(path, self.candidate, root=self.root)
        self.assertTrue(result["publication_verified"])
        self.assertEqual(result["version"], "v1.0.0")

    def test_package_signature_is_actually_verified(self):
        self.policy["release_package"].update(approved_version="v1.0.0", approved_delivery_profile="A",
                                              approved_signer_identity="release@example")
        self.write_policy()
        key = self.signer("release@example", self.policy["release_package"]["allowed_signers_path"],
                          "release-key")
        report = self.package_report()
        report["signature"] = self.sign(key, self.policy["release_package"]["signature_namespace"],
                                        report["archive"])
        remote_path = self.out / report["publication"]["remote_query"]["stdout"]["path"]
        remote = json.loads(remote_path.read_text())
        signature_path = self.out / report["signature"]["path"]
        signature_asset = next(row for row in remote["assets"]
                               if row["browser_download_url"] ==
                               report["publication"]["signature_asset_url"])
        signature_asset["size"] = signature_path.stat().st_size
        signature_asset["digest"] = "sha256:" + report["signature"]["sha256"]
        remote_path.write_text(json.dumps(remote))
        report["publication"]["remote_query"]["stdout"]["sha256"] = external.common.sha(remote_path)
        path = self.write_report("package.json", report)
        with self.check_snapshot(), patch.object(external, "query_json", return_value=remote):
            self.assertTrue(external.check_release_package(path, self.candidate, root=self.root)
                            ["release_package_built"])

    def test_package_rejects_remote_asset_digest_mismatch(self):
        self.policy["release_package"].update(approved_version="v1.0.0", approved_delivery_profile="A",
                                              approved_signer_identity="release@example")
        self.write_policy()
        report = self.package_report()
        remote_path = self.out / report["publication"]["remote_query"]["stdout"]["path"]
        remote = json.loads(remote_path.read_text())
        remote["assets"][0]["digest"] = "sha256:" + "0" * 64
        remote_path.write_text(json.dumps(remote))
        report["publication"]["remote_query"]["stdout"]["sha256"] = external.common.sha(remote_path)
        path = self.write_report("package.json", report)
        with self.check_snapshot(), self.assertRaisesRegex(RuntimeError, "asset state/size/digest"):
            external.check_release_package(path, self.candidate, root=self.root)

    def test_package_rejects_unpublished_signature(self):
        self.policy["release_package"].update(approved_version="v1.0.0", approved_delivery_profile="A",
                                              approved_signer_identity="release@example")
        self.write_policy()
        report = self.package_report()
        remote_path = self.out / report["publication"]["remote_query"]["stdout"]["path"]
        remote = json.loads(remote_path.read_text())
        remote["assets"] = [row for row in remote["assets"]
                            if row["browser_download_url"] != report["publication"]["signature_asset_url"]]
        remote_path.write_text(json.dumps(remote))
        report["publication"]["remote_query"]["stdout"]["sha256"] = external.common.sha(remote_path)
        path = self.write_report("package.json", report)
        with self.check_snapshot(), self.assertRaisesRegex(RuntimeError, "signature asset URL"):
            external.check_release_package(path, self.candidate, root=self.root)

    def third_party_report(self):
        performer = {"identity": "alice@example", "name": "Alice", "affiliation": "Independent Lab",
                     "independent": True, "maintainer": False, "assistant": False}
        package = self.make_json("package-report.json", {"fixture": "package"})
        statement_value = {
            "schema_version": 1,
            "kind": "third-party-reproduction-statement-v1",
            "candidate": self.candidate,
            "performer": performer,
            "source_snapshot_sha256": self.snapshot["snapshot_sha256"],
            "release_package": package,
            "result": copy.deepcopy(self.result),
        }
        statement = self.make_json("statement.json", statement_value)
        signature = self.make_file("statement.sig", b"fixture signature")
        return {
            "schema_version": 1,
            "kind": "third-party-reproduction-v1",
            "status": "passed",
            "candidate": self.candidate,
            "performer": performer,
            "source_snapshot": self.snapshot_ref,
            "release_package": package,
            "stages": self.stage_rows(self.policy["third_party"]["required_stages"]),
            "result": copy.deepcopy(self.result),
            "statement": statement,
            "signature": signature,
            "boundaries": {"release_claimed": False, "week6_closed": False,
                           "independent_third_party": True, "third_party_reproduced": True},
        }

    def test_third_party_requires_pinned_identity_and_valid_signature(self):
        report = self.third_party_report()
        path = self.write_report("third-party.json", report)
        with self.check_snapshot(), self.assertRaisesRegex(RuntimeError, "not approved"):
            external.check_third_party(path, self.candidate, root=self.root)
        allowed = self.root / self.policy["third_party"]["allowed_signers_path"]
        allowed.write_text("alice@example ssh-ed25519 AAAAfixture\n")
        with self.check_snapshot(), patch.object(external.subprocess, "run",
                return_value=SimpleNamespace(returncode=0, stdout=b"Good", stderr=b"")) as verify:
            result = external.check_third_party(path, self.candidate, root=self.root)
        self.assertTrue(result["third_party_reproduced"])
        self.assertIn("ssh-keygen", verify.call_args.args[0][0])

    def test_third_party_signature_is_actually_verified(self):
        key = self.signer("alice@example", self.policy["third_party"]["allowed_signers_path"], "third-key")
        report = self.third_party_report()
        report["signature"] = self.sign(key, self.policy["third_party"]["require_signature_namespace"],
                                        report["statement"])
        path = self.write_report("third-party.json", report)
        with self.check_snapshot():
            self.assertTrue(external.check_third_party(path, self.candidate, root=self.root)
                            ["third_party_reproduced"])

    def test_third_party_rejects_signature_failure_or_non_independent_performer(self):
        allowed = self.root / self.policy["third_party"]["allowed_signers_path"]
        allowed.write_text("alice@example ssh-ed25519 AAAAfixture\n")
        for mutate, code, pattern in [
            (lambda r: None, 1, "signature verification failed"),
            (lambda r: r["performer"].update(independent=False), 0, "not independent"),
        ]:
            report = self.third_party_report()
            mutate(report)
            path = self.write_report("third-party.json", report)
            with self.subTest(pattern=pattern), self.check_snapshot(), \
                    patch.object(external.subprocess, "run",
                                 return_value=SimpleNamespace(returncode=code, stdout=b"", stderr=b"bad")), \
                    self.assertRaisesRegex(RuntimeError, pattern):
                external.check_third_party(path, self.candidate, root=self.root)


if __name__ == "__main__":
    unittest.main()
