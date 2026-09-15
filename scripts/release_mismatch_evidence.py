"""Finite minimization replay audit and explicit negative-case inventory gaps.

Never infer root-cause equivalence or let a single minimized trap case close
the distinct two-program/trace-truncation negative-test obligations.
"""
from pathlib import Path
import shlex

import minimize_mismatch as mini
import paired_negative_evidence as paired
import release_evidence as common
import release_rust_tests as rust_tests
import release_runtime_evidence as trace
from probes import probe_release_runtime as runtime

ROOT = common.ROOT
require, read, sha = common.require, common.read, common.sha
CASES = ['a_diverging_instruction_stream_is_located', 'a_missing_final_event_is_detected',
         'a_trapping_instruction_diverges_and_is_reported_not_hidden']


class IncompleteEvidence(RuntimeError):
    def __init__(self, details):
        super().__init__('semantic negative-case inventory is not fully evidenced')
        self.details = details


def reference(row):
    require(type(row) is dict and set(row) == {'path', 'sha256'}, 'invalid mismatch evidence reference')
    return common.linked(ROOT, row['path'], row['sha256'])


def absolute(path, digest):
    path = Path(path)
    require(path.is_absolute() and path.is_relative_to(ROOT), 'mismatch evidence outside checkout')
    return common.linked(ROOT, str(path.relative_to(ROOT)), digest)


def observation(artifact):
    """Check actual first differing normalized field, not just a summary claim."""
    for name in ['ckb_trace', 'sail_trace']:
        value = artifact[name]
        require(type(value) is dict and set(value) == {'events', 'end'} and value['events'], 'missing engine trace')
        for event in value['events']:
            require(set(event) == set(trace.FIELDS), 'unknown/missing normalized event field')
    field, step = trace.first_difference(artifact['ckb_trace'], artifact['sail_trace'])
    difference = artifact['comparison']['mismatch']
    if field is None:
        require(difference is None, 'invented mismatch on equal traces')
        compared = len(artifact['ckb_trace']['events'])
    else:
        require(type(difference) is dict and difference['field'] == field and trace.same(difference['step'], step),
                'reported mismatch differs from actual normalized traces')
        compared = step if step is not None else min(len(artifact[k]['events']) for k in ['ckb_trace', 'sail_trace'])
    require(trace.same(artifact['comparison']['compared_steps'], compared), 'wrong compared-step count')
    return mini.signature(artifact)


