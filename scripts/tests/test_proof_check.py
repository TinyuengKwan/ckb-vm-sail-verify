#!/usr/bin/env python3
"""Isolated fail-closed tests; real kernel mutations live in test_lean_step.py."""

import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_proof as gate


class ProofCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ckb-proof-check-test-")
        self.addCleanup(self.temp.cleanup)
        self.artifacts = Path(self.temp.name)
        self.policy = json.loads(gate.POLICY.read_text())
        self.audit = {"theorem": self.policy["theorem"],
                      "contract_axioms": json.loads(json.dumps(self.policy["contract_axioms"])),
                      "witness_axioms": json.loads(json.dumps(self.policy["witness_axioms"])),
                      "axioms": [n for group in self.policy["axioms"].values() for n in group],
                      "boundary": {"signature": {"type": "reviewed", "definition": ""}}}
        self.policy["boundary_sha256"] = gate.boundary_hashes(self.audit)

    def test_reviewed_audit_passes(self):
        gate.check_audit(self.audit, self.policy)

    def test_additional_axiom_rejected(self):
        self.audit["axioms"].append("new_assumption")
        with self.assertRaisesRegex(RuntimeError, "axiom set"):
            gate.check_audit(self.audit, self.policy)

    def test_removed_axiom_requires_review(self):
        self.audit["axioms"].pop()
        with self.assertRaisesRegex(RuntimeError, "axiom set"):
            gate.check_audit(self.audit, self.policy)

    def test_sorry_rejected_even_if_allowlisted(self):
        self.audit["axioms"].append("sorryAx")
        self.policy["axioms"]["injected"] = ["sorryAx"]
        with self.assertRaisesRegex(RuntimeError, "sorryAx"):
            gate.check_audit(self.audit, self.policy)

    def test_strengthened_explicit_premise_rejected(self):
        self.audit["boundary"]["signature"]["type"] = "False -> reviewed"
        with self.assertRaisesRegex(RuntimeError, "signature / contract"):
            gate.check_audit(self.audit, self.policy)

    def test_changed_relation_body_rejected(self):
        self.audit["boundary"]["signature"]["definition"] = "True"
        with self.assertRaisesRegex(RuntimeError, "state relation"):
            gate.check_audit(self.audit, self.policy)

    def test_wrong_theorem_rejected(self):
        self.audit["theorem"] = "weaker_theorem"
        with self.assertRaisesRegex(RuntimeError, "theorem name"):
            gate.check_audit(self.audit, self.policy)

    def test_wrapper_contract_dependency_drift_rejected(self):
        name = next(iter(self.audit["contract_axioms"]))
        self.audit["contract_axioms"][name].append("unjustified_wrapper_law")
        with self.assertRaisesRegex(RuntimeError, "wrapper contract axiom"):
            gate.check_audit(self.audit, self.policy)

    def test_missing_or_duplicate_export_rejected(self):
        record = gate.MARKER + json.dumps(self.audit) + "\n"
        self.assertEqual(gate.parse_audit(record), self.audit)
        for log in ("", record + record):
            with self.assertRaises(RuntimeError):
                gate.parse_audit(log)

    def test_nonvacuity_witness_dependency_drift_rejected(self):
        name = next(iter(self.audit["witness_axioms"]))
        self.audit["witness_axioms"][name].append("unjustified_nonvacuity")
        with self.assertRaisesRegex(RuntimeError, "witness axiom"):
            gate.check_audit(self.audit, self.policy)

    def test_missing_nonvacuity_witness_rejected(self):
        self.audit["witness_axioms"].pop(next(iter(self.audit["witness_axioms"])))
        with self.assertRaisesRegex(RuntimeError, "witness axiom"):
            gate.check_audit(self.audit, self.policy)

    def test_source_drift_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "review required"):
            gate.require_equal({"a.lean": "changed"}, {"a.lean": "pinned"}, "sources")

    def test_generated_drift_rejected(self):
        with patch.object(gate, "tree_files", return_value={"Model.lean": "changed"}):
            with self.assertRaisesRegex(RuntimeError, "generated Lean"):
                gate.generated_evidence(self.policy)

    def test_stage_nonzero_panic_and_timeout_rejected(self):
        cases = [("exit 3", "10", RuntimeError), ("echo PANIC; exit 0", "10", RuntimeError),
                 ("sleep 3", "1", subprocess.TimeoutExpired)]
        for command, timeout, error in cases:
            with self.subTest(command=command), patch.object(gate, "ARTIFACTS", self.artifacts):
                with self.assertRaises(error):
                    gate.run_stage("fixture", ["bash", "-c", command],
                                   os.environ | {"PROOF_BUILD_TIMEOUT": timeout}, {"stages": []})

    def test_failed_rerun_replaces_previous_pass_report(self):
        gate.write_json(self.artifacts / "report.json", {"status": "passed"})
        with patch.object(gate, "ARTIFACTS", self.artifacts), \
             patch.object(gate, "execute", side_effect=RuntimeError("generation failed")):
            self.assertEqual(gate.main(["lean"]), 1)
        report = json.loads((self.artifacts / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIn("generation failed", report["error"])

    def test_unsupported_backend_never_runs_generation(self):
        with patch.object(gate, "ARTIFACTS", self.artifacts), patch.object(gate, "execute") as execute:
            self.assertEqual(gate.main(["rocq"]), 1)
            execute.assert_not_called()

    def test_no_generation_skip_argument(self):
        with patch.object(gate, "ARTIFACTS", self.artifacts), patch.object(gate, "execute") as execute:
            self.assertEqual(gate.main(["lean", "--skip-generation"]), 1)
            execute.assert_not_called()

    def test_orchestration_requires_generation_kernel_audit_and_tests(self):
        calls = []
        def stage(name, *args, **kwargs):
            calls.append(name)
            return gate.MARKER + json.dumps(self.audit)
        def public(run_stage, env, report):
            run_stage('public-decoder', [], env, report)
            return {"clean_build": {"status": "passed", "initial_compiled_modules": 0,
                    "theorem": self.policy["theorem"], "policy_sha256": "policy"}}
        report = {"stages": [], "policy_sha256": "policy"}
        with patch.object(gate, "ARTIFACTS", self.artifacts), \
             patch.object(gate, "tools_and_environment", return_value=({}, {}, Path("."), "lake")), \
             patch.object(gate, "source_evidence", return_value={}), \
             patch.object(gate, "generated_evidence", return_value={}), \
             patch.object(gate, "output", return_value="fixture"), \
             patch.object(gate, "file_hash", return_value="policy"), \
             patch('public_decoder_gate.execute', side_effect=public), \
             patch.object(gate, "run_stage", side_effect=stage):
            gate.execute(self.policy, report)
        self.assertEqual(calls, ["sail-config", "environment", "generate-rust", "generate-sail",
                                "kernel-step", "theorem-audit", "test_lean_imports",
                                "test_lean_step", "test_proof_check", "test_ckb_source_baseline",
                                "test_lean_clean", "test_decoder_public_source", "test_decoder_public_clean",
                                "test_public_decoder_acceptance", "test_public_decoder_gate",
                                "test_decoder_harness", "test_decoder_model_identity", "test_decoder_iterator_identity",
                                "test_decoder_input_bundle", "test_decoder_input_locations",
                                "test_sail_model_transaction", "test_decoder_rebuilt_inputs",
                                "test_decoder_rebuilt_locations", "test_rebuilt_main_tools",
                                "test_generate_rebuilt_rust", "test_rebuilt_production_rust",
                                "test_source_snapshot", "public-decoder"])
        self.assertEqual(report["status"], "passed")


if __name__ == "__main__":
    unittest.main()
