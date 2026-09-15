"""Hermetic bookkeeping regressions, not formal execution evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
spec = importlib.util.spec_from_file_location('formal_final_driver', HERE.parent / 'week6_formal_record.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class RecordingTests(unittest.TestCase):
    def before(self):
        roots = driver.inventory.roots()
        result = {'schema_version': 1, 'kind': driver.inventory.KIND, 'roots': roots,
                  'entries': dict.fromkeys(roots), 'symlinks_followed': False,
                  'whole_workspace_coverage_claimed': False}
        result['snapshot_sha256'] = driver.inventory.digest(result)
        return result

    def test_original_observation_preserved(self):
        before = self.before()
        original = driver.inventory.digest(before)
        expanded, added = driver.expand(before, ['old'], ['new', 'old'])
        self.assertEqual(driver.inventory.digest(before), original)
        self.assertEqual(added, ['artifacts/boundary-check/new'])
        self.assertIsNone(expanded['entries'][added[0]])
        self.assertEqual(expanded['roots'], driver.inventory.roots(added))

    def test_unknown_producer_not_silently_dropped(self):
        _, added = driver.expand(self.before(), [], ['unexpected-output'])
        self.assertEqual(added, ['artifacts/boundary-check/unexpected-output'])

    def test_removed_existing_evidence_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'disappeared'):
            driver.expand(self.before(), ['old'], [])

    def test_malformed_parent_list_rejected(self):
        for later in [['a', 'a'], ['b', 'a'], ['../elsewhere'], ['a/b'], ['.git']]:
            with self.subTest(later=later), self.assertRaises(RuntimeError):
                driver.expand(self.before(), [], later)

    def test_mandatory_scope_cannot_shrink(self):
        before = self.before()
        before['roots'].pop()
        with self.assertRaises(RuntimeError): driver.expand(before, [], [])

    def test_archive_preserves_records_without_copying_historical_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'original'
            original.mkdir()
            (original / 'report.json').write_bytes(b'old record\n')
            (original / '.lock').write_bytes(b'')
            (original / 'old-clean-tree').mkdir()
            (original / 'old-clean-tree/old.olean').write_bytes(b'not copied')
            result = driver.archive_top_files(original, root / 'saved')
            self.assertEqual(set(result['files']), {'report.json', '.lock'})
            self.assertEqual(result['unscanned_historical_directories'], ['old-clean-tree'])
            self.assertEqual((root / 'saved/report.json').read_bytes(), b'old record\n')
            self.assertEqual((original / 'report.json').read_bytes(), b'old record\n')
            self.assertFalse((root / 'saved/old-clean-tree').exists())
            with self.assertRaises(FileExistsError): driver.archive_top_files(original, root / 'saved')

    def test_archive_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / 'original'
            original.mkdir()
            (root / 'outside').write_bytes(b'not an original record')
            (original / 'report.json').symlink_to(root / 'outside')
            with self.assertRaisesRegex(RuntimeError, 'linked'):
                driver.archive_top_files(original, root / 'saved')

    def test_output_must_be_new_named_direct_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / 'artifacts/boundary-check'
            parent.mkdir(parents=True)
            accepted = driver.new_output(parent / 'week6-formal-fixture', root=root)
            self.assertTrue(accepted.is_dir())
            for path in [parent / 'other', parent / 'week6-formal-',
                         root / 'week6-formal-outside', accepted]:
                with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, 'new Week6 formal'):
                    driver.new_output(path, root=root)

    def test_producer_and_validator_share_stage_contract(self):
        self.assertEqual(driver.formal_review.STAGES,
                         ['inventory-before', 'proof-check', 'proof-spike',
                          'inventory-after', 'independent-acceptance'])
        self.assertIn('run.py', driver.formal_review.RECORD_FILES)
        self.assertEqual(driver.POLICY_SHA, driver.common.sha(driver.proof.POLICY))


if __name__ == '__main__':
    unittest.main()
