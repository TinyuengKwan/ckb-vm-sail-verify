import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_rebuilt_lower_models as p


class RebuiltLowerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='rebuilt-lower-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = {'root': 'factory', 'include': ['body'], 'opaque': ['boundary']}

    def command(self, stem):
        return p.extraction_command(stem, '/new/charon', '/new/model.llbc', '/new/sysroot', self.root, self.config)

    def test_fields_six_roots_locked_explicit_sysroot(self):
        cmd = self.command('LocalFields')
        expected = ['/new/charon', 'cargo', '--preset=aeneas', '--sysroot', '/new/sysroot',
                    '--dest-file', '/new/model.llbc']
        for root in p.fields.ROOTS:
            expected += ['--start-from', root]
        self.assertEqual(cmd, expected + ['--', '--lib', '--locked'])
        self.assertEqual(len(p.fields.ROOTS), 6)

    def test_factory_scope_unchanged(self):
        self.assertEqual(self.command('FactoryScoped'), ['/new/charon', 'cargo', '--preset=aeneas',
            '--sysroot', '/new/sysroot', '--dest-file', '/new/model.llbc', '--start-from', 'factory',
            '--include', 'body', '--opaque', 'boundary', '--', '--lib', '--locked'])

    def test_mini_uses_real_option_and_candidate_fixture(self):
        self.assertEqual(self.command('MiniComplete'), ['/new/charon', 'rustc', '--preset=aeneas',
            '--sysroot', '/new/sysroot', '--dest-file', '/new/model.llbc', '--include', 'core::option::_',
            '--', self.root / 'proof/lean/decoder/toolchain/decoder_shared_closure.rs', '--crate-type', 'lib'])

    def test_unknown_model_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unknown lower model'):
            self.command('public')

    def test_field_identity_no_comment_normalization(self):
        path = self.root / 'LocalFields.lean'
        path.write_text('def value := 42\n')
        policy = {'generated_sha256': p.sha(path)}
        self.assertTrue(p.model_identity('LocalFields', path, policy, {})['matches_existing_policy'])
        path.write_text('def value := 42\n-- moved source\n')
        result = p.model_identity('LocalFields', path, policy, {})
        self.assertFalse(result['matches_existing_policy'])
        self.assertFalse(result['new_normalization_used'])

    def test_raw_identity_delegates_only_existing_normalizer(self):
        path = self.root / 'FactoryScoped.lean'
        path.write_text('def value := 42\n')
        with patch.object(p.raw, 'normalized_model', return_value='actual') as normalize:
            row = p.model_identity('FactoryScoped', path, {}, {'generated_normalized_sha256': 'expected'})
        normalize.assert_called_once_with(path)
        self.assertFalse(row['matches_existing_policy'])
        self.assertEqual(row['existing_policy_actual_sha256'], 'actual')
        self.assertEqual(path.read_text(), 'def value := 42\n')

    def test_join_patch_exact_four_files(self):
        state = {'changed': dict.fromkeys(p.PATCH_FILES)}
        with patch.object(p.aeneas, 'check_source', return_value=state) as check:
            self.assertEqual(p.check_join_source(self.root), state)
        check.assert_called_once_with(self.root, True, p.PATCH_SHA)
        for changes in [{}, {**state['changed'], 'src/extra.ml': None}]:
            with patch.object(p.aeneas, 'check_source', return_value={'changed': changes}), \
                 self.assertRaisesRegex(RuntimeError, 'file set drift'):
                p.check_join_source(self.root)

    def test_relocated_factory_is_not_silently_accepted(self):
        path = self.root / 'FactoryScoped.lean'
        line = "    Source: '{}/deps/ckb-vm/src/instructions/i.rs', lines 1:0-2:0\n"
        path.write_text(line.format(p.ROOT))
        policy = {'generated_normalized_sha256': p.raw.normalized_model(path)}
        self.assertTrue(p.model_identity('FactoryScoped', path, {}, policy)['matches_existing_policy'])
        path.write_text(line.format(p.ROOT / 'artifacts/candidate/checkout'))
        self.assertFalse(p.model_identity('FactoryScoped', path, {}, policy)['matches_existing_policy'])

    def test_candidate_report_digest_fail_closed(self):
        with patch.object(p, 'sha', return_value='unreviewed'), patch.object(p, 'read') as read, \
             self.assertRaisesRegex(RuntimeError, 'joint-chain report drift'):
            p.candidate()
        read.assert_not_called()

    def test_ignored_lock_materialized_exactly_once(self):
        original = self.root / 'deps/ckb-vm/Cargo.lock'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'frozen lock\n')
        checkout = self.root / 'candidate'
        (checkout / 'deps/ckb-vm').mkdir(parents=True)
        with patch.object(p, 'ROOT', self.root):
            row = p.install_ignored_lock(checkout, p.sha(original))
            self.assertFalse(row['already_present'])
            self.assertFalse(row['dependency_resolution_performed'])
            self.assertTrue(p.install_ignored_lock(checkout, p.sha(original))['already_present'])
        self.assertEqual(Path(row['path']).read_bytes(), original.read_bytes())

    def test_ignored_lock_drift_never_overwritten(self):
        original = self.root / 'deps/ckb-vm/Cargo.lock'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'frozen lock\n')
        checkout = self.root / 'candidate'
        dest = checkout / 'deps/ckb-vm/Cargo.lock'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'unreviewed lock\n')
        with patch.object(p, 'ROOT', self.root), self.assertRaisesRegex(RuntimeError, 'candidate CKB lock drift'):
            p.install_ignored_lock(checkout, p.sha(original))
        self.assertEqual(dest.read_bytes(), b'unreviewed lock\n')

    def test_ignored_lock_symlink_rejected(self):
        original = self.root / 'deps/ckb-vm/Cargo.lock'
        original.parent.mkdir(parents=True)
        original.write_bytes(b'frozen lock\n')
        checkout = self.root / 'candidate'
        dest = checkout / 'deps/ckb-vm/Cargo.lock'
        dest.parent.mkdir(parents=True)
        dest.symlink_to(original)
        with patch.object(p, 'ROOT', self.root), self.assertRaisesRegex(RuntimeError, 'lock is linked'):
            p.install_ignored_lock(checkout, p.sha(original))

    def test_enclosing_workspace_rejected_without_manifest_edits(self):
        checkout = self.root / 'artifacts/candidate/checkout'
        manifest = self.root / 'Cargo.toml'
        p.check_outer_workspace(checkout)
        manifest.write_text('[workspace]\n')
        with self.assertRaisesRegex(RuntimeError, 'enclosing Cargo manifest'):
            p.check_outer_workspace(checkout)
        self.assertEqual(manifest.read_text(), '[workspace]\n')

    def test_incomplete_candidate_rejected(self):
        for status, stages in [('failed', [{}] * 20),
                               ('rebuilt_tools_three_models_match_qualification_pending', [])]:
            with patch.object(p, 'sha', return_value=p.ORIGIN_SHA), \
                 patch.object(p, 'read', return_value={'status': status, 'stages': stages}), \
                 self.assertRaisesRegex(RuntimeError, 'joint-chain incomplete'):
                p.candidate()

    def test_strict_join_intended_failure(self):
        p.check_result(2, 'Uncaught exception: Failure ' + p.STRICT_REASON, strict=True)
        p.check_result(1, p.STRICT_REASON, strict=True)

    def test_strict_join_success_signal_or_other_failure_rejected(self):
        for code, output in [(0, p.STRICT_REASON), (-9, p.STRICT_REASON), (1, 'unrelated failure'),
                             (True, p.STRICT_REASON), (127, p.STRICT_REASON)]:
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                p.check_result(code, output, strict=True)

    def test_strict_join_resource_and_import_failure_rejected(self):
        for diagnostic in ('unknown module', 'out of memory', 'Stack overflow', 'Internal error',
                           'timeout', 'maximum recursion depth', 'PANIC', 'unknownIdentifier'):
            with self.subTest(diagnostic=diagnostic), self.assertRaises(RuntimeError):
                p.check_result(2, p.STRICT_REASON + '\n' + diagnostic, strict=True)

    def test_positive_stage_requires_actual_zero(self):
        p.check_result(0, '')
        for code in (1, 2, -9, False):
            with self.assertRaises(RuntimeError):
                p.check_result(code, '')

    def test_failed_preflight_has_no_success_claim(self):
        with patch.object(p.chain, 'verify_components', side_effect=RuntimeError('preflight failed')), \
             patch('builtins.print'):
            self.assertEqual(p.run_probe(self.root), 1)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stages'], [])
        for key in ('rust_reextracted', 'kernel_executed', 'policy_changed', 'new_tools_approved',
                    'clean_room_claimed', 'release_claimed'):
            self.assertIs(report[key], False)

    def test_existing_output_never_reused(self):
        with patch.object(sys, 'argv', ['probe', '--out', str(self.root)]), patch.object(p, 'run_probe') as run:
            with self.assertRaises(FileExistsError):
                p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
