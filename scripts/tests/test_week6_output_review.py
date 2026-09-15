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
SPEC = importlib.util.spec_from_file_location(
    "week6_output_review", HERE.parent / "week6_output_review.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OutputReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "artifacts/boundary-check").mkdir(parents=True)
        (self.root / "proof").mkdir()
        (self.root / "proof/evidence.md").write_text("review\n")
        (self.root / "docs/release").mkdir(parents=True)
        self.policy = self.root / "docs/release/week6-review-policy-v1.json"
        policy = {"schema_version": 1, "kind": "week6-source-review-policy-v1",
                  "reviewed_by": "fixture", "require_root_repository_clean": True,
                  "allowed_source_changes": {".": {}, "deps/ckb-vm": {}, "deps/sail-riscv": {}},
                  "output_review": {
                      "allowed_root_prefixes": ["artifacts/boundary-check/week6-native-"],
                      "registry_marker": "/cargo/registry/",
                      "build_markers": ["/target/", "/build/"],
                  },
                  "boundaries": {name: False for name in MODULE.review_policy.POLICY_BOUNDARIES}}
        self.policy.write_text(json.dumps(policy) + "\n")
        self.observation = self.root / "artifacts/boundary-check/observation"
        self.observation.mkdir()
        roots = MODULE.inventory.roots(["artifacts/boundary-check/week6-native-fixture"])
        entries = dict.fromkeys(roots)
        directory_nodes = {name: {"kind": "directory", "mode": 0o755} for name in [
            "artifacts/boundary-check/week6-native-fixture",
            "artifacts/boundary-check/week6-native-fixture/cargo",
            "artifacts/boundary-check/week6-native-fixture/cargo/registry",
            "artifacts/boundary-check/week6-native-fixture/target",
        ]}
        nodes = {**directory_nodes,
            "artifacts/boundary-check/week6-native-fixture/cargo/registry/file":
                {"kind": "file", "mode": 0o644, "size": 1, "sha256": "a" * 64},
            "artifacts/boundary-check/week6-native-fixture/target/file":
                {"kind": "file", "mode": 0o644, "size": 1, "sha256": "b" * 64},
            "artifacts/boundary-check/week6-native-fixture/report.json":
                {"kind": "file", "mode": 0o644, "size": 1, "sha256": "c" * 64},
        }
        entries.update(nodes)
        snapshot = {"schema_version": 1, "kind": MODULE.inventory.KIND, "roots": roots,
                    "entries": entries, "symlinks_followed": False,
                    "whole_workspace_coverage_claimed": False}
        snapshot["snapshot_sha256"] = MODULE.inventory.digest(snapshot)
        (self.observation / "current").mkdir()
        current_path = self.observation / "current/snapshot.json"
        current_path.write_text(json.dumps(snapshot) + "\n")
        projected_entries = {name: None for name in MODULE.inventory.CANONICAL_ROOTS}
        projected = {"schema_version": 1, "kind": MODULE.inventory.KIND,
                     "roots": list(MODULE.inventory.CANONICAL_ROOTS),
                     "entries": projected_entries, "symlinks_followed": False,
                     "whole_workspace_coverage_claimed": False}
        projected["snapshot_sha256"] = MODULE.inventory.digest(projected)
        projected_path = self.observation / "current-formal-scope.json"
        projected_path.write_text(json.dumps(projected) + "\n")
        additional = {"schema_version": 1, "scope": "fixture",
                      "observed_snapshot_sha256": snapshot["snapshot_sha256"], "entries": nodes,
                      "historical_absence_claimed": False, "generated_outputs_audited": False}
        additional_path = self.observation / "additional-observed-nodes.json"
        additional_path.write_text(json.dumps(additional) + "\n")
        report = {"schema_version": 1, "kind": "current-expanded-output-observation-v1",
                  "status": "current_output_observation_and_complete_formal_delta_recorded_pending_review",
                  "errors": [], "source_snapshot_sha256": "d" * 64,
                  "changed_historical_nodes": 0, "change_operations": {},
                  "non_atomic_observation_only": True,
                  "current_inventory": {"path": current_path.relative_to(self.root).as_posix(),
                                        "sha256": MODULE.sha(current_path)},
                  "record_files": {
                      "additional-observed-nodes.json": MODULE.sha(additional_path),
                      "current-formal-scope.json": MODULE.sha(projected_path),
                  },
                  **{name: False for name in MODULE.validator.OBSERVATION_FLAGS}}
        self.report = self.observation / "report.json"
        self.report.write_text(json.dumps(report) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def produce(self):
        out = self.root / "artifacts/boundary-check/week6-output-review-fixture"
        with patch.object(MODULE.source_snapshot, "capture",
                          return_value={"snapshot_sha256": "d" * 64}):
            return MODULE.produce(self.report, self.policy, out, root=self.root), out

    def test_partitions_all_nodes_disjointly(self):
        result, out = self.produce()
        self.assertEqual(result["counts"], {"registry": 1, "build": 1, "record": 5})
        reviews = [json.loads((out / name / "review.json").read_text())
                   for name in ["registry", "build", "record"]]
        keys = [set(row.get("reviewed_nodes", row.get("new_reviewed_nodes", {}))) for row in reviews]
        self.assertFalse(keys[0] & keys[1] or keys[0] & keys[2] or keys[1] & keys[2])
        self.assertEqual(len(set().union(*keys)), 7)

    def test_unknown_root_rejected_before_output(self):
        with self.assertRaisesRegex(RuntimeError, "outside approved"):
            MODULE.classify("artifacts/boundary-check/unknown/file",
                            {"kind": "file", "mode": 0o644, "size": 1,
                             "sha256": "f" * 64},
                            {"allowed_root_prefixes": [
                                "artifacts/boundary-check/week6-native-"]})

    def test_observation_with_historical_change_rejected(self):
        report = json.loads(self.report.read_text())
        report["changed_historical_nodes"] = 1
        self.report.write_text(json.dumps(report) + "\n")
        with self.assertRaisesRegex(RuntimeError, "historical output changed"):
            self.produce()

    def test_forged_additional_partition_rejected(self):
        path = self.observation / "additional-observed-nodes.json"
        value = json.loads(path.read_text())
        value["entries"].pop(next(iter(value["entries"])))
        path.write_text(json.dumps(value) + "\n")
        report = json.loads(self.report.read_text())
        report["record_files"]["additional-observed-nodes.json"] = MODULE.sha(path)
        self.report.write_text(json.dumps(report) + "\n")
        with self.assertRaisesRegex(RuntimeError, "additional-node record"):
            self.produce()

    def test_node_identity_is_bound(self):
        result, out = self.produce()
        review = json.loads((out / "record/review.json").read_text())
        name, row = next(iter(review["new_reviewed_nodes"].items()))
        additional = json.loads((self.observation / "additional-observed-nodes.json").read_text())
        self.assertEqual(row["node_sha256"], MODULE.inventory.digest(additional["entries"][name]))
        self.assertFalse(row["semantic_correctness_proven"])

    def test_existing_output_rejected(self):
        out = self.root / "artifacts/boundary-check/week6-output-review-fixture"
        out.mkdir()
        with patch.object(MODULE.source_snapshot, "capture",
                          return_value={"snapshot_sha256": "d" * 64}), \
                self.assertRaisesRegex(RuntimeError, "new Week6 output review"):
            MODULE.produce(self.report, self.policy, out, root=self.root)


if __name__ == "__main__":
    unittest.main()
