#!/usr/bin/env python3
"""Find a shortest nonempty subsequence reproducing an observed divergence.

Every candidate is freshly replayed on both engines. The search is exhaustive
by increasing instruction count, not a heuristic global-minimum claim. Budget
exhaustion, execution errors and nonreproducibility never certify minimality.
This tool does not change Rust/Lean sources or establish a defect's root cause.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ('unclassified_mismatch', 'unsupported', 'configuration_or_version_difference',
          'adapter_defect', 'ckb_candidate_defect')
ENVIRONMENT_KEYS = ('ckb_vm_commit', 'ckb_vm_source_baseline', 'sail_riscv_commit',
                    'sail_model_version', 'sail_config_sha256', 'ckb_vm_isa_bits',
                    'ckb_vm_isa', 'ckb_vm_version', 'rustc', 'cargo', 'sail_compiler')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def program(artifact):
    require(artifact['schema_version'] == 3, 'only source-baseline-aware schema 3 is supported')
    words = artifact['case']['instructions']
    require(isinstance(words, list) and 0 < len(words) <= 256 and
            all(type(w) is int and 0 <= w < 2**32 for w in words), 'invalid instruction sequence')
    require(artifact['instructions_hex'] == [f'0x{w:08x}' for w in words], 'hex/case instruction mismatch')
    require(artifact['initial_state'] == {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
            'replay CLI does not implement arbitrary initial states')
    return words


def signature(artifact):
    """Preserve the observed field and offending words, not absolute step/PC.

    This is an observation signature, NOT a proof of identical bug root cause.
    For length/termination differences there need not be an offending event.
    """
    require(artifact['error'] is None, 'runner error is not a semantic outcome')
    for key in ['ckb_trace', 'sail_trace']:
        require(isinstance(artifact[key], dict) and artifact[key]['events'], 'missing/empty engine trace')
    comparison = artifact['comparison']
    require(isinstance(comparison, dict), 'missing comparison')
    difference = comparison['mismatch']
    if artifact['passed'] is True:
        require(difference is None and artifact['classification'] == 'match', 'inconsistent passing evidence')
        return None
    require(artifact['passed'] is False and artifact['classification'] == 'unclassified_mismatch' and
            isinstance(difference, dict), 'not a recorded semantic mismatch')
    field = difference['field']
    require(isinstance(field, str) and field and field != 'empty_trace', 'invalid mismatch field')
    step = difference['step']
    events = [artifact[name]['events'] for name in ['ckb_trace', 'sail_trace']]
    if field == 'trace_length':
        require(type(step) is int and step == min(map(len, events)) and
                len(events[0]) != len(events[1]), 'invalid trace-length boundary')
        return {'field': field, 'offending_words': None}
    if step is None:
        require(field == 'termination', 'event mismatch has no step')
        return {'field': field, 'offending_words': None}
    require(type(step) is int and step >= 0, 'invalid mismatch step')
    require(all(step < len(rows) for rows in events), 'mismatch step outside actual traces')
    return {'field': field, 'offending_words': [rows[step]['instruction'] for rows in events]}


def check_trial(envelope, artifact, exit_code, expected_words):
    require(type(exit_code) is int and exit_code in (0, 1), 'abnormal replay process exit')
    require(envelope['schema_version'] == 3 and envelope['mode'] == 'replay' and
            envelope['terminal_policy'] == 'exact' and envelope['mutations'] is None,
            'wrong replay comparison mode')
    require(len(envelope['results']) == 1, 'expected one replay result')
    require(program(artifact) == expected_words, 'runner used a different input')
    result = envelope['results'][0]
    for key in ['passed', 'classification', 'comparison', 'error']:
        require(result[key] == artifact[key], 'report/artifact disagreement: ' + key)
    require(envelope['environment'] == artifact['environment'], 'report/artifact environment disagreement')
    require(result['id'] == artifact['case']['id'] and result['instructions'] == len(expected_words),
            'replay result identifies a different case')
    observed = signature(artifact)
    passed = observed is None
    require(envelope['summary'] == {'total': 1, 'failures': 0 if passed else 1,
            'mutations_passed': None, 'passed': passed}, 'inconsistent replay summary')
    require(exit_code == (0 if passed else 1), 'replay exit does not match observed outcome')
    return observed


def check_environment(original, fresh):
    for key in ENVIRONMENT_KEYS:
        require(original.get(key) is not None and fresh.get(key) == original[key],
                'replay environment differs or is unidentified: ' + key)


def shortest_subsequence(words, expected, evaluate):
    """All smaller nonempty subsequences are checked before returning a result.

    An exception from the evaluator aborts: an errored candidate is not evidence
    that the signature is absent. Original indices preserve duplicate words.
    """
    for size in range(1, len(words)):
        for indices in itertools.combinations(range(len(words)), size):
            candidate = [words[i] for i in indices]
            if evaluate(candidate) == expected:
                return candidate, list(indices)
    return list(words), list(range(len(words)))


class BudgetExhausted(RuntimeError):
    pass


class ReplayOracle:
    def __init__(self, args, artifact, directory, report):
        self.args, self.artifact, self.directory, self.report = args, artifact, directory, report
        self.paths = {'differential_binary': args.differential_binary.resolve(),
                      'sail_binary': args.sail_bin.resolve(), 'sail_config': args.sail_config.resolve()}
        self.identity = {name: {'path': str(path), 'sha256': sha(path)} for name, path in self.paths.items()}
        report['runner_inputs'] = self.identity

    def check_identity(self):
        require({name: {'path': str(path), 'sha256': sha(path)} for name, path in self.paths.items()} ==
                self.identity, 'runner/config bytes changed during minimization')

    def __call__(self, words):
        if len(self.report['trials']) >= self.args.max_evaluations:
            raise BudgetExhausted('replay budget exhausted; no minimality claim')
        self.check_identity()
        number = len(self.report['trials'])
        directory = self.directory / f'trial-{number:05d}'
        directory.mkdir()
        candidate = copy.deepcopy(self.artifact)
        candidate['case'].update(id='candidate', instructions=list(words), focus_step=0,
            description='minimizer replay input; focus_step is not a mismatch location', seed=None)
        candidate.update(instructions_hex=[f'0x{w:08x}' for w in words], passed=False,
            classification='input_only', comparison=None, error='not yet executed', ckb_trace=None,
            sail_trace=None, sail_raw_packets=[], replay={'from_artifact': '', 'from_corpus': None})
        source = directory / 'input.json'
        save(source, candidate)
        command = [str(self.paths['differential_binary']), '--replay', str(source), '--json',
                   '--artifact-dir', str(directory / 'evidence'), '--sail-bin', str(self.paths['sail_binary']),
                   '--sail-config', str(self.paths['sail_config']), '--sail-timeout', str(self.args.sail_timeout)]
        row = {'index': number, 'input_words': list(words), 'input_sha256': sha(source),
               'command': command, 'cwd': str(ROOT), 'status': 'running'}
        self.report['trials'].append(row)
        save(self.directory / 'report.json', self.report)
        print(f'==> minimize: trial {number}, {len(words)} instruction(s)', flush=True)
        stdout, stderr = directory / 'stdout.json', directory / 'stderr.log'
        try:
            with stdout.open('w') as out, stderr.open('w') as err:
                proc = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err, timeout=self.args.timeout)
            row['exit_code'] = proc.returncode
            observed_file = directory / 'evidence/candidate.json'
            observed = json.loads(observed_file.read_text())
            result = check_trial(json.loads(stdout.read_text()), observed, proc.returncode, words)
            check_environment(self.artifact['environment'], observed['environment'])
            self.check_identity()
            require(sha(source) == row['input_sha256'], 'candidate input changed during execution')
            row.update(status='observed', signature=result, artifact=str(observed_file),
                       artifact_sha256=sha(observed_file), stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
            return result
        except BaseException as error:
            row.update(status='failed', error=str(error) or type(error).__name__)
            raise
        finally:
            save(self.directory / 'report.json', self.report)


def run(args):
    require(args.classification in TRIAGE and args.rationale.strip(), 'classification rationale required')
    require(args.max_evaluations >= 2 and args.timeout > 0 and args.sail_timeout > 0, 'invalid budget/timeout')
    original = args.artifact.resolve()
    original_hash = sha(original)
    artifact = json.loads(original.read_text())
    words = program(artifact)
    expected = signature(artifact)
    require(expected is not None, 'matching artifact is not a mismatch to minimize')
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'status': 'running', 'minimum_proved': False,
        'scope': 'shortest nonempty order-preserving subsequence preserving observed field/offending words',
        'root_cause_equivalence_claimed': False, 'release_claimed': False,
        'source_artifact': str(original), 'source_sha256': original_hash, 'original_words': words,
        'signature': expected, 'triage': {'classification': args.classification,
            'rationale': args.rationale, 'authority': 'operator interpretation, not automatically inferred'},
        'script_sha256': sha(Path(__file__)), 'trials': [],
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    save(directory / 'report.json', report)
    try:
        oracle = ReplayOracle(args, artifact, directory, report)
        require(oracle(words) == expected, 'original mismatch is not reproducible now')
        minimum, indices = shortest_subsequence(words, expected, oracle)
        require(oracle(minimum) == expected, 'final minimized input is not reproducible')
        require(sha(original) == original_hash, 'original evidence changed during minimization')
        require(sha(Path(__file__)) == report['script_sha256'], 'minimizer source changed during run')
        final = report['trials'][-1]
        command = [*final['command'][:1], '--replay', final['artifact'], '--json',
                   '--sail-bin', str(oracle.paths['sail_binary']), '--sail-config', str(oracle.paths['sail_config']),
                   '--sail-timeout', str(args.sail_timeout)]
        report.update(status='minimized', minimum_proved=True, minimal_words=minimum,
            retained_original_indices=indices, minimized_artifact=final['artifact'],
            minimized_artifact_sha256=final['artifact_sha256'], replay_argv=command,
            replay_command=shlex.join(command), replay_cwd=str(ROOT), expected_replay_exit=1)
        return_code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='incomplete' if isinstance(error, BudgetExhausted) else 'failed',
                      error=str(error) or type(error).__name__)
        return_code = 2 if isinstance(error, BudgetExhausted) else 1
    finally:
        report['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        save(directory / 'report.json', report)
        print('Report: ' + str(directory / 'report.json'), flush=True)
    return return_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--classification', choices=TRIAGE, default='unclassified_mismatch')
    parser.add_argument('--rationale', required=True)
    parser.add_argument('--differential-binary', type=Path, default=ROOT / 'target/debug/ckb-vm-sail-diff')
    parser.add_argument('--sail-bin', type=Path, default=ROOT / 'deps/sail-riscv/build/c_emulator/sail_riscv_sim')
    parser.add_argument('--sail-config', type=Path, default=ROOT / 'sail-model/build/ckb_vm_config.json')
    parser.add_argument('--max-evaluations', type=int, default=256)
    parser.add_argument('--sail-timeout', type=int, default=30)
    parser.add_argument('--timeout', type=int, default=120)
    return run(parser.parse_args())


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print('ERROR: ' + (str(error) or type(error).__name__), file=sys.stderr)
        sys.exit(1)
