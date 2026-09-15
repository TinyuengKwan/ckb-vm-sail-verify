"""Hermetic release-runtime checks; these fixtures are not execution evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_runtime_evidence as gate
from probes import probe_release_runtime as probe


def fixture():
    environment = {'test_fixture_only': True}
    cases, rows, mutations = {}, [], []
    for i in range(30):
        family, word = [('ADD', 0x33), ('ADDI', 0x13), ('BEQ', 0x63)][i % 3]
        name = f'fixture-{i}'
        case = {'id': name, 'description': 'synthetic validator fixture', 'family': family,
                'instructions': [word], 'focus_step': 0, 'seed': None}
        event = dict(order=0, instruction=word, pc_before=0x80000000, pc_after=0x80000004,
                     register_writes=[] if i == 0 else [{'index': 31, 'value': 4}],
                     memory=[], trap=False, halt=False)
        trace = {'events': [event], 'end': {'kind': 'injection_complete'}}
        result = {'passed': True, 'classification': 'match', 'error': None,
                  'comparison': {'compared_steps': 1, 'mismatch': None}}
        cases[name] = {'schema_version': 3, 'case': case, 'environment': environment,
            'instructions_hex': [f'0x{word:08x}'], 'initial_state':
                {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
            **copy.deepcopy(result), 'ckb_trace': copy.deepcopy(trace), 'sail_trace': copy.deepcopy(trace),
            'sail_raw_packets': ['0' * 176] * 2, 'replay': {'from_artifact': 'not executed'}}
        rows.append({**copy.deepcopy(case), **copy.deepcopy(result), 'instructions': 1,
                     'artifact': '/original/location/' + name + '.json'})
        for kind, field in gate.MUTATIONS.items():
            skip = i == 0 and kind.startswith('register_')
            mutations.append({'case_id': name, 'mutation': kind, 'description': 'synthetic',
                'expected_field': field, 'applied': not skip, 'detected': not skip, 'passed': not skip,
                'skipped_because': 'no writes' if skip else None, 'located_field': None if skip else field,
                'located_step': None if skip or kind == 'termination' else 0})
    summary = {'cases': 30, 'passed': True, 'baseline_failures': [], 'undetected': [], 'mislocated': [],
        'applied': 178, 'skipped': 2, 'reports': mutations, 'coverage': [
            {'mutation': kind, 'expected_field': field, 'applied': 29 if kind.startswith('register_') else 30,
             'located': 29 if kind.startswith('register_') else 30, 'example_case': 'fixture-1'}
            for kind, field in gate.MUTATIONS.items()]}
    report = {'schema_version': 3, 'mode': 'corpus', 'seed': 1, 'terminal_policy': 'exact',
        'environment': environment, 'results': rows, 'mutations': summary,
        'summary': {'total': 30, 'failures': 0, 'mutations_passed': True, 'passed': True}}
    return report, cases, environment


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report, self.cases, self.env = fixture()
        temporary = tempfile.TemporaryDirectory(prefix='runtime-gate-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir()

    def save(self):
        path = self.root / 'report.json'
        path.write_text(json.dumps(self.report))
        for name, artifact in self.cases.items():
            (self.artifacts / (name + '.json')).write_text(json.dumps(artifact))
        (self.artifacts / 'mutations.json').write_text(json.dumps({'schema_version': 3,
            'environment': self.env, 'seed': self.report['seed'], 'summary': self.report['mutations'],
            'replay': 'not executed'}))
        return path

    def validate(self):
        return gate.validate(self.save(), self.artifacts, self.env)

    def test_valid_matrix_and_relocated_filenames(self):
        result = self.validate()
        self.assertEqual(result['mutations']['applied'], 178)
        self.assertEqual(result['mutations']['skipped'], 2)
        self.assertEqual(result['families'], {'ADD': 10, 'ADDI': 10, 'BEQ': 10})
        self.assertFalse(result['release_claimed'])

    def test_total_thirty_cannot_hide_a_family_with_nine(self):
        original_report, original_cases = copy.deepcopy(self.report), copy.deepcopy(self.cases)
        for family, replacement, word in [('ADD', 'ADDI', 0x13), ('ADDI', 'BEQ', 0x63), ('BEQ', 'ADD', 0x33)]:
            self.report, self.cases = copy.deepcopy(original_report), copy.deepcopy(original_cases)
            row = next(row for row in self.report['results'] if row['family'] == family)
            row['family'] = replacement
            case = self.cases[row['id']]
            case['case'].update(family=replacement, instructions=[word])
            case['instructions_hex'] = [f'0x{word:08x}']
            for key in ['ckb_trace', 'sail_trace']:
                case[key]['events'][0]['instruction'] = word
            with self.subTest(family=family), self.assertRaisesRegex(RuntimeError, '10 cases per instruction family'):
                self.validate()

    def test_schema2_rejected(self):
        self.cases['fixture-0']['schema_version'] = 2
        with self.assertRaises(RuntimeError): self.validate()

    def test_missing_family(self):
        for row in self.report['results']:
            if row['family'] == 'BEQ':
                row['family'] = 'ADD'
                case = self.cases[row['id']]
                case['case'].update(family='ADD', instructions=[0x33])
                case['instructions_hex'] = ['0x00000033']
                for key in ['ckb_trace', 'sail_trace']: case[key]['events'][0]['instruction'] = 0x33
        with self.assertRaisesRegex(RuntimeError, 'missing required'): self.validate()

    def test_family_label_not_enough(self):
        self.cases['fixture-0']['case']['family'] = 'BEQ'
        with self.assertRaisesRegex(RuntimeError, 'opcode'): self.validate()

    def test_environment_independent_of_report(self):
        path = self.save()
        with self.assertRaises(RuntimeError): gate.validate(path, self.artifacts, {'different': True})

    def test_mixed_case_environment(self):
        self.cases['fixture-0']['environment'] = {}
        with self.assertRaises(RuntimeError): self.validate()

    def test_summary_cannot_hide_actual_difference(self):
        self.cases['fixture-0']['sail_trace']['events'][0]['pc_after'] += 4
        with self.assertRaisesRegex(RuntimeError, 'traces differ'): self.validate()

    def test_bad_program_hex_initial_state_and_order(self):
        original = copy.deepcopy(self.cases)
        for change in [lambda a: a.update(instructions_hex=[]),
                       lambda a: a['initial_state'].update(pc=0),
                       lambda a: a['ckb_trace']['events'][0].update(order=True),
                       lambda a: a['case'].update(instructions=[True]),
                       lambda a: a['case'].update(focus_step=-1)]:
            self.cases = copy.deepcopy(original)
            change(self.cases['fixture-0'])
            with self.subTest(change=change), self.assertRaises(RuntimeError): self.validate()

    def test_incomplete_or_abnormal_trace(self):
        original = copy.deepcopy(self.cases)
        for change in [lambda a: a['ckb_trace'].update(events=[]),
                       lambda a: a['sail_trace'].update(end={'kind': 'step_limit'}),
                       lambda a: a['ckb_trace']['events'][0].update(trap=True),
                       lambda a: a['ckb_trace']['events'][0].update(memory=[{}]),
                       lambda a: a.update(sail_raw_packets=[]),
                       lambda a: a['ckb_trace']['events'][0].update(register_writes=[{'index': 0, 'value': 0}])]:
            self.cases = copy.deepcopy(original)
            change(self.cases['fixture-0'])
            with self.subTest(change=change), self.assertRaises(RuntimeError): self.validate()

    def test_missing_duplicated_or_unsafe_case(self):
        original = copy.deepcopy(self.report)
        for change in [lambda r: r['results'].pop(),
                       lambda r: r['results'].__setitem__(1, r['results'][0]),
                       lambda r: r['results'][0].update(id='../outside')]:
            self.report = copy.deepcopy(original)
            change(self.report)
            with self.subTest(change=change), self.assertRaises(RuntimeError): self.validate()

    def test_mutation_matrix_missing_or_duplicated(self):
        self.report['mutations']['reports'][0] = self.report['mutations']['reports'][1]
        with self.assertRaisesRegex(RuntimeError, 'matrix'): self.validate()

    def test_mutation_false_counts_or_location(self):
        original = copy.deepcopy(self.report)
        for change in [lambda m: m.update(applied=999), lambda m: m.update(undetected=['bad']),
                       lambda m: m['reports'][0].update(located_step=9),
                       lambda m: m['reports'][0].update(located_step=False),
                       lambda m: m['reports'][0].update(located_field='trap'),
                       lambda m: m['coverage'][0].update(located=0),
                       lambda m: m['coverage'][0].update(example_case='nonexistent')]:
            self.report = copy.deepcopy(original)
            change(self.report['mutations'])
            with self.subTest(change=change), self.assertRaises(RuntimeError): self.validate()

    def test_skip_cannot_count_as_pass(self):
        self.report['mutations']['reports'][1]['passed'] = True
        with self.assertRaisesRegex(RuntimeError, 'skipped'): self.validate()

    def test_applicable_mutation_cannot_skip(self):
        self.report['mutations']['reports'][6]['applied'] = False
        with self.assertRaises(RuntimeError): self.validate()

    def test_boolean_numeric_alias_rejected(self):
        self.report['summary']['failures'] = False
        with self.assertRaises(RuntimeError): self.validate()

    def test_no_extra_or_linked_artifacts(self):
        path = self.save()
        extra = self.artifacts / 'extra.json'
        extra.write_text('{}')
        with self.assertRaises(RuntimeError): gate.validate(path, self.artifacts, self.env)
        extra.unlink()
        case = self.artifacts / 'fixture-0.json'
        target = self.root / 'saved.json'
        case.rename(target)
        case.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'linked'): gate.validate(path, self.artifacts, self.env)

    def test_mutation_artifact_not_summary_only(self):
        path = self.save()
        (self.artifacts / 'mutations.json').write_text('{}')
        with self.assertRaises((KeyError, RuntimeError)): gate.validate(path, self.artifacts, self.env)

    def test_duplicate_json_and_nonfinite_rejected(self):
        path = self.root / 'bad.json'
        for value in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            path.write_text(value)
            with self.subTest(value=value), self.assertRaises(RuntimeError): gate.read_json(path)

    def test_mutation_semantics_and_trace_length_boundary(self):
        trace = self.cases['fixture-1']['ckb_trace']
        changed = gate.mutated(trace, 'register_index', 0)
        self.assertEqual(changed['events'][0]['register_writes'][0]['index'], 1)
        self.assertEqual(trace['events'][0]['register_writes'][0]['index'], 31)
        self.assertEqual(gate.first_difference(gate.mutated(trace, 'trace_length', 0), trace), ('trace_length', 0))
        self.assertEqual(gate.first_difference(gate.mutated(trace, 'termination', 0), trace), ('termination', None))

    def test_replay_matches_entire_original_not_just_pass(self):
        original = self.cases['fixture-0']
        report = {**copy.deepcopy(self.report), 'mode': 'replay', 'seed': None, 'mutations': None,
            'results': [self.report['results'][0]], 'summary':
                {'total': 1, 'failures': 0, 'mutations_passed': None, 'passed': True}}
        gate.check_replay(report, original, original, self.env)
        artifact = copy.deepcopy(original)
        artifact['case']['seed'] = 2
        with self.assertRaisesRegex(RuntimeError, 'original evidence'):
            gate.check_replay(report, artifact, original, self.env)

    def test_probe_environment_failure_records_failure(self):
        with patch.object(probe, 'environment', side_effect=RuntimeError('missing compiler')):
            report, code = probe.run_probe(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['release_claimed'])
        self.assertEqual(gate.read_json(self.root / 'report.json'), report)


if __name__ == '__main__':
    unittest.main()
