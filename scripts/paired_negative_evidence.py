#!/usr/bin/env python3
"""Real paired-input negatives, finite minimization and byte-identical copy replay.

Freshly builds an evidence-only Rust executable linking the unchanged runners
and comparator. Searches independent nonempty subsequences by total word count.
No source policy is refreshed. No same-program ISA or root-cause claim.
"""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import release_evidence as common
import release_runtime_evidence as trace
from probes import probe_release_runtime as runtime

ROOT = common.ROOT
require, read, sha, same = common.require, common.read, common.sha, common.same
SOURCE = 'scripts/fixtures/paired_runner.rs'
LIBS = ['ckb_vm_sail_ckb_runner', 'ckb_vm_sail_core', 'ckb_vm_sail_diff',
        'ckb_vm_sail_riscv_runner', 'serde_json']
BUILD = ['cargo', 'build', '--workspace', '--lib', '--locked', '--message-format=json']
ORIGINALS = {
    'instruction': {'schema_version': 1, 'ckb_program': [0x00500093, 0x00700113, 0x002081b3],
                    'sail_program': [0x00500093, 0x00700113, 0x00208233]},
    'trace_length': {'schema_version': 1, 'ckb_program': [0x00500093, 0x00700113, 0x002081b3],
                     'sail_program': [0x00500093, 0x00700113]},
}
TEST_NAMES = {'instruction': 'a_diverging_instruction_stream_is_located',
              'trace_length': 'a_missing_final_event_is_detected'}
SCOPE = 'minimum total words among independent nonempty order-preserving subsequences, preserving negative signature'


class BudgetExhausted(RuntimeError):
    pass


def inputs(compiler):
    result = runtime.inputs(compiler)
    for name in [SOURCE, 'scripts/paired_negative_evidence.py', 'scripts/tests/test_paired_negative_evidence.py',
                 'scripts/release_evidence.py']:
        result[str(ROOT / name)] = sha(ROOT / name)
    return result


def libraries(log, target):
    found, finished = {}, []
    for line in log.splitlines():
        row = json.loads(line)
        if row['reason'] == 'build-finished': finished.append(row['success'])
        if row['reason'] != 'compiler-artifact' or row['target']['name'] not in LIBS:
            continue
        name = row['target']['name']
        files = [Path(p) for p in row['filenames'] if p.endswith('.rlib')]
        require(name not in found and len(files) == 1, 'missing/duplicate linked Rust library')
        path = files[0]
        require(path.is_absolute() and path.is_relative_to(target), 'library outside fresh Cargo target')
        common.member(target, str(path.relative_to(target)))
        found[name] = {'path': str(path), 'sha256': sha(path)}
    require(set(found) == set(LIBS) and finished == [True], 'workspace library build incomplete')
    return found


def compile_command(libs, out):
    command = ['rustc', '--edition=2021', str(ROOT / SOURCE), '-L', 'dependency=' + str(out / 'cargo-target/debug/deps')]
    for name in LIBS:
        command += ['--extern', name + '=' + libs[name]['path']]
    return command + ['-o', str(out / 'paired-runner')]


def command(out, source):
    return [str(out / 'paired-runner'), '--input', str(source), '--sail-bin', runtime.SAIL_BIN,
            '--sail-config', runtime.CONFIG]


def check_input(value):
    require(set(value) == {'schema_version', 'ckb_program', 'sail_program'} and same(value['schema_version'], 1),
            'paired input schema')
    for key in ['ckb_program', 'sail_program']:
        require(type(value[key]) is list and 0 < len(value[key]) <= 256 and
                all(trace.integer(w, 0, 2**32-1) for w in value[key]), 'invalid paired program')


