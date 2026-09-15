import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_mismatch_evidence as checks
from test_release_runtime_evidence import fixture


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.artifact = copy.deepcopy(fixture()[1]['fixture-1'])

    def test_matching_trace(self):
        self.assertIsNone(checks.observation(self.artifact))

    def mismatch(self):
        self.artifact['passed'] = False
        self.artifact['classification'] = 'unclassified_mismatch'
        self.artifact['sail_trace']['events'][0]['pc_after'] += 4
        self.artifact['comparison'] = {'compared_steps': 0, 'mismatch': {'field': 'pc_after', 'step': 0}}

    def test_actual_field_and_step(self):
        self.mismatch()
        self.assertEqual(checks.observation(self.artifact)['field'], 'pc_after')

    def test_lying_about_field_or_location_or_prefix(self):
        self.mismatch()
        original = copy.deepcopy(self.artifact)
        for edit in [lambda a: a['comparison']['mismatch'].update(field='trap'),
                     lambda a: a['comparison']['mismatch'].update(step=1),
                     lambda a: a['comparison'].update(compared_steps=1),
                     lambda a: a['comparison']['mismatch'].update(step=False)]:
            item = copy.deepcopy(original)
            edit(item)
            with self.subTest(edit=edit), self.assertRaises(RuntimeError): checks.observation(item)

    def test_invented_mismatch_on_equal_traces(self):
        self.artifact['comparison']['mismatch'] = {'field': 'trap', 'step': 0}
        with self.assertRaises(RuntimeError): checks.observation(self.artifact)

    def test_extra_observation_field_rejected(self):
        self.artifact['ckb_trace']['events'][0]['extra'] = 0
        with self.assertRaises(RuntimeError): checks.observation(self.artifact)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mismatch-inventory-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'inventory.json'
        self.inventory = {'schema_version': 1, 'runtime': {'path': 'runtime'}, 'rust_tests': {'path': 'rust'},
                          'semantic_negative_cases': dict.fromkeys(checks.CASES)}
        for manager in [patch.object(checks, 'reference', return_value=self.root / 'referenced.json'),
                        patch.object(checks.common, 'check_runtime', return_value={'cases': 32}),
                        patch.object(checks.rust_tests, 'check', return_value={'engine_tests': 10})]:
            manager.start()
            self.addCleanup(manager.stop)

    def run_check(self):
        self.path.write_text(json.dumps(self.inventory))
        return checks.check_inventory(self.path)

    def test_three_negatives_missing_not_zero_mismatches_done(self):
        with self.assertRaises(checks.IncompleteEvidence) as failure: self.run_check()
        self.assertEqual(failure.exception.details['pending'], checks.CASES)

    def test_negative_case_cannot_be_omitted(self):
        del self.inventory['semantic_negative_cases'][checks.CASES[0]]
        with self.assertRaisesRegex(RuntimeError, 'inventory'): self.run_check()

    def test_paired_input_reference_requires_actual_validator(self):
        self.inventory['semantic_negative_cases'][checks.CASES[0]] = {'path': 'paired-pass'}
        with patch.object(checks.paired, 'check', side_effect=RuntimeError('invalid paired record')) as validator:
            with self.assertRaisesRegex(RuntimeError, 'invalid paired record'): self.run_check()
        validator.assert_called_once_with(self.root / 'referenced.json', 'instruction')

    def test_failing_runtime_not_treated_as_expected_negative(self):
        with patch.object(checks.common, 'check_runtime', side_effect=RuntimeError('unexpected mismatch')):
            with self.assertRaisesRegex(RuntimeError, 'unexpected mismatch'): self.run_check()

    def test_failed_rust_tests_cannot_be_hidden_by_inventory(self):
        with patch.object(checks.rust_tests, 'check', side_effect=RuntimeError('failed test')):
            with self.assertRaisesRegex(RuntimeError, 'failed test'): self.run_check()

    def test_budget_exhausted_report_cannot_pass(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'incomplete'}))
        with self.assertRaisesRegex(RuntimeError, 'incomplete'): checks.check_minimization(self.path)

    def test_old_minimizer_script_cannot_relabel_new_evidence(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'minimized', 'minimum_proved': True,
            'root_cause_equivalence_claimed': False, 'release_claimed': False, 'script_sha256': 'old'}))
        with self.assertRaisesRegex(RuntimeError, 'stale minimizer'): checks.check_minimization(self.path)


if __name__ == '__main__':
    unittest.main()
