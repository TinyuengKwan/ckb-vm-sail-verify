import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_snapshot as source
from probes.probe_isolated_foundation import check_initial_outputs


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='source-snapshot-test-')
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.root = self.directory / 'original'
        for name in source.REPOS:
            repo = self.root / name
            repo.mkdir(parents=True, exist_ok=True)
            self.command(repo, 'init', '-q')
            (repo / 'source.txt').write_text('original\n')
            (repo / '.gitignore').write_text('build/\n')
            self.commit(repo)
        # Capture the two embedded repositories as the expected gitlinks.
        self.commit(self.root)
        manager = patch.object(source.baseline, 'check', return_value={'fixture_only': True})
        manager.start()
        self.addCleanup(manager.stop)

    def command(self, repo, *argv):
        return subprocess.check_output(['git', '-C', str(repo), *argv], stderr=subprocess.PIPE)

    def commit(self, repo):
        self.command(repo, 'add', '--all')
        self.command(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                     'commit', '-qm', 'synthetic fixture only')

    def clone(self):
        destination = self.directory / 'checkout'
        for name in source.REPOS:
            target = destination / name
            subprocess.check_output(['git', 'clone', '--no-hardlinks', str(self.root / name), str(target)], stderr=subprocess.PIPE)
        return destination

    def test_clean_source_identity(self):
        value = source.capture(self.root)
        self.assertFalse(value['semantic_review_claimed'])
        self.assertEqual(value['repositories']['.']['changes_from_head'], {})
        self.assertEqual(value['snapshot_sha256'], source.digest(source.canonical({k:v for k,v in value.items() if k != 'snapshot_sha256'})))

    def test_worktree_add_modify_delete_and_mode_are_explicit(self):
        (self.root / 'source.txt').write_text('modified\n')
        (self.root / 'added.py').write_text('fixture\n')
        (self.root / '.gitignore').unlink()
        value = source.capture(self.root)['repositories']['.']['changes_from_head']
        self.assertEqual({k:v['operation'] for k,v in value.items()},
                         {'.gitignore':'deleted', 'added.py':'added', 'source.txt':'modified'})
        self.assertIsNone(value['added.py']['before'])

    def test_mode_only_change_detected(self):
        (self.root / 'source.txt').chmod(0o755)
        row = source.inventory(self.root)['changes_from_head']['source.txt']
        self.assertEqual(row['after']['mode'], '100755')
        self.assertEqual(row['operation'], 'modified')

    def test_ignored_build_artifacts_not_exported(self):
        build = self.root / 'build'
        build.mkdir()
        (build / 'cached-model').write_text('not source')
        value = source.capture(self.root)
        self.assertNotIn('build/cached-model', value['repositories']['.']['files'])

    def test_source_symlink_rejected(self):
        (self.root / 'linked').symlink_to(self.root / 'source.txt')
        with self.assertRaisesRegex(RuntimeError, 'symlink'): source.capture(self.root)

    def test_broken_source_symlink_rejected(self):
        (self.root / 'broken').symlink_to(self.root / 'absent')
        with self.assertRaises(RuntimeError): source.capture(self.root)

    def test_sail_changes_not_implicitly_adopted(self):
        (self.root / 'deps/sail-riscv/source.txt').write_text('different')
        with self.assertRaisesRegex(RuntimeError, 'Sail'): source.capture(self.root)

    def test_submodule_head_drift_rejected(self):
        repo = self.root / 'deps/ckb-vm'
        (repo / 'new').write_text('new')
        self.commit(repo)
        with self.assertRaisesRegex(RuntimeError, 'revision'): source.capture(self.root)

    def test_unsafe_names_rejected(self):
        for name in ['../source.txt', '/absolute', 'a//b', '.git/config', 'a/../b', './b', '']:
            with self.subTest(name=name), self.assertRaises(RuntimeError): source.safe(name)

    def test_export_and_restore_exact_overlay(self):
        (self.root / 'source.txt').write_text('modified')
        (self.root / 'new').write_text('added')
        (self.root / '.gitignore').unlink()
        value = source.capture(self.root)
        payload = self.directory / 'payload'
        source.export(self.root, value, payload)
        destination = self.clone()
        source.restore(destination, payload, value)
        self.assertEqual(source.capture(destination), value)
        self.assertEqual((destination / 'source.txt').read_text(), 'modified')
        self.assertFalse((destination / '.gitignore').exists())

    def test_export_refuses_stale_snapshot_and_existing_output(self):
        value = source.capture(self.root)
        destination = self.directory / 'payload'
        source.export(self.root, value, destination)
        with self.assertRaises(FileExistsError): source.export(self.root, value, destination)
        (self.root / 'source.txt').write_text('changed during run')
        with self.assertRaisesRegex(RuntimeError, 'changed'): source.export(self.root, value, self.directory / 'new')

    def test_restore_does_not_overwrite_dirty_clone(self):
        value = source.capture(self.root)
        payload = self.directory / 'payload'
        source.export(self.root, value, payload)
        destination = self.clone()
        (destination / 'source.txt').write_text('user edit')
        with self.assertRaisesRegex(RuntimeError, 'dirty'): source.restore(destination, payload, value)
        self.assertEqual((destination / 'source.txt').read_text(), 'user edit')

    def test_corrupt_payload_rejected(self):
        value = source.capture(self.root)
        payload = self.directory / 'payload'
        source.export(self.root, value, payload)
        (payload / 'source.txt').write_text('corrupt')
        with self.assertRaisesRegex(RuntimeError, 'payload'): source.restore(self.clone(), payload, value)

    def test_object_alternates_rejected(self):
        path = self.root / '.git/objects/info/alternates'
        path.write_text(str(self.root / 'deps/ckb-vm/.git/objects'))
        with self.assertRaisesRegex(RuntimeError, 'alternates'): source.independent(self.root)

    def test_versioned_artifacts_readme_is_not_cached_evidence(self):
        artifacts = self.root / 'artifacts'
        artifacts.mkdir()
        (artifacts / 'README.md').write_text('source documentation')
        self.assertIn('target', check_initial_outputs(self.root))

    def test_historical_artifacts_still_rejected(self):
        artifacts = self.root / 'artifacts'
        artifacts.mkdir()
        (artifacts / 'report.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'historical'): check_initial_outputs(self.root)

    def test_generated_paths_even_empty_or_broken_symlink_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'generated'): check_initial_outputs(self.root)
        target.rmdir()
        target.symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(RuntimeError, 'generated'): check_initial_outputs(self.root)


if __name__ == '__main__':
    unittest.main()