def check_observation(artifact, source, code, environment):
    check_input(source)
    require(same(artifact['schema_version'], 1) and artifact['mode'] == 'paired_programs' and
            artifact['terminal_policy'] == 'exact' and artifact['same_program_equivalence_claimed'] is False and
            artifact['error'] is None and same(artifact['programs'], source) and
            same(artifact['environment'], environment), 'paired runner input/environment/assurance differs')
    require(artifact['initial_state'] == {'pc': 0x80000000, 'integer_registers': 'x0..x31 = 0'},
            'paired initial state changed')
    for engine, key in [('ckb_trace', 'ckb_program'), ('sail_trace', 'sail_program')]:
        words = source[key]
        for word in words:
            require((word & 0xfe00707f) == 0x33 or (word & 0x707f) == 0x13, 'paired example outside ADD/ADDI')
        value = artifact[engine]
        require(set(value) == {'events', 'end'} and type(value['events']) is list and
                len(value['events']) == len(words) and value['end'] == {'kind': 'injection_complete'},
                'paired trace length/end differs from its own input')
        pc = 0x80000000
        for i, event in enumerate(value['events']):
            require(set(event) == set(trace.FIELDS) and same(event['order'], i) and
                    same(event['instruction'], words[i]), 'paired trace input/order mismatch')
            require(same(event['pc_before'], pc) and trace.integer(event['pc_after'], 0, 2**64-1), 'paired PC sequence')
            require(event['trap'] is False and event['halt'] is False and event['memory'] == [], 'paired abnormal event')
            writes = event['register_writes']
            require(type(writes) is list and all(set(w) == {'index', 'value'} and
                    trace.integer(w['index'], 1, 31) and trace.integer(w['value'], 0, 2**64-1) for w in writes),
                    'paired invalid register write')
            indices = [w['index'] for w in writes]
            require(indices == sorted(set(indices)), 'paired unnormalized writes')
            pc = event['pc_after']
    packets = artifact['sail_raw_packets']
    import re
    require(len(packets) == len(source['sail_program'])+1 and
            all(isinstance(p, str) and re.fullmatch('[0-9a-f]{176}', p) for p in packets), 'raw Sail packets missing')
    field, step = trace.first_difference(artifact['ckb_trace'], artifact['sail_trace'])
    difference = artifact['comparison']['mismatch']
    if field is None:
        require(difference is None and artifact['passed'] is True and same(code, 0), 'paired false failure')
    else:
        require(artifact['passed'] is False and same(code, 1) and type(difference) is dict and
                difference['field'] == field and same(difference['step'], step), 'paired comparator disagrees')
    compared = step if step is not None else min(len(source['ckb_program']), len(source['sail_program']))
    require(same(artifact['comparison']['compared_steps'], compared), 'paired compared-step count')
    return field, step


def signature(artifact, field, step, kind):
    if field != kind:
        return False
    if kind == 'trace_length':
        return len(artifact['ckb_trace']['events']) > len(artifact['sail_trace']['events'])
    a, b = artifact['ckb_trace']['events'][step], artifact['sail_trace']['events'][step]
    # Preserve the original negative's differing actual effects as well as words.
    return (a['instruction'] == 0x002081b3 and b['instruction'] == 0x00208233 and
            len(a['register_writes']) == len(b['register_writes']) == 1 and
            a['register_writes'][0]['index'] == 3 and b['register_writes'][0]['index'] == 4)


def shortest(original, evaluate):
    left, right = original['ckb_program'], original['sail_program']
    for total in range(2, len(left)+len(right)):
        for n in range(1, len(left)+1):
            m = total-n
            if not 1 <= m <= len(right): continue
            for a in itertools.combinations(range(len(left)), n):
                for b in itertools.combinations(range(len(right)), m):
                    candidate = {'schema_version': 1, 'ckb_program': [left[i] for i in a],
                                 'sail_program': [right[i] for i in b]}
                    if evaluate(candidate): return candidate
    return original


