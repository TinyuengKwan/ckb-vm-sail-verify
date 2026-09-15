"""Hermetic checks, not real execution artifacts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paired_negative_evidence as paired


def observation(left, right):
    def events(words):
        return [{'order': i, 'instruction': word, 'pc_before': 0x80000000+4*i,
                 'pc_after': 0x80000004+4*i, 'register_writes': [], 'memory': [], 'trap': False, 'halt': False}
                for i, word in enumerate(words)]
    value = {'schema_version': 1, 'mode': 'paired_programs', 'programs':
        {'schema_version': 1, 'ckb_program': left, 'sail_program': right}, 'environment': {'fixture': True},
        'initial_state': {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
        'terminal_policy': 'exact', 'same_program_equivalence_claimed': False, 'error': None,
        'ckb_trace': {'events': events(left), 'end': {'kind': 'injection_complete'}},
        'sail_trace': {'events': events(right), 'end': {'kind': 'injection_complete'}},
        'sail_raw_packets': ['0' * 176] * (len(right)+1)}
    field, step = paired.trace.first_difference(value['ckb_trace'], value['sail_trace'])
    value.update(passed=field is None, comparison={'compared_steps': step if step is not None else min(len(left), len(right)),
        'mismatch': {'field': field, 'step': step} if field else None})
    return value


class SearchTests(unittest.TestCase):
    def test_total_length_order_and_both_sides_nonempty(self):
        original = {'schema_version': 1, 'ckb_program': [1, 2], 'sail_program': [3, 4]}
        seen = []
        result = paired.shortest(original, lambda x: seen.append(x) or x['ckb_program'] == [2])
        self.assertEqual(result['ckb_program'], [2])
        self.assertEqual(result['sail_program'], [3])
        self.assertEqual([(x['ckb_program'], x['sail_program']) for x in seen], [([1], [3]), ([1], [4]), ([2], [3])])

    def test_no_match_requires_every_shorter_pair(self):
        original = {'schema_version': 1, 'ckb_program': [1, 2], 'sail_program': [3, 4]}
        seen = []
        self.assertEqual(paired.shortest(original, lambda x: seen.append(x)), original)
        self.assertEqual(len(seen), 8)
        self.assertEqual([len(x['ckb_program'])+len(x['sail_program']) for x in seen], [2]*4+[3]*4)

    def test_budget_or_runner_error_not_treated_as_no_signature(self):
        for error in [paired.BudgetExhausted('budget'), RuntimeError('runner')]:
            with self.subTest(error=error), self.assertRaises(type(error)):
                paired.shortest(paired.ORIGINALS['instruction'], lambda _: (_ for _ in ()).throw(error))

    def test_original_at_nonempty_lower_bound(self):
        original = {'schema_version': 1, 'ckb_program': [1], 'sail_program': [2]}
        self.assertEqual(paired.shortest(original, lambda _: self.fail('no shorter nonempty pair')), original)


class ObservationTests(unittest.TestCase):
    def check(self, value, code=None):
        return paired.check_observation(value, value['programs'], 0 if value['passed'] else 1 if code is None else code,
                                        {'fixture': True})

    def test_distinct_programs_are_not_required_to_match(self):
        value = observation([0x002081b3], [0x00208233])
        self.assertEqual(self.check(value), ('instruction', 0))
        self.assertFalse(paired.signature(value, 'instruction', 0, 'instruction'))

    def test_instruction_signature_requires_both_actual_destination_effects(self):
        value = observation([0x002081b3], [0x00208233])
        value['ckb_trace']['events'][0]['register_writes'] = [{'index': 3, 'value': 5}]
        value['sail_trace']['events'][0]['register_writes'] = [{'index': 4, 'value': 5}]
        self.assertTrue(paired.signature(value, 'instruction', 0, 'instruction'))
        value['sail_trace']['events'][0]['register_writes'] = []
        self.assertFalse(paired.signature(value, 'instruction', 0, 'instruction'))

    def test_length_boundary_and_direction(self):
        value = observation([0x00500093, 0x00700113], [0x00500093])
        self.assertEqual(self.check(value), ('trace_length', 1))
        self.assertTrue(paired.signature(value, 'trace_length', 1, 'trace_length'))
        reverse = observation([0x00500093], [0x00500093, 0x00700113])
        self.assertFalse(paired.signature(reverse, 'trace_length', 1, 'trace_length'))

    def test_normal_matching_candidate_is_permitted(self):
        self.assertEqual(self.check(observation([0x00500093], [0x00500093])), (None, None))

    def test_invalid_programs(self):
        for value in [[], [True], [2**32], [-1]]:
            source = {'schema_version': 1, 'ckb_program': value, 'sail_program': [0x13]}
            with self.subTest(value=value), self.assertRaises(RuntimeError): paired.check_input(source)

    def test_summary_field_cannot_hide_actual_difference(self):
        value = observation([0x002081b3], [0x00208233])
        value['comparison']['mismatch']['field'] = 'register_writes'
        with self.assertRaises(RuntimeError): self.check(value)

    def test_own_input_order_and_length_checked(self):
        original = observation([0x002081b3], [0x00208233])
        for edit in [lambda x: x['ckb_trace'].update(events=[]),
                     lambda x: x['ckb_trace']['events'][0].update(instruction=0x13),
                     lambda x: x['sail_trace']['events'][0].update(order=True),
                     lambda x: x['sail_trace'].update(end={'kind': 'step_limit'})]:
            value = copy.deepcopy(original)
            edit(value)
            with self.subTest(edit=edit), self.assertRaises(RuntimeError): self.check(value)

    def test_error_or_same_program_claim_rejected(self):
        for key, value in [('error', 'runner failed'), ('same_program_equivalence_claimed', True)]:
            item = observation([0x002081b3], [0x00208233])
            item[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.check(item)

    def test_abnormal_exit_and_missing_packets_rejected(self):
        item = observation([0x002081b3], [0x00208233])
        with self.assertRaises(RuntimeError): self.check(item, 2)
        item['sail_raw_packets'] = []
        with self.assertRaises(RuntimeError): self.check(item)


class RecordedSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='paired-record-test-')
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)
        self.original = {'schema_version': 1, 'ckb_program': [0x00500093, 0x00700113], 'sail_program': [0x00500093]}
        manager = patch.dict(paired.ORIGINALS, {'trace_length': self.original})
        manager.start()
        self.addCleanup(manager.stop)
        self.data = {'original': self.original, 'test_name': paired.TEST_NAMES['trace_length'],
            'classification': 'intentional_distinct_input_negative', 'minimum_scope': paired.SCOPE,
            'trials': [], 'minimum': self.original}
        self.stages = {}
        values = [self.original,
            {'schema_version': 1, 'ckb_program': [0x00500093], 'sail_program': [0x00500093]},
            {'schema_version': 1, 'ckb_program': [0x00700113], 'sail_program': [0x00500093]}, self.original]
        for i, value in enumerate(values):
            name = f'trace_length-{i:05d}'
            source = self.out / (name + '.input.json')
            source.write_text(json.dumps(value))
            artifact = observation(value['ckb_program'], value['sail_program'])
            (self.out / (name + '.stdout')).write_text(json.dumps(artifact))
            self.data['trials'].append({'input': value, 'input_sha256': paired.sha(source), 'retains_signature': i in [0, 3]})
            self.stages[name] = {'argv': paired.command(self.out, source), 'exit_code': 0 if artifact['passed'] else 1}
        source = self.out / 'trace_length-replay.input.json'
        source.write_bytes((self.out / 'trace_length-00003.input.json').read_bytes())
        (self.out / 'trace_length-replay.stdout').write_bytes((self.out / 'trace_length-00003.stdout').read_bytes())
        self.data.update(replay_input_sha256=paired.sha(source), replay_argv=paired.command(self.out, source))
        self.stages['trace_length-replay'] = {'argv': self.data['replay_argv'], 'exit_code': 1}

    def check(self):
        return paired.inspect_case('trace_length', self.data, self.out, {'fixture': True}, self.stages)

    def test_complete_shorter_search_and_copy_replay(self):
        self.assertEqual(self.check()['minimum_total_words'], 3)

    def test_no_shorter_candidates_can_be_omitted(self):
        self.data['trials'].pop()
        with self.assertRaises(RuntimeError): self.check()

    def test_budget_result_cannot_be_certified(self):
        self.data['trials'] = self.data['trials'][:2]
        with self.assertRaises(RuntimeError): self.check()

    def test_reported_minimum_cannot_be_shortened_without_execution(self):
        self.data['minimum'] = {'schema_version': 1, 'ckb_program': [0x00500093], 'sail_program': [0x00500093]}
        with self.assertRaises(RuntimeError): self.check()

    def test_changed_input_and_wrong_command_rejected(self):
        self.stages['trace_length-00001']['argv'] = ['true']
        with self.assertRaises(RuntimeError): self.check()

    def test_copy_replay_must_preserve_actual_trace(self):
        path = self.out / 'trace_length-replay.stdout'
        value = json.loads(path.read_text())
        value['ckb_trace']['events'][-1]['pc_after'] += 4
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, 'changed actual traces'): self.check()

    def test_classification_cannot_claim_same_program_bug(self):
        self.data['classification'] = 'ckb_candidate_defect'
        with self.assertRaises(RuntimeError): self.check()


if __name__ == '__main__':
    unittest.main()
