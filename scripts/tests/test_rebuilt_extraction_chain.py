import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_rebuilt_extraction_chain as p


class RebuiltChainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='rebuilt-chain-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.main = {'preset': 'aeneas', 'root': 'production', 'include': ['wrapper'], 'opaque': ['memory']}
        self.public = {'outer_start_from': ['decoder'], 'outer_include': ['factory'],
                       'outer_opaque': ['boundary'], 'outer_cargo_args': ['--lib', '--locked', '--offline']}
        self.iterator = {'translated': {'options': {'include': ['iterator-body']}}}

    def command(self, kind):
        return p.extraction_command(kind, '/new/charon', self.root / 'Fresh.llbc', '/new/sysroot',
                                    self.root, self.main, self.public, self.iterator)

    def test_main_root_and_opacity_unchanged(self):
        self.assertEqual(self.command('main'), ['/new/charon', 'cargo', '--preset=aeneas',
            '--sysroot', '/new/sysroot', '--dest-file', self.root / 'Fresh.llbc',
            '--start-from', 'production', '--include', 'wrapper', '--opaque', 'memory', '--', '--lib'])

    def test_public_keeps_locked_offline_and_scope(self):
        self.assertEqual(self.command('public'), ['/new/charon', 'cargo', '--preset=aeneas',
            '--sysroot', '/new/sysroot', '--dest-file', self.root / 'Fresh.llbc',
            '--start-from', 'decoder', '--include', 'factory', '--opaque', 'boundary',
            '--', '--lib', '--locked', '--offline'])

    def test_iterator_uses_verified_source_and_fresh_output(self):
        self.assertEqual(self.command('iterator'), ['/new/charon', 'rustc', '--preset=aeneas',
            '--sysroot', '/new/sysroot', '--dest-file', self.root / 'Fresh.llbc',
            '--include', 'iterator-body', '--', self.root / p.identity.ITERATOR_RELATIVE, '--crate-type=lib'])

    def test_unknown_root_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unknown extraction root'):
            self.command('all')

    def test_changed_main_preset_rejected(self):
        self.main['preset'] = 'other'
        with self.assertRaisesRegex(RuntimeError, 'preset drift'):
            self.command('main')

    def test_miri_and_old_tool_environments_removed(self):
        components = {'rustup_home': '/new/rustup', 'opam': {'root': '/new/opam', 'switch': 'new'}}
        old = {'HOME': '/unchanged', 'PATH': '/old/bin', 'OPAMROOT': '/old/opam',
               'MIRI_SYSROOT': '/old/sysroot', 'AENEAS_FACTOR_RETURN_GUARDS': 'bad',
               'CHARON_ARGS': 'opaque all', 'RUSTC_WRAPPER': '/old/wrapper', 'LD_PRELOAD': '/old.so'}
        with patch.dict(os.environ, old, clear=True):
            env = p.environment(self.root, components)
        for key in ('MIRI_SYSROOT', 'AENEAS_FACTOR_RETURN_GUARDS', 'CHARON_ARGS', 'RUSTC_WRAPPER', 'LD_PRELOAD'):
            self.assertNotIn(key, env)
        self.assertEqual(env['HOME'], '/unchanged')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        self.assertEqual(env['RUSTUP_HOME'], '/new/rustup')
        self.assertEqual(env['CARGO_HOME'], str(self.root / 'cargo'))
        self.assertEqual(env['CARGO_TARGET_DIR'], str(self.root / 'cargo-target'))
        self.assertEqual(env['OPAMROOT'], '/new/opam')
        self.assertEqual(env['OPAMSWITCH'], 'new')

    def test_only_exact_historical_policy_transition_allowed(self):
        name = 'proof/lean/audit/step-policy.json'
        live, archive = self.root / 'live', self.root / 'archive'
        with patch.object(p.evidence, 'member', side_effect=[live, archive]), \
             patch.object(p, 'sha', side_effect=[p.NEW_POLICY, p.migration.OLD_POLICY]):
            p.input_identity(name, p.migration.OLD_POLICY, historical_policy=True)
        for digest, current in [('arbitrary-old', p.NEW_POLICY), (p.migration.OLD_POLICY, 'unreviewed-new')]:
            with self.subTest(digest=digest, current=current), \
                 patch.object(p.evidence, 'member', return_value=live), patch.object(p, 'sha', return_value=current), \
                 self.assertRaisesRegex(RuntimeError, 'unreviewed policy transition'):
                p.input_identity(name, digest, historical_policy=True)

    def test_history_does_not_allow_other_stale_sources(self):
        source = self.root / 'source.py'
        source.write_text('new input')
        with patch.object(p, 'ROOT', self.root), self.assertRaisesRegex(RuntimeError, 'input drift'):
            p.input_identity('source.py', 'old-hash', historical_policy=True)

    def test_live_build_policy_needs_current_digest(self):
        source = self.root / 'step-policy.json'
        source.write_text('current policy')
        with patch.object(p, 'ROOT', self.root):
            p.input_identity('step-policy.json', p.sha(source))
            with self.assertRaisesRegex(RuntimeError, 'input drift'):
                p.input_identity('step-policy.json', 'old')

    def test_main_identity_is_whole_bytes_not_new_normalization(self):
        baseline = self.root / 'proof/lean/generated/rust/CkbVmProduction.lean'
        baseline.parent.mkdir(parents=True)
        baseline.write_text('def answer := 42\n')
        model = self.root / 'model.lean'
        model.write_bytes(baseline.read_bytes())
        with patch.object(p, 'ROOT', self.root):
            self.assertTrue(p.main_model(model)['whole_file_identical'])
            for data in [b'def answer := 43\n', b'def answer := 42\n-- path\n']:
                model.write_bytes(data)
                with self.assertRaisesRegex(RuntimeError, 'no new normalization'):
                    p.main_model(model)

    def test_linked_or_changed_executable_rejected(self):
        binary = self.root / 'tool'
        binary.write_bytes(b'fixture')
        binary.chmod(0o700)
        digest = p.sha(binary)
        p.executable(binary, digest)
        link = self.root / 'link'
        link.symlink_to(binary)
        with self.assertRaises(RuntimeError):
            p.executable(link, digest)
        with self.assertRaises(RuntimeError):
            p.executable(binary, 'old-hash')
        os.link(binary, self.root / 'hardlink')
        with self.assertRaises(RuntimeError):
            p.executable(binary, digest)

    def test_failed_preflight_preserved_without_success_claims(self):
        with patch.object(p, 'verify_components', side_effect=RuntimeError('preflight failed')), patch('builtins.print'):
            self.assertEqual(p.run_probe(self.root), 1)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stages'], [])
        for key in ['rust_reextracted', 'new_tools_approved', 'kernel_executed', 'clean_room_claimed', 'release_claimed']:
            self.assertIs(report[key], False)

    def test_existing_output_rejected_before_execution(self):
        with patch.object(sys, 'argv', ['probe', '--out', str(self.root)]), patch.object(p, 'run_probe') as run:
            with self.assertRaises(FileExistsError):
                p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