def inspect_case(kind, data, out, environment, stages):
    require(data['original'] == ORIGINALS[kind] and data['test_name'] == TEST_NAMES[kind] and
            data['classification'] == 'intentional_distinct_input_negative' and data['minimum_scope'] == SCOPE,
            'paired negative identity/scope changed')
    observations, artifacts = [], []
    for i, row in enumerate(data['trials']):
        name = f'{kind}-{i:05d}'
        source = common.linked(out, name + '.input.json', row['input_sha256'])
        stage = stages[name]
        require(stage['argv'] == command(out, source), 'paired trial command changed')
        artifact = read(out / (name + '.stdout'))
        value = read(source)
        require(value == row['input'], 'paired candidate changed')
        field, step = check_observation(artifact, value, stage['exit_code'], environment)
        observed = signature(artifact, field, step, kind)
        require(same(row['retains_signature'], observed), 'paired signature changed')
        observations.append(observed)
        artifacts.append(artifact)
    position = 0
    def consume(value):
        nonlocal position
        require(position < len(observations) and data['trials'][position]['input'] == value,
                'paired search missing candidate/order changed')
        result = observations[position]
        position += 1
        return result
    require(consume(ORIGINALS[kind]), 'original negative absent')
    minimum = shortest(ORIGINALS[kind], consume)
    require(consume(minimum) and position == len(observations) and minimum == data['minimum'],
            'minimum/final repeat not established')
    source = common.linked(out, kind + '-replay.input.json', data['replay_input_sha256'])
    require(source.read_bytes() == (out / f'{kind}-{position-1:05d}.input.json').read_bytes(), 'copy replay bytes differ')
    replay_stage = stages[kind + '-replay']
    require(replay_stage['argv'] == command(out, source) == data['replay_argv'], 'copy replay command differs')
    replay = read(out / (kind + '-replay.stdout'))
    check_observation(replay, minimum, replay_stage['exit_code'], environment)
    require(same(replay, artifacts[-1]), 'copied-input replay changed actual traces')
    return {'trials': len(observations), 'minimum': minimum, 'minimum_total_words':
            len(minimum['ckb_program'])+len(minimum['sail_program']), 'copied_replay_exit': 1,
            'classification': data['classification'], 'scope': SCOPE}


def check(path, kind):
    path = Path(path)
    out, report = path.parent, read(path)
    require(same(report['schema_version'], 1) and report['status'] == 'paired_negatives_verified' and
            report['release_claimed'] is False and report['same_program_equivalence_claimed'] is False and
            report['clean_room_claimed'] is False and report['cargo_target_initially_absent'] is True,
            'paired report incomplete/overclaimed')
    env, compiler = runtime.environment()
    environment = runtime.observed_environment(env)
    require(report['inputs_before'] == report['inputs_after'] == inputs(compiler) and
            report['environment_before'] == report['environment_after'] == environment, 'paired source/tool drift')
    common.linked(out, 'paired-runner', report['runner_sha256'])
    libs = libraries((out / 'build-libraries.stdout').read_text(), out / 'cargo-target')
    require(libs == report['libraries'], 'linked library identity changed')
    require(set(report['cases']) == set(ORIGINALS), 'paired case inventory')
    names = ['verify-environment', 'build-libraries', 'build-paired-runner']
    for key in ORIGINALS:
        names += [f'{key}-{i:05d}' for i in range(len(report['cases'][key]['trials']))] + [key + '-replay']
    require([row['name'] for row in report['stages']] == names, 'paired stage inventory')
    stages = {row['name']: row for row in report['stages']}
    for name, argv in [('verify-environment', ['bash', 'scripts/verify_environment.sh']),
                       ('build-libraries', BUILD), ('build-paired-runner', compile_command(libs, out))]:
        require(stages[name]['argv'] == argv and same(stages[name]['exit_code'], 0), 'paired build/env failed')
    for name, stage in stages.items():
        require(set(stage['logs']) == {name + '.stdout', name + '.stderr'}, 'paired stage logs missing')
        for file, digest in stage['logs'].items(): common.linked(out, file, digest)
    summaries = {key: inspect_case(key, report['cases'][key], out, environment, stages) for key in ORIGINALS}
    require(same(summaries, report['summary']), 'paired summary differs')
    return summaries[kind]


