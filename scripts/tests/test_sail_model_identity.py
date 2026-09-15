import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probes import probe_sail_model_identity as p


class SailModelIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='sail-model-identity-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_exact_inventory(self):
        (self.root/'model.lean').write_text('fixture')
        self.assertEqual(p.files(self.root),{'model.lean':p.sha(self.root/'model.lean')})

    def test_empty_inventory_rejected(self):
        with self.assertRaises(RuntimeError): p.files(self.root)

    def test_link_rejected(self):
        (self.root/'target').write_text('fixture')
        (self.root/'alias').symlink_to('target')
        with self.assertRaisesRegex(RuntimeError,'symlink'): p.files(self.root)

    def test_linked_root_rejected(self):
        (self.root/'dir').mkdir()
        (self.root/'alias').symlink_to('dir')
        with self.assertRaises(RuntimeError): p.files(self.root/'alias')

    def test_special_file_rejected(self):
        os.mkfifo(self.root/'pipe')
        with self.assertRaisesRegex(RuntimeError,'special'): p.files(self.root)

    def test_equal_files(self):
        result = p.difference({'a':'123'},{'a':'123'})
        self.assertTrue(result['identical'])
        self.assertEqual(result['changed'],{})

    def test_change_missing_extra_all_retained(self):
        result = p.difference({'a':'123','b':'x'},{'a':'456','c':'x'})
        self.assertFalse(result['identical'])
        self.assertEqual(result['only_left'],['b'])
        self.assertEqual(result['only_right'],['c'])
        self.assertEqual(result['changed'],{'a':{'left':'123','right':'456'}})

    def test_empty_comparison_rejected(self):
        for left,right in [({},{}),({'a':'x'},{}),({},{'a':'x'})]:
            with self.assertRaises(RuntimeError): p.difference(left,right)

    def test_install_prefix_change_never_normalized(self):
        self.assertFalse(p.difference({'model':'/old/share'},{'model':'/new/share'})['identical'])

    def test_environment_uses_explicit_new_plugins(self):
        original = {'SAIL_NO_PLUGINS':'1','SAIL_DIR':'/old','CMAKE_TOOLCHAIN_FILE':'/old',
                    'LEAN_PATH':'/old','ELAN_TOOLCHAIN':'old','PATH':'/old/bin'}
        with patch.dict(os.environ,original,clear=True): env = p.compiler_environment(self.root,self.root/'prefix')
        self.assertEqual(env['SAIL_PLUGIN_DIR'],str(self.root/'prefix/share/libsail/plugins'))
        self.assertEqual(env['SAIL_DIR'],str(self.root/'prefix/share/sail'))
        for key in ['SAIL_NO_PLUGINS','CMAKE_TOOLCHAIN_FILE','LEAN_PATH','ELAN_TOOLCHAIN']:
            self.assertNotIn(key,env)

    def test_lean_exact_policy(self):
        (self.root/'Model.lean').write_text('fixture')
        (self.root/'lean-toolchain').write_text('fixed')
        files = p.proof.tree_files(self.root,p.proof.lean_sources)
        policy = {'generated_sha256':{'sail':p.proof.digest(p.canonical(files))}}
        self.assertEqual(p.accepted_lean(self.root,policy),files)

    def test_lean_body_or_toolchain_drift_rejected(self):
        (self.root/'Model.lean').write_text('fixture')
        (self.root/'lean-toolchain').write_text('fixed')
        files = p.proof.tree_files(self.root,p.proof.lean_sources)
        policy = {'generated_sha256':{'sail':p.proof.digest(p.canonical(files))}}
        for filename in ['Model.lean','lean-toolchain']:
            with self.subTest(filename=filename):
                path = self.root/filename
                old = path.read_text()
                path.write_text('changed')
                with self.assertRaisesRegex(RuntimeError,'existing policy'): p.accepted_lean(self.root,policy)
                path.write_text(old)

    def test_raw_outputs_require_real_backends(self):
        with self.assertRaises(FileNotFoundError): p.raw_outputs(self.root)

    def test_raw_lean_entry_missing_rejected(self):
        for name in ['sail_riscv_model.cpp','sail_riscv_model.h','sail_riscv_config_schema.json']:
            (self.root/name).write_text('fixture')
        (self.root/'model/Lean_RV64D').mkdir(parents=True)
        (self.root/'model/Lean_RV64D/other.lean').write_text('fixture')
        (self.root/'rocq').mkdir()
        (self.root/'rocq/rv64d.v').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError,'Lean model outputs'): p.raw_outputs(self.root)

    def test_old_output_rejected_before_execution(self):
        with patch.object(sys,'argv',['probe','--out',str(self.root)]), patch.object(p,'run_probe') as run:
            with self.assertRaises(FileExistsError): p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
