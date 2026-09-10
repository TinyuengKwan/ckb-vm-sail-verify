"""Reject missing/stale/failed public evidence before main-gate integration."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from public_decoder_acceptance import STAGES, MODELS, check_shape, check_models, main


class PublicAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            'status': 'EXPERIMENTAL_PUBLIC_CHECK_PASS', 'rust_reextracted': True,
            'clean_dependency_build': True, 'weakened_premise_rejected_by_type_audit': True,
            'clean_dependencies': {'status': 'passed', 'initial_compiled_modules': 0,
                'main_policy_sha256': 'pinned', 'main_axiom_count': 137,
                'field_theorem_count': 9, 'raw_theorem_count': 15},
            'stages': [{'stage': name, 'exit_code': 1 if name == 'negative-wrong-public' else 0}
                       for name in STAGES],
            'protected_before': {'source': 'same'}, 'protected_after': {'source': 'same'},
            'source_reextraction': {'cargo_target_initially_absent': True,
                'source_before': {'rust': 'same'}, 'source_after': {'rust': 'same'}}}

    def test_complete_shape(self):
        check_shape(self.report, 'pinned')
        self.assertEqual(len(STAGES), 47)

    def test_failure_or_running_is_not_pass(self):
        for status in ['FAIL', 'running']:
            self.report['status'] = status
            with self.assertRaisesRegex(RuntimeError, 'did not pass'):
                check_shape(self.report, 'pinned')

    def test_reused_dependencies_or_archived_rust_rejected(self):
        for key in ['rust_reextracted', 'clean_dependency_build', 'weakened_premise_rejected_by_type_audit']:
            report = copy.deepcopy(self.report)
            report[key] = False
            with self.assertRaisesRegex(RuntimeError, 'missing required'):
                check_shape(report, 'pinned')

    def test_compiled_initial_input_rejected(self):
        self.report['clean_dependencies']['initial_compiled_modules'] = 1
        with self.assertRaisesRegex(RuntimeError, 'compiled input'):
            check_shape(self.report, 'pinned')

    def test_stale_policy_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'stale main policy'):
            check_shape(self.report, 'different')

    def test_incomplete_lower_audit_rejected(self):
        self.report['clean_dependencies']['raw_theorem_count'] = 14
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            check_shape(self.report, 'pinned')

    def test_missing_duplicate_reordered_stage_rejected(self):
        for stages in [self.report['stages'][:-1], self.report['stages'] + self.report['stages'][:1],
                       list(reversed(self.report['stages']))]:
            report = copy.deepcopy(self.report)
            report['stages'] = stages
            with self.assertRaisesRegex(RuntimeError, 'stages missing'):
                check_shape(report, 'pinned')

    def test_unexpected_kernel_failure_rejected(self):
        self.report['stages'][0]['exit_code'] = 1
        with self.assertRaisesRegex(RuntimeError, 'unexpected stage exit'):
            check_shape(self.report, 'pinned')

    def test_wrong_result_must_actually_fail(self):
        next(s for s in self.report['stages'] if s['stage'] == 'negative-wrong-public')['exit_code'] = 0
        with self.assertRaisesRegex(RuntimeError, 'unexpected stage exit'):
            check_shape(self.report, 'pinned')

    def test_source_drift_rejected(self):
        self.report['protected_after']['source'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'source/policy drift'):
            check_shape(self.report, 'pinned')

    def test_cargo_cache_reuse_rejected(self):
        self.report['source_reextraction']['cargo_target_initially_absent'] = False
        with self.assertRaisesRegex(RuntimeError, 'Cargo target'):
            check_shape(self.report, 'pinned')

    def test_rust_input_drift_rejected(self):
        self.report['source_reextraction']['source_after']['rust'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'Rust extraction source drift'):
            check_shape(self.report, 'pinned')


class PublicModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='public-model-guard-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        original = main.ROOT / 'artifacts/boundary-check/public-check-7tj_85_6/report.json'
        self.models = {}
        for name, digest in json.loads(original.read_text())['models'].items():
            path = self.directory / Path(name).name
            shutil.copyfile(name, path)
            self.models[str(path)] = digest

    def test_exact_reviewed_models(self):
        check_models(self.models, self.directory)

    def test_omitted_model_rejected(self):
        self.models.pop(next(iter(self.models)))
        with self.assertRaisesRegex(RuntimeError, 'model set incomplete'):
            check_models(self.models, self.directory)

    def test_changed_bytes_rejected(self):
        Path(next(iter(self.models))).write_text('changed model')
        with self.assertRaisesRegex(RuntimeError, 'model changed'):
            check_models(self.models, self.directory)

    def test_self_reported_hash_cannot_approve_changed_model(self):
        path = Path(next(iter(self.models)))
        path.write_text('changed model')
        self.models[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, 'unreviewed generated model'):
            check_models(self.models, self.directory)

    def test_external_model_rejected(self):
        name = next(iter(self.models))
        digest = self.models.pop(name)
        self.models[str(self.directory.parent / Path(name).name)] = digest
        with self.assertRaisesRegex(RuntimeError, 'outside evidence directory'):
            check_models(self.models, self.directory)


if __name__ == '__main__':
    unittest.main()
