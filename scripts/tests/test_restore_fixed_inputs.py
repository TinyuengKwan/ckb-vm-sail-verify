import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import restore_fixed_inputs as restore


class RestoreInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_staging_destination_is_new_and_noncanonical(self):
        out = self.root / 'out'
        self.assertEqual(restore.destination_for('staging', out), out / 'checkout')
        self.assertFalse(out.exists())

    def test_existing_output_refused(self):
        out = self.root / 'out'
        out.mkdir()
        (out / 'keep').write_text('keep')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            restore.destination_for('staging', out)
        self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_existing_canonical_checkout_refused_before_inputs(self):
        canonical = self.root / 'canonical'
        canonical.mkdir()
        with patch.object(restore, 'CANONICAL', canonical), patch.object(restore, 'load_handoff') as load:
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                restore.run(self.root / 'missing-handoff', self.root, self.root / 'out', 'canonical')
            load.assert_not_called()
        self.assertFalse((self.root / 'out').exists())

    def test_canonical_mode_has_exact_destination(self):
        canonical = self.root / 'canonical'
        with patch.object(restore, 'CANONICAL', canonical):
            self.assertEqual(restore.destination_for('canonical', self.root / 'out'), canonical)
            with self.assertRaisesRegex(RuntimeError, 'overlaps'):
                restore.destination_for('canonical', canonical / 'reports')

    def test_staging_cannot_masquerade_as_canonical(self):
        out = self.root / 'out'
        with patch.object(restore, 'CANONICAL', out / 'checkout'):
            with self.assertRaisesRegex(RuntimeError, 'scope differs'):
                restore.destination_for('staging', out)

    def test_unknown_mode_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'unknown restoration mode'):
            restore.destination_for('run-proof', self.root / 'out')

    def test_aliased_output_refused(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'aliased'):
            restore.new_path(alias / 'new')

    def test_handoff_is_fixed_identity_not_self_approval(self):
        path = self.root / 'handoff.json'
        path.write_text('{"kind":"fixed-input-handoff-preparation-only"}')
        with self.assertRaisesRegex(RuntimeError, 'unapproved handoff identity'):
            restore.load_handoff(path)

    def test_reference_hash_and_path_protection(self):
        path = self.root / 'input'
        path.write_bytes(b'fixed')
        row = {'path': 'input', 'sha256': restore.sha(path)}
        self.assertEqual(restore.reference(self.root, row), path)
        for bad in [{**row, 'path': '../input'}, {**row, 'path': '/input'}, {**row, 'sha256': '0' * 64},
                    {**row, 'approved': True}]:
            with self.subTest(row=bad), self.assertRaises(RuntimeError): restore.reference(self.root, bad)

    def test_reference_symlink_refused(self):
        path = self.root / 'input'
        path.write_bytes(b'fixed')
        (self.root / 'alias').symlink_to(path)
        with self.assertRaisesRegex(RuntimeError, 'reference differs'):
            restore.reference(self.root, {'path': 'alias', 'sha256': restore.sha(path)})

    def test_duplicate_json_refused(self):
        path = self.root / 'input.json'
        path.write_text('{"a":0,"a":1}')
        with self.assertRaisesRegex(RuntimeError, 'duplicate JSON'):
            restore.read(path)

    def test_environment_is_minimal_and_restored_even_after_error(self):
        before = dict(os.environ)
        with patch.dict(os.environ, {'GIT_DIR': '/wrong', 'LD_PRELOAD': '/wrong', 'PYTHONPATH': '/wrong'}):
            dirty = dict(os.environ)
            with self.assertRaisesRegex(RuntimeError, 'stop'):
                with restore.isolated_process_environment():
                    self.assertEqual(dict(os.environ), restore.clean_environment())
                    self.assertEqual(os.environ['GIT_ALLOW_PROTOCOL'], 'file')
                    raise RuntimeError('stop')
            self.assertEqual(dict(os.environ), dirty)
        self.assertEqual(dict(os.environ), before)

    def source_fixture(self):
        source = self.root / 'body'
        source.write_bytes(b'source bytes')
        empty = self.root / 'empty'
        empty.mkdir(mode=0o750)
        entries = {'source/file': restore.bundle.identity(source), 'source/empty': restore.bundle.identity(empty)}
        archive = self.root / 'source.tar.gz'
        restore.bundle.write_archive(archive, {'source/file': source, 'source/empty': empty}, entries)
        return archive, {'entries': entries}

    def test_source_transfer_extraction_and_empty_directory(self):
        archive, descriptor = self.source_fixture()
        destination = self.root / 'extracted'
        restore.extract_source(archive, descriptor, destination, restore.sha(archive))
        self.assertEqual((destination / 'source/file').read_bytes(), b'source bytes')
        self.assertEqual((destination / 'source/empty').stat().st_mode & 0o777, 0o750)

    def test_source_archive_hash_rejected_before_destination_creation(self):
        archive, descriptor = self.source_fixture()
        with self.assertRaisesRegex(RuntimeError, 'archive drift before'):
            restore.extract_source(archive, descriptor, self.root / 'extracted', '0' * 64)
        self.assertFalse((self.root / 'extracted').exists())

    def test_source_links_refused_before_extraction(self):
        archive, descriptor = self.source_fixture()
        descriptor['entries']['source/link'] = {'kind': 'symlink', 'target': 'file'}
        with self.assertRaisesRegex(RuntimeError, 'source link refused'):
            restore.extract_source(archive, descriptor, self.root / 'extracted', restore.sha(archive))
        self.assertFalse((self.root / 'extracted').exists())

    def test_source_content_mismatch_fails(self):
        archive, descriptor = self.source_fixture()
        descriptor['entries']['source/file']['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'staged inventory differs'):
            restore.extract_source(archive, descriptor, self.root / 'extracted', restore.sha(archive))

    def root_fixture(self):
        staged = self.root / 'staged'
        entries = {}
        for name in restore.INSTALL_ROOTS:
            path = staged / 'artifacts/boundary-check' / name
            path.mkdir(parents=True)
            entries[str(path.relative_to(staged))] = {'kind': 'directory', 'mode': path.stat().st_mode & 0o777}
        return staged, entries

    def test_installation_roots_are_exact_not_arbitrary_destinations(self):
        staged, entries = self.root_fixture()
        self.assertEqual(restore.installation_roots(entries), sorted(restore.INSTALL_ROOTS))
        for bad in [{**entries, 'scripts/injected.py': {'kind': 'file'}}, {},
                    {key: value for key, value in entries.items() if not key.endswith(restore.INSTALL_ROOTS[0])}]:
            with self.assertRaises(RuntimeError): restore.installation_roots(bad)

    def test_installation_collision_checked_before_any_move(self):
        staged, entries = self.root_fixture()
        checkout = self.root / 'checkout'
        occupied = checkout / 'artifacts/boundary-check' / restore.INSTALL_ROOTS[-1]
        occupied.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, 'destination occupied'):
            restore.install_staged_roots(staged, checkout, entries)
        self.assertTrue(all((staged / 'artifacts/boundary-check' / name).is_dir() for name in restore.INSTALL_ROOTS))

    def test_installation_moves_only_new_disjoint_roots(self):
        staged, entries = self.root_fixture()
        checkout = self.root / 'checkout'
        checkout.mkdir()
        (checkout / 'keep').write_text('keep')
        restore.install_staged_roots(staged, checkout, entries)
        self.assertEqual((checkout / 'keep').read_text(), 'keep')
        self.assertTrue(all((checkout / name).is_dir() for name in entries))


if __name__ == '__main__':
    unittest.main()
