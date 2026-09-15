"""The new Rocq driver must not inherit the Aeneas switch for compilation."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_main_rocq as driver


class RocqContextTests(unittest.TestCase):
    def setUp(self):
        self.env = {'OPAMROOT': '/private/aeneas', 'OPAMSWITCH': 'isolated-aeneas', 'PATH': '/private/old/bin',
                    'OPAMCLI': 'old', 'OCAMLPATH': 'old', 'CAML_LD_LIBRARY_PATH': 'old',
                    'COQPATH': 'old', 'ROCQPATH': 'old', 'SAIL_DIR': '/private/sail'}
        self.installation = {'opam_root': '/private/rocq', 'switch': 'isolated-rocq',
                             'opam_bootstrap': {'path': '/usr/bin/opam'},
                             'binaries': {'rocq': {'path': '/private/rocq/isolated-rocq/bin/rocq'}}}
        self.root, self.out = Path('/candidate'), Path('/new/spike')
        self.binaries = {'aeneas': Path('/package/bin/base/aeneas')}

    def commands(self):
        return driver.commands(self.root, self.out, self.env, self.binaries, self.installation)

    def test_rocq_context_clears_ambient_switch_and_library_paths(self):
        original = self.env.copy()
        env = driver.rocq_environment(self.env, self.installation)
        self.assertEqual(env['OPAMROOT'], '/private/rocq')
        self.assertEqual(env['OPAMSWITCH'], 'isolated-rocq')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        for key in ('OPAMCLI', 'OCAMLPATH', 'CAML_LD_LIBRARY_PATH', 'COQPATH', 'ROCQPATH'):
            self.assertNotIn(key, env)
        self.assertEqual(self.env, original)

    def test_rocq_context_rejects_unreviewed_switch(self):
        for switch in ('rocq-spike', 'isolated-aeneas', '', '--help'):
            with self.subTest(switch=switch), self.assertRaises(RuntimeError):
                driver.rocq_environment(self.env, {**self.installation, 'switch': switch})

    def test_opam_requires_absolute_selection_and_safe_switch(self):
        for opam, root, switch in [('opam', '/private', 's'), ('/usr/bin/opam', 'relative', 's'),
                                  ('/usr/bin/opam', '/private', '--help'), ('/usr/bin/opam', '/private', '../s')]:
            with self.subTest(root=root, switch=switch), self.assertRaises(RuntimeError):
                driver.opam_exec(opam, root, switch)

    def test_exact_original_ten_stage_inventory(self):
        self.assertEqual(list(self.commands()), driver.STAGES)
        self.assertEqual(len(self.commands()), 10)

    def test_rust_translation_selects_aeneas_context_and_real_new_llbc(self):
        argv, cwd = self.commands()['rust-generate']
        self.assertEqual(argv, ['/usr/bin/opam', 'exec', '--root=/private/aeneas',
            '--switch=isolated-aeneas', '--set-switch', '--', '/package/bin/base/aeneas',
            '-backend', 'rocq', '-dest', '/new/spike/rust', '/candidate/target/CkbVmProduction.llbc'])
        self.assertEqual(cwd, self.out)

    def test_every_compilation_selects_pinned_rocq_binary_and_context(self):
        for name, (argv, _) in self.commands().items():
            if name in ('rust-generate', 'packages'): continue
            with self.subTest(name=name):
                self.assertEqual(argv[:7], ['/usr/bin/opam', 'exec', '--root=/private/rocq',
                    '--switch=isolated-rocq', '--set-switch', '--', '/private/rocq/isolated-rocq/bin/rocq'])
                self.assertNotIn('--root=/private/aeneas', argv)

    def test_commands_and_working_directories_are_verified(self):
        commands = self.commands()
        report = {'stages': [{'name': n, 'command': a, 'cwd': str(d)} for n, (a, d) in commands.items()]}
        driver.check_commands(report, commands)
        for field, value in [('cwd', '/ambient'), ('command', ['rocq', 'compile'])]:
            changed = copy.deepcopy(report)
            changed['stages'][4][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'command/context'):
                driver.check_commands(changed, commands)

    def test_missing_and_reordered_stages_rejected(self):
        commands = self.commands()
        rows = [{'name': n, 'command': a, 'cwd': str(d)} for n, (a, d) in commands.items()]
        for stages in (rows[1:], rows[::-1], rows + [rows[0]]):
            with self.assertRaisesRegex(RuntimeError, 'inventory'):
                driver.check_commands({'stages': stages}, commands)

    def generation(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'candidate'
        out = Path(temp.name) / 'evidence'
        out.mkdir()
        destination = root / 'proof/rocq/generated/sail'
        backup = destination.parent / '.sail-install-test'
        destination.mkdir(parents=True)
        backup.mkdir()
        for name in ('rv64d.v', 'rv64d_types.v'):
            (destination / name).write_text(name)
        record = {'source': str(root / 'deps/sail-riscv/build/rocq'), 'destination': str(destination),
                  'installation_backup': str(backup), 'status': 'installed', 'published': True,
                  'policy_changed': False, 'installed_files': ['rv64d.v', 'rv64d_types.v']}
        transaction = backup / 'transaction.json'
        transaction.write_text(driver.json.dumps(record))
        log = out / 'generate-sail-rocq.log'
        log.write_text('SAIL_INSTALL_JSON=' + driver.json.dumps(record) + '\n')
        report = {'candidate': str(root), 'stages': [{'name': 'generate-sail-rocq',
                  'argv': ['bash', 'scripts/generate_proof_model.sh', 'rocq'], 'exit_code': 0,
                  'log': log.name, 'log_sha256': driver.sha(log)}], 'sail_generation': record,
                  'sail_transaction': {'path': str(transaction), 'sha256': driver.sha(transaction)}}
        return root, out, report

    def test_generation_binds_exact_transaction_and_published_file_bytes(self):
        root, out, report = self.generation()
        result = driver.generation_evidence(report, out, root)
        self.assertEqual(set(result['installed_files_sha256']), {'rv64d.v', 'rv64d_types.v'})
        self.assertEqual(result['transaction_sha256'], report['sail_transaction']['sha256'])
        path = root / 'proof/rocq/generated/sail/rv64d.v'
        path.write_text('new bytes')
        self.assertNotEqual(driver.generation_evidence(report, out, root), result)

    def test_generation_refuses_missing_or_relocated_output_and_extra_logs(self):
        root, out, report = self.generation()
        changed = copy.deepcopy(report)
        changed['sail_generation']['destination'] = '/old/rocq'
        with self.assertRaises(RuntimeError): driver.generation_evidence(changed, out, root)
        log = out / 'generate-sail-rocq.log'
        log.write_text(log.read_text() * 2)
        report['stages'][0]['log_sha256'] = driver.sha(log)
        with self.assertRaisesRegex(RuntimeError, 'record mismatch'):
            driver.generation_evidence(report, out, root)

    def test_generation_refuses_failed_stage_missing_file_and_symlink(self):
        root, out, report = self.generation()
        changed = copy.deepcopy(report)
        changed['stages'][0]['exit_code'] = 1
        with self.assertRaisesRegex(RuntimeError, 'not completed'):
            driver.generation_evidence(changed, out, root)
        path = root / 'proof/rocq/generated/sail/rv64d.v'
        path.rename(out / 'saved.v')
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            driver.generation_evidence(report, out, root)
        path.symlink_to(out / 'saved.v')
        with self.assertRaisesRegex(RuntimeError, 'linked'):
            driver.generation_evidence(report, out, root)

    def primitives(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = root / 'source.v'
        source.write_text('upstream support\n')
        return source, root / 'Primitives.v', driver.sha(source)

    def test_missing_primitives_are_copied_from_explicit_hashed_source(self):
        source, target, expected = self.primitives()
        result = driver.install_primitives(source, target, expected)
        self.assertEqual(result, {'source': str(source), 'sha256': expected, 'installation': 'copied_from_verified_source'})
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(driver.install_primitives(source, target, expected)['installation'], 'translator_emitted_exact')

    def test_unexpected_existing_primitives_are_not_overwritten(self):
        source, target, expected = self.primitives()
        target.write_text('unexpected')
        with self.assertRaisesRegex(RuntimeError, 'not overwritten'):
            driver.install_primitives(source, target, expected)
        self.assertEqual(target.read_text(), 'unexpected')

    def test_primitives_source_drift_and_output_symlink_rejected(self):
        source, target, expected = self.primitives()
        with self.assertRaisesRegex(RuntimeError, 'source identity'):
            driver.install_primitives(source, target, 'wrong')
        target.symlink_to(source)
        with self.assertRaisesRegex(RuntimeError, 'linked'):
            driver.install_primitives(source, target, expected)


if __name__ == '__main__':
    unittest.main()
