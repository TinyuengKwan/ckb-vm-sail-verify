#!/usr/bin/env python3
"""Fail-closed NO-GO classification tests; actual compilation is separate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rocq_spike as spike


RUST = "Error:\nIn environment\ncore_cmp_PartialEq_t : Type -> Type -> Type\n" + spike.RUST_ERROR
SAIL = "Error: " + spike.SAIL_ERROR


class DiagnosticTests(unittest.TestCase):
    def test_exact_reviewed_errors(self):
        spike.check_failure("rust", 1, RUST)
        spike.check_failure("sail", 1, SAIL)

    def test_unexpected_success_fails(self):
        for kind, text in [("rust", RUST), ("sail", SAIL)]:
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                spike.check_failure(kind, 0, text)

    def test_signal_or_other_exit_fails(self):
        for code in [-9, 2, 124, 137]:
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                spike.check_failure("sail", code, SAIL)

    def test_unrelated_type_error_fails(self):
        for kind in ["rust", "sail"]:
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                spike.check_failure(kind, 1, "Error: The term has type nat, expected bool.")

    def test_resource_or_import_failure_not_accepted(self):
        for message in ["out of memory", "Stack overflow", "Cannot find a physical path",
                        "No such file", "Segmentation fault", "Anomaly", "Timed out"]:
            with self.subTest(message=message), self.assertRaises(RuntimeError):
                spike.check_failure("sail", 1, message + "\n" + SAIL)

    def test_missing_or_multiple_error_markers_fail(self):
        for text in ["", spike.SAIL_ERROR, SAIL + "\n" + SAIL]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                spike.check_failure("sail", 1, text)

    def test_wrong_rust_declaration_fails(self):
        with self.assertRaises(RuntimeError):
            spike.check_failure("rust", 1, RUST.replace("core_cmp_PartialEq_t", "unrelated"))

    def test_unknown_classifier_fails(self):
        with self.assertRaises(RuntimeError):
            spike.check_failure("other", 1, SAIL)

    def test_expected_package_pins(self):
        text = "\n".join(k + " " + v for k, v in spike.PACKAGES.items())
        self.assertEqual(spike.check_packages(text), spike.PACKAGES)

    def test_missing_changed_or_duplicate_package_fails(self):
        text = "\n".join(k + " " + v for k, v in spike.PACKAGES.items())
        for bad in ["", text.replace("9.1.1", "9.2.0"), text + "\nocaml 5.2.1"]:
            with self.subTest(text=bad), self.assertRaises(RuntimeError):
                spike.check_packages(bad)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rocq-spike-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_inputs_fail_before_any_compiler(self):
        out = self.root / "out"
        out.mkdir()
        with patch.object(spike, "ROOT", self.root), patch.object(spike.proof, "tools_and_environment") as tool:
            with self.assertRaisesRegex(RuntimeError, "no SKIP"):
                spike.execute(out, {"stages": []})
            tool.assert_not_called()

    def rebuilt_fixture(self):
        policy = self.root / 'policy.json'
        policy.write_text(json.dumps({'main_toolchain': 'rebuilt-main-v1'}))
        env = {'OPAMROOT': '/private/aeneas', 'OPAMSWITCH': 'isolated-aeneas'}
        installation = {'switch': 'isolated-rocq', 'opam_root': '/private/rocq',
                        'opam_bootstrap': {'path': '/usr/bin/opam'},
                        'binaries': {'rocq': {'path': '/private/rocq/bin/rocq'}}}
        return policy, env, installation

    def test_rebuilt_entry_generates_sail_before_any_compilation(self):
        policy, env, installation = self.rebuilt_fixture()
        with patch.object(spike, 'ROOT', self.root), patch.object(spike.proof, 'POLICY', policy), \
             patch.object(spike, 'inputs', return_value={}) as inputs, \
             patch.object(spike.proof, 'tools_and_environment', return_value=(env, {'aeneas': Path('/aeneas')}, self.root, 'lake')), \
             patch.object(spike.proof, 'source_evidence', return_value={}), \
             patch.object(spike.proof, 'generated_evidence', return_value={}), \
             patch.object(spike.rebuilt_context, 'resolve', return_value=(installation, {'rocq': 'environment'}, {})), \
             patch.dict(os.environ, {}, clear=True), \
             patch.object(spike, 'stage', side_effect=RuntimeError('stop before actual generation')) as stage, \
             self.assertRaisesRegex(RuntimeError, 'stop before actual'):
            spike.execute(self.root / 'out', {'stages': []})
        inputs.assert_called_once_with(self.root, include_sail=False, rebuilt=True)
        self.assertEqual(stage.call_args.args[2:6], (env, 'sail-generate',
                         ['bash', 'scripts/generate_proof_model.sh', 'rocq'], self.root))
        self.assertEqual(stage.call_args.kwargs['timeout'], 3600)

    def test_rebuilt_entry_refuses_conflicting_ambient_switch(self):
        policy, env, installation = self.rebuilt_fixture()
        with patch.object(spike, 'ROOT', self.root), patch.object(spike.proof, 'POLICY', policy), \
             patch.object(spike, 'inputs', return_value={}), \
             patch.object(spike.proof, 'tools_and_environment', return_value=(env, {'aeneas': Path('/aeneas')}, self.root, 'lake')), \
             patch.object(spike.proof, 'source_evidence', return_value={}), \
             patch.object(spike.proof, 'generated_evidence', return_value={}), \
             patch.object(spike.rebuilt_context, 'resolve', return_value=(installation, {}, {})), \
             patch.dict(os.environ, {'ROCQ_SPIKE_SWITCH': 'ambient'}, clear=True), \
             patch.object(spike, 'stage') as stage, self.assertRaisesRegex(RuntimeError, 'conflicting Rocq'):
            spike.execute(self.root / 'out', {'stages': []})
        stage.assert_not_called()

    def test_default_directories_are_unique(self):
        first = spike.new_directory(self.root)
        second = spike.new_directory(self.root)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_dir() and second.is_dir())

    def test_existing_requested_directory_is_preserved(self):
        sentinel = self.root / "previous.log"
        sentinel.write_text("old evidence")
        with self.assertRaises(FileExistsError):
            spike.new_directory(self.root, str(self.root))
        self.assertEqual(sentinel.read_text(), "old evidence")

    def test_new_requested_directory_supported(self):
        target = self.root / "fresh"
        self.assertEqual(spike.new_directory(self.root, str(target)), target)

    def test_real_nonzero_success_stage_records_failure(self):
        report = {"stages": []}
        with self.assertRaises(RuntimeError):
            spike.stage(self.root, report, None, "bad-generation",
                        [sys.executable, "-c", "raise SystemExit(2)"], self.root)
        row = json.loads((self.root / "report.json").read_text())["stages"][0]
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["exit_code"], 2)
        self.assertEqual(row["log_sha256"], spike.sha(self.root / row["log"]))

    def test_timeout_records_failure_not_no_go(self):
        report = {"stages": []}
        with patch.object(spike.subprocess, "run", side_effect=subprocess.TimeoutExpired("rocq", 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                spike.stage(self.root, report, None, "timed", ["rocq"], self.root, "sail")
        self.assertEqual(report["stages"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
