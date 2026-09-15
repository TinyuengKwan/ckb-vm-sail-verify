"""Orchestration guards; no policy adoption or compiler execution in these tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import public_decoder_gate as public


class PublicGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='public-adapter-test-')
        self.addCleanup(temporary.cleanup)
        self.policy_path = Path(temporary.name) / 'policy.json'
        self.policy = {'inputs': 'artifacts/decoder-inputs/fixture',
                       'input_layout': 'public-decoder-rebuilt-inputs-v2',
                       'configuration': public.CONFIGURATION, 'limitations': public.LIMITATIONS}
        self.policy_path.write_text(json.dumps(self.policy))

    def test_command_forces_fresh_and_clean(self):
        command = public.command(self.policy)
        self.assertEqual(command[-2:], ['--reextract-rust', '--clean-dependencies'])
        self.assertEqual(command.count('--inputs'), 1)
        self.assertNotIn('--reuse-report', command)

    def test_main_policy_must_name_actual_public_gate(self):
        public.check_main_policy_link({'configuration': {
            'required_public_decoder_policy': str(public.POLICY.relative_to(public.main.ROOT))}})

    def test_missing_old_or_other_public_policy_link_rejected(self):
        for value in [None, 'proof/lean/decoder/public-policy.json',
                      'proof/lean/decoder/raw-rebuilt-policy.json']:
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'main/public policy link'):
                public.check_main_policy_link({'configuration': {'required_public_decoder_policy': value}})

    def test_inputs_must_stay_isolated(self):
        self.policy['inputs'] = '/tmp/unreviewed-tools'
        with self.assertRaisesRegex(RuntimeError, 'outside isolated'):
            public.command(self.policy)

    def test_legacy_layout_rejected(self):
        self.policy['input_layout'] = 'legacy-experimental'
        with self.assertRaisesRegex(RuntimeError, 'input layout'):
            public.command(self.policy)

    def test_legacy_experiment_path_rejected(self):
        self.policy['inputs'] = 'artifacts/boundary-check/old-tools'
        with self.assertRaisesRegex(RuntimeError, 'outside isolated'):
            public.command(self.policy)

    def test_unadopted_policy_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'public tool adoption'):
            public.check_policy({'schema_version': 1, 'status': 'experimental'})

    def test_configuration_change_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'configuration'):
            public.check_policy({'schema_version': 1, 'status': 'adopted-rv64-add-public-rebuilt-v2',
                                 'configuration': dict(public.CONFIGURATION, mop=True)})

    def test_omitted_limitations_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'trust boundary'):
            public.check_policy({'schema_version': 1, 'status': 'adopted-rv64-add-public-rebuilt-v2',
                                 'configuration': public.CONFIGURATION, 'limitations': []})

    def test_wrong_production_baseline_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'production baseline'):
            public.check_policy({'schema_version': 1, 'status': 'adopted-rv64-add-public-rebuilt-v2',
                'configuration': public.CONFIGURATION, 'limitations': public.LIMITATIONS,
                'production_baseline': 'unpatched-upstream'})

    def test_missing_policy_never_starts_producer(self):
        with patch.object(public, 'POLICY', self.policy_path.with_name('missing')), \
             patch.object(public, 'command') as command:
            with self.assertRaises(FileNotFoundError):
                public.execute(None, {}, {})
            command.assert_not_called()

    def test_failed_stage_does_not_accept_old_report(self):
        with patch.object(public, 'POLICY', self.policy_path), \
             patch.object(public, 'check_policy', return_value=self.policy), \
             patch.object(public.acceptance, 'validate') as validate:
            def fail(*args):
                raise RuntimeError('producer failed')
            with self.assertRaisesRegex(RuntimeError, 'producer failed'):
                public.execute(fail, {}, {})
            validate.assert_not_called()

    def test_missing_duplicate_or_external_report_rejected(self):
        for output in ['', 'Report: /tmp/a\nReport: /tmp/b\n', 'Report: /tmp/a\n']:
            with self.subTest(output=output), patch.object(public, 'POLICY', self.policy_path), \
                 patch.object(public, 'check_policy', return_value=self.policy), \
                 patch.object(public.acceptance, 'validate') as validate:
                with self.assertRaises(RuntimeError):
                    public.execute(lambda *args: output, {}, {})
                validate.assert_not_called()

    def test_success_requires_actual_producer_and_validator(self):
        events = []
        report = {}
        path = public.main.ROOT / 'artifacts/boundary-check/fixture/report.json'
        def run_stage(name, command, env, current):
            events.append(name)
            self.assertIs(current, report)
            return 'Report: ' + str(path) + '\n'
        def validate(actual):
            events.append('validate')
            self.assertEqual(actual, path)
            return {'tool_adoption_claimed': False}
        with patch.object(public, 'POLICY', self.policy_path), \
             patch.object(public, 'check_policy', return_value=self.policy), \
             patch.object(public.acceptance, 'validate', side_effect=validate):
            public.execute(run_stage, {}, report)
        self.assertEqual(events, ['public-decoder', 'validate'])
        self.assertTrue(report['public_decoder']['main_gate_adopted'])


if __name__ == '__main__':
    unittest.main()
