#!/usr/bin/env python3
"""Collector over a faked GitHub transport with a real bundle, real extraction
and a real (fixture) replay binary.  Not CI evidence."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as audit
import ci_evidence
import evidence_bundle as bundle
import release_common as common

CANDIDATE = "a" * 40
RUN_ID = 424242


class CollectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ci evidence with spaces ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "root"
        clean = self.root / bundle.CLEAN
        (clean / "runtime/original").mkdir(parents=True)
        (clean / "replay-inputs").mkdir()
        (self.root / "docs/release").mkdir(parents=True)
        self.policy = {"schema_version": 2, "kind": "release-policy-v2", "repository": "fixture/repo",
                       "ci": {"workflow": ".github/workflows/release.yml", "jobs": ["fast", "intake", "replay"],
                              "artifact_name_prefix": "release-evidence-", "replay_case": "add-signed-overflow"}}
        (self.root / "docs/release/policy.json").write_text(json.dumps(self.policy))
        (clean / "report.json").write_text(json.dumps({"kind": "clean-room-evidence-v2", "candidate": CANDIDATE}))
        (clean / bundle.VM_RECORD).write_text("{}\n")
        (clean / "runtime/original/add-signed-overflow.json").write_text('{"fixture":"case"}\n')
        (clean / "replay-inputs/sail_riscv_sim").write_text("#!/bin/sh\nexit 0\n")
        (clean / "replay-inputs/ckb_vm_config.json").write_text("{}\n")
        (clean / "runtime/ckb-vm-sail-diff").write_text(
            "#!/usr/bin/env python3\nimport json, pathlib, sys\nargs = sys.argv[1:]\n"
            "for flag in ('--sail-bin', '--sail-config', '--replay'):\n"
            "    assert pathlib.Path(args[args.index(flag) + 1]).is_file(), flag\n"
            "assert json.loads(pathlib.Path(args[args.index('--replay') + 1]).read_text()) == {'fixture': 'case'}\n"
            "out = pathlib.Path(args[args.index('--artifact-dir') + 1]); out.mkdir(); (out / 'ok').write_text('ok')\n")
        for name in ("runtime/ckb-vm-sail-diff", "replay-inputs/sail_riscv_sim"):
            (clean / name).chmod(0o755)
        self.bundle = self.base / "vm-evidence.tar.gz"
        self.sha = bundle.pack(self.root, self.bundle)["sha256"]
        self.run = {"id": RUN_ID, "head_sha": CANDIDATE, "event": "workflow_dispatch", "conclusion": "success",
                    "path": ".github/workflows/release.yml", "run_attempt": 1, "html_url": "https://example.invalid/run"}
        self.jobs = {"jobs": [{"id": i + 1, "name": n, "conclusion": "success"} for i, n in enumerate(["fast", "intake", "replay"])]}
        self.artifacts = {"artifacts": [{"id": 9, "name": "release-evidence-" + CANDIDATE, "expired": False}]}
        self.corrupt_second = False
        self.real_run = common.run_command

    def fake_run(self, out, label, argv, cwd, env=None, timeout=1800):
        out = Path(out)
        if label == "replay":
            return self.real_run(out, label, argv, cwd, env=env, timeout=timeout)
        self.assertEqual(argv[0], "gh", label)
        if label.startswith("query-"):
            body = json.dumps({"run": self.run, "jobs": self.jobs, "artifacts": self.artifacts}[label[6:]]).encode()
        elif label.endswith("-download") and "run" in argv:
            dest = Path(cwd) / argv[argv.index("--dir") + 1]
            dest.mkdir()
            (dest / ci_evidence.BUNDLE_NAME).write_bytes(self.bundle.read_bytes() + (b"x" if label == "second-download" and self.corrupt_second else b""))
            body = b"downloaded\n"
        elif label == "attestation-download":
            (Path(cwd) / "fixture.jsonl").write_text('{"fixture": true}\n')
            body = b"attested\n"
        elif label == "attestation-verify":
            body = b'[{"fixture": true}]'
        else:
            self.assertTrue(label.startswith("job-log-"), label)
            body = b"log\n"
        a, b = out / (label + ".stdout"), out / (label + ".stderr")
        a.write_bytes(body)
        b.write_bytes(b"")
        return {"name": label, "argv": [str(x) for x in argv], "cwd": str(cwd), "exit_code": 0,
                "stdout": common.ref(out, a), "stderr": common.ref(out, b)}

    def collect(self, name="collected"):
        verify = subprocess.CompletedProcess(["gh"], 0, b'[{"fixture": true}]', b"")
        real = subprocess.run

        def fake_subprocess(argv, *args, **kwargs):
            return verify if argv[:3] == ["gh", "attestation", "verify"] else real(argv, *args, **kwargs)
        with patch.object(common, "run_command", side_effect=self.fake_run), \
                patch.object(audit, "check_vm_report", return_value={"provider": "independent-ephemeral-vm", "source_snapshot_sha256": "b" * 64}), \
                patch.object(audit.subprocess, "run", side_effect=fake_subprocess):
            return ci_evidence.collect(argparse.Namespace(run_id=RUN_ID, candidate=CANDIDATE, out=self.base / name), root=self.root)

    def test_full_collection_replays_and_validates(self):
        result = self.collect()
        self.assertEqual((result["ci_run_id"], result["bundle_sha256"], result["replayed_case"]), (RUN_ID, self.sha, "add-signed-overflow"))
        self.assertTrue((self.base / "collected/replay-result/ok").is_file())
        report = json.loads((self.base / "collected/report.json").read_text())
        self.assertEqual(report["clean_room"]["bundle_sha256"], self.sha)

    def test_differing_downloads_and_wrong_remote_state_fail(self):
        self.corrupt_second = True
        with self.assertRaisesRegex(RuntimeError, "downloads differ"):
            self.collect("c1")
        self.corrupt_second = False
        self.jobs["jobs"][1]["conclusion"] = "failure"
        with self.assertRaisesRegex(RuntimeError, "remote job"):
            self.collect("c2")

    def test_select_remote_rejects_wrong_workflow_and_expired_artifact(self):
        with self.assertRaisesRegex(RuntimeError, "remote run"):
            ci_evidence.select_remote({**self.run, "path": "other.yml"}, self.jobs, self.artifacts, self.policy, RUN_ID, CANDIDATE)
        expired = {"artifacts": [{**self.artifacts["artifacts"][0], "expired": True}]}
        with self.assertRaisesRegex(RuntimeError, "artifact"):
            ci_evidence.select_remote(self.run, self.jobs, expired, self.policy, RUN_ID, CANDIDATE)


if __name__ == "__main__":
    unittest.main()
