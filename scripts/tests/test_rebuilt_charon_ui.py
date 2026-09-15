import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_rebuilt_charon_ui as p


class RebuiltUITests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='rebuilt-ui-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.out = self.root / 'out'
        self.out.mkdir()
        self.name = 'charon/tests/ui/example.rs'
        self.fixture = self.source / self.name
        self.fixture.parent.mkdir(parents=True)
        self.fixture.write_text('pub fn test() {}\n')
        self.fixture.with_suffix('.out').write_text('expected\n')

    def record(self, code=0, stdout='expected\n', stderr='', stream='stdout'):
        row = {'new_fixture': False, 'stream': stream, 'check_golden': True, 'results': {},
               'same_exit_code': True, 'same_selected_output': True, 'status': 'pair-identical'}
        for side in ('baseline', 'candidate'):
            folder = self.out / 'logs/tests/ui/example' / side
            folder.mkdir(parents=True, exist_ok=True)
            result = {'exit_code': code, 'status': 'command-failed' if code else 'golden-pass'}
            for channel, text in [('stdout', stdout), ('stderr', stderr)]:
                path = folder / (channel + '.log')
                path.write_text(text)
                result[channel + '_sha256'] = p.sha(path)
            selected = stdout if stream == 'stdout' else stderr
            result['normalized_output_sha256'] = p.chain.proof.digest(p.driver.normalize(selected).encode())
            row['results'][side] = result
        return row

    def inspect(self, row):
        return p.inspect_case(self.name, row, self.out, self.source, {self.name})

    def test_golden_success_recomputed(self):
        row = self.record()
        self.assertEqual(self.inspect(row), row)

    def test_shared_command_failure_not_golden_success(self):
        row = self.record(code=2, stdout='', stderr='actual failure\n')
        self.assertEqual(self.inspect(row)['results']['candidate']['status'], 'command-failed')
        row['results']['candidate']['status'] = 'golden-pass'
        with self.assertRaisesRegex(RuntimeError, 'misclassified'):
            self.inspect(row)

    def test_changed_stderr_rejected_even_when_stdout_compared(self):
        row = self.record()
        (self.out / 'logs/tests/ui/example/candidate/stderr.log').write_text('new error\n')
        with self.assertRaisesRegex(RuntimeError, 'hash differs'):
            self.inspect(row)

    def test_known_failure_compares_stderr(self):
        self.fixture.write_text('//@ known-failure\npub fn test() {}\n')
        row = self.record(stdout='ignored by golden\n', stderr='expected\n', stream='stderr')
        self.inspect(row)
        row['stream'] = 'stdout'
        with self.assertRaisesRegex(RuntimeError, 'directives changed'):
            self.inspect(row)

    def test_ignore_requires_actual_fixture_directive(self):
        ignored = {'new_fixture': False, 'status': 'ignored'}
        self.fixture.write_text('//@ ignore\npub fn test() {}\n')
        self.assertEqual(self.inspect(ignored), ignored)
        self.fixture.write_text('pub fn test() {}\n')
        with self.assertRaises((RuntimeError, KeyError)):
            self.inspect(ignored)

    def test_missing_or_boolean_exit_is_not_execution(self):
        for value in [None, True]:
            row = self.record()
            row['results']['candidate']['exit_code'] = value
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'execution missing'):
                self.inspect(row)

    def test_false_pair_equality_rejected(self):
        row = self.record()
        row['same_selected_output'] = False
        with self.assertRaisesRegex(RuntimeError, 'pair comparison'):
            self.inspect(row)

    def test_empty_case_inventory_rejected(self):
        report = {'status': 'DIFFERENTIAL_AUDIT_FINISHED_NOT_ADOPTED', 'compiler_adopted': False,
                  'full_upstream_suite_passed': False, 'fixtures_before': {}, 'fixtures_after': {}, 'cases': {}}
        path = self.root / 'report.json'
        path.write_text(json.dumps(report))
        with patch.object(p.chain.bundle, 'git', return_value=b''), \
             self.assertRaisesRegex(RuntimeError, 'case inventory'):
            p.inspect(path, self.source, {'fixtures_before': {}})

    def test_private_cache_and_native_sysroot_are_explicit(self):
        components = {'rustup_home': '/new/rustup', 'sysroot': '/new/full-mir',
                      'opam': {'root': '/new/opam', 'switch': 'new'}}
        with patch.dict(os.environ, {'HOME': '/unchanged', 'CHARON_CACHE_DIR': '/old',
                                   'CHARON_MIRI_SYSROOTS': '/old', 'RUSTC_WRAPPER': '/old'}, clear=True):
            env = p.environment(self.out, components)
        self.assertEqual(env['HOME'], '/unchanged')
        self.assertEqual(env['CHARON_CACHE_DIR'], str(self.out / 'charon-cache'))
        self.assertEqual(env['CHARON_MIRI_SYSROOTS'], '/new/full-mir')
        self.assertEqual(env['CARGO_NET_OFFLINE'], 'true')
        self.assertEqual(env['RUSTUP_HOME'], '/new/rustup')
        self.assertNotIn('RUSTC_WRAPPER', env)

    def test_old_output_directory_never_overwritten(self):
        with patch.object(sys, 'argv', ['probe', '--out', str(self.out)]), patch.object(p, 'run_probe') as run:
            with self.assertRaises(FileExistsError):
                p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
