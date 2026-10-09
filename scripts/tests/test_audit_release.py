#!/usr/bin/env python3
"""Aggregation over the six slots with validators replaced by fixtures, plus the
VM provenance and manifest checks that need no toolchain."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as audit

CANDIDATE = "a" * 40
SNAPSHOT = "b" * 64


class AggregationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="audit-release-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reports = {}
        for name in audit.SLOTS:
            path = self.root / "artifacts" / name / "report.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"fixture": name}))
            self.reports[name] = audit.common.ref(self.root, path)
        self.patch(patch.object(audit.public_claims, "check", return_value={"status": "passed"}))
        self.patch(patch.object(audit, "current_snapshot", return_value={"snapshot_sha256": SNAPSHOT}))
        self.results = {name: {"fixture": True, "source_snapshot_sha256": SNAPSHOT} for name in audit.SLOTS}
        self.results["runtime"] = {"cases": 33}
        self.patch(patch.dict(audit.VALIDATORS, {name: (lambda p, c, r, n=name: self.results[n]) for name in audit.SLOTS}))

    def patch(self, mock):
        mock.start()
        self.addCleanup(mock.stop)

    def manifest(self, **overrides):
        slots = {name: self.reports[name] for name in audit.SLOTS}
        slots.update(overrides)
        return {"schema_version": 2, "kind": "release-audit-manifest-v2", "candidate": CANDIDATE, "slots": slots}

    def test_all_verified_passes_and_claims_only_then(self):
        report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((report["status"], code), ("passed", 0))
        self.assertTrue(report["boundaries"]["release_claimed"] and report["boundaries"]["third_party_reproduced"])

    def test_deferred_third_party_passes_but_is_not_reproduced(self):
        report, code = audit.aggregate(self.manifest(third_party=None), self.root)
        self.assertEqual((report["status"], code, report["deferred"]), ("passed", 0, ["third_party"]))
        self.assertFalse(report["boundaries"]["third_party_reproduced"])

    def test_missing_other_slot_is_incomplete(self):
        report, code = audit.aggregate(self.manifest(release=None), self.root)
        self.assertEqual((report["status"], code, report["outstanding"]), ("incomplete", 2, ["release"]))
        self.assertFalse(report["boundaries"]["release_claimed"])

    def test_incomplete_and_invalid_validators(self):
        def incomplete(p, c, r):
            raise audit.Incomplete("companion absent")

        def invalid(p, c, r):
            raise RuntimeError("bad signature")
        with patch.dict(audit.VALIDATORS, {"clean_room": incomplete}):
            report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((report["status"], code, report["slots"]["clean_room"]["status"]), ("incomplete", 2, "incomplete"))
        with patch.dict(audit.VALIDATORS, {"release": invalid}):
            report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((report["status"], code, report["invalid"]), ("invalid", 1, ["release"]))

    def test_snapshot_disagreement_and_public_claims_failure_are_invalid(self):
        self.results["release"] = {"source_snapshot_sha256": "c" * 64}
        report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((code, report["invalid"]), (1, ["source_snapshot"]))
        self.results["release"] = {"source_snapshot_sha256": SNAPSHOT}
        with patch.object(audit.public_claims, "check", side_effect=RuntimeError("forbidden phrase")):
            report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((code, report["invalid"]), (1, ["public_claims"]))

    def test_changed_report_hash_is_invalid(self):
        (self.root / "artifacts/lean/report.json").write_text("{}")
        report, code = audit.aggregate(self.manifest(), self.root)
        self.assertEqual((code, report["slots"]["lean"]["status"]), (1, "invalid"))

    def test_manifest_shape(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest()))
        self.assertEqual(audit.load_manifest(path)["candidate"], CANDIDATE)
        broken = self.manifest()
        broken["slots"].pop("rocq")
        path.write_text(json.dumps(broken))
        with self.assertRaisesRegex(RuntimeError, "slot inventory"):
            audit.load_manifest(path)

    def test_cli_composes_manifest_and_writes_report(self):
        out = self.root / "out"
        argv = [sys.executable, str(Path(audit.__file__)), "--candidate", CANDIDATE, "--root", str(self.root), "--out", str(out)]
        for name in audit.SLOTS:
            argv += ["--" + name.replace("_", "-"), str(self.root / self.reports[name]["path"])]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)  # fixture reports are not real evidence
        report = json.loads((out / "report.json").read_text())
        self.assertEqual((report["candidate"], report["status"]), (CANDIDATE, "invalid"))
        self.assertEqual(set(json.loads((out / "manifest.json").read_text())["slots"]), set(audit.SLOTS))


class VmProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="vm-provenance-test-")
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)
        self.provider = {"kind": "independent-ephemeral-vm", "environment_id": "env-1", "image": "img",
                         "image_digest": "sha256:" + "1" * 64, "created_at": "t", "ephemeral": True,
                         "original_workspace_mounted": False}
        self.report = self.dir / "report.json"
        self.report.write_text(json.dumps({"provider": self.provider}))
        (self.dir / "console.log").write_text("console\n")
        self.record = {
            "schema_version": 2, "kind": audit.VM_RECORD_KIND, "status": audit.VM_RECORD_STATUS,
            "provider": {k: self.provider[k] for k in ("kind", "environment_id", "image", "image_digest")},
            "hypervisor": {"executable": "/usr/bin/qemu-system-x86_64", "executable_sha256": "2" * 64, "version": "QEMU 8", "accelerator": "kvm"},
            "disks": {"base_image_sha256": "1" * 64, "overlay": {"destroyed": True}, "evidence": {"destroyed": True}, "secrets": {"destroyed": True}},
            "seed": {}, "launch": {"argv": ["qemu", "-machine", "q35,accel=kvm"], "exit_code": 0,
                                   "console_log": audit.common.ref(self.dir, self.dir / "console.log")},
            "guest": {"controller_exit_code": 0}, "report": {"path": "report.json", "sha256": audit.sha(self.report)},
            "boundaries": {"operator_attested": True, "platform_signed_identity": False, "release_claimed": False, "week6_closed": False}}

    def write(self):
        (self.dir / audit.VM_RECORD).write_text(json.dumps(self.record))

    def test_absent_record_is_incomplete_not_invalid(self):
        with self.assertRaises(audit.Incomplete):
            audit.check_vm_provenance(self.report)

    def test_bound_record_passes_and_tampering_fails(self):
        self.write()
        self.assertTrue(audit.check_vm_provenance(self.report)["operator_attested"])
        for mutate, pattern in [
            (lambda r: r["disks"]["secrets"].update(destroyed=False), "not destroyed"),
            (lambda r: r["launch"].update(argv=["qemu", "-virtfs", "x", "-machine", "q35,accel=kvm"]), "launch argv"),
            (lambda r: r["report"].update(sha256="3" * 64), "different clean-room report"),
            (lambda r: r["boundaries"].update(platform_signed_identity=True), "boundary"),
            (lambda r: r["provider"].update(environment_id="other"), "differs from the clean-room report"),
        ]:
            record = json.loads(json.dumps(self.record))
            mutate(record)
            (self.dir / audit.VM_RECORD).write_text(json.dumps(record))
            with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                audit.check_vm_provenance(self.report)


if __name__ == "__main__":
    unittest.main()
