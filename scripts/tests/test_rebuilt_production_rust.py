"""Staged extraction must preserve production selections and failure evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_production_rust as production


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.config = production.configuration(production.ROOT)

    def test_exact_production_selectors_and_explicit_sysroot(self):
        command = production.extraction_command('/base/charon', '/out/model.llbc', '/verified/std', self.config)
        self.assertEqual(command[:8], ['/base/charon', 'cargo', '--preset=aeneas', '--sysroot',
                                      '/verified/std', '--dest-file', '/out/model.llbc', '--start-from'])
        self.assertEqual(command[8], self.config['root'])
        expected = []
        for flag in ('include', 'opaque'):
            for name in self.config[flag]: expected.extend(['--' + flag, name])
        self.assertEqual(command[9:], expected + ['--', '--lib'])

    def test_wrong_preset_rejected(self):
        config = {**self.config, 'preset': 'different'}
        with self.assertRaisesRegex(RuntimeError, 'preset'):
            production.extraction_command('charon', 'out', 'std', config)

    def test_selection_identity_checked_before_json(self):
        with patch.object(production, 'sha', return_value='wrong'), patch.object(production, 'read') as read:
            with self.assertRaisesRegex(RuntimeError, 'selection changed'):
                production.configuration(Path('/unused'))
            read.assert_not_called()

    def test_historical_tool_label_not_rewritten(self):
        self.assertEqual(self.config['aeneas'], 'aeneas nightly-2026.09.01-379890b')
        self.assertNotEqual(self.config['aeneas'], 'aeneas 379890b5')

    def test_model_identity_requires_fixed_whole_file(self):
        with patch.object(production, 'sha', return_value=production.MODEL_SHA):
            self.assertEqual(production.model_identity('fresh', 'archive'),
                             {'sha256': production.MODEL_SHA, 'whole_file_identical': True,
                              'normalization_used': False})

    def test_changed_or_cochanged_models_rejected(self):
        for digests in ([production.MODEL_SHA, 'wrong'], ['wrong', 'wrong']):
            with self.subTest(digests=digests), patch.object(production, 'sha', side_effect=digests):
                with self.assertRaisesRegex(RuntimeError, 'whole-file identity'):
                    production.model_identity('fresh', 'archive')

    def test_stage_failure_retains_exit_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = {'stages': []}
            with self.assertRaisesRegex(RuntimeError, 'stage failed'):
                production.stage(report, out, 'fail', [sys.executable, '-c',
                    'print("intentional failure"); raise SystemExit(7)'], out, {})
            saved = json.loads((out / 'report.json').read_text())['stages'][0]
            self.assertEqual(saved['exit_code'], 7)
            self.assertEqual(saved['log_sha256'], production.sha(out / 'fail.log'))
            self.assertIn('intentional failure', (out / 'fail.log').read_text())

    def test_stage_timeout_retained_not_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = {'stages': []}
            with patch.object(production.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['tool'], 900)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    production.stage(report, out, 'timeout', ['tool'], out, {})
            self.assertNotIn('exit_code', report['stages'][0])
            self.assertEqual(report['stages'][0]['log_sha256'], production.sha(out / 'timeout.log'))

    def test_invalid_inputs_leave_failed_report_no_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(production, 'input_state', return_value={}), \
                 patch.object(production.locations, 'configuration', side_effect=RuntimeError('not admitted')), \
                 patch.object(production, 'clone_source') as clone:
                self.assertEqual(production.run(out, Path('/bad')), 1)
                clone.assert_not_called()
            report = json.loads((out / 'report.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['error'], 'not admitted')
            self.assertTrue(all(report[key] is False for key in production.BOUNDARIES))

    def test_existing_output_rejected_before_run(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sys, 'argv', ['stager', '--out', directory]), patch.object(production, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'already exists'):
                    production.main()
                run.assert_not_called()

    def test_environment_clears_public_flags_and_uses_new_caches(self):
        runtime = {'rustup_home': '/private/rust', 'opam_root': '/private/opam', 'opam_switch': 'fixed'}
        config = {'rust_toolchain': 'fixed-nightly'}
        with patch.dict(production.locations.os.environ, {'AENEAS_RELAXED': '1', 'RUSTC_WRAPPER': 'old',
                        'CARGO_TARGET_DIR': '/old', 'CHARON_CACHE_DIR': '/old', 'LD_PRELOAD': '/old'}, clear=True):
            env = production.locations.environment(Path('/fresh'), runtime, config)
        self.assertFalse(any(key.startswith('AENEAS') for key in env))
        self.assertNotIn('RUSTC_WRAPPER', env)
        self.assertNotIn('LD_PRELOAD', env)
        self.assertEqual(env['CARGO_TARGET_DIR'], '/fresh/cargo-target')
        self.assertEqual(env['CHARON_CACHE_DIR'], '/fresh/charon-cache')
        self.assertEqual(env['RUSTUP_HOME'], '/private/rust')

    def test_translation_uses_explicit_private_opam(self):
        runtime = {'opam_bootstrap': {'path': '/usr/bin/opam'}, 'opam_switch': 'fixed'}
        args = [*self.config['aeneas_args'], '-dest', '/out', '/fresh.llbc']
        before = copy.deepcopy(args)
        command = production.locations.translator_command(runtime, '/base/aeneas', args)
        self.assertEqual(command, ['/usr/bin/opam', 'exec', '--switch=fixed', '--set-switch', '--',
                                   '/base/aeneas', *args])
        self.assertEqual(args, before)


if __name__ == '__main__':
    unittest.main()
