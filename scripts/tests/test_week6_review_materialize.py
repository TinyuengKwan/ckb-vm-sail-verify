#!/usr/bin/env python3
import copy
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
    "week6_review_materialize", HERE.parent / "week6_review_materialize.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CANDIDATE = "a" * 40


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "artifacts/boundary-check").mkdir(parents=True)
        (self.root / "docs/release").mkdir(parents=True)
        (self.root / "proof/lean/extraction").mkdir(parents=True)
        (self.root / "proof/lean/extraction/ADOPTION.md").write_text("review evidence\n")
        self.policy_path = self.root / "docs/release/week6-review-policy-v1.json"
        self.policy = {
            "schema_version": 1, "kind": "week6-source-review-policy-v1",
            "reviewed_by": "fixture reviewer record", "require_root_repository_clean": True,
            "allowed_source_changes": {
                ".": {},
                "deps/ckb-vm": {
                    "src/machine/mod.rs": {
                        "operation": "modified", "category": "production",
                        "rationale": "fixture reviewed patch",
                        "evidence": ["proof/lean/extraction/ADOPTION.md"],
                    },
                    "tests/runtime_container_probe.rs": {
                        "operation": "added", "category": "test",
                        "rationale": "fixture regression probe",
                        "evidence": ["proof/lean/extraction/ADOPTION.md"],
                    },
                },
                "deps/sail-riscv": {},
            },
            "output_review": {
                "allowed_root_prefixes": ["artifacts/boundary-check/week6-formal-review-"],
                "registry_marker": "/cargo/registry/", "build_markers": ["/target/"],
            },
            "boundaries": {name: False for name in MODULE.POLICY_BOUNDARIES},
        }
        self.snapshot = {
            "schema_version": 1,
            "identity_kind": "HEAD-plus-byte-inventoried-working-tree-not-a-commit",
            "repositories": {
                ".": {"head": CANDIDATE, "gitlinks": {}, "files": {}, "changes_from_head": {}},
                "deps/ckb-vm": {"head": "b" * 40, "gitlinks": {}, "files": {},
                    "changes_from_head": {
                        "src/machine/mod.rs": {"operation": "modified", "before": {"git_blob": "x"},
                                                "after": {"sha256": "1" * 64}},
                        "tests/runtime_container_probe.rs": {"operation": "added", "before": None,
                                                              "after": {"sha256": "2" * 64}},
                    }},
                "deps/sail-riscv": {"head": "c" * 40, "gitlinks": {}, "files": {},
                                     "changes_from_head": {}},
            },
            "ckb_source_baseline": {}, "ignored_build_and_evidence_files_included": False,
            "semantic_review_claimed": False, "snapshot_sha256": "d" * 64,
        }
        self.write_policy()

    def tearDown(self):
        self.temporary.cleanup()

    def write_policy(self):
        self.policy_path.write_text(json.dumps(self.policy) + "\n")

    def materialize(self, name="week6-review-fixture"):
        out = self.root / "artifacts/boundary-check" / name
        with patch.object(MODULE.source_snapshot, "capture", return_value=copy.deepcopy(self.snapshot)):
            return MODULE.materialize(CANDIDATE, self.policy_path, out, root=self.root), out

    def test_materializes_source_review_accepted_by_existing_validator(self):
        result, out = self.materialize()
        self.assertEqual(result["remaining"], ["fresh_formal_output_review",
                                               "explicit_profile_A_delivery_approval"])
        self.assertEqual(result["validated"]["reviewed_head_changes"], 2)
        review = json.loads((out / "source-review.json").read_text())
        row = review["reviews"]["deps/ckb-vm"]["src/machine/mod.rs"]
        self.assertEqual(row["reviewed_by"], "fixture reviewer record")
        self.assertFalse(result["boundaries"]["worktree_audit_closed"])

    def test_rejects_unlisted_change(self):
        self.snapshot["repositories"]["deps/ckb-vm"]["changes_from_head"]["new.rs"] = {
            "operation": "added", "before": None, "after": {"sha256": "3" * 64}}
        with self.assertRaisesRegex(RuntimeError, "unlisted/missing source change"):
            self.materialize()

    def test_rejects_dirty_root_candidate(self):
        self.snapshot["repositories"]["."]["changes_from_head"]["README.md"] = {
            "operation": "modified", "before": {}, "after": {}}
        with self.assertRaisesRegex(RuntimeError, "root repository is not clean"):
            self.materialize()

    def test_rejects_changed_operation(self):
        self.policy["allowed_source_changes"]["deps/ckb-vm"]["src/machine/mod.rs"]["operation"] = "added"
        self.write_policy()
        with self.assertRaisesRegex(RuntimeError, "operation differs"):
            self.materialize()

    def test_rejects_policy_assurance_upgrade(self):
        self.policy["boundaries"]["delivery_approval_claimed"] = True
        self.write_policy()
        with self.assertRaisesRegex(RuntimeError, "assurance upgrade"):
            self.materialize()

    def test_rejects_existing_output(self):
        out = self.root / "artifacts/boundary-check/week6-review-fixture"
        out.mkdir()
        with self.assertRaisesRegex(RuntimeError, "new Week6 review output"):
            self.materialize()

    def test_rejects_candidate_different_from_head(self):
        self.snapshot["repositories"]["."]["head"] = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "candidate differs"):
            self.materialize()

    def envelope_inputs(self):
        refs = {}
        for name in ["source", "producer", "generation-review", "observation", "registry",
                     "build", "record", "confirmation", "approval"]:
            path = self.root / (name + ".json")
            path.write_text("{}\n")
            refs[name] = {"path": path.name, "sha256": MODULE.sha(path)}
        value = {
            "schema_version": 1, "kind": "week6-worktree-envelope-inputs-v1",
            "candidate": CANDIDATE, "source_review": refs["source"],
            "generation": {"producer": refs["producer"], "review": refs["generation-review"]},
            "source_increment": None,
            "output_identity": {"observation": refs["observation"],
                                "registry_review": refs["registry"], "build_review": refs["build"],
                                "record_review": refs["record"], "confirmation": refs["confirmation"]},
            "approval": refs["approval"],
        }
        path = self.root / "inputs.json"
        path.write_text(json.dumps(value) + "\n")
        return path, value

    def preapproval_inputs(self):
        inputs, value = self.envelope_inputs()
        value.pop("approval")
        value["kind"] = "week6-worktree-preapproval-inputs-v1"
        inputs.write_text(json.dumps(value) + "\n")
        return inputs, value

    def test_connects_v3_but_retains_approval_and_formal_linkage(self):
        inputs, _ = self.preapproval_inputs()
        out = self.root / "artifacts/boundary-check/week6-review-preapproval"
        expected = ["final_delivery_scope_and_semantic_approval", MODULE.worktree.EXECUTION_LINKAGE]
        checked = {"delivery_approval_verified": False, "remaining": expected,
                   "worktree_audit_closed": False}
        with patch.object(MODULE.worktree, "check", return_value=checked) as validator:
            result = MODULE.connect_preapproval(CANDIDATE, inputs, out, root=self.root)
        envelope = json.loads((out / "worktree-envelope.json").read_text())
        self.assertEqual(envelope["schema_version"], 3)
        self.assertEqual(envelope["kind"], "worktree-record-review-v3")
        self.assertNotIn("approval", envelope)
        self.assertEqual(result["remaining"], expected)
        self.assertFalse(result["boundaries"]["delivery_approval_claimed"])
        validator.assert_called_once()

    def test_preapproval_rejects_checker_that_drops_approval_obligation(self):
        inputs, _ = self.preapproval_inputs()
        out = self.root / "artifacts/boundary-check/week6-review-preapproval"
        checked = {"delivery_approval_verified": False,
                   "remaining": [MODULE.worktree.EXECUTION_LINKAGE],
                   "worktree_audit_closed": False}
        with patch.object(MODULE.worktree, "check", return_value=checked), \
                self.assertRaisesRegex(RuntimeError, "retain exactly approval"):
            MODULE.connect_preapproval(CANDIDATE, inputs, out, root=self.root)

    def test_preapproval_rejects_approval_field(self):
        inputs, value = self.preapproval_inputs()
        value["approval"] = {"path": "approval.json", "sha256": "0" * 64}
        inputs.write_text(json.dumps(value) + "\n")
        out = self.root / "artifacts/boundary-check/week6-review-preapproval"
        with self.assertRaisesRegex(RuntimeError, "preapproval input fields"):
            MODULE.connect_preapproval(CANDIDATE, inputs, out, root=self.root)
        self.assertFalse(out.exists())

    def test_connects_v4_but_retains_formal_linkage(self):
        inputs, _ = self.envelope_inputs()
        out = self.root / "artifacts/boundary-check/week6-review-envelope"
        checked = {"delivery_approval_verified": True,
                   "remaining": [MODULE.worktree.EXECUTION_LINKAGE],
                   "worktree_audit_closed": False}
        with patch.object(MODULE.worktree, "check", return_value=checked) as validator:
            result = MODULE.connect(CANDIDATE, inputs, out, root=self.root)
        envelope = json.loads((out / "worktree-envelope.json").read_text())
        self.assertEqual(envelope["schema_version"], 4)
        self.assertEqual(envelope["source_increment"], None)
        self.assertTrue(all(value is False for value in envelope["boundaries"].values()))
        self.assertEqual(result["remaining"], [MODULE.worktree.EXECUTION_LINKAGE])
        validator.assert_called_once()

    def test_connect_rejects_checker_that_claims_premature_closure(self):
        inputs, _ = self.envelope_inputs()
        out = self.root / "artifacts/boundary-check/week6-review-envelope"
        checked = {"delivery_approval_verified": True, "remaining": [],
                   "worktree_audit_closed": True}
        with patch.object(MODULE.worktree, "check", return_value=checked), \
                self.assertRaisesRegex(RuntimeError, "retain exactly"):
            MODULE.connect(CANDIDATE, inputs, out, root=self.root)

    def test_connect_rejects_changed_reference_before_output(self):
        inputs, value = self.envelope_inputs()
        value["approval"]["sha256"] = "0" * 64
        inputs.write_text(json.dumps(value) + "\n")
        out = self.root / "artifacts/boundary-check/week6-review-envelope"
        with self.assertRaisesRegex(RuntimeError, "approval reference differs"):
            MODULE.connect(CANDIDATE, inputs, out, root=self.root)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
