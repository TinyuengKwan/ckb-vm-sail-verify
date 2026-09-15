from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sail_model_transaction as transaction


class SailModelTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sail-transaction-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.destination = self.root / 'source', self.root / 'destination'
        for directory in (self.source, self.destination):
            directory.mkdir()
            (directory / 'stale.lean').write_text('old')

    def generate(self):
        self.assertFalse(self.source.exists())
        self.source.mkdir()
        (self.source / 'Fresh.lean').write_text('fresh')

    def adapt(self, stage):
        self.assertNotEqual(stage, self.destination)
        self.assertEqual((self.destination / 'stale.lean').read_text(), 'old')
        (stage / 'Fresh.lean').write_text('adapted')

    def test_exact_replacement_keeps_both_backups(self):
        row = transaction.replace_model(self.source, self.destination, self.generate, self.adapt)
        self.assertEqual(row['status'], 'installed')
        self.assertEqual(sorted(p.name for p in self.destination.iterdir()), ['Fresh.lean'])
        self.assertEqual((self.destination / 'Fresh.lean').read_text(), 'adapted')
        self.assertEqual((self.source / 'Fresh.lean').read_text(), 'fresh')
        for field in ('generation_backup', 'installation_backup'):
            self.assertEqual((Path(row[field]) / 'previous/stale.lean').read_text(), 'old')

    def test_generation_failure_restores_original_names(self):
        def fail():
            self.generate()
            raise RuntimeError('generation failed')
        with self.assertRaisesRegex(RuntimeError, 'generation failed'):
            transaction.replace_model(self.source, self.destination, fail, self.adapt)
        for directory in (self.source, self.destination):
            self.assertEqual((directory / 'stale.lean').read_text(), 'old')
        failed = list(self.root.glob('.sail-generation-*/failed-output/Fresh.lean'))
        self.assertEqual(len(failed), 1)

    def test_adaptation_failure_does_not_publish(self):
        def fail(stage):
            self.adapt(stage)
            raise RuntimeError('adapter failed')
        with self.assertRaisesRegex(RuntimeError, 'adapter failed'):
            transaction.replace_model(self.source, self.destination, self.generate, fail)
        self.assertTrue((self.source / 'stale.lean').is_file())
        self.assertTrue((self.destination / 'stale.lean').is_file())
        self.assertEqual(len(list(self.root.glob('.sail-install-*/staged/Fresh.lean'))), 1)

    def test_publish_failure_restores_previous_destination(self):
        rename = Path.rename
        def fail(path, target):
            if path.name == 'staged':
                raise OSError('publish failed')
            return rename(path, target)
        with patch.object(Path, 'rename', fail), self.assertRaisesRegex(OSError, 'publish failed'):
            transaction.replace_model(self.source, self.destination, self.generate, self.adapt)
        self.assertTrue((self.source / 'stale.lean').is_file())
        self.assertTrue((self.destination / 'stale.lean').is_file())

    def test_failure_before_generation_does_not_move_original(self):
        rename = Path.rename
        def fail(path, target):
            if path == self.source:
                raise OSError('backup failed')
            return rename(path, target)
        with patch.object(Path, 'rename', fail), self.assertRaisesRegex(OSError, 'backup failed'):
            transaction.replace_model(self.source, self.destination, self.generate, self.adapt)
        self.assertTrue((self.source / 'stale.lean').is_file())
        self.assertFalse(list(self.root.glob('.sail-generation-*/failed-output')))

    def test_first_generation_without_existing_trees(self):
        source, dest = self.root / 'new-source', self.root / 'new-destination'
        def generate():
            source.mkdir()
            (source / 'New.v').write_text('new')
        row = transaction.replace_model(source, dest, generate, lambda _: None)
        self.assertFalse(row['old_source_saved'])
        self.assertFalse(row['old_destination_saved'])
        self.assertEqual((dest / 'New.v').read_text(), 'new')

    def test_no_output_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'missing fresh'):
            transaction.replace_model(self.source, self.destination, lambda: None, self.adapt)
        self.assertTrue((self.source / 'stale.lean').is_file())

    def test_empty_output_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'empty fresh'):
            transaction.replace_model(self.source, self.destination, self.source.mkdir, self.adapt)

    def test_symlink_output_rejected(self):
        def generate():
            self.generate()
            (self.source / 'Link.lean').symlink_to(self.destination / 'stale.lean')
        with self.assertRaisesRegex(RuntimeError, 'nonregular'):
            transaction.replace_model(self.source, self.destination, generate, self.adapt)

    def test_symlink_directory_rejected_before_mutation(self):
        link = self.root / 'link'
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            transaction.replace_model(link, self.destination, self.generate, self.adapt)
        self.assertTrue((self.source / 'stale.lean').is_file())

    def test_hardlink_output_rejected(self):
        def generate():
            self.generate()
            os.link(self.destination / 'stale.lean', self.source / 'Linked.lean')
        with self.assertRaisesRegex(RuntimeError, 'hardlinked'):
            transaction.replace_model(self.source, self.destination, generate, self.adapt)

    def test_cached_modules_rejected(self):
        def generate():
            self.generate()
            (self.source / 'Old.olean').write_bytes(b'cache')
        with self.assertRaisesRegex(RuntimeError, 'cached'):
            transaction.replace_model(self.source, self.destination, generate, self.adapt)

    def test_overlapping_paths_rejected(self):
        for destination in (self.source, self.source / 'child', self.root):
            with self.subTest(destination=destination), self.assertRaisesRegex(RuntimeError, 'overlapping'):
                transaction.replace_model(self.source, destination, self.generate, self.adapt)

    def test_broad_directory_rejected(self):
        for directory in (Path('/'), Path.home()):
            with self.assertRaisesRegex(RuntimeError, 'broad'):
                transaction.directory_path(directory)


class SailBackendTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sail-backend-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sail = self.root / 'deps/sail-riscv'
        self.build = self.sail / 'build'
        (self.build / 'model').mkdir(parents=True)
        (self.build / 'config').mkdir()
        (self.build / 'config/rv64d_v256_e64.json').write_text('old config')
        (self.build / 'CMakeCache.txt').write_text('CMAKE_HOME_DIRECTORY:INTERNAL=' + str(self.sail) + '\n')
        self.config = self.root / 'sail-model/build/ckb_vm_config.json'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('{"config":"current"}')
        self.calls = []

    def runner(self, argv, cwd, check):
        self.assertEqual(cwd, self.root)
        self.assertTrue(check)
        self.calls.append(argv)
        if argv[0] == 'cmake':
            self.assertEqual((self.build / 'config/rv64d_v256_e64.json').read_bytes(), self.config.read_bytes())
            lean = argv[-1] == 'generated_lean_rv64d'
            source = self.build / ('model/Lean_RV64D' if lean else 'rocq')
            self.assertFalse(source.exists())
            source.mkdir()
            files = ['LeanRV64D.lean', 'LeanRV64D/Defs.lean', 'lakefile.toml'] if lean else ['rv64d.v', 'rv64d_types.v']
            for name in files:
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('fresh')
        else:
            self.assertEqual(argv[2], 'lean')
            stage = Path(argv[3])
            self.assertEqual(stage.name, 'staged')
            (stage / 'lean-toolchain').write_text('pinned')

    def test_lean_generates_and_adapts_only_staging(self):
        row = transaction.run_backend(self.root, 'lean', runner=self.runner)
        self.assertEqual(row['status'], 'installed')
        self.assertEqual(len(self.calls), 2)
        destination = Path(row['destination'])
        self.assertEqual((destination / 'lean-toolchain').read_text(), 'pinned')
        self.assertIn(str(destination / 'ckb_vm_config.json'),
                      (destination / 'ckb_vm_config.json.sha256').read_text())

    def test_rocq_alias_generates_fresh_without_lean_adapter(self):
        for backend in ('rocq', 'coq'):
            with self.subTest(backend=backend):
                row = transaction.run_backend(self.root, backend, runner=self.runner)
                self.assertEqual(row['status'], 'installed')
                self.assertEqual(self.calls[-1][-1], 'generated_rocq_rv64d')
        self.assertEqual(len(self.calls), 2)

    def test_config_drift_rejects_publication(self):
        def runner(*args, **kwargs):
            self.runner(*args, **kwargs)
            self.config.write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'configuration changed'):
            transaction.run_backend(self.root, 'lean', runner=runner)
        self.assertFalse((self.root / 'proof/lean/generated/sail').exists())

    def test_wrong_cmake_source_rejected_before_generation(self):
        (self.build / 'CMakeCache.txt').write_text('CMAKE_HOME_DIRECTORY:INTERNAL=/wrong\n')
        with self.assertRaisesRegex(RuntimeError, 'CMake source'):
            transaction.run_backend(self.root, 'lean', runner=self.runner)
        self.assertFalse(self.calls)

    def test_unknown_backend_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'backend'):
            transaction.run_backend(self.root, 'bad', runner=self.runner)
        self.assertFalse(self.calls)

    def test_concurrent_generation_rejected(self):
        import fcntl
        with (self.build / '.sail-proof-generation.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                transaction.run_backend(self.root, 'lean', runner=self.runner)
        self.assertFalse(self.calls)

    def test_real_adapter_only_modifies_exact_staging_directory(self):
        repository = Path(__file__).resolve().parents[2]
        for name in ('scripts/configure_lean_project.sh', 'proof/lean/compat/sail-defs-computable.patch',
                     'proof/lean/expected_build_status.txt', 'proof/lean/theorems/lean-toolchain'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / name, target)
        published = self.root / 'proof/lean/generated/sail'
        published.mkdir(parents=True)
        (published / 'unchanged.txt').write_text('old model')
        stage = published.parent / '.sail-install-fixture/staged'
        (stage / 'LeanRV64D').mkdir(parents=True)
        (stage / 'lakefile.toml').write_text('name = "Lean_RV64D"\nrev = "main"\n')
        defs = stage / 'LeanRV64D/Defs.lean'
        defs.write_text('\n' * 8 + 'open Sail\nopen Sail.ConcurrencyInterfaceV1\n\n' +
                        'noncomputable section\nnamespace LeanRV64D\n\n' +
                        '/-- Type quantifiers: k_a : Type -/\n')
        adapter = self.root / 'scripts/configure_lean_project.sh'
        for _ in range(2):
            subprocess.run(['bash', adapter, 'lean', stage], check=True, capture_output=True)
        self.assertNotIn('noncomputable section', defs.read_text())
        self.assertTrue((stage / 'lean-toolchain').is_file())
        self.assertEqual(sorted(p.name for p in published.iterdir()), ['unchanged.txt'])
        self.assertEqual((published / 'unchanged.txt').read_text(), 'old model')
        for invalid in (self.root, published, stage.parent):
            result = subprocess.run(['bash', adapter, 'lean', invalid], capture_output=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
