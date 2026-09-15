"""Independently validate runtime/mutation artifacts for release aggregation.

No PASS from summary fields alone. Reopens every artifact and checks normalized
traces plus all six mutations. This is not a proof of the adapters or ISA model.
"""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

FIELDS = ('order', 'instruction', 'pc_before', 'pc_after', 'register_writes', 'memory', 'trap', 'halt')
MUTATIONS = {'pc_after': 'pc_after', 'register_index': 'register_writes',
             'register_value': 'register_writes', 'trap': 'trap',
             'trace_length': 'trace_length', 'termination': 'termination'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise RuntimeError('non-finite JSON value: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left['events'], right['events'])):
        for field in FIELDS:
            if a[field] != b[field]:
                return field, i
    if len(left['events']) != len(right['events']):
        return 'trace_length', min(len(left['events']), len(right['events']))
    if left['end'] != right['end']:
        return 'termination', None
    if not left['events']:
        return 'empty_trace', None
    return None, None


def mutated(trace, kind, focus):
    result = copy.deepcopy(trace)
    events = result['events']
    if kind in ('register_index', 'register_value'):
        index = focus if events[focus]['register_writes'] else next(
            (i for i, row in enumerate(events) if row['register_writes']), None)
        if index is None:
            return None
        write = events[index]['register_writes'][0]
        if kind == 'register_index':
            write['index'] = 1 if write['index'] >= 31 else write['index'] + 1
        else:
            write['value'] ^= 1
    elif kind == 'pc_after':
        events[focus]['pc_after'] = (events[focus]['pc_after'] + 2) % 2**64
    elif kind == 'trap':
        events[focus]['trap'] = not events[focus]['trap']
    elif kind == 'trace_length':
        events.pop()
    elif kind == 'termination':
        result['end'] = {'kind': 'step_limit'}
    else:
        raise RuntimeError('unknown mutation')
    return result


def check_case(row, artifact, environment):
    require(same(artifact['schema_version'], 3), 'old/unknown case schema')
    case = artifact['case']
    words, focus = case['instructions'], case['focus_step']
    require(isinstance(words, list) and words and all(integer(w, 0, 2**32-1) for w in words),
            'invalid program words')
    require(integer(focus, 0, len(words)-1), 'invalid focus instruction')
    require(artifact['instructions_hex'] == [f'0x{w:08x}' for w in words], 'program/hex mismatch')
    masks = {'ADD': (0xfe00707f, 0x33), 'ADDI': (0x707f, 0x13), 'BEQ': (0x707f, 0x63)}
    require(case['family'] in masks, 'unapproved corpus family')
    mask, value = masks[case['family']]
    require(words[focus] & mask == value, 'focus opcode does not match declared family')
    require(artifact['initial_state'] == {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
            'unsupported initial state')
    require(same(artifact['environment'], environment), 'mixed runtime environments')
    for key in ['id', 'description', 'family', 'focus_step']:
        require(same(row[key], case[key]), 'case/report mismatch: ' + key)
    require(type(row['instructions']) is int and row['instructions'] == len(words), 'instruction count mismatch')
    for evidence in [row, artifact]:
        require(evidence['passed'] is True and evidence['classification'] == 'match' and
                evidence['error'] is None, 'case is not a clean passing baseline')
        require(same(evidence['comparison'], {'compared_steps': len(words), 'mismatch': None}),
                'comparison omitted events or reports mismatch')
    for name in ['ckb_trace', 'sail_trace']:
        trace = artifact[name]
        require(isinstance(trace, dict) and set(trace) == {'events', 'end'}, 'invalid trace schema')
        require(len(trace['events']) == len(words) and trace['end'] == {'kind': 'injection_complete'},
                'trace length/termination mismatch')
        pc = 0x80000000
        for i, event in enumerate(trace['events']):
            require(set(event) == set(FIELDS), 'unknown/missing observation field')
            require(type(event['order']) is int and event['order'] == i and
                    type(event['instruction']) is int and event['instruction'] == words[i],
                    'trace order/instruction not the input stream')
            require(integer(event['pc_before'], 0, 2**64-1) and event['pc_before'] == pc and
                    integer(event['pc_after'], 0, 2**64-1), 'invalid PC sequence')
            require(event['trap'] is False and event['halt'] is False and event['memory'] == [],
                    'unexpected trap/halt/memory observation in corpus')
            writes = event['register_writes']
            require(isinstance(writes, list), 'invalid register writes')
            require(all(set(w) == {'index', 'value'} and integer(w['index'], 1, 31) and
                        integer(w['value'], 0, 2**64-1) for w in writes), 'invalid register write')
            indices = [w['index'] for w in writes]
            require(indices == sorted(set(indices)), 'unnormalized register writes')
            pc = event['pc_after']
    require(first_difference(artifact['ckb_trace'], artifact['sail_trace']) == (None, None),
            'actual normalized engine traces differ')
    packets = artifact['sail_raw_packets']
    require(len(packets) == len(words)+1 and all(isinstance(p, str) and
            re.fullmatch('[0-9a-f]{176}', p) for p in packets), 'missing/invalid raw RVFI-DII packets')
    require(isinstance(artifact['replay']['from_artifact'], str) and artifact['replay']['from_artifact'],
            'missing replay command')


def check_mutations(summary, cases):
    require(type(summary['cases']) is int and summary['cases'] == len(cases), 'mutation case count')
    require(summary['passed'] is True and all(summary[k] == [] for k in
            ['baseline_failures', 'undetected', 'mislocated']), 'mutation failures reported')
    rows = summary['reports']
    expected = {(name, kind) for name in cases for kind in MUTATIONS}
    keys = [(r['case_id'], r['mutation']) for r in rows]
    require(len(keys) == len(expected) and set(keys) == expected, 'mutation matrix incomplete or duplicated')
    counts = Counter()
    located_cases = {kind: [] for kind in MUTATIONS}
    for row in rows:
        kind = row['mutation']
        require(row['expected_field'] == MUTATIONS[kind], 'mutation expected field changed')
        artifact = cases[row['case_id']]
        result = mutated(artifact['ckb_trace'], kind, artifact['case']['focus_step'])
        if result is None:
            require(row['applied'] is False and row['detected'] is False and row['passed'] is False and
                    row['located_field'] is None and row['located_step'] is None and
                    isinstance(row['skipped_because'], str) and row['skipped_because'],
                    'invalid skipped mutation evidence')
            counts['skipped'] += 1
            continue
        field, step = first_difference(result, artifact['sail_trace'])
        require(field == MUTATIONS[kind], 'recomputed mutation not localized')
        require(row['applied'] is True and row['detected'] is True and row['passed'] is True and
                row['skipped_because'] is None and row['located_field'] == field and same(row['located_step'], step),
                'mutation result disagrees with actual trace mutation')
        counts['applied'] += 1
        counts[kind] += 1
        located_cases[kind].append(row['case_id'])
    require(all(type(summary[k]) is int and summary[k] == counts[k] for k in ['applied', 'skipped']),
            'mutation total counts changed')
    coverage = summary['coverage']
    require(len(coverage) == len(MUTATIONS) and {c['mutation'] for c in coverage} == set(MUTATIONS),
            'mutation coverage incomplete/duplicated')
    for row in coverage:
        kind = row['mutation']
        require(counts[kind] > 0 and row['expected_field'] == MUTATIONS[kind] and
                type(row['applied']) is int and type(row['located']) is int and
                row['applied'] == row['located'] == counts[kind] and
                row['example_case'] in located_cases[kind], 'invalid coverage tally/example')
    return dict(counts)


def validate(report_path, artifact_directory, environment):
    report_path, artifact_directory = Path(report_path), Path(artifact_directory).resolve()
    report = read_json(report_path)
    require(same(report['schema_version'], 3) and report['mode'] == 'corpus' and
            report['terminal_policy'] == 'exact', 'wrong runtime report schema/mode')
    require(same(report['environment'], environment), 'runtime environment not approved')
    rows = report['results']
    require(len(rows) >= 10 and len({r['id'] for r in rows}) == len(rows), 'too few/duplicate corpus cases')
    require(same(report['summary'], {'total': len(rows), 'failures': 0, 'mutations_passed': True, 'passed': True}),
            'runtime summary failure or inconsistent counts')
    cases, hashes = {}, {}
    for row in rows:
        require(isinstance(row['id'], str) and re.fullmatch('[a-z0-9][a-z0-9-]*', row['id']), 'unsafe case id')
        name = row['id'] + '.json'
        require(Path(row['artifact']).name == name, 'recorded artifact filename differs')
        path = artifact_directory / name
        require(not path.is_symlink(), 'linked case artifact')
        artifact = read_json(path)
        check_case(row, artifact, environment)
        cases[row['id']], hashes[name] = artifact, sha(path)
    families = Counter(a['case']['family'] for a in cases.values())
    require(set(families) == {'ADD', 'ADDI', 'BEQ'}, 'missing required instruction family')
    require(all(count >= 10 for count in families.values()),
            'Week6 requires at least 10 cases per instruction family: ' + str(dict(families)))
    mutation_file = artifact_directory / 'mutations.json'
    require(not mutation_file.is_symlink(), 'linked mutation artifact')
    recorded = read_json(mutation_file)
    require(same(recorded['schema_version'], 3) and same(recorded['environment'], environment) and
            same(recorded['seed'], report['seed']) and same(recorded['summary'], report['mutations']) and
            isinstance(recorded['replay'], str) and recorded['replay'], 'mutation artifact/report mismatch')
    mutations = check_mutations(report['mutations'], cases)
    hashes['mutations.json'] = sha(mutation_file)
    require({p.name for p in artifact_directory.iterdir()} == set(hashes), 'unexpected/missing artifact entry')
    return {'status': 'runtime_evidence_verified', 'report_sha256': sha(report_path),
            'artifact_sha256': hashes, 'cases': len(cases), 'families': dict(families),
            'mutations': mutations, 'release_claimed': False}


def check_replay(report, artifact, original, environment):
    require(same(report['schema_version'], 3) and report['mode'] == 'replay' and
            report['terminal_policy'] == 'exact' and report['mutations'] is None and report['seed'] is None,
            'invalid replay envelope')
    require(same(report['environment'], environment) and same(report['summary'],
            {'total': 1, 'failures': 0, 'mutations_passed': None, 'passed': True}), 'replay did not pass')
    require(len(report['results']) == 1, 'replay case count')
    check_case(report['results'][0], artifact, environment)
    for key in ['case', 'instructions_hex', 'initial_state', 'ckb_trace', 'sail_trace', 'sail_raw_packets']:
        require(same(artifact[key], original[key]), 'replay changed original evidence: ' + key)
