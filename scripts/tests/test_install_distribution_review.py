import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install_distribution_review as review


class DistributionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        (self.source / 'bin').mkdir(parents=True)
        (self.source / 'bin/tool').write_bytes(b'fixed bytes')
        (self.source / 'bin/tool').chmod(0o755)
        self.expected = review.tools.locations.installation_inventory(self.source, ['bin'])

    def test_anchor_requires_existing_scoped_absolute_path(self):
        self.assertEqual(review.anchored(self.root, self.source), self.source)
        for bad in [self.root, self.root.parent, Path('relative'), self.root / 'absent']:
            with self.subTest(path=bad), self.assertRaises((RuntimeError, FileNotFoundError)):
                review.anchored(self.root, bad)

    def test_anchor_rejects_symlink(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'aliased'):
            review.anchored(self.root, alias)

    def test_summary_counts_without_claiming_relocation(self):
        summary = review.inventory_summary(self.expected)
        self.assertEqual(summary['entries'], 1)
        self.assertEqual(summary['regular_bytes'], len(b'fixed bytes'))
        self.assertEqual(summary['symlinks'], 0)
        self.assertNotIn('relocatable', summary)

    def test_summary_reports_absolute_symlink(self):
        closure = {'sha256': 'record', 'files': {'a': {'symlink': '/fixed/tool'},
                                               'b': {'symlink': 'tool'}}}
        self.assertEqual(review.inventory_summary(closure)['absolute_symlinks'], ['a'])

    def test_copy_preserves_identity_without_hardlinks(self):
        target = self.root / 'copy'
        review.copy_prefix(self.source, target, self.expected, ['bin'])
        self.assertEqual(review.tools.locations.installation_inventory(target, ['bin']), self.expected)
        self.assertNotEqual((self.source / 'bin/tool').stat().st_ino, (target / 'bin/tool').stat().st_ino)

    def test_copy_refuses_existing_target(self):
        target = self.root / 'copy'
        target.mkdir()
        sentinel = target / 'sentinel'
        sentinel.write_text('preserve')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            review.copy_prefix(self.source, target, self.expected, ['bin'])
        self.assertEqual(sentinel.read_text(), 'preserve')

    def test_copy_rejects_drift_before_creating_destination(self):
        (self.source / 'bin/tool').write_bytes(b'drift')
        target = self.root / 'copy'
        with self.assertRaisesRegex(RuntimeError, 'source installation drift'):
            review.copy_prefix(self.source, target, self.expected, ['bin'])
        self.assertFalse(target.exists())

    def test_copy_rejects_external_link(self):
        (self.source / 'bin/external').symlink_to(self.root)
        with self.assertRaisesRegex(RuntimeError, 'external installed symlink'):
            review.copy_prefix(self.source, self.root / 'copy', self.expected, ['bin'])

    def test_opam_control_tracks_content_and_discloses_missing(self):
        control = self.source / 'switch/.opam-switch'
        control.mkdir(parents=True)
        (control / 'switch-state').write_text('installed: []')
        report = review.control_files(self.source, 'switch')
        self.assertIn('switch/.opam-switch/switch-state', report['files'])
        self.assertIn('config', report['missing_selected_paths'])
        self.assertFalse(report['complete_runtime_closure_claimed'])
        (control / 'switch-state').write_text('installed: [other]')
        self.assertNotEqual(report, review.control_files(self.source, 'switch'))

    def test_opam_control_rejects_symlink(self):
        (self.source / 'config').symlink_to(self.source / 'bin/tool')
        with self.assertRaisesRegex(RuntimeError, 'aliased'):
            review.control_files(self.source, 'switch')

    def test_smoke_environment_does_not_inherit_injection(self):
        with patch.dict(os.environ, {'SAIL_DIR': '/old', 'SAIL_PLUGIN_DIR': '/old',
                                    'LD_PRELOAD': '/untrusted', 'BASH_ENV': '/startup'}):
            env = review.smoke_environment(self.source, self.root / 'tmp')
        self.assertEqual(set(env), {'PATH', 'LC_ALL', 'TMPDIR', 'SAIL_DIR', 'SAIL_PLUGIN_DIR'})
        self.assertEqual(env['SAIL_DIR'], str(self.source / 'share/sail'))
        self.assertEqual(env['SAIL_PLUGIN_DIR'], str(self.source / 'share/libsail/plugins'))


if __name__ == '__main__':
    unittest.main()
