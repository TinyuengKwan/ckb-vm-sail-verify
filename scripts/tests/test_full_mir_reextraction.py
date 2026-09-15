import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probes import probe_full_mir_reextraction as p


class FullMirReextractionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='full-mir-reextraction-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.archive = {'has_errors':False,'charon_version':'fixed',
                        'translated':{'crate_name':'root','target_information':{'bits':64},
                        'options':{'sysroot':'/old','dest_file':'/old.llbc','include':['body'],
                                   'opaque':['existing'],'checks':True}}}
        self.fresh = copy.deepcopy(self.archive)
        self.fresh['translated']['options'].update(sysroot=str(self.root/'sysroot'),dest_file='/new.llbc')

    def compare(self):
        return p.candidate_options(self.archive,self.fresh,self.root/'sysroot')

    def test_only_verified_sysroot_and_destination_move(self):
        before = copy.deepcopy(self.fresh)
        result = self.compare()
        self.assertEqual(self.fresh,before)
        self.assertTrue(result['only_sysroot_location_and_output_path_vary'])
        self.assertFalse(result['candidate_libraries_approved'])
        self.assertFalse(result['llbc_ast_equivalence_claimed'])

    def test_wrong_candidate_location_rejected(self):
        self.fresh['translated']['options']['sysroot']='/not-the-verified-root'
        with self.assertRaises(RuntimeError): self.compare()

    def test_missing_bodies_not_silently_allowed(self):
        self.fresh['translated']['options']['include']=[]
        with self.assertRaises(RuntimeError): self.compare()

    def test_added_opaque_not_silently_allowed(self):
        self.fresh['translated']['options']['opaque'].append('new_assumption')
        with self.assertRaises(RuntimeError): self.compare()

    def test_checks_not_disabled(self):
        self.fresh['translated']['options']['checks']=False
        with self.assertRaises(RuntimeError): self.compare()

    def test_frontend_errors_rejected(self):
        self.fresh['has_errors']=True
        with self.assertRaises(RuntimeError): self.compare()

    def test_format_change_rejected(self):
        self.fresh['charon_version']='other'
        with self.assertRaises(RuntimeError): self.compare()

    def test_target_or_root_change_rejected(self):
        for key,value in [('crate_name','other'),('target_information',{'bits':32})]:
            original=self.fresh['translated'][key]
            self.fresh['translated'][key]=value
            with self.assertRaises(RuntimeError): self.compare()
            self.fresh['translated'][key]=original

    def test_old_install_environment_removed(self):
        config={'rust_toolchain':'nightly-fixed','aeneas_env':{'AENEAS_FACTOR_RETURN_GUARDS':'1'}}
        old={'HOME':'/unchanged','CARGO_HOME':'/old','RUSTUP_HOME':'/old','RUSTUP_TOOLCHAIN':'old',
             'CHARON_ARGS':'opaque all','AENEAS_BRANCH_DIAGNOSTIC':'1','RUSTFLAGS':'changed',
             'GIT_DIR':'/old','PATH':'/old/bin'}
        with patch.dict(os.environ,old,clear=True): env=p.environment(self.root,self.root/'rustup',config)
        self.assertEqual(env['HOME'],'/unchanged')
        self.assertEqual(env['RUSTUP_HOME'],str(self.root/'rustup'))
        self.assertEqual(env['RUSTUP_TOOLCHAIN'],'nightly-fixed')
        self.assertEqual(env['CARGO_HOME'],str(self.root/'cargo'))
        self.assertEqual(env['CARGO_TARGET_DIR'],str(self.root/'cargo-target'))
        self.assertEqual(env['AENEAS_FACTOR_RETURN_GUARDS'],'1')
        for key in ['CHARON_ARGS','AENEAS_BRANCH_DIAGNOSTIC','RUSTFLAGS','GIT_DIR']: self.assertNotIn(key,env)

    def test_old_output_directory_rejected(self):
        with patch.object(sys,'argv',['probe','--out',str(self.root)]),patch.object(p,'run_probe') as run:
            with self.assertRaises(FileExistsError): p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
