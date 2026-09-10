"""Exercise the public clean-mode boundary before any compiler invocation.

These are guard tests, not substitutes for the live complete kernel build.
Use real, policy-checked field/factory sources, but mock the large source setup.
"""
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decoder_public_clean as public


class ReachedBuild(Exception):
    pass


class PublicCleanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='public-clean-guard-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.out = self.root / 'new'
        self.out.mkdir()
        self.compiler = self.root / 'compiler'
        self.project = self.out / 'clean/proof/lean/theorems'
        self.import_path = self.project / '.lake/build/lib/lean'
        self.calls = []
        self.report = {'clean_dependency_build': False}
        stack = ExitStack()
        self.addCleanup(stack.close)
        def prepare(clean_root, aeneas):
            self.project.mkdir(parents=True)
            return self.project, {}
        def output(command, **kwargs):
            if '--print-prefix' in command:
                return str(self.compiler) + '\n'
            if 'which' in command:
                return str(self.compiler / 'bin/lean') + '\n'
            return os.pathsep.join([str(self.import_path), str(self.compiler / 'lib/lean')]) + '\n'
        stack.enter_context(patch.object(public.clean, 'prepare', side_effect=prepare))
        stack.enter_context(patch.object(public.gate, 'tools_and_environment',
                                         return_value=({}, {}, self.root / 'support', 'lake')))
        stack.enter_context(patch.object(public.gate, 'source_evidence', return_value={}))
        stack.enter_context(patch.object(public.gate, 'generated_evidence', return_value={}))
        stack.enter_context(patch.object(public.subprocess, 'check_output', side_effect=output))

    def run_stage(self, name, command, *args, **kwargs):
        self.calls.append((name, command))
        raise ReachedBuild()

    def test_source_only_reaches_no_cache_build(self):
        with self.assertRaises(ReachedBuild):
            public.build(self.out, self.run_stage, self.report)
        self.assertEqual(self.calls[0][0], 'clean-main-build')
        self.assertIn('--no-cache', self.calls[0][1])
        self.assertEqual(self.report['clean_dependencies']['initial_compiled_modules'], 0)
        self.assertFalse(self.report['clean_dependency_build'])
        self.assertEqual(list(self.out.rglob('*.olean')), [])

    def test_cached_olean_rejected_before_build(self):
        (self.out / 'Old.olean').write_bytes(b'old compiled input')
        with self.assertRaisesRegex(RuntimeError, 'empty entire public-check compilation tree'):
            public.build(self.out, self.run_stage, self.report)
        self.assertEqual(self.calls, [])

    def test_main_audit_receives_clean_import_path(self):
        stages = []
        def run(name, command, cwd, env, **kwargs):
            stages.append(name)
            if name == 'clean-main-build':
                return ''
            self.assertEqual(name, 'clean-main-audit')
            self.assertEqual(env['LEAN_PATH'], os.pathsep.join([
                str(self.import_path), str(self.compiler / 'lib/lean')]))
            raise ReachedBuild()
        with self.assertRaises(ReachedBuild):
            public.build(self.out, run, self.report)
        self.assertEqual(stages, ['clean-main-build', 'clean-main-audit'])

    def test_cached_ilean_rejected_before_build(self):
        (self.out / 'Old.ilean').write_bytes(b'old compiled input')
        with self.assertRaisesRegex(RuntimeError, 'empty entire public-check compilation tree'):
            public.build(self.out, self.run_stage, self.report)
        self.assertEqual(self.calls, [])

    def test_old_dependency_import_path_rejected(self):
        self.import_path = self.root / 'old/.lake/build/lib/lean'
        with self.assertRaisesRegex(RuntimeError, 'external compiled dependency'):
            public.build(self.out, self.run_stage, self.report)
        self.assertEqual(self.calls, [])

    def test_symlinked_external_dependency_rejected(self):
        self.import_path = self.out / 'looks-local'
        self.import_path.symlink_to(self.root / 'old-cache', target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'external compiled dependency'):
            public.build(self.out, self.run_stage, self.report)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
