import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probes import probe_isolated_rocq as probe


class IsolatedRocqTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='isolated-rocq-test-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def binary(self):
        path = self.root/'switch/bin/rocq'
        path.parent.mkdir(parents=True)
        path.write_text('fixture, not executed')
        path.chmod(0o755)
        return path

    def package_text(self):
        return '\n'.join(k+' '+v for k,v in probe.PACKAGES.items())

    def test_environment_cannot_inherit_fake_build_or_global_switch(self):
        original = {'OPAMFAKE':'true','OPAMDRYRUN':'true','OPAMROOT':'/old',
                    'OPAMSWITCH':'old','HOME':'/unchanged',
                    'PATH':'/usr/bin:/home/a/.opam/default/bin:/a/_opam/bin:/tmp/ocaml-switch/bin:/bootstrap'}
        original.update({k:'ambient' for k in probe.STRIP})
        env = probe.environment(self.root,original)
        self.assertEqual(env['HOME'],original['HOME'])
        self.assertEqual(env['PATH'],'/usr/bin:/bootstrap')
        self.assertEqual(env['OPAMROOT'],str(self.root/'opam-root'))
        self.assertEqual(env['OPAMSWITCH'],probe.SWITCH)
        self.assertNotIn('OPAMFAKE',env)
        self.assertNotIn('OPAMDRYRUN',env)
        self.assertEqual(env['DUNE_CACHE'],'disabled')
        for key in probe.STRIP:
            if key != 'DUNE_CACHE': self.assertNotIn(key,env)

    def test_full_metadata_lock_and_inventory(self):
        self.assertEqual(probe.sha(probe.LOCK),probe.LOCK_SHA)
        text = probe.LOCK.read_text()
        self.assertEqual(set(re.findall(r'^package "([^"]+)" \{',text,re.M)),set(probe.PACKAGES))
        self.assertEqual(len(probe.PACKAGES),21)

    def test_exact_packages(self):
        self.assertEqual(probe.check_packages(self.package_text()),probe.PACKAGES)

    def test_exact_export_requires_exact_invariant(self):
        result = probe.check_export(probe.LOCK.read_text(),'['+probe.COMPILER_FORMULA+']')
        self.assertTrue(result['exact_export_bytes'])
        with self.assertRaisesRegex(RuntimeError,'invariant'):
            probe.check_export(probe.LOCK.read_text(),'["ocaml-base-compiler"]')

    def test_only_compiler_header_omission_with_exact_invariant_accepted(self):
        text = probe.LOCK.read_text().replace(probe.COMPILER_HEADER,'',1)
        result = probe.check_export(text,'['+probe.COMPILER_FORMULA+']')
        self.assertFalse(result['exact_export_bytes'])
        self.assertEqual(result['only_export_difference'],'top-level compiler list omitted')
        with self.assertRaisesRegex(RuntimeError,'invariant'): probe.check_export(text,'[]')

    def test_other_export_change_never_normalized(self):
        original = probe.LOCK.read_text()
        for text in [original.replace('9.1.1','9.1.2'), original.replace('sha256=','sha512='),
                     original+'\n'+probe.COMPILER_HEADER, original.replace('roots:','other:')]:
            with self.assertRaises(RuntimeError): probe.check_export(text,'['+probe.COMPILER_FORMULA+']')

    def test_extra_package_rejected(self):
        with self.assertRaises(RuntimeError): probe.check_packages(self.package_text()+'\nunreviewed 1')

    def test_missing_non_spike_dependency_rejected(self):
        text = self.package_text().replace('dune 3.23.1\n','')
        with self.assertRaises(RuntimeError): probe.check_packages(text)

    def test_package_version_and_duplicate_rejected(self):
        for text in [self.package_text().replace('dune 3.23.1','dune 3.24.2'),self.package_text()+'\nocaml 5.2.1']:
            with self.assertRaises(RuntimeError): probe.check_packages(text)

    def test_private_compiler(self):
        path = self.binary()
        self.assertEqual(probe.private_binary(str(path),self.root/'switch'),path)

    def test_outside_compiler_rejected(self):
        path = self.binary()
        with self.assertRaises(RuntimeError): probe.private_binary(str(path),self.root/'other')

    def test_shared_compiler_rejected(self):
        path = self.binary()
        os.link(path,self.root/'shared')
        with self.assertRaisesRegex(RuntimeError,'hardlinked'): probe.private_binary(str(path),self.root/'switch')

    def test_installed_library_drift_detected(self):
        self.binary()
        before = probe.installed_inventory(self.root/'switch')
        lib = self.root/'switch/lib'
        lib.mkdir()
        (lib/'fixture.vo').write_text('new library')
        self.assertNotEqual(probe.installed_inventory(self.root/'switch')['sha256'],before['sha256'])

    def test_external_installed_symlink_rejected(self):
        path = self.binary()
        outside = self.root/'outside'
        outside.write_text('external')
        path.with_name('link').symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError,'external'): probe.installed_inventory(self.root/'switch')

    def test_internal_symlink_recorded(self):
        path = self.binary()
        path.with_name('link').symlink_to('rocq')
        self.assertEqual(probe.installed_inventory(self.root/'switch')['files']['bin/link'],{'symlink':'rocq'})

    def test_empty_switch_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'empty'): probe.installed_inventory(self.root)


if __name__ == '__main__':
    unittest.main()
