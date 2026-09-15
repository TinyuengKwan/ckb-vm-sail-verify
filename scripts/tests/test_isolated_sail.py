import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probes import probe_isolated_sail as p


class IsolatedSailTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='isolated-sail-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def packages(self):
        return '\n'.join(k+' '+v for k,v in p.locked_packages().items())

    def test_lock_full_metadata(self):
        packages = p.locked_packages()
        self.assertEqual(len(packages),56)
        self.assertEqual(set(re.findall(r'^package "([^"]+)" \{',p.LOCK.read_text(),re.M)),set(packages))
        self.assertEqual(packages['ocaml-compiler'],'5.4.1')

    def test_lock_tampering_rejected(self):
        lock = self.root/'lock'
        lock.write_text(p.LOCK.read_text()+'\n')
        with patch.object(p,'LOCK',lock), self.assertRaisesRegex(RuntimeError,'lock changed'):
            p.locked_packages()

    def test_environment(self):
        original = {'HOME':'/unchanged','PATH':'/old/bin','OPAMROOT':'/old', 'OPAMFAKE':'true',
                    'SAIL_PLUGIN_DIR':'/old/plugins','SAIL_CONFIG':'/old/config','SAIL_NO_PLUGINS':'1',
                    'DUNE_PROFILE':'release','DUNE_CACHE':'enabled','OCAMLTOP_INCLUDE_PATH':'/old',
                    'GIT_DIR':'/old','GIT_CONFIG_COUNT':'1','LD_LIBRARY_PATH':'/old'}
        env = p.environment(self.root,original)
        self.assertEqual(env['HOME'],'/unchanged')
        self.assertEqual(env['OPAMROOT'],str(self.root/'opam-root'))
        self.assertEqual(env['OPAMSWITCH'],p.SWITCH)
        self.assertEqual(env['PATH'],'/usr/bin:/bin')
        self.assertEqual(env['DUNE_CACHE'],'disabled')
        for key in original.keys()-{'HOME','PATH','OPAMROOT','DUNE_CACHE'}:
            self.assertNotIn(key,env)

    def test_exact_packages(self):
        self.assertEqual(p.check_packages(self.packages()),p.locked_packages())

    def test_package_drift(self):
        for text in [self.packages()+'\nextra 1',self.packages().replace('dune 3.24.1','dune 3.23.1'),
                     self.packages().replace('linenoise 1.5.1\n','')]:
            with self.subTest(text=text[-25:]), self.assertRaises(RuntimeError): p.check_packages(text)

    def test_duplicate_or_malformed_package(self):
        for text in [self.packages()+'\nsail 0.20.2',self.packages()+'\nbroken']:
            with self.assertRaises(RuntimeError): p.check_packages(text)

    def test_export_exact(self):
        result = p.check_export(p.LOCK.read_text(),'['+p.COMPILER_FORMULA+']')
        self.assertTrue(result['exact_export_bytes'])

    def test_export_only_compiler_header_missing(self):
        text = p.LOCK.read_text().replace(p.COMPILER_HEADER,'',1)
        result = p.check_export(text,'['+p.COMPILER_FORMULA+']')
        self.assertFalse(result['exact_export_bytes'])
        self.assertTrue(result['all_other_export_bytes_identical'])

    def test_export_other_difference_rejected(self):
        for text in [p.LOCK.read_text().replace('sha256=','sha512='),p.LOCK.read_text().replace('roots:','other:')]:
            with self.assertRaises(RuntimeError): p.check_export(text,'['+p.COMPILER_FORMULA+']')

    def test_invariant_must_be_exact_source_compiler(self):
        for invariant in ['[]','["ocaml-base-compiler"]','["ocaml-system" {= "5.4.1"}]',
                          '['+p.COMPILER_FORMULA+' | "ocaml-system" {= "5.4.1"}]']:
            with self.assertRaisesRegex(RuntimeError,'invariant'): p.check_export(p.LOCK.read_text(),invariant)

    def test_source_clean_pin(self):
        row = {'head':p.COMMIT, 'gitlinks':{}, 'changes_from_head':{}}
        with patch.object(p,'inventory',return_value=row): self.assertEqual(p.check_source(self.root),row)

    def test_source_drift_rejected(self):
        row = {'head':p.COMMIT, 'gitlinks':{}, 'changes_from_head':{}}
        for key,value in [('head','0'*40),('gitlinks',{'nested':'a'}),('changes_from_head',{'changed':{}})]:
            with patch.object(p,'inventory',return_value={**row,key:value}), self.assertRaises(RuntimeError):
                p.check_source(self.root)

    def test_matching_identity_is_not_new_policy_approval(self):
        binary = self.root/'binary'
        binary.write_bytes(b'test fixture')
        policy = {'tool_binaries':{'sail':p.sha(binary)}}
        result = p.identity(p.VERSION,binary,policy)
        self.assertTrue(result['matches_policy_binary'])
        self.assertFalse(result['policy_changed'])
        self.assertFalse(result['new_tool_approved'])

    def test_mismatch_retained_not_auto_approved(self):
        binary = self.root/'binary'
        binary.write_bytes(b'test fixture')
        policy = {'tool_binaries':{'sail':'0'*64}}
        result = p.identity(p.VERSION,binary,policy)
        self.assertFalse(result['matches_policy_binary'])
        self.assertEqual(result['policy_sha256'],'0'*64)
        self.assertEqual(policy,{'tool_binaries':{'sail':'0'*64}})

    def test_release_or_wrong_commit_rejected_even_if_binary_matches(self):
        binary = self.root/'binary'
        binary.write_bytes(b'test fixture')
        policy = {'tool_binaries':{'sail':p.sha(binary)}}
        for version in ['Sail 0.20.2',p.VERSION.replace(p.COMMIT,'0'*40)]:
            with self.assertRaisesRegex(RuntimeError,'source-built'): p.identity(version,binary,policy)

    def test_old_output_directory_rejected_before_probe(self):
        with patch.object(sys,'argv',['probe','--out',str(self.root)]), patch.object(p,'run_probe') as run:
            with self.assertRaises(FileExistsError): p.main()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
