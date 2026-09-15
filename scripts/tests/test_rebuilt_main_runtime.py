"""Native evidence must use the reviewed candidate after generation stabilizes."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_main_runtime as runner


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = {'status': 'running', 'policy_sha256': runner.anchors.POLICY_SHA, 'stages': []}
        for name in runner.PREFIX:
            path = self.root / (name + '.log')
            path.write_text(name)
            self.report['stages'].append({'name': name, 'status': 'passed', 'exit_code': 0,
                                         'log': path.name, 'sha256': runner.sha(path)})

    def test_completed_generation_allows_running_main_without_claiming_proof_pass(self):
        self.assertEqual(runner.ready(self.report, self.root), self.report['stages'])
        self.report['stages'].append({'name': 'kernel-step', 'status': 'running'})
        self.assertEqual(len(runner.ready(self.report, self.root)), 4)

    def test_incomplete_generation_rejected(self):
        for name in runner.PREFIX:
            report = copy.deepcopy(self.report)
            next(row for row in report['stages'] if row['name'] == name)['status'] = 'running'
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'not complete'):
                runner.ready(report, self.root)

    def test_cli_refuses_incomplete_generation_before_any_producer_runs(self):
        directory = self.root / 'artifacts/proof-check'
        directory.mkdir(parents=True)
        (self.root / 'artifacts/boundary-check').mkdir()
        self.report['stages'][-1]['status'] = 'running'
        for name in runner.PREFIX:
            (directory / (name + '.log')).write_text(name)
        (directory / 'report.json').write_text(runner.json.dumps(self.report))
        with mock.patch.object(runner.anchors, 'ROOT', self.root), \
             mock.patch.object(runner.anchors, 'CANDIDATE', self.root), \
             mock.patch.object(runner.sys, 'argv', ['rebuilt_main_runtime.py']), \
             mock.patch.object(runner.subprocess, 'run') as execute, \
             mock.patch('builtins.print'):
            self.assertEqual(runner.main(), 1)
        execute.assert_not_called()
        reports = list((self.root / 'artifacts/boundary-check').glob('*/report.json'))
        self.assertEqual(len(reports), 1)
        result = runner.read(reports[0])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['stages'], [])
        self.assertIn('generation is not complete', result['error'])
        self.assertFalse(result['formal_adoption_claimed'])

    def test_wrong_main_policy_or_failure_rejected(self):
        for key, value in [('status', 'failed'), ('status', None), ('policy_sha256', 'old')]:
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                runner.ready({**self.report, key: value}, self.root)

    def test_missing_or_reordered_generation_rejected(self):
        for rows in (self.report['stages'][1:], self.report['stages'][::-1]):
            with self.assertRaisesRegex(RuntimeError, 'missing or reordered'):
                runner.ready({**self.report, 'stages': rows}, self.root)

    def test_failed_exit_and_boolean_exit_rejected(self):
        for value in (1, None, False):
            self.report['stages'][0]['exit_code'] = value
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'not complete'):
                runner.ready(self.report, self.root)

    def test_changed_or_symlinked_generation_log_rejected(self):
        path = self.root / 'sail-config.log'
        path.write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'log identity'):
            runner.ready(self.report, self.root)
        path.rename(self.root / 'saved')
        path.symlink_to('saved')
        with self.assertRaisesRegex(RuntimeError, 'log identity'):
            runner.ready(self.report, self.root)

    def installation(self):
        files = {}
        for name in ('rustc', 'cargo', 'rustdoc'):
            path = self.root / 'toolchains' / runner.STABLE / 'bin' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
            path.chmod(0o755)
            files[str(path.relative_to(self.root))] = {'sha256': runner.sha(path)}
        return {'private_homes': {'RUSTUP_HOME': str(self.root)},
                'installed_closures': {'rustup': {'files': files}}}

    def test_native_tools_explicit_and_do_not_mutate_extractor_environment(self):
        installation = self.installation()
        original = {'RUSTUP_HOME': str(self.root), 'RUSTUP_TOOLCHAIN': 'nightly',
                    'PATH': '/usr/bin:/bin', 'CARGO_TARGET_DIR': 'shared'}
        env, tools = runner.native_environment(original, installation, self.root / 'out')
        self.assertEqual(env['RUSTUP_TOOLCHAIN'], runner.STABLE)
        self.assertNotIn('CARGO_TARGET_DIR', env)
        self.assertEqual(env['PATH'].split(':')[0], str(self.root / 'toolchains' / runner.STABLE / 'bin'))
        self.assertEqual(set(tools), {'rustc', 'cargo', 'rustdoc'})
        self.assertEqual(original['RUSTUP_TOOLCHAIN'], 'nightly')
        self.assertEqual(original['CARGO_TARGET_DIR'], 'shared')

    def test_wrong_native_home_binary_permissions_and_symlink_rejected(self):
        installation = self.installation()
        env = {'RUSTUP_HOME': str(self.root), 'PATH': '/usr/bin'}
        with self.assertRaisesRegex(RuntimeError, 'home differs'):
            runner.native_environment({**env, 'RUSTUP_HOME': '/ambient'}, installation, self.root)
        path = self.root / 'toolchains' / runner.STABLE / 'bin/rustc'
        path.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'binary differs'):
            runner.native_environment(env, installation, self.root)
        path.chmod(0o755)
        path.write_text('drift')
        with self.assertRaisesRegex(RuntimeError, 'binary differs'):
            runner.native_environment(env, installation, self.root)
        path.rename(self.root / 'rustc-saved')
        path.symlink_to(self.root / 'rustc-saved')
        with self.assertRaisesRegex(RuntimeError, 'binary differs'):
            runner.native_environment(env, installation, self.root)

    def test_independent_summary_inventory_and_marker(self):
        summary = {'runtime': {'cases': 32, 'replays': 32, 'mutations': {'applied': 188, 'skipped': 4}},
                   'rust_tests': {'test_binaries': 7, 'tests_passed': 78, 'engine_tests': 10,
                                  'doctest_targets': 5, 'doctests_passed': 0, 'ignored': 0, 'filtered_out': 0}}
        line = runner.MARKER + runner.json.dumps(summary)
        self.assertEqual(runner.parse_check('compiler warning\n' + line), summary)
        for text in ('{}', line + '\n' + line, runner.MARKER + '{}'):
            with self.assertRaises(RuntimeError):
                runner.parse_check(text)
        for key in summary['rust_tests']:
            changed = copy.deepcopy(summary)
            changed['rust_tests'][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'test inventory'):
                runner.parse_check(runner.MARKER + runner.json.dumps(changed))
        summary['runtime']['cases'] = 31
        with self.assertRaisesRegex(RuntimeError, 'corpus inventory'):
            runner.parse_check(runner.MARKER + runner.json.dumps(summary))


if __name__ == '__main__':
    unittest.main()
