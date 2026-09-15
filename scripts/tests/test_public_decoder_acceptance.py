"""Reject missing/stale/failed public evidence before main-gate integration."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from public_decoder_acceptance import STAGES, MODELS, check_shape, check_models, main
import decoder_model_identity as identity
import public_decoder_acceptance as acceptance
import public_decoder_gate as public_gate


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
        self.assertEqual(len(STAGES), 48)

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
        public = b'import Aeneas\ndef fixture : Nat := 1\n'
        iterator = b'import Aeneas\ndef iteratorFixture : Nat := 2\n'
        contents = {'OuterClosedDepsV3.lean': public,
                    'OuterRawLinked.lean': public.replace(b'import Aeneas\n',
                        b'import Aeneas\nimport CkbVmProduction\n'), 'FnPtrFullMir.lean': iterator}
        approved = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
        for mock in [patch.dict(MODELS, approved),
                     patch.object(identity, 'APPROVED_SHA256', approved['OuterClosedDepsV3.lean']),
                     patch.object(identity, 'ITERATOR_SHA256', approved['FnPtrFullMir.lean'])]:
            mock.start()
            self.addCleanup(mock.stop)
        self.models = {}
        for name, data in contents.items():
            path = self.directory / name
            path.write_bytes(data)
            self.models[str(path)] = approved[name]

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

    def test_linkage_cannot_change_with_self_reported_hash(self):
        path = self.directory / 'OuterRawLinked.lean'
        path.write_bytes(path.read_bytes().replace(b'CkbVmProduction', b'FakeProduction'))
        self.models[str(path)] = main.file_hash(path)
        with self.assertRaisesRegex(RuntimeError, 'import linkage changed'):
            check_models(self.models, self.directory)


class InstalledEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='installed-evidence-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory = self.root / 'run'
        self.directory.mkdir()
        self.installed = {'directory': str(self.root / 'artifacts/decoder-inputs/fixture'),
                          'payload': str(self.root / 'artifacts/decoder-inputs/fixture/payload')}
        policy_path = self.root / 'policy.json'
        policy_path.write_text(json.dumps({'input_layout': 'public-decoder-rebuilt-inputs-v2',
                                           'inputs': 'artifacts/decoder-inputs/fixture'}))
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(public_gate, 'POLICY', policy_path))
        stack.enter_context(patch.object(main, 'ROOT', self.root))
        self.loader = stack.enter_context(patch.object(acceptance.locations, 'load', return_value=self.installed))
        stack.enter_context(patch.object(acceptance.locations, 'runtime', return_value={'runtime': 'fixed'}))
        config = Path(self.installed['payload']) / 'candidate/extraction.json'
        config.parent.mkdir(parents=True); config.write_text('{}')
        self.harness = {'files': {'lib.rs': 'approved'}}
        stack.enter_context(patch.object(acceptance.harness, 'verify', return_value=self.harness))
        self.compare = stack.enter_context(patch.object(acceptance.locations, 'check_extraction',
                                                         return_value={'only_locations': True}))
        rows = {}
        for name in ['OuterClosedDepsV3.llbc', 'FnPtrFullMir.llbc']:
            path = self.directory / name
            path.write_text(json.dumps({'translated': {'options': {'include': ['approved']}}}))
            rows[name] = {'sha256': main.file_hash(path), 'options': {'include': ['approved']},
                          'location_mapping': {'only_locations': True}}
        self.report = {'installed_inputs': self.installed,
            'clean_dependencies': {'installed_inputs': self.installed},
            'source_reextraction': {'installed_inputs': self.installed, 'harness_before': self.harness,
                                   'runtime_before': {'runtime': 'fixed'}, 'runtime_after': {'runtime': 'fixed'},
                                   'configuration_sha256': main.file_hash(config),
                                   'harness_after': self.harness, 'inputs': rows}}

    def check(self):
        return acceptance.check_installed_evidence(self.report, self.directory)

    def test_reopens_both_fresh_roots_and_installed_package(self):
        self.assertEqual(self.check(), self.installed)
        self.loader.assert_called_once_with(Path(self.installed['directory']))
        self.assertEqual({call.args[2] for call in self.compare.call_args_list},
                         {'OuterClosedDepsV3.llbc', 'FnPtrFullMir.llbc'})

    def test_missing_or_bad_package_never_falls_back(self):
        self.loader.side_effect = FileNotFoundError('missing installed package')
        with self.assertRaises(FileNotFoundError):
            self.check()
        self.compare.assert_not_called()

    def test_different_package_for_extraction_or_clean_rejected(self):
        for key in ['source_reextraction', 'clean_dependencies']:
            with self.subTest(key=key):
                self.report[key]['installed_inputs'] = {'payload': 'other'}
                with self.assertRaisesRegex(RuntimeError, 'different installed inputs'):
                    self.check()
                self.report[key]['installed_inputs'] = self.installed

    def test_harness_drift_rejected(self):
        self.report['source_reextraction']['harness_after'] = {}
        with self.assertRaisesRegex(RuntimeError, 'harness identity'):
            self.check()

    def test_omitted_or_extra_root_rejected(self):
        self.report['source_reextraction']['inputs'].pop('FnPtrFullMir.llbc')
        with self.assertRaisesRegex(RuntimeError, 'roots incomplete'):
            self.check()

    def test_changed_llbc_rejected(self):
        (self.directory / 'FnPtrFullMir.llbc').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'LLBC changed'):
            self.check()

    def test_self_reported_options_and_mapping_rejected(self):
        row = self.report['source_reextraction']['inputs']['OuterClosedDepsV3.llbc']
        row['options'] = {}
        with self.assertRaisesRegex(RuntimeError, 'reported extraction options'):
            self.check()
        row['options'] = {'include': ['approved']}
        row['location_mapping'] = {}
        with self.assertRaisesRegex(RuntimeError, 'location mapping differs'):
            self.check()

    def test_option_identity_failure_is_propagated(self):
        self.compare.side_effect = RuntimeError('actual extraction options changed')
        with self.assertRaisesRegex(RuntimeError, 'actual extraction options changed'):
            self.check()


if __name__ == '__main__':
    unittest.main()