def run(out, budget):
    report = {'schema_version': 1, 'status': 'running', 'started_at': runtime.now(), 'stages': [],
              'cases': {}, 'release_claimed': False, 'same_program_equivalence_claimed': False,
              'clean_room_claimed': False}
    def stage(name, argv, codes=(0,)):
        row = {'name': name, 'argv': list(map(str, argv)), 'started_at': runtime.now()}
        report['stages'].append(row)
        a, b = out / (name + '.stdout'), out / (name + '.stderr')
        try:
            with a.open('xb') as stdout, b.open('xb') as stderr:
                result = subprocess.run(row['argv'], cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=900)
            row['exit_code'] = result.returncode
            require(result.returncode in codes, 'paired process failed: ' + name)
        finally:
            row.update(finished_at=runtime.now(), logs={p.name: sha(p) for p in [a, b] if p.is_file()})
        return a, row['exit_code']
    try:
        env, compiler = runtime.environment()
        env['CARGO_TERM_COLOR'] = 'never'
        target = out / 'cargo-target'
        require(not target.exists() and budget >= 2, 'invalid budget/reused target')
        env['CARGO_TARGET_DIR'] = str(target)
        report.update(cargo_target_initially_absent=True, inputs_before=inputs(compiler),
                      environment_before=runtime.observed_environment(env))
        stage('verify-environment', ['bash', 'scripts/verify_environment.sh'])
        log, _ = stage('build-libraries', BUILD)
        report['libraries'] = libraries(log.read_text(), target)
        stage('build-paired-runner', compile_command(report['libraries'], out))
        report['runner_sha256'] = sha(out / 'paired-runner')
        for kind, original in ORIGINALS.items():
            data = {'original': original, 'test_name': TEST_NAMES[kind], 'trials': [],
                    'classification': 'intentional_distinct_input_negative', 'minimum_scope': SCOPE}
            report['cases'][kind] = data
            def observe(value):
                if len(data['trials']) >= budget: raise BudgetExhausted('paired search budget exhausted')
                name = f'{kind}-{len(data["trials"]):05d}'
                source = out / (name + '.input.json')
                source.write_text(json.dumps(value, indent=2) + '\n')
                row = {'input': value, 'input_sha256': sha(source)}
                data['trials'].append(row)
                artifact_path, code = stage(name, command(out, source), (0, 1))
                artifact = read(artifact_path)
                field, step = check_observation(artifact, value, code, report['environment_before'])
                row['retains_signature'] = signature(artifact, field, step, kind)
                return row['retains_signature']
            require(observe(original), 'original paired negative did not reproduce')
            minimum = shortest(original, observe)
            require(observe(minimum), 'final paired negative did not reproduce')
            data['minimum'] = minimum
            source = out / (kind + '-replay.input.json')
            import shutil
            shutil.copyfile(out / f'{kind}-{len(data["trials"])-1:05d}.input.json', source)
            data.update(replay_input_sha256=sha(source), replay_argv=command(out, source))
            stage(kind + '-replay', data['replay_argv'], (1,))
        stages = {row['name']: row for row in report['stages']}
        report['summary'] = {kind: inspect_case(kind, data, out, report['environment_before'], stages)
                             for kind, data in report['cases'].items()}
        report.update(inputs_after=inputs(compiler), environment_after=runtime.observed_environment(env))
        require(report['inputs_before'] == report['inputs_after'] and
                report['environment_before'] == report['environment_after'] and
                report['runner_sha256'] == sha(out / 'paired-runner'), 'paired inputs changed during run')
        report['status'] = 'paired_negatives_verified'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='incomplete' if isinstance(error, BudgetExhausted) else 'failed', error=str(error))
        code = 2 if isinstance(error, BudgetExhausted) else 1
    report['finished_at'] = runtime.now()
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--budget', type=int, default=256, help='maximum evaluations per case')
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='paired-negatives-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    return run(out, args.budget)


if __name__ == '__main__':
    sys.exit(main())
