"""A minimization claim needs real, consistent outcomes and exhaustive search."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import minimize_mismatch as mini


def artifact(words=(1, 2, 3), mismatch=True):
    return {'schema_version': 3, 'case': {'id': 'fixture', 'instructions': list(words)},
        'instructions_hex': [f'0x{w:08x}' for w in words],
        'initial_state': {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
        'passed': not mismatch, 'error': None,
        'classification': 'unclassified_mismatch' if mismatch else 'match',
        'comparison': {'compared_steps': 0, 'mismatch':
            {'field': 'pc_after', 'step': 0, 'left': 'a', 'right': 'b'} if mismatch else None},
        'environment': {key: 'fixed-' + key for key in mini.ENVIRONMENT_KEYS},
        'ckb_trace': {'events': [{'instruction': 2}]},
        'sail_trace': {'events': [{'instruction': 2}]}}


def envelope(data):
    return {'schema_version': 3, 'mode': 'replay', 'terminal_policy': 'exact', 'mutations': None,
        'environment': data['environment'], 'results': [{**{k: data[k] for k in
            ['passed', 'classification', 'comparison', 'error']},
            'id': data['case']['id'], 'instructions': len(data['case']['instructions'])}],
        'summary': {'total': 1, 'failures': 0 if data['passed'] else 1,
                    'mutations_passed': None, 'passed': data['passed']}}


class SearchTests(unittest.TestCase):
    def test_shortest_and_all_smaller_candidates_checked(self):
        seen = []
        def observe(words):
            seen.append(words)
            return 'target' if words == [2, 3] else None
        self.assertEqual(mini.shortest_subsequence([1, 2, 3], 'target', observe), ([2, 3], [1, 2]))
        self.assertEqual(seen, [[1], [2], [3], [1, 2], [1, 3], [2, 3]])

    def test_original_is_minimum_only_after_all_smaller_subsequences(self):
        seen = []
        result = mini.shortest_subsequence([1, 2, 3], 'target', lambda words: seen.append(words))
        self.assertEqual(result, ([1, 2, 3], [0, 1, 2]))
        self.assertEqual(len(seen), 6)

    def test_duplicate_words_retain_original_indices(self):
        self.assertEqual(mini.shortest_subsequence([7, 7, 8], 'target',
            lambda words: 'target' if words == [8] else None), ([8], [2]))

    def test_error_or_budget_cannot_be_treated_as_absent_signature(self):
        for error in [RuntimeError('runner failed'), mini.BudgetExhausted('limit')]:
            with self.subTest(error=error), self.assertRaises(type(error)):
                mini.shortest_subsequence([1, 2], 'target', lambda _: (_ for _ in ()).throw(error))

    def test_no_empty_candidate_or_change_of_instruction_order(self):
        seen = []
        mini.shortest_subsequence([1, 2, 3], 'missing', lambda words: seen.append(words))
        self.assertNotIn([], seen)
        self.assertNotIn([3, 2], seen)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.artifact = artifact()
        self.report = envelope(self.artifact)

    def test_trace_length_position_is_common_prefix_not_existing_event(self):
        data = copy.deepcopy(self.artifact)
        data['ckb_trace']['events'].append({'instruction': 3})
        data['comparison']['mismatch'].update(field='trace_length', step=1)
        self.assertEqual(mini.signature(data), {'field': 'trace_length', 'offending_words': None})
        for step in [None, True, 0, 2]:
            data['comparison']['mismatch']['step'] = step
            with self.subTest(step=step), self.assertRaises(RuntimeError): mini.signature(data)

    def test_trace_length_cannot_claim_equal_lengths(self):
        data = copy.deepcopy(self.artifact)
        data['comparison']['mismatch'].update(field='trace_length', step=1)
        with self.assertRaises(RuntimeError): mini.signature(data)

    def test_consistent_mismatch_and_match(self):
        self.assertEqual(mini.check_trial(self.report, self.artifact, 1, [1, 2, 3])['field'], 'pc_after')
        passed = artifact(mismatch=False)
        self.assertIsNone(mini.check_trial(envelope(passed), passed, 0, [1, 2, 3]))

    def test_signal_unexpected_exit_or_false_success_rejected(self):
        for code in [-9, 2, 0, True]:
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                mini.check_trial(self.report, self.artifact, code, [1, 2, 3])

    def test_wrong_mode_or_relaxed_termination_rejected(self):
        for key, value in [('schema_version', 2), ('mode', 'corpus'), ('terminal_policy', 'category_only'),
                           ('mutations', {'passed': True})]:
            trial = copy.deepcopy(self.report)
            trial[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                mini.check_trial(trial, self.artifact, 1, [1, 2, 3])

    def test_self_reported_summary_or_comparison_not_accepted(self):
        for key, value in [('summary', {'passed': True}), ('results', [])]:
            trial = copy.deepcopy(self.report)
            trial[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                mini.check_trial(trial, self.artifact, 1, [1, 2, 3])

    def test_runner_error_empty_trace_and_bad_step_rejected(self):
        for alter in [lambda a: a.update(error='timeout'), lambda a: a.update(ckb_trace=None),
                      lambda a: a['sail_trace'].update(events=[]),
                      lambda a: a['comparison']['mismatch'].update(step=9),
                      lambda a: a['comparison']['mismatch'].update(field='empty_trace')]:
            trial = copy.deepcopy(self.artifact)
            alter(trial)
            with self.assertRaises(RuntimeError):
                mini.signature(trial)

    def test_signature_preserves_offending_words_not_absolute_pc(self):
        changed = copy.deepcopy(self.artifact)
        changed['comparison']['mismatch'].update(left='new address', right='other address')
        self.assertEqual(mini.signature(changed), mini.signature(self.artifact))
        changed['ckb_trace']['events'][0]['instruction'] = 99
        self.assertNotEqual(mini.signature(changed), mini.signature(self.artifact))

    def test_program_and_initial_state_rejected_when_inconsistent(self):
        for alter in [lambda a: a.update(schema_version=2),
                      lambda a: a.update(instructions_hex=['0x0']),
                      lambda a: a['initial_state'].update(pc=0),
                      lambda a: a['case'].update(instructions=[True]),
                      lambda a: a['case'].update(instructions=[])]:
            trial = copy.deepcopy(self.artifact)
            alter(trial)
            with self.assertRaises(RuntimeError):
                mini.program(trial)

    def test_environment_must_be_known_and_unchanged(self):
        original = self.artifact['environment']
        mini.check_environment(original, copy.deepcopy(original))
        for key in mini.ENVIRONMENT_KEYS:
            changed = dict(original, **{key: 'different'})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                mini.check_environment(original, changed)
        with self.assertRaises(RuntimeError):
            mini.check_environment({}, {})

    def test_report_and_artifact_environment_or_case_must_agree(self):
        for alter in [lambda r: r.update(environment={}),
                      lambda r: r['results'][0].update(id='other'),
                      lambda r: r['results'][0].update(instructions=99),
                      lambda r: r['results'][0].update(error='ignored failure')]:
            trial = copy.deepcopy(self.report)
            alter(trial)
            with self.assertRaises(RuntimeError):
                mini.check_trial(trial, self.artifact, 1, [1, 2, 3])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='minimizer-workflow-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        source = self.root / 'original.json'
        mini.save(source, artifact())
        self.args = argparse.Namespace(artifact=source, output=self.root / 'out',
            classification='unclassified_mismatch', rationale='fixture', max_evaluations=10,
            timeout=1, sail_timeout=1)

    def execute_with_failure(self, error):
        with patch.object(mini, 'ReplayOracle') as oracle:
            oracle.return_value.side_effect = error
            code = mini.run(self.args)
        report = json.loads((self.args.output / 'report.json').read_text())
        self.assertFalse(report['minimum_proved'])
        self.assertNotIn('minimal_words', report)
        return code, report

    def test_budget_exhaustion_is_incomplete(self):
        code, report = self.execute_with_failure(mini.BudgetExhausted('budget'))
        self.assertEqual((code, report['status']), (2, 'incomplete'))

    def test_timeout_and_runner_error_are_failures(self):
        code, report = self.execute_with_failure(RuntimeError('runner failure'))
        self.assertEqual((code, report['status']), (1, 'failed'))

    def test_nonreproducible_original_is_failure(self):
        before = self.args.artifact.read_bytes()
        with patch.object(mini, 'ReplayOracle') as oracle:
            oracle.return_value.return_value = None
            self.assertEqual(mini.run(self.args), 1)
        self.assertEqual(before, self.args.artifact.read_bytes())
        self.assertFalse(json.loads((self.args.output / 'report.json').read_text())['minimum_proved'])

    def test_existing_output_is_never_overwritten(self):
        self.args.output.mkdir()
        keep = self.args.output / 'keep'
        keep.write_text('original')
        with self.assertRaises(FileExistsError):
            mini.run(self.args)
        self.assertEqual(keep.read_text(), 'original')

    def test_matching_input_or_missing_rationale_creates_no_output(self):
        mini.save(self.args.artifact, artifact(mismatch=False))
        with self.assertRaisesRegex(RuntimeError, 'matching artifact'):
            mini.run(self.args)
        self.assertFalse(self.args.output.exists())
        self.args.rationale = ''
        with self.assertRaisesRegex(RuntimeError, 'rationale'):
            mini.run(self.args)


if __name__ == '__main__':
    unittest.main()
