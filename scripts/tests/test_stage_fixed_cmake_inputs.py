import hashlib
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage_fixed_cmake_inputs as stage


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def archive(self, rows):
        path = self.root / 'source.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, kind, data, mode in rows:
                member = tarfile.TarInfo(name)
                member.type, member.mode = kind, mode
                if kind == tarfile.REGTYPE:
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
                else:
                    member.linkname = 'root/file' if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ''
                    archive.addfile(member)
        return path

    def row(self, data, algorithm='SHA256'):
        return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'declaration': {'hash_algorithm': algorithm,
                                'digest': hashlib.new({'SHA256': 'sha256', 'SHA3_256': 'sha3_256'}[algorithm], data).hexdigest()}}

    def test_exact_bytes_and_both_hash_algorithms(self):
        for algorithm in ['SHA256', 'SHA3_256']: stage.data_matches(b'data', self.row(b'data', algorithm))

    def test_changed_bytes_rejected(self):
        with self.assertRaises(RuntimeError): stage.data_matches(b'datb', self.row(b'data'))

    def test_wrong_length_rejected(self):
        with self.assertRaises(RuntimeError): stage.data_matches(b'dat', self.row(b'data'))

    def test_wrong_declaration_hash_rejected(self):
        row = self.row(b'data'); row['declaration']['digest'] = '0' * 64
        with self.assertRaises(RuntimeError): stage.data_matches(b'data', row)

    def test_unknown_algorithm_rejected(self):
        row = self.row(b'data'); row['declaration']['hash_algorithm'] = 'MD5'
        with self.assertRaises(RuntimeError): stage.data_matches(b'data', row)

    def test_files_empty_directories_and_modes(self):
        archive = self.archive([('root/', tarfile.DIRTYPE, b'', 0o755), ('root/empty/', tarfile.DIRTYPE, b'', 0o750),
                                ('root/file', tarfile.REGTYPE, b'fixed', 0o644)])
        records = stage.unpack_source(archive, self.root / 'out', 'root')
        self.assertEqual(set(records), {'root', 'root/empty', 'root/file'})
        self.assertEqual(records['root/empty']['mode'], 0o750)
        self.assertEqual((self.root / 'out/root/file').read_bytes(), b'fixed')

    def test_duplicate_member_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755)] * 2)
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_wrong_root_rejected(self):
        archive = self.archive([('other', tarfile.DIRTYPE, b'', 0o755)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_traversal_rejected(self):
        archive = self.archive([('root/../escape', tarfile.REGTYPE, b'x', 0o644)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')
        self.assertFalse((self.root / 'escape').exists())

    def test_symlink_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755), ('root/link', tarfile.SYMTYPE, b'', 0o777)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_hardlink_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755), ('root/link', tarfile.LNKTYPE, b'', 0o644)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_special_file_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755), ('root/fifo', tarfile.FIFOTYPE, b'', 0o644)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_special_permissions_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755), ('root/file', tarfile.REGTYPE, b'x', 0o4755)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_missing_explicit_parent_rejected(self):
        archive = self.archive([('root', tarfile.DIRTYPE, b'', 0o755), ('root/sub/file', tarfile.REGTYPE, b'x', 0o644)])
        with self.assertRaises(RuntimeError): stage.unpack_source(archive, self.root / 'out', 'root')

    def test_existing_output_refused_before_hashing(self):
        with patch.object(stage, 'sha', side_effect=AssertionError('must not read inputs')):
            with self.assertRaises(RuntimeError): stage.stage(self.root / 'missing', self.root / 'missing2', self.root)

    def test_symlink_parent_refused(self):
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(RuntimeError): stage.new_directory(self.root / 'alias/out')

    def test_disconnected_fetch_overrides_are_explicit(self):
        options = stage.configure_options(self.root)
        self.assertIn('-DFETCHCONTENT_FULLY_DISCONNECTED:BOOL=ON', options)
        self.assertIn('-DDOWNLOAD_GMP:BOOL=TRUE', options)
        self.assertEqual(sum('SOURCE_DIR_' in option for option in options), 3)
        self.assertNotIn('-DDOWNLOAD_GMP:BOOL=FALSE', options)


if __name__ == '__main__': unittest.main()
