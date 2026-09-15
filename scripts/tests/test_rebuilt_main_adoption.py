"""Formal cutover must not smuggle unrelated source changes or ignore failures."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import review_rebuilt_main_adoption as review


class AdoptionReviewTests(unittest.TestCase):
    def setUp(self):
        self.names = review.CORE_CHANGES[:2]
        self.old = {**dict.fromkeys(self.names, 'old'), 'proof.lean': 'fixed'}
        self.replacements = dict.fromkeys(self.names, 'new')
        self.new = {**self.old, **self.replacements, 'new-helper.py': 'helper'}

    def test_exact_core_and_added_helper_inventory(self):
        self.assertEqual(review.prospective_sources(self.old, self.old, self.new,
            self.replacements, ['new-helper.py']), self.new)

    def test_changed_formal_input_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'formal source inventory'):
            review.prospective_sources(self.old, {**self.old, 'proof.lean': 'drift'}, self.new,
                                       self.replacements, ['new-helper.py'])

    def test_unreviewed_additional_change_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'additional formal source'):
            review.prospective_sources(self.old, self.old, {**self.new, 'proof.lean': 'changed'},
                                       self.replacements, ['new-helper.py'])

    def test_other_replacement_file_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unexpected core'):
            review.prospective_sources(self.old, self.old, self.new,
                                       {**self.replacements, 'proof.lean': 'changed'}, ['new-helper.py'])

    def test_only_exact_cmake_rejection_is_accepted_as_observation(self):
        def expected(): raise RuntimeError('Sail CMake compiler differs')
        self.assertEqual(review.old_cmake_rejection(expected), 'Sail CMake compiler differs')
        for message in ('source drift', 'missing tools', 'Sail CMake cache missing'):
            def wrong(message=message): raise RuntimeError(message)
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, 'unexpected rebuilt'):
                review.old_cmake_rejection(wrong)
        with self.assertRaisesRegex(RuntimeError, 'no longer current'):
            review.old_cmake_rejection(lambda: None)


if __name__ == '__main__':
    unittest.main()