def check_minimization(path):
    path = Path(path)
    out, report = path.parent, read(path)
    require(trace.same(report['schema_version'], 1) and report['status'] == 'minimized' and
            report['minimum_proved'] is True and report['root_cause_equivalence_claimed'] is False and
            report['release_claimed'] is False, 'minimization incomplete/overclaimed')
    require(report['script_sha256'] == sha(ROOT / 'scripts/minimize_mismatch.py'), 'stale minimizer source')
    require(report['scope'] == 'shortest nonempty order-preserving subsequence preserving observed field/offending words',
            'minimization scope changed')
    original_path = absolute(report['source_artifact'], report['source_sha256'])
    original = read(original_path)
    words = mini.program(original)
    expected = observation(original)
    require(expected is not None and report['signature'] == expected and report['original_words'] == words,
            'original mismatch signature/input changed')
    env, _ = runtime.environment()
    mini.check_environment(runtime.observed_environment(env), original['environment'])
    triage = report['triage']
    require(triage['classification'] in mini.TRIAGE and triage['classification'] != 'unclassified_mismatch' and
            isinstance(triage['rationale'], str) and triage['rationale'].strip() and
            triage['authority'] == 'operator interpretation, not automatically inferred', 'triage absent/overclaimed')
    runners = report['runner_inputs']
    require(set(runners) == {'differential_binary', 'sail_binary', 'sail_config'}, 'minimizer runner inventory')
    for row in runners.values():
        require(set(row) == {'path', 'sha256'}, 'runner identity fields')
        absolute(row['path'], row['sha256'])
    require(runners['sail_binary']['sha256'] == sha(ROOT / runtime.SAIL_BIN) and
            runners['sail_config']['sha256'] == sha(ROOT / runtime.CONFIG), 'Sail/config identity changed')
    signatures = []
    for i, row in enumerate(report['trials']):
        folder = out / f'trial-{i:05d}'
        require(trace.same(row['index'], i) and row['status'] == 'observed', 'missing/failed minimization trial')
        source = common.linked(folder, 'input.json', row['input_sha256'])
        stdout = common.linked(folder, 'stdout.json', row['stdout_sha256'])
        common.linked(folder, 'stderr.log', row['stderr_sha256'])
        artifact_path = common.linked(folder, 'evidence/candidate.json', row['artifact_sha256'])
        require(row['artifact'] == str(artifact_path) and row['cwd'] == str(ROOT), 'trial path/cwd changed')
        artifact = read(artifact_path)
        require(mini.program(read(source)) == row['input_words'], 'trial input file changed')
        observed = mini.check_trial(read(stdout), artifact, row['exit_code'], row['input_words'])
        require(observed == observation(artifact) == row['signature'], 'trial signature differs')
        mini.check_environment(original['environment'], artifact['environment'])
        command = row['command']
        require(command[:10] == [runners['differential_binary']['path'], '--replay', str(source), '--json',
                '--artifact-dir', str(folder / 'evidence'), '--sail-bin', runners['sail_binary']['path'],
                '--sail-config', runners['sail_config']['path']] and len(command) == 12 and
                command[10] == '--sail-timeout' and command[11].isdigit() and int(command[11]) > 0,
                'unexpected trial command')
        signatures.append(observed)
    position = 0
    def consume(candidate):
        nonlocal position
        require(position < len(signatures), 'unchecked candidate: minimization search incomplete')
        require(report['trials'][position]['input_words'] == candidate, 'candidate search order/coverage differs')
        result = signatures[position]
        position += 1
        return result
    require(consume(words) == expected, 'original did not reproduce')
    minimum, indices = mini.shortest_subsequence(words, expected, consume)
    require(consume(minimum) == expected and position == len(signatures), 'final repeat missing/extra trials')
    final = report['trials'][-1]
    require(report['minimal_words'] == minimum and report['retained_original_indices'] == indices and
            report['minimized_artifact'] == final['artifact'] and
            report['minimized_artifact_sha256'] == final['artifact_sha256'] and
            trace.same(report['expected_replay_exit'], 1), 'minimum/replay identity differs')
    replay = [runners['differential_binary']['path'], '--replay', final['artifact'], '--json',
              '--sail-bin', runners['sail_binary']['path'], '--sail-config', runners['sail_config']['path'],
              '--sail-timeout', final['command'][-1]]
    require(report['replay_argv'] == replay and report['replay_cwd'] == str(ROOT) and
            report['replay_command'] == shlex.join(replay), 'minimized replay command changed')
    return {'trials': len(signatures), 'minimal_words': minimum, 'signature': expected,
            'triage': triage, 'minimum_scope': 'nonempty order-preserving subsequences only',
            'root_cause_equivalence_claimed': False}


def check_inventory(path):
    report = read(path)
    require(set(report) == {'schema_version', 'runtime', 'rust_tests', 'semantic_negative_cases'} and
            trace.same(report['schema_version'], 1), 'wrong mismatch inventory schema')
    runtime_path, rust_path = reference(report['runtime']), reference(report['rust_tests'])
    runtime_result, rust_result = common.check_runtime(runtime_path), rust_tests.check(rust_path)
    # A passing corpus has zero unexpected runtime mismatches; failing test stages
    # are rejected above, never silently classified as expected negatives.
    cases = report['semantic_negative_cases']
    require(set(cases) == set(CASES), 'semantic negative inventory omitted/added cases')
    completed, pending = {}, []
    for name in CASES:
        row = cases[name]
        if row is None:
            pending.append(name)
        elif name == CASES[-1]:
            evidence_path = reference(row)
            completed[name] = check_minimization(evidence_path)
            runner = read(evidence_path)['runner_inputs']['differential_binary']
            require(runner['sha256'] == read(runtime_path)['binary_sha256'] and
                    runner['path'] == str(runtime_path.parent / 'cargo-target/debug/ckb-vm-sail-diff'),
                    'mismatch did not use the validated runtime binary')
            # Bind the observed original to this existing test, not an unrelated failure.
            require(read(evidence_path)['original_words'] == [0x00500093, 0x0000107b, 0x00700113],
                    'trap evidence is not the negative-test input')
        else:
            kind = next(key for key, test_name in paired.TEST_NAMES.items() if test_name == name)
            completed[name] = paired.check(reference(row), kind)
    details = {'scope': 'current corpus and three semantic real-engine negative tests',
        'unexpected_corpus_mismatches': 0, 'runtime_cases': runtime_result['cases'],
        'engine_tests_passed': rust_result['engine_tests'], 'completed': completed, 'pending': pending,
        'classification_authority': 'operator interpretation, not root-cause proof'}
    if pending:
        raise IncompleteEvidence(details)
    return details
