import copy
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fixed_install_bundle as bundle


class FixedInstallBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'tool'
        self.source.write_bytes(b'fixed tool bytes')
        self.source.chmod(0o755)
        self.entries = {'prefix/bin/tool': bundle.identity(self.source)}
        self.manifest = {'schema_version': 1, 'kind': 'extra-fixed-prefix-installations-v1',
            'canonical_checkout': '/canonical/checkout', 'inputs': {'policy': 'fixed'},
            'required_external': ['host tools'], 'boundaries': {key: False for key in
                ['clean_room', 'release', 'kernel_execution', 'relocatable', 'host_closure_complete']},
            'entries': self.entries}
        self.path = self.root / 'manifest.json'
        self.archive = self.root / 'tools.tar.gz'

    def save(self, manifest=None):
        self.path.write_text(json.dumps(self.manifest if manifest is None else manifest))
        return bundle.sha(self.path)

    def build(self):
        digest = self.save()
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source}, self.entries)
        return digest

    def raw_archive(self, names=None, body=b'fixed tool bytes', kind=tarfile.REGTYPE):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name in names or ['prefix/bin/tool']:
                item = tarfile.TarInfo(name)
                item.type, item.mode = kind, 0o755
                item.size = len(body) if kind == tarfile.REGTYPE else 0
                if kind == tarfile.LNKTYPE: item.linkname = 'prefix/bin/tool'
                archive.addfile(item, io.BytesIO(body) if item.size else None)

    def test_new_packages_are_xz_and_old_gzip_packages_still_verify(self):
        digest = self.save()
        xz_archive = self.root / 'tools.tar.xz'
        bundle.write_archive(xz_archive, {'prefix/bin/tool': self.source}, self.entries)
        self.assertEqual(bundle.compression_of(xz_archive), 'xz')
        self.assertEqual(xz_archive.read_bytes()[:6], b'\xfd7zXZ\x00')
        result = bundle.stage(xz_archive, self.path, digest, self.root / 'staged-xz')
        self.assertEqual((result['compression'], result['entries']), ('xz', 1))
        self.assertEqual((self.root / 'staged-xz/prefix/bin/tool').read_bytes(), self.source.read_bytes())
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source}, self.entries, 'gz')
        self.assertEqual(bundle.compression_of(self.archive), 'gz')
        self.assertEqual(bundle.verify_archive(self.archive, self.path, digest)['compression'], 'gz')
        self.assertEqual(bundle.decompressed_digest(self.archive), bundle.decompressed_digest(xz_archive))
        misnamed = self.root / 'lying.tar.gz'
        misnamed.write_bytes(xz_archive.read_bytes())
        self.assertEqual(bundle.compression_of(misnamed), 'xz')
        plain = self.root / 'plain.tar'
        with tarfile.open(plain, 'w'): pass
        with self.assertRaisesRegex(RuntimeError, 'unsupported archive compression'):
            bundle.verify_archive(plain, self.path, digest)
        with self.assertRaisesRegex(RuntimeError, 'unsupported archive compression'):
            bundle.write_archive(self.root / 'x.tar.bz2', {'prefix/bin/tool': self.source}, self.entries, 'bz2')

    def test_recompress_xz_keeps_member_and_manifest_identity(self):
        digest = self.save()
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source}, self.entries, 'gz')
        out = self.root / 'repacked.tar.xz'
        result = bundle.recompress_xz(self.archive, self.path, digest, out, threads=2)
        self.assertEqual(result['manifest_sha256'], digest)
        self.assertEqual(result['source_archive_sha256'], bundle.sha(self.archive))
        self.assertEqual(result['archive_sha256'], bundle.sha(out))
        self.assertEqual(result['tar_stream_sha256'], bundle.decompressed_digest(out))
        self.assertEqual(result['compression'], 'xz')
        self.assertFalse(result['clean_room_claimed'])
        self.assertIn('-9', result['xz_argv'])
        staged = bundle.stage(out, self.path, digest, self.root / 'staged-repacked')
        self.assertEqual(staged['archive_sha256'], result['archive_sha256'])
        with self.assertRaisesRegex(RuntimeError, 'destination exists'):
            bundle.recompress_xz(self.archive, self.path, digest, out)
        with self.assertRaisesRegex(RuntimeError, 'not a gzip package'):
            bundle.recompress_xz(out, self.path, digest, self.root / 'twice.tar.xz')
        self.raw_archive(body=b'tampered bytes!!')
        with self.assertRaisesRegex(RuntimeError, 'archived bytes differ'):
            bundle.recompress_xz(self.archive, self.path, digest, self.root / 'tampered.tar.xz')
        self.assertFalse((self.root / 'tampered.tar.xz').exists())
        with self.assertRaisesRegex(RuntimeError, 'xz executable missing'):
            bundle.recompress_xz(self.archive, self.path, digest, self.root / 'noxz.tar.xz', xz='/nonexistent/xz')

    def test_name_validation(self):
        for bad in ['', '/absolute', '../outside', 'a/../b', 'a//b', './a', 'a/', 'a\\b', 'a\0b', True]:
            with self.subTest(name=bad), self.assertRaises(RuntimeError): bundle.safe_name(bad)
        self.assertEqual(bundle.safe_name('source/.git/HEAD'), 'source/.git/HEAD')

    def test_verify_and_stage_roundtrip(self):
        digest = self.build()
        result = bundle.stage(self.archive, self.path, digest, self.root / 'staged')
        self.assertFalse(result['operational_installation_claimed'])
        self.assertEqual((self.root / 'staged/prefix/bin/tool').read_bytes(), self.source.read_bytes())
        self.assertEqual(result['entries'], 1)

    def test_wrong_external_manifest_digest(self):
        self.build()
        with self.assertRaisesRegex(RuntimeError, 'manifest digest'):
            bundle.verify_archive(self.archive, self.path, '0' * 64)

    def test_duplicate_json_key(self):
        self.path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(RuntimeError, 'duplicate JSON'):
            bundle.load_manifest(self.path, bundle.sha(self.path))

    def test_assurance_cannot_be_upgraded_or_number(self):
        for value in [True, 0]:
            changed = copy.deepcopy(self.manifest)
            changed['boundaries']['clean_room'] = value
            digest = self.save(changed)
            with self.subTest(value=value), self.assertRaises(RuntimeError): bundle.load_manifest(self.path, digest)

    def test_unknown_field_rejected(self):
        digest = self.save({**self.manifest, 'approved': True})
        with self.assertRaisesRegex(RuntimeError, 'manifest fields'):
            bundle.load_manifest(self.path, digest)

    def test_entry_boolean_size_and_special_modes_rejected(self):
        for field, value in [('bytes', True), ('bytes', -1), ('mode', True), ('mode', 0o4755)]:
            entries = copy.deepcopy(self.entries)
            entries['prefix/bin/tool'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError): bundle.entries_valid(entries)

    def test_relative_symlink_roundtrip(self):
        link = self.root / 'link'
        link.symlink_to('tool')
        self.entries['prefix/bin/alias'] = bundle.identity(link)
        digest = self.save()
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source, 'prefix/bin/alias': link}, self.entries)
        bundle.stage(self.archive, self.path, digest, self.root / 'staged')
        self.assertEqual((self.root / 'staged/prefix/bin/alias').resolve(), self.root / 'staged/prefix/bin/tool')

    def test_external_link_and_link_parent_rejected(self):
        for target in ['/outside', '../../../outside', 'missing']:
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                bundle.entries_valid({**self.entries, 'prefix/bin/alias': {'kind': 'symlink', 'target': target}})
        with self.assertRaisesRegex(RuntimeError, 'parent'):
            bundle.entries_valid({**self.entries, 'prefix/bin/tool/child': self.entries['prefix/bin/tool']})

    def test_internal_link_chain_roundtrip(self):
        first, second = self.root / 'first', self.root / 'second'
        first.symlink_to('second')
        second.symlink_to('tool')
        self.entries.update({'prefix/bin/first': bundle.identity(first),
                             'prefix/bin/second': bundle.identity(second)})
        digest = self.save()
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source,
            'prefix/bin/first': first, 'prefix/bin/second': second}, self.entries)
        bundle.stage(self.archive, self.path, digest, self.root / 'staged')
        self.assertEqual((self.root / 'staged/prefix/bin/first').resolve(), self.root / 'staged/prefix/bin/tool')

    def test_link_cycles_rejected(self):
        for links in [{'a': {'kind': 'symlink', 'target': 'a'}},
                      {'a': {'kind': 'symlink', 'target': 'b'}, 'b': {'kind': 'symlink', 'target': 'a'}}]:
            with self.subTest(links=links), self.assertRaisesRegex(RuntimeError, 'cycle'):
                bundle.entries_valid({**self.entries, **links})

    def test_dangling_link_chain_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'end at a recorded regular file'):
            bundle.entries_valid({**self.entries, 'a': {'kind': 'symlink', 'target': 'b'},
                                  'b': {'kind': 'symlink', 'target': 'missing'}})

    def test_archive_duplicate_and_extra_rejected(self):
        digest = self.save()
        for names in [['prefix/bin/tool'] * 2, ['outside']]:
            self.raw_archive(names=names)
            with self.subTest(names=names), self.assertRaisesRegex(RuntimeError, 'extra or repeated'):
                bundle.verify_archive(self.archive, self.path, digest)

    def test_archive_missing_rejected(self):
        digest = self.save()
        with tarfile.open(self.archive, 'w:gz'): pass
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            bundle.verify_archive(self.archive, self.path, digest)

    def test_hardlink_archive_rejected(self):
        digest = self.save()
        self.raw_archive(kind=tarfile.LNKTYPE)
        with self.assertRaisesRegex(RuntimeError, 'metadata'):
            bundle.verify_archive(self.archive, self.path, digest)

    def test_corrupted_archived_bytes_rejected(self):
        digest = self.save()
        self.raw_archive(body=b'changed tool by!')
        with self.assertRaises(RuntimeError): bundle.verify_archive(self.archive, self.path, digest)

    def test_source_changed_before_pack_rejected(self):
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'source changed'):
            bundle.write_archive(self.archive, {'prefix/bin/tool': self.source}, self.entries)

    def test_existing_stage_never_overwritten(self):
        digest = self.build()
        target = self.root / 'staged'
        target.mkdir()
        sentinel = target / 'sentinel'
        sentinel.write_text('keep')
        with self.assertRaisesRegex(RuntimeError, 'destination exists'):
            bundle.stage(self.archive, self.path, digest, target)
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_linked_stage_parent_rejected(self):
        digest = self.build()
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'linked staging ancestor'):
            bundle.stage(self.archive, self.path, digest, alias / 'new')

    def test_staged_extra_file_rejected(self):
        digest = self.build()
        target = self.root / 'staged'
        bundle.stage(self.archive, self.path, digest, target)
        (target / 'extra').write_text('not recorded')
        with self.assertRaisesRegex(RuntimeError, 'staged inventory'):
            bundle.verify_staged(target, self.entries)

    def test_empty_directory_and_permissions_roundtrip(self):
        empty = self.root / 'empty'
        empty.mkdir(mode=0o750)
        self.entries['prefix/empty'] = bundle.identity(empty)
        digest = self.save()
        bundle.write_archive(self.archive, {'prefix/bin/tool': self.source, 'prefix/empty': empty}, self.entries)
        target = self.root / 'staged'
        bundle.stage(self.archive, self.path, digest, target)
        self.assertTrue((target / 'prefix/empty').is_dir())
        self.assertEqual((target / 'prefix/empty').stat().st_mode & 0o777, 0o750)

    def test_missing_or_extra_staged_directory_rejected(self):
        digest = self.build()
        target = self.root / 'staged'
        bundle.stage(self.archive, self.path, digest, target)
        (target / 'extra-empty').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'unexpected staged directory'):
            bundle.verify_staged(target, self.entries)
        (target / 'extra-empty').rmdir()
        with self.assertRaisesRegex(RuntimeError, 'staged inventory'):
            bundle.verify_staged(target, {**self.entries, 'missing-empty': {'kind': 'directory', 'mode': 0o755}})

    def test_git_empty_refs_preserved_as_independent_root(self):
        repository = self.root / 'repository'
        env = {'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'init', '-q', repository], env=env, check=True)
        sources = {'source/' + str(p.relative_to(repository)): p for p in repository.rglob('*')}
        self.manifest['entries'] = {name: bundle.identity(p) for name, p in sources.items()}
        digest = self.save()
        bundle.write_archive(self.archive, sources, self.manifest['entries'])
        target = self.root / 'staged'
        bundle.stage(self.archive, self.path, digest, target)
        output = subprocess.check_output(['git', '-C', target / 'source', 'rev-parse', '--show-toplevel'], env=env, text=True)
        self.assertEqual(output.strip(), str(target / 'source'))
        self.assertTrue((target / 'source/.git/refs/heads').is_dir())


if __name__ == '__main__':
    unittest.main()
