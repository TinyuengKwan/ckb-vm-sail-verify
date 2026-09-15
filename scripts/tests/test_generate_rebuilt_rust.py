"""Pair publication preserves old outputs and explicit provenance boundaries."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_rebuilt_rust as generator


class GeneratorTests(unittest.TestCase):
    def fixture(self, root, old=True):
        model, llbc = root / 'new.lean', root / 'new.llbc'
        model.write_text('new lean\n')
        llbc.write_text('new llbc\n')
        toolchain = root / 'proof/lean/theorems/lean-toolchain'
        toolchain.parent.mkdir(parents=True)
        toolchain.write_text(generator.tools.TOOLCHAIN + '\n')
        destination = root / 'proof/lean/generated/rust'
        target = root / 'target/CkbVmProduction.llbc'
        if old:
            destination.mkdir(parents=True)
            (destination / 'CkbVmProduction.lean').write_text('old lean\n')
            (destination / 'unrelated-user-file').write_text('keep\n')
            target.parent.mkdir()
            target.write_text('old llbc\n')
        provenance = {'generated_lean_sha256': generator.sha(model), 'llbc_sha256': generator.sha(llbc)}
        return model, llbc, provenance, destination, target

    def test_success_retains_both_old_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, llbc, provenance, dest, target = self.fixture(root)
            result = generator.install(root, model, llbc, provenance, root / 'support')
            self.assertEqual(result['status'], 'installed')
            backup = Path(result['backup'])
            self.assertEqual((backup / 'previous/CkbVmProduction.lean').read_text(), 'old lean\n')
            self.assertEqual((backup / 'previous/unrelated-user-file').read_text(), 'keep\n')
            self.assertEqual((backup / 'previous.llbc').read_text(), 'old llbc\n')
            self.assertEqual(target.read_bytes(), llbc.read_bytes())
            self.assertEqual((dest / 'CkbVmProduction.lean').read_bytes(), model.read_bytes())
            self.assertEqual(json.loads((dest / 'SOURCE_BASELINE.json').read_text()), provenance)

    def test_success_from_no_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, llbc, provenance, dest, target = self.fixture(root, old=False)
            result = generator.install(root, model, llbc, provenance, root / 'support')
            self.assertFalse(result['old_model_saved'])
            self.assertFalse(result['old_llbc_saved'])
            self.assertEqual(target.read_bytes(), llbc.read_bytes())

    def test_failure_at_each_rename_restores_exact_pair_and_extra_file(self):
        for failure in range(1, 5):
            with self.subTest(rename=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model, llbc, provenance, dest, target = self.fixture(root)
                calls = []
                def move(source, destination):
                    calls.append((source, destination))
                    if len(calls) == failure: raise OSError('injected rename failure')
                    source.rename(destination)
                with self.assertRaisesRegex(OSError, 'injected'):
                    generator.install(root, model, llbc, provenance, root / 'support', move)
                self.assertEqual((dest / 'CkbVmProduction.lean').read_text(), 'old lean\n')
                self.assertEqual((dest / 'unrelated-user-file').read_text(), 'keep\n')
                self.assertEqual(target.read_text(), 'old llbc\n')
                records = list(dest.parent.glob('.rust-install-*/transaction.json'))
                self.assertEqual(len(records), 1)
                self.assertEqual(json.loads(records[0].read_text())['status'], 'failed-restored')
                self.assertEqual(model.read_text(), 'new lean\n')
                self.assertEqual(llbc.read_text(), 'new llbc\n')

    def test_wrong_pair_rejected_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, llbc, provenance, dest, target = self.fixture(root)
            provenance['llbc_sha256'] = 'wrong'
            with self.assertRaisesRegex(RuntimeError, 'new model pair'):
                generator.install(root, model, llbc, provenance, root / 'support')
            self.assertEqual(list(dest.parent.glob('.rust-install-*')), [])
            self.assertEqual(target.read_text(), 'old llbc\n')

    def test_linked_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, llbc, provenance, dest, target = self.fixture(root, old=False)
            target.parent.mkdir()
            target.symlink_to(llbc)
            with self.assertRaisesRegex(RuntimeError, 'unsafe old LLBC'):
                generator.install(root, model, llbc, provenance, root / 'support')
            self.assertTrue(target.is_symlink())

    def test_formal_profile_rejects_before_resolver_or_extraction(self):
        with patch.object(generator, 'read', return_value={}), \
             patch.object(generator.tools, 'resolve') as resolve, patch.object(generator.extraction, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'explicitly selected'):
                generator.run()
            resolve.assert_not_called()
            run.assert_not_called()

    def test_provenance_escape_rejected(self):
        policy = {'main_toolchain': generator.tools.PROFILE, 'tool_binaries': generator.tools.BINARIES,
                  'translator_versions': generator.tools.VERSIONS, 'lean_toolchain': generator.tools.TOOLCHAIN,
                  'aeneas_lean_sources_sha256': generator.tools.SUPPORT}
        for name in ('../report.json', '/outside/report.json', 'docs/report.json'):
            provenance = {'rebuilt_extraction': {'profile': generator.tools.PROFILE, 'report': name, 'report_sha256': 'x'}}
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                generator.check_provenance(Path('/unused'), policy, provenance)

    def test_current_checkout_policy_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / 'proof/lean/audit/step-policy.json'
            policy.parent.mkdir(parents=True)
            policy.write_text('{"candidate": true}\n')
            generator.policy_binding(root, {'inputs_after': {str(policy): generator.sha(policy)}})

    def test_old_policy_report_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / 'proof/lean/audit/step-policy.json'
            policy.parent.mkdir(parents=True)
            policy.write_text('{"candidate": true}\n')
            with self.assertRaisesRegex(RuntimeError, 'another checkout or policy'):
                generator.policy_binding(root, {'inputs_after': {str(policy): 'old policy hash'}})

    def test_other_checkout_same_policy_report_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / 'proof/lean/audit/step-policy.json'
            policy.parent.mkdir(parents=True)
            policy.write_text('{"candidate": true}\n')
            with self.assertRaisesRegex(RuntimeError, 'another checkout or policy'):
                generator.policy_binding(root, {'inputs_after': {'/other/proof/lean/audit/step-policy.json': generator.sha(policy)}})


if __name__ == '__main__':
    unittest.main()
