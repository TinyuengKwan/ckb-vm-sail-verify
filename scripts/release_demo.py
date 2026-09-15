#!/usr/bin/env python3
"""Record and independently check a real, scoped maintainer terminal demo.

Uses util-linux script/scriptreplay, never records stdin, and never certifies
release, clean-room, third-party reproduction or a new Lean kernel execution.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

import release_evidence as common
import release_mismatch_evidence as mismatch
import minimize_mismatch as mini
from probes import probe_release_runtime as runtime

ROOT = common.ROOT
SCRIPT = ROOT / 'scripts/release_demo.py'
RECORDER, PLAYER = Path('/usr/bin/script'), Path('/usr/bin/scriptreplay')
require, read, sha, same = common.require, common.read, common.sha, common.same
SCOPE = 'local maintainer runtime, mutation and known unsupported replay demonstration'
CLAIMS = {'release_claimed': False, 'week6_closed': False, 'clean_room_claimed': False,
          'third_party_claimed': False, 'fresh_kernel_run_claimed': False}
INTRO = [
    'CKB-VM / Sail maintainer demo: real local execution',
    'Scope: VERSION2, IMC+B, ADD/ADDI/BEQ runtime corpus; not the full VM.',
    'Production baseline includes the declared runtime-container patch.',
    'Lean assurance remains conditional; no new kernel run is claimed here.',
    'This recording is not clean-room, third-party reproduction or a release.',
    'Raw command output and replay artifacts are preserved alongside this recording.',
]
OUTRO = [
    'Known trap remains unsupported; detecting its mismatch is not a proof of correctness.',
    'Memory coupling, reset reachability, other ISA paths and full tool trust remain outside this demo.',
    'Demo complete. Week6 release acceptance is NOT claimed.',
]


def save(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def reference(path):
    path = Path(path).absolute()
    name = str(path.relative_to(ROOT))
    return {'path': name, 'sha256': sha(common.member(ROOT, name))}


def resolve(row):
    require(type(row) is dict and set(row) == {'path', 'sha256'}, 'demo reference fields')
    return common.linked(ROOT, row['path'], row['sha256'])


def inputs(compiler):
    files = runtime.inputs(compiler)
    for path in [SCRIPT, RECORDER, PLAYER, Path(sys.executable).resolve(),
                 *[ROOT / ('scripts/' + name) for name in
                   ['release_evidence.py', 'release_mismatch_evidence.py', 'minimize_mismatch.py',
                    'tests/test_release_demo.py']]]:
        files[str(path)] = sha(path)
    return files


def prepare(plan):
    require(type(plan) is dict and set(plan) == {'schema_version', 'runtime', 'trap'} and
            same(plan['schema_version'], 1), 'demo plan schema')
    source = resolve(plan['runtime'])
    common.check_runtime(source)
    trap_path = resolve(plan['trap'])
    trap = read(trap_path)
    summary = mismatch.check_minimization(trap_path)
    binary = source.parent / 'cargo-target/debug/ckb-vm-sail-diff'
    require(trap['runner_inputs']['differential_binary'] == {'path': str(binary), 'sha256': sha(binary)},
            'demo trap uses another runtime binary')
    require(summary['minimal_words'] == [0x107b] and summary['signature']['field'] == 'pc_after' and
            summary['triage']['classification'] == 'unsupported', 'unexpected demo trap boundary')
    artifact = mismatch.absolute(trap['minimized_artifact'], trap['minimized_artifact_sha256'])
    return binary, artifact


def commands(out, binary, trap):
    base = [str(binary), '--json', '--sail-bin', runtime.SAIL_BIN, '--sail-config', runtime.CONFIG]
    return [
        ('corpus-mutations', [*base, '--corpus', '--mutate', '--artifact-dir', str(out / 'corpus')], 0),
        ('replay-add', [*base, '--replay', str(out / 'corpus/add-zero.json'),
                        '--artifact-dir', str(out / 'replay-add')], 0),
        ('replay-known-trap', [*base, '--replay', str(trap),
                               '--artifact-dir', str(out / 'replay-known-trap')], 1),
    ]


def results(out, environment, trap):
    corpus = runtime.evidence.validate(out / 'corpus-mutations.stdout', out / 'corpus', environment)
    runtime.evidence.check_replay(read(out / 'replay-add.stdout'),
        read(out / 'replay-add/add-zero.json'), read(out / 'corpus/add-zero.json'), environment)
    original = read(trap)
    fresh = read(out / 'replay-known-trap/candidate.json')
    signature = mini.check_trial(read(out / 'replay-known-trap.stdout'), fresh, 1, [0x107b])
    require(signature == mismatch.observation(fresh) == mismatch.observation(original),
            'demo trap first difference changed')
    require(fresh['environment'] == environment, 'demo trap environment changed')
    for key in ['case', 'instructions_hex', 'initial_state', 'ckb_trace', 'sail_trace', 'sail_raw_packets']:
        require(same(fresh[key], original[key]), 'demo trap replay changed: ' + key)
    return {'cases': corpus['cases'], 'families': corpus['families'], 'mutations': corpus['mutations'],
            'add_replay': 'strict trace match', 'trap_replay': signature,
            'trap_classification': 'unsupported', 'trap_expected_exit': 1}


def conclusion(name, summary):
    if name == 'corpus-mutations':
        return ('Strict corpus: ' + str(summary['cases']) + ' cases; ADD/ADDI/BEQ=' +
                '/'.join(str(summary['families'][k]) for k in ['ADD', 'ADDI', 'BEQ']) +
                '; detected mutations=' + str(summary['mutations']['applied']) +
                '; inapplicable=' + str(summary['mutations']['skipped']) + '.')
    if name == 'replay-add': return 'ADD replay: strict trace match, exit 0.'
    require(name == 'replay-known-trap', 'unknown demo stage')
    return 'Known unsupported 0x0000107b replay: pc_after mismatch detected, expected exit 1.'


def transcript(command_list, summary):
    lines = list(INTRO)
    for name, argv, code in command_list:
        lines += ['', '$ ' + shlex.join(argv), 'Expected exit: ' + str(code), conclusion(name, summary)]
    return '\n'.join(lines + [''] + OUTRO) + '\n'


def session(out):
    env, _ = runtime.environment()
    plan = read(out / 'plan.json')
    binary, trap = prepare(plan)
    environment = runtime.observed_environment(env)
    command_list = commands(out, binary, trap)
    stages = []
    print('\n'.join(INTRO), flush=True)
    for name, argv, code in command_list:
        print('\n$ ' + shlex.join(argv) + '\nExpected exit: ' + str(code), flush=True)
        row = {'name': name, 'argv': argv, 'started_at': runtime.now()}
        stages.append(row)
        with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
            done = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                  stdout=stdout, stderr=stderr, timeout=300)
        row.update(exit_code=done.returncode, finished_at=runtime.now(),
                   logs={name + '.' + ext: sha(out / (name + '.' + ext)) for ext in ['stdout', 'stderr']})
        require(type(done.returncode) is int and done.returncode == code, 'demo command unexpected exit: ' + name)
        if name == 'corpus-mutations':
            summary = runtime.evidence.validate(out / (name + '.stdout'), out / 'corpus', environment)
        elif name == 'replay-add':
            runtime.evidence.check_replay(read(out / (name + '.stdout')), read(out / 'replay-add/add-zero.json'),
                                         read(out / 'corpus/add-zero.json'), environment)
        else:
            summary = results(out, environment, trap)
        print(conclusion(name, summary), flush=True)
    print('\n' + '\n'.join(OUTRO), flush=True)
    save(out / 'session.json', {'schema_version': 1, 'status': 'completed',
                               'stages': stages, 'summary': summary})


def recording_command(out):
    return [str(RECORDER), '--quiet', '--return', '--flush', '--echo', 'never',
            '--logging-format', 'classic', '--log-out', str(out / 'terminal.log'),
            '--log-timing', str(out / 'timing.log'), '--command',
            shlex.join([sys.executable, str(SCRIPT), '--session', str(out)])]


def playback_command(out):
    return [str(PLAYER), '--log-out', str(out / 'terminal.log'), '--log-timing', str(out / 'timing.log'),
            '--divisor', '1000', '--maxdelay', '0.01', '--cr-mode', 'never']


def check_terminal(terminal, timing, expected):
    """Validate classic util-linux timing coverage and the exact displayed session."""
    rows = timing.splitlines()
    require(0 < len(rows) <= 100000, 'empty/oversized terminal timing')
    size, duration = 0, 0.0
    for row in rows:
        require(re.fullmatch(rb'[0-9]+\.[0-9]+ [1-9][0-9]*', row) is not None, 'invalid terminal timing row')
        delay, count = row.split()
        duration += float(delay)
        size += int(count)
    require(0 < duration <= 1200 and size == len(expected), 'terminal timing coverage/duration differs')
    header, separator, rest = terminal.partition(b'\n')
    require(separator and header.startswith(b'Script started on '), 'terminal header absent')
    require(rest[:size] == expected, 'terminal content differs from independently checked execution')
    footer = rest[size:]
    require(re.fullmatch(rb'\nScript done on [^\n]+ \[COMMAND_EXIT_CODE="0"\]\n', footer) is not None,
            'terminal incomplete/nonzero/extra output')
    return {'output_bytes': size, 'timing_events': len(rows), 'duration_seconds': duration}


def check_session(out, recorded, command_list, environment, trap):
    require(same(recorded['schema_version'], 1) and recorded['status'] == 'completed', 'demo session incomplete')
    require(len(recorded['stages']) == len(command_list), 'demo stage inventory')
    for row, (name, argv, code) in zip(recorded['stages'], command_list):
        require(row['name'] == name and row['argv'] == argv and same(row['exit_code'], code),
                'demo stage command/order/exit differs')
        require(set(row['logs']) == {name + '.stdout', name + '.stderr'}, 'demo stage log inventory')
        for file, digest in row['logs'].items(): common.linked(out, file, digest)
    summary = results(out, environment, trap)
    require(same(summary, recorded['summary']), 'demo summary changed')
    return summary


def check(path):
    path = Path(path); out = path.parent; report = read(path)
    require(same(report['schema_version'], 1) and report['status'] == 'recorded_and_replayed' and
            report['scope'] == SCOPE and all(report.get(k) is False for k in CLAIMS),
            'demo incomplete/overclaimed')
    env, compiler = runtime.environment()
    require(report['inputs_before'] == report['inputs_after'] == inputs(compiler), 'demo source/tool drift')
    environment = runtime.observed_environment(env)
    require(report['environment_before'] == report['environment_after'] == environment, 'demo environment drift')
    plan = read(common.linked(out, 'plan.json', report['plan_sha256']))
    binary, trap = prepare(plan)
    command_list = commands(out, binary, trap)
    recorded = read(common.linked(out, 'session.json', report['files']['session.json']))
    summary = check_session(out, recorded, command_list, environment, trap)
    require(set(report['files']) == {'session.json', 'terminal.log', 'timing.log',
            'recorder.stdout', 'recorder.stderr', 'playback.stdout', 'playback.stderr'}, 'demo recording file inventory')
    files = {name: common.linked(out, name, digest).read_bytes() for name, digest in report['files'].items()}
    expected = transcript(command_list, summary).replace('\n', '\r\n').encode()
    timing = check_terminal(files['terminal.log'], files['timing.log'], expected)
    require(report['recorder_argv'] == recording_command(out) and same(report['recorder_exit'], 0) and
            files['recorder.stdout'] == expected and not files['recorder.stderr'], 'recorder failed/output differs')
    require(report['playback_argv'] == playback_command(out) and same(report['playback_exit'], 0) and
            files['playback.stdout'] == expected + b'\n' and not files['playback.stderr'], 'playback failed/output differs')
    require(report['timing'] == timing, 'recording duration differs')
    return {'scope': SCOPE, 'summary': summary, 'recording': timing, **CLAIMS}


def record(out, runtime_report, trap_report):
    report = {'schema_version': 1, 'status': 'running', 'scope': SCOPE, 'started_at': runtime.now(), **CLAIMS}
    code = 1
    try:
        env, compiler = runtime.environment()
        report.update(inputs_before=inputs(compiler), environment_before=runtime.observed_environment(env))
        plan = {'schema_version': 1, 'runtime': reference(runtime_report), 'trap': reference(trap_report)}
        prepare(plan)
        save(out / 'plan.json', plan)
        report['plan_sha256'] = sha(out / 'plan.json')
        for name, argv in [('recorder', recording_command(out)), ('playback', playback_command(out))]:
            report[name + '_argv'] = argv
            with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
                result = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                        stdout=stdout, stderr=stderr, timeout=1200)
            report[name + '_exit'] = result.returncode
            require(result.returncode == 0, 'demo ' + name + ' failed')
        report['files'] = {name: sha(out / name) for name in ['session.json', 'terminal.log', 'timing.log',
            'recorder.stdout', 'recorder.stderr', 'playback.stdout', 'playback.stderr']}
        binary, trap = prepare(plan)
        expected = transcript(commands(out, binary, trap), results(out, report['environment_before'], trap))
        report['timing'] = check_terminal((out / 'terminal.log').read_bytes(), (out / 'timing.log').read_bytes(),
                                         expected.replace('\n', '\r\n').encode())
        report.update(inputs_after=inputs(compiler), environment_after=runtime.observed_environment(env))
        require(report['inputs_before'] == report['inputs_after'] and
                report['environment_before'] == report['environment_after'], 'demo inputs changed')
        report['status'] = 'recorded_and_replayed'
        # Retain the candidate even if full read-only acceptance rejects it.
        # The terminal report cannot claim success from recorder exit alone.
        save(out / 'candidate-report.json', report)
        check(out / 'candidate-report.json')
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    report['finished_at'] = runtime.now()
    save(out / 'report.json', report)
    print(json.dumps({'report': str(out / 'report.json'), 'status': report['status']}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-report', type=Path)
    parser.add_argument('--trap-report', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    parser.add_argument('--session', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.session:
        require(not any([args.out, args.check, args.runtime_report, args.trap_report]), 'mixed demo modes')
        session(args.session.resolve()); return 0
    if args.check:
        require(not any([args.out, args.runtime_report, args.trap_report]), 'mixed demo modes')
        print(json.dumps(check(args.check.resolve()), indent=2)); return 0
    require(args.runtime_report is not None and args.trap_report is not None, 'runtime and trap reports required')
    if args.out:
        out = args.out.absolute(); out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='maintainer-demo-', dir=ROOT / 'artifacts/boundary-check'))
    return record(out, args.runtime_report, args.trap_report)


if __name__ == '__main__':
    sys.exit(main())
