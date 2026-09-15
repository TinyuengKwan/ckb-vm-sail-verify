"""Candidate validation may extend, never reduce, the existing main gate."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_main_acceptance as acceptance


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.counts = acceptance.OLD_TESTS.copy()
        self.stages = [*acceptance.PREFIX, *self.counts, 'public-decoder']

    def test_add_exact_four_groups_and_preserve_all_old_stages(self):
        counts, stages = acceptance.inventories(self.counts, self.stages)
        self.assertEqual(sum(counts.values()), 287)
        self.assertEqual(len(stages), 28)
        self.assertEqual(list(counts.items())[:17], list(self.counts.items()))
        self.assertEqual(self.stages, [s for s in stages if s not in acceptance.EXTRA_TESTS])

    def test_changed_old_counts_rejected(self):
        for name in self.counts:
            counts = {**self.counts, name: self.counts[name] - 1}
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                acceptance.inventories(counts, self.stages)

    def test_removed_or_reordered_old_stage_rejected(self):
        for stages in (self.stages[1:], self.stages[::-1], self.stages + ['unknown']):
            with self.subTest(stages=stages), self.assertRaises(RuntimeError):
                acceptance.inventories(self.counts, stages)

    def test_running_or_failed_report_never_passes(self):
        for status in ('running', 'failed', 'expected_blocked', None):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, 'not complete'):
                acceptance.terminal_report({'status': status})

    def test_other_policy_report_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'policy identity'):
            acceptance.terminal_report({'status': 'passed', 'policy_sha256': 'old'})

    def test_missing_new_tests_rejected_even_if_old_pass(self):
        with self.assertRaisesRegex(RuntimeError, 'mandatory stage'):
            acceptance.terminal_report({'status': 'passed', 'policy_sha256': acceptance.POLICY_SHA,
                                        'stages': [{'name': name} for name in self.stages]})

    def test_full_new_shape_is_only_a_precondition(self):
        _, stages = acceptance.inventories(self.counts, self.stages)
        acceptance.terminal_report({'status': 'passed', 'policy_sha256': acceptance.POLICY_SHA,
                                    'stages': [{'name': name} for name in stages]})
        # Actual log/source/kernel validation is separately mandatory in validate().

    def test_only_explicit_policy_delta_allowed(self):
        old = {'axioms': ['fixed'], 'contracts': {'T': 'fixed'}, 'configuration': {'version': 2},
               'local_sources': {'old.py': 'old'}, 'translator_versions': {}, 'tool_binaries': {}}
        new = copy.deepcopy(old)
        new.update(main_toolchain='profile', translator_versions={'aeneas': 'new'}, tool_binaries={'aeneas': 'hash'})
        new['local_sources']['new.py'] = 'new'
        acceptance.policy_delta(old, new, {'aeneas': 'hash'}, {'aeneas': 'new'}, {'new.py': 'new'}, 'profile')
        for key, value in [('axioms', []), ('contracts', {}), ('configuration', {'version': 1}), ('skip', True)]:
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'unreviewed fields'):
                acceptance.policy_delta(old, {**new, key: value}, {'aeneas': 'hash'}, {'aeneas': 'new'}, {'new.py': 'new'}, 'profile')


if __name__ == '__main__':
    unittest.main()
