#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load("week6_output_confirm", HERE.parent / "week6_output_confirm.py")
GATE_FIXTURE = load("current_output_gate_fixture", HERE / "test_release_current_output_review.py")


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = GATE_FIXTURE.OutputReviewTests("test_valid")
        self.fixture.setUp()
        self.root = self.fixture.root
        (self.root / "artifacts/boundary-check").mkdir(parents=True)
        policy = self.root / "policy.json"
        policy.write_text("{}\n")
        counts = {}
        for report_name, short, field in [
                ("registry_review", "registry", "reviewed_nodes"),
                ("build_review", "build", "new_reviewed_nodes"),
                ("record_review", "record", "new_reviewed_nodes")]:
            review = self.fixture.reviews[short]["review"]
            counts[short] = len(review[field])
        self.materialized = {
            "schema_version": 1, "kind": "week6-output-review-materialization-v1",
            "status": "all_additional_output_nodes_partitioned_pending_exact_rescan",
            "source_snapshot_sha256": self.fixture.SOURCE,
            "observation": self.fixture.ref(self.fixture.observation),
            "policy": self.fixture.ref(policy),
            "reports": {name: self.fixture.ref(self.fixture.reviews[short]["report_path"])
                        for name, short in [("registry_review", "registry"),
                                            ("build_review", "build"),
                                            ("record_review", "record")]},
            "counts": counts, "remaining": ["exact_current_output_rescan_confirmation"],
            "boundaries": {"semantic_correctness_proven": False,
                           "generated_outputs_audited": False, "delivery_approved": False,
                           "worktree_audit_closed": False, "release_claimed": False,
                           "week6_closed": False},
        }
        self.reviews = self.root / "reviews.json"
        self.reviews.write_text(json.dumps(self.materialized, indent=2) + "\n")

    def tearDown(self):
        self.fixture.doCleanups()

    def fake_command(self, out, name, argv, env, timeout, cwd):
        del env
        started = {"name": name, "argv": argv, "cwd": str(cwd),
                   "started_at": MODULE.recording.now(),
                   "timeout_seconds": timeout, "exit_code": None,
                   "status": "starting", "log": name + ".log"}
        MODULE.recording.write(out / (name + "-started.json"), started)
        process = {**started, "pid": 42}
        MODULE.recording.write(out / (name + "-process.json"), process)
        (out / "current").mkdir()
        (out / "current/snapshot.json").write_text(
            json.dumps(self.fixture.current, indent=2) + "\n")
        log = out / (name + ".log")
        log.write_text("captured\n")
        finished = {**process, "exit_code": 0, "status": "completed",
                    "finished_at": MODULE.recording.now(),
                    "log_sha256": MODULE.common.sha(log)}
        MODULE.recording.write(out / (name + "-finished.json"), finished)
        return finished

    def test_end_to_end_producer_enters_strict_validator(self):
        out = self.root / "artifacts/boundary-check/week6-output-confirmation-fixture"
        source = {"snapshot_sha256": self.fixture.SOURCE}
        with patch.object(MODULE.source_snapshot, "capture", return_value=source), \
                patch.object(MODULE.recording, "command", side_effect=self.fake_command):
            report, result = MODULE.run(self.fixture.observation, self.reviews, out,
                                        root=self.root, timeout=37)
        self.assertEqual(report["status"],
                         "current_24_root_snapshot_exactly_matches_reviewed_observation")
        self.assertEqual(result["reviewed_additional_nodes"], len(self.fixture.additional))
        self.assertEqual(result["current_snapshot_sha256"], self.fixture.current["snapshot_sha256"])
        self.assertFalse(result["generated_outputs_audited"])

    def test_review_reference_drift_rejected_before_output(self):
        path = self.fixture.reviews["build"]["report_path"]
        path.write_text("{}\n")
        out = self.root / "artifacts/boundary-check/week6-output-confirmation-never"
        with self.assertRaisesRegex(RuntimeError, "hash differs"):
            MODULE.run(self.fixture.observation, self.reviews, out, root=self.root)
        self.assertFalse(out.exists())

    def test_materialized_count_drift_rejected(self):
        value = json.loads(self.reviews.read_text())
        value["counts"]["record"] += 1
        self.reviews.write_text(json.dumps(value) + "\n")
        with self.assertRaisesRegex(RuntimeError, "count differs"):
            MODULE.load_inputs(self.fixture.observation, self.reviews, self.root)

    def test_output_must_be_new_named_direct_child(self):
        parent = self.root / "artifacts/boundary-check"
        accepted = MODULE.new_output(parent / "week6-output-confirmation-ok", self.root)
        self.assertTrue(accepted.is_dir())
        for path in [parent / "other", parent / "week6-output-confirmation-",
                     self.root / "week6-output-confirmation-outside", accepted]:
            with self.subTest(path=path), self.assertRaisesRegex(
                    RuntimeError, "new Week6 output confirmation"):
                MODULE.new_output(path, self.root)

    def test_copy_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source").write_text("source\n")
            (root / "link").symlink_to(root / "source")
            with self.assertRaisesRegex(RuntimeError, "linked"):
                MODULE.copy_regular(root / "link", root / "target")


if __name__ == "__main__":
    unittest.main()
