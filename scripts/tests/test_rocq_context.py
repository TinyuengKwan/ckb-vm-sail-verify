"""Production Rocq selection and fresh-generation provenance fail closed."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rocq_context as context


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.env = {'OPAMROOT': '/private/aeneas', 'OPAMSWITCH': 'isolated-aeneas', 'PATH': '/ambient/bin',
                    'OCAMLPATH': 'ambient', 'CAML_LD_LIBRARY_PATH': 'ambient', 'COQPATH': 'ambient', 'OPAMCLI': 'old'}
        self.installation = {'opam_root': '/private/rocq', 'switch': 'isolated-rocq',
                             'opam_bootstrap': {'path': '/usr/bin/opam'},
                             'binaries': {'rocq': {'path': '/private/rocq/isolated-rocq/bin/rocq'}}}

    def test_profile_is_explicit_and_unknown_profiles_do_not_fall_back(self):
        self.assertFalse(context.selected({}))
        self.assertTrue(context.selected({'main_toolchain': 'rebuilt-main-v1'}))
        for value in (None, '', 'unknown'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                context.selected({'main_toolchain': value})

    def test_rocq_environment_does_not_change_aeneas_context(self):
        old = self.env.copy()
        env = context.environment(self.env, self.installation)
        self.assertEqual((env['OPAMROOT'], env['OPAMSWITCH'], env['PATH']),
                         ('/private/rocq', 'isolated-rocq', '/usr/bin:/bin'))
        for key in ('OCAMLPATH', 'CAML_LD_LIBRARY_PATH', 'COQPATH', 'OPAMCLI'):
            self.assertNotIn(key, env)
        self.assertEqual(self.env, old)
        with self.assertRaises(RuntimeError):
            context.environment(self.env, {**self.installation, 'switch': 'rocq-spike'})

    def test_opam_requires_absolute_binary_root_and_safe_switch(self):
        for binary, root, switch in [('opam', '/private', 's'), ('/usr/bin/opam', 'relative', 's'),
                                     ('/usr/bin/opam', '/private', '--help'), ('/usr/bin/opam', '/private', '../s')]:
            with self.subTest(binary=binary, root=root, switch=switch), self.assertRaises(RuntimeError):
                context.opam_exec(binary, root, switch)

    def command_fixture(self):
        return context.commands(Path('/project'), Path('/out'), self.env,
                                {'aeneas': Path('/package/bin/aeneas')}, self.installation)

    def test_generation_is_mandatory_before_original_ten_stages(self):
        commands = self.command_fixture()
        self.assertEqual(list(commands), ['sail-generate', *context.MODEL_STAGES])
        self.assertEqual(len(commands), 11)
        self.assertEqual(commands['sail-generate'], (['bash', 'scripts/generate_proof_model.sh', 'rocq'], Path('/project')))

    def test_translation_and_compilation_have_distinct_explicit_roots(self):
        commands = self.command_fixture()
        self.assertIn('--root=/private/aeneas', commands['rust-generate'][0])
        self.assertIn('--switch=isolated-aeneas', commands['rust-generate'][0])
        for name, (argv, _) in commands.items():
            if name in ('sail-generate', 'rust-generate'): continue
            self.assertIn('--root=/private/rocq', argv)
            self.assertIn('--switch=isolated-rocq', argv)
            if name != 'packages': self.assertIn('/private/rocq/isolated-rocq/bin/rocq', argv)

    def test_command_cwd_and_stage_inventory_are_checked(self):
        commands = self.command_fixture()
        report = {'stages': [{'name': n, 'command': a, 'cwd': str(d)} for n, (a, d) in commands.items()]}
        context.check_commands(report, commands)
        for key, value in [('cwd', '/ambient'), ('command', ['rocq', 'compile'])]:
            bad = copy.deepcopy(report)
            bad['stages'][4][key] = value
            with self.assertRaises(RuntimeError): context.check_commands(bad, commands)
        for rows in (report['stages'][1:], report['stages'][::-1]):
            with self.assertRaises(RuntimeError): context.check_commands({'stages': rows}, commands)

    def primitive_fixture(self):
        source, target = self.directory / 'source.v', self.directory / 'Primitives.v'
        source.write_text('upstream support\n')
        return source, target, context.sha(source)

    def test_missing_primitives_are_copied_with_explicit_source_record(self):
        source, target, expected = self.primitive_fixture()
        self.assertEqual(context.install_primitives(source, target, expected),
                         {'source': str(source), 'sha256': expected, 'installation': 'copied_from_verified_source'})
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(context.install_primitives(source, target, expected)['installation'], 'translator_emitted_exact')

    def test_wrong_existing_primitives_are_not_overwritten(self):
        source, target, expected = self.primitive_fixture()
        target.write_text('wrong support')
        with self.assertRaisesRegex(RuntimeError, 'not overwritten'):
            context.install_primitives(source, target, expected)
        self.assertEqual(target.read_text(), 'wrong support')

    def test_primitive_source_drift_and_output_link_rejected(self):
        source, target, expected = self.primitive_fixture()
        with self.assertRaises(RuntimeError): context.install_primitives(source, target, 'wrong')
        target.symlink_to(source)
        with self.assertRaises(RuntimeError): context.install_primitives(source, target, expected)

    def generation_fixture(self):
        root, out = self.directory / 'project', self.directory / 'out'
        out.mkdir()
        destination = root / 'proof/rocq/generated/sail'
        destination.mkdir(parents=True)
        backup = destination.parent / '.sail-install-test'
        backup.mkdir()
        for name in ('rv64d.v', 'rv64d_types.v'):
            (destination / name).write_text(name)
        record = {'source': str(root / 'deps/sail-riscv/build/rocq'), 'destination': str(destination),
                  'installation_backup': str(backup), 'status': 'installed', 'published': True,
                  'policy_changed': False, 'installed_files': ['rv64d.v', 'rv64d_types.v']}
        (backup / 'transaction.json').write_text(json.dumps(record))
        log = out / 'sail-generate.log'
        log.write_text('SAIL_INSTALL_JSON=' + json.dumps(record) + '\n')
        report = {'stages': [{'name': 'sail-generate', 'command': ['bash', 'scripts/generate_proof_model.sh', 'rocq'],
                             'cwd': str(root), 'status': 'passed', 'exit_code': 0,
                             'log': log.name, 'log_sha256': context.sha(log)}]}
        return root, out, report

    def test_generation_binds_transaction_and_published_file_bytes(self):
        root, out, report = self.generation_fixture()
        result = context.generation_evidence(root, out, report)
        self.assertEqual(set(result['installed_files_sha256']), {'rv64d.v', 'rv64d_types.v'})
        (root / 'proof/rocq/generated/sail/rv64d.v').write_text('changed')
        self.assertNotEqual(context.generation_evidence(root, out, report), result)

    def test_generation_rejects_failed_stage_and_wrong_command(self):
        root, out, report = self.generation_fixture()
        for key, value in [('exit_code', 1), ('exit_code', False), ('command', ['true']), ('cwd', '/old')]:
            bad = copy.deepcopy(report)
            bad['stages'][0][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): context.generation_evidence(root, out, bad)

    def test_generation_rejects_duplicate_marker_or_missing_file(self):
        root, out, report = self.generation_fixture()
        path = root / 'proof/rocq/generated/sail/rv64d.v'
        path.rename(out / 'saved.v')
        with self.assertRaisesRegex(RuntimeError, 'inventory'): context.generation_evidence(root, out, report)
        (out / 'saved.v').rename(path)
        log = out / 'sail-generate.log'
        log.write_text(log.read_text() * 2)
        report['stages'][0]['log_sha256'] = context.sha(log)
        with self.assertRaisesRegex(RuntimeError, 'duplicate'): context.generation_evidence(root, out, report)

    def test_generation_rejects_output_symlink(self):
        root, out, report = self.generation_fixture()
        path = root / 'proof/rocq/generated/sail/rv64d.v'
        path.rename(out / 'saved.v')
        path.symlink_to(out / 'saved.v')
        with self.assertRaisesRegex(RuntimeError, 'linked'): context.generation_evidence(root, out, report)


if __name__ == '__main__':
    unittest.main()
