import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probes import probe_isolated_full_mir as p


class IsolatedFullMirTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='isolated-full-mir-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def libs(self):
        directory = self.root/'libs'
        directory.mkdir()
        for name in ['libstd-test.rlib',*[f'libtest-{i}.rmeta' for i in range(45)]]:
            (directory/name).write_bytes(b'fixture, not real MIR')
        return directory

    def test_environment_private_rust_and_empty_cargo(self):
        old = {'RUSTUP_HOME':'/old','CARGO_HOME':'/old','CARGO_TARGET_DIR':'/old','RUSTFLAGS':'unsafe',
               'CARGO_BUILD_RUSTC_WRAPPER':'/old','OPAMROOT':'/old','LD_LIBRARY_PATH':'/old',
               'HOME':'/unchanged','PATH':'/old'}
        env = p.environment(self.root,self.root/'rustup',old)
        self.assertEqual(env['RUSTUP_HOME'],str(self.root/'rustup'))
        self.assertEqual(env['CARGO_HOME'],str(self.root/'cargo'))
        self.assertEqual(env['HOME'],'/unchanged')
        self.assertEqual(env['PATH'],'/usr/bin:/bin')
        for key in ['CARGO_TARGET_DIR','RUSTFLAGS','CARGO_BUILD_RUSTC_WRAPPER','OPAMROOT','LD_LIBRARY_PATH']:
            self.assertNotIn(key,env)

    def test_complete_library_shape(self):
        self.assertEqual(len(p.libraries(self.libs())),46)

    def test_missing_library_rejected(self):
        directory = self.libs()
        (directory/'libtest-0.rmeta').unlink()
        with self.assertRaisesRegex(RuntimeError,'incomplete'): p.libraries(directory)

    def test_unexpected_file_rejected(self):
        directory = self.libs()
        (directory/'unexpected.txt').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError,'unexpected'): p.libraries(directory)

    def test_hardlink_rejected_for_materialized_libraries(self):
        directory = self.libs()
        os.link(directory/'libtest-0.rmeta',self.root/'outside')
        with self.assertRaisesRegex(RuntimeError,'linked/shared'): p.libraries(directory)

    def test_symlink_rejected_for_materialized_libraries(self):
        directory = self.libs()
        path=directory/'libtest-0.rmeta'
        path.rename(self.root/'outside')
        path.symlink_to(self.root/'outside')
        with self.assertRaises(RuntimeError): p.libraries(directory)

    def test_build_link_allowed_only_within_exact_root(self):
        directory = self.libs()
        path=directory/'libtest-0.rmeta'
        path.rename(self.root/'built')
        path.symlink_to(self.root/'built')
        self.assertEqual(len(p.libraries(directory,self.root)),46)
        with self.assertRaisesRegex(RuntimeError,'escaped'): p.libraries(directory,directory)

    def test_changed_library_not_normalized(self):
        directory = self.libs()
        before=p.libraries(directory)
        (directory/'libstd-test.rlib').write_bytes(b'changed')
        result=p.difference(before,p.libraries(directory))
        self.assertFalse(result['identical'])
        self.assertEqual(set(result['changed']),{'libstd-test.rlib'})

    def test_single_child_report(self):
        child=self.root/'artifacts/boundary-check/decoder-sysroot-build-test/report.json'
        child.parent.mkdir(parents=True)
        child.write_text('{}')
        with patch.object(p,'ROOT',self.root):
            self.assertEqual(p.child_report('Report: '+str(child)+'\nSysroot: elsewhere'),child)

    def test_wrong_or_ambiguous_child_report(self):
        child=self.root/'report.json'
        child.write_text('{}')
        for text in ['','Report: '+str(child),'Report: '+str(child)+'\nReport: '+str(child)]:
            with self.assertRaises(RuntimeError): p.child_report(text)

    def test_old_directory_rejected(self):
        with patch.object(sys,'argv',['probe','--out',str(self.root)]),patch.object(p,'run_probe') as run:
            with self.assertRaises(FileExistsError): p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
