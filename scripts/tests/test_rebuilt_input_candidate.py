import copy
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_input_candidate as p


class RebuiltInputTests(unittest.TestCase):
    def fixture(self, root):
        payload = root / 'payload'; payload.mkdir()
        (payload / 'fixture').write_bytes(b'candidate input')
        (payload / 'fixture').chmod(0o644)
        files = {'fixture': {'sha256': p.sha(payload / 'fixture'), 'bytes': 15, 'mode': 0o644}}
        catalogue = {'kind': 'rebuilt-decoder-candidate-catalogue', 'boundaries': dict(p.BOUNDARIES),
                     'files': files, 'source_commits': {}}
        manifest = {'schema_version': 1, 'kind': 'rebuilt-decoder-candidate-inputs',
                    'boundaries': dict(p.BOUNDARIES), 'files': copy.deepcopy(files), 'source_commits': {}}
        (payload / 'package.json').write_text(json.dumps(manifest))
        (payload / 'package.json').chmod(0o644)
        return payload, catalogue, manifest

    def test_exact_candidate_files_verify_without_adoption(self):
        with tempfile.TemporaryDirectory() as temp:
            payload, catalogue, _ = self.fixture(Path(temp))
            self.assertEqual(p.verify(payload, catalogue), {'files': 1, 'bytes': 15})
            self.assertFalse(catalogue['boundaries']['tool_adopted'])

    def test_candidate_cannot_pass_the_existing_formal_bundle_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            payload, _, _ = self.fixture(Path(temp))
            with self.assertRaisesRegex(RuntimeError, 'unknown input package schema'):
                p.bundle.verify_payload(payload)

    def test_archive_manifest_cannot_self_approve_different_input(self):
        with tempfile.TemporaryDirectory() as temp:
            payload, catalogue, manifest = self.fixture(Path(temp))
            (payload / 'fixture').write_bytes(b'changed input')
            manifest['files']['fixture']['sha256'] = p.sha(payload / 'fixture')
            (payload / 'package.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'external catalogue'):
                p.verify(payload, catalogue)

    def test_missing_extra_and_mode_drift_are_rejected(self):
        for change in ('missing', 'extra', 'mode'):
            with tempfile.TemporaryDirectory() as temp:
                payload, catalogue, _ = self.fixture(Path(temp))
                if change == 'missing': (payload / 'fixture').unlink()
                if change == 'extra': (payload / 'extra').write_text('unexpected')
                if change == 'mode': (payload / 'fixture').chmod(0o755)
                with self.assertRaises(RuntimeError): p.verify(payload, catalogue)

    def test_symlink_and_hardlink_are_not_materialized_inputs(self):
        for link in ('symbolic', 'hard'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); payload, catalogue, _ = self.fixture(root)
                if link == 'hard': os.link(payload / 'fixture', root / 'outside')
                else:
                    (payload / 'fixture').rename(root / 'outside')
                    (payload / 'fixture').symlink_to(root / 'outside')
                with self.assertRaises(RuntimeError): p.verify(payload, catalogue)

    def test_catalogue_cannot_claim_adoption_or_complete_historical_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            payload, catalogue, _ = self.fixture(Path(temp))
            for key in p.BOUNDARIES:
                changed = copy.deepcopy(catalogue); changed['boundaries'][key] = True
                with self.assertRaisesRegex(RuntimeError, 'cannot grant adoption'):
                    p.verify(payload, changed)

    def test_integer_boundary_flags_cannot_impersonate_booleans(self):
        with tempfile.TemporaryDirectory() as temp:
            payload, catalogue, manifest = self.fixture(Path(temp))
            manifest['boundaries']['tool_adopted'] = 0
            (payload / 'package.json').write_text(json.dumps(manifest))
            with self.assertRaises(RuntimeError): p.verify(payload, catalogue)
            catalogue['boundaries']['tool_adopted'] = 0
            with self.assertRaisesRegex(RuntimeError, 'booleans'): p.verify(payload, catalogue)

    def test_unpack_requires_hash_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); payload, catalogue, _ = self.fixture(root)
            archive = root / 'input.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                for name in ('fixture', 'package.json'): stream.add(payload / name, arcname=name)
            with self.assertRaisesRegex(RuntimeError, 'archive identity'):
                p.unpack(archive, '0' * 64, root / 'unpack', catalogue)
            self.assertFalse((root / 'unpack').exists())
            self.assertEqual(p.unpack(archive, p.sha(archive), root / 'unpack', catalogue), {'files': 1, 'bytes': 15})
            with self.assertRaises(FileExistsError):
                p.unpack(archive, p.sha(archive), root / 'unpack', catalogue)

    def test_path_escape_and_link_members_fail_before_destination_creation(self):
        for kind in ('escape', 'symlink', 'hardlink'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); _, catalogue, _ = self.fixture(root); archive = root / 'input.tar.gz'
                with tarfile.open(archive, 'w:gz') as stream:
                    info = tarfile.TarInfo('../escape' if kind == 'escape' else 'fixture'); info.mode = 0o644
                    if kind != 'escape':
                        info.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE; info.linkname = '../escape'
                    stream.addfile(info, io.BytesIO())
                with self.assertRaises(RuntimeError):
                    p.unpack(archive, p.sha(archive), root / 'unpack', catalogue)
                self.assertFalse((root / 'unpack').exists())

    def test_failed_packaging_cannot_update_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(p.kernel.chain, 'verify_components', side_effect=RuntimeError('component drift')), patch('builtins.print'):
                self.assertEqual(p.run(root), 1)
            report = p.read(root / 'report.json')
            self.assertEqual(report['status'], 'failed')
            self.assertFalse(report['tool_adopted'])
            self.assertFalse((root / 'payload').exists())


if __name__ == '__main__':
    unittest.main()
