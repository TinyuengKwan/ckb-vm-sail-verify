#!/usr/bin/env python3
"""Build and execute every workspace test (including ignored engine tests).

Enumerates Cargo targets and each built test harness before execution. Existing
Sail/tools/caches are reused; this is not a whole-environment clean-room.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import release_evidence as common
from probes import probe_release_runtime as runtime

ROOT = common.ROOT
require, same, sha, read = common.require, common.same, common.sha, common.read
BUILD = ['cargo', 'test', '--workspace', '--locked', '--no-run', '--message-format=json']
METADATA = ['cargo', 'metadata', '--locked', '--no-deps', '--format-version=1']
DOC = ['cargo', 'test', '--workspace', '--locked', '--doc', '--', '--include-ignored', '--test-threads=1']
LIST_DOC = ['cargo', 'test', '--workspace', '--locked', '--doc', '--', '--list']
ENGINE_TESTS = {
    'every_corpus_case_agrees_step_by_step', 'a_diverging_instruction_stream_is_located',
    'a_missing_final_event_is_detected', 'the_packet_fixture_still_matches_the_live_emulator',
    'a_compressed_instruction_is_normalized_on_both_sides',
    'a_trapping_instruction_diverges_and_is_reported_not_hidden',
    'a_failing_engine_is_an_error_rather_than_a_pass',
    'every_mandatory_mutation_is_detected_and_located_on_real_traces',
    'a_mutation_matrix_over_no_cases_does_not_pass', 'concurrent_sessions_survive_the_port_race'}


def listings(text):
    groups, names = [], []
    for line in text.splitlines():
        if not line.strip(): continue
        if line.endswith(': test'):
            name = line[:-6]
            require(name and name not in names, 'duplicate listed test')
            names.append(name)
        else:
            match = re.fullmatch(r'(\d+) tests?, 0 benchmarks', line)
            require(match and int(match[1]) == len(names), 'invalid/incomplete test listing')
            groups.append(names)
            names = []
    require(not names, 'unterminated test listing')
    return groups


def results(text, expected):
    groups, names, count = [], [], None
    for line in text.splitlines():
        if not line.strip(): continue
        start = re.fullmatch(r'running (\d+) tests?', line)
        passed = re.fullmatch(r'test (.+) \.\.\. ok', line)
        finish = re.fullmatch(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored; 0 measured; '
                              r'0 filtered out; finished in [0-9.]+s', line)
        if start:
            require(count is None, 'nested/incomplete test result')
            count = int(start[1])
        elif passed:
            require(count is not None and passed[1] not in names, 'duplicate/outside test result')
            names.append(passed[1])
        elif finish:
            require(count is not None and count == int(finish[1]) == len(names), 'test total disagrees')
            groups.append(names)
            count, names = None, []
        else:
            raise RuntimeError('unexpected test output (failure/ignored/filter): ' + line[:160])
    require(count is None and len(groups) == len(expected) and
            all(sorted(a) == sorted(b) for a, b in zip(groups, expected)), 'missing/extra test execution')
    return sum(map(len, groups))


def catalogue(metadata, build_text, target):
    require(metadata['workspace_root'] == str(ROOT), 'wrong workspace')
    packages = {p['id']: p for p in metadata['packages'] if p['id'] in metadata['workspace_members']}
    require(set(packages) == set(metadata['workspace_members']) and packages, 'workspace members incomplete')
    expected = {}
    docs = []
    for package in packages.values():
        require(Path(package['manifest_path']).is_relative_to(ROOT / 'crates'), 'non-workspace test package')
        for item in package['targets']:
            key = (package['id'], item['name'], tuple(item['kind']))
            if item['test']:
                require(item['kind'] in [['lib'], ['bin'], ['test']], 'unhandled test target kind')
                expected[key] = package['name'] + '/' + item['name'] + '/' + item['kind'][0]
            if item['doctest']:
                require(item['kind'] == ['lib'], 'unhandled doctest target')
                docs.append(item['name'])
    found, finished = {}, []
    for line in build_text.splitlines():
        row = json.loads(line)
        if row['reason'] == 'build-finished': finished.append(row['success'])
        if row['reason'] != 'compiler-artifact' or not row['profile']['test'] or row['executable'] is None:
            continue
        key = (row['package_id'], row['target']['name'], tuple(row['target']['kind']))
        require(key in expected and key not in found, 'unexpected/duplicate built test executable')
        path = Path(row['executable'])
        require(path.is_absolute() and path.is_relative_to(target), 'test binary outside new Cargo target')
        common.member(target, str(path.relative_to(target)))
        found[key] = {'id': expected[key], 'binary': str(path), 'sha256': sha(path)}
    require(finished == [True] and set(found) == set(expected) and found, 'missing test binary/build failure')
    return sorted(found.values(), key=lambda row: row['id']), sorted(docs)


def inputs(compiler):
    files = runtime.inputs(compiler)
    for name in ['scripts/release_rust_tests.py', 'scripts/tests/test_release_rust_tests.py',
                 'scripts/release_evidence.py']:
        files[str(ROOT / name)] = sha(ROOT / name)
    return files


def inspect(out, report, *, check_stages=True):
    """Recompute test completeness from metadata, listings, execution logs and binaries."""
    out = Path(out)
    binaries, docs = catalogue(read(out / 'metadata.stdout'), (out / 'build-tests.stdout').read_text(), out / 'cargo-target')
    require(binaries == report['binaries'] and docs == report['doctest_targets'], 'test catalogue changed')
    stages = [('verify-environment', ['bash', 'scripts/verify_environment.sh']), ('metadata', METADATA), ('build-tests', BUILD)]
    count = 0
    all_names = set()
    for i, row in enumerate(binaries):
        base = f'harness-{i:03d}'
        stages += [(base + '-list', [row['binary'], '--list']),
                   (base + '-run', [row['binary'], '--include-ignored', '--test-threads=1'])]
        groups = listings((out / (base + '-list.stdout')).read_text())
        require(len(groups) == 1, 'harness listing missing')
        count += results((out / (base + '-run.stdout')).read_text(), groups)
        all_names.update(groups[0])
        if row['id'] == 'ckb-vm-sail-diff/dii_end_to_end/test':
            require(set(groups[0]) == ENGINE_TESTS, 'engine negative-test inventory changed')
    require(ENGINE_TESTS <= all_names, 'mandatory real-engine tests not executed')
    stages += [('doc-list', LIST_DOC), ('doc-run', DOC)]
    for name in ['doc-list', 'doc-run']:
        actual = re.findall(r'(?m)^\s*Doc-tests\s+(\S+)\s*$', (out / (name + '.stderr')).read_text())
        require(sorted(actual) == docs, 'doctest targets missing/duplicated')
    groups = listings((out / 'doc-list.stdout').read_text())
    require(len(groups) == len(docs), 'doctest listings missing')
    doc_count = results((out / 'doc-run.stdout').read_text(), groups)
    if check_stages:
        require([r['name'] for r in report['stages']] == [name for name, _ in stages], 'test stage inventory')
        for row, (name, argv) in zip(report['stages'], stages):
            require(same(row['exit_code'], 0) and row['argv'] == argv, 'test exit/command changed')
            require(set(row['logs']) == {name + '.stdout', name + '.stderr'}, 'test log inventory')
            for file, digest in row['logs'].items(): common.linked(out, file, digest)
    return {'test_binaries': len(binaries), 'tests_passed': count, 'engine_tests': len(ENGINE_TESTS),
            'doctest_targets': len(docs), 'doctests_passed': doc_count, 'ignored': 0, 'filtered_out': 0}


def check(path):
    path = Path(path)
    report = read(path)
    require(same(report['schema_version'], 1) and report['status'] == 'local_rust_tests_passed' and
            report['release_claimed'] is False and report['clean_room_claimed'] is False and
            report['cargo_target_initially_absent'] is True, 'Rust test report incomplete/assurance changed')
    env, compiler = runtime.environment()
    require(report['environment_before'] == report['environment_after'] == runtime.observed_environment(env),
            'Rust test environment changed')
    require(report['inputs_before'] == report['inputs_after'] == inputs(compiler), 'Rust test sources/tools changed')
    summary = inspect(path.parent, report)
    require(same(summary, report['summary']), 'Rust test summary differs')
    return {'scope': 'existing_all_default_workspace_tests_including_ignored', **summary,
            'fresh_execution_claimed': False}


def run(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': runtime.now(),
              'release_claimed': False, 'clean_room_claimed': False, 'stages': []}
    def stage(name, argv):
        row = {'name': name, 'argv': list(map(str, argv)), 'started_at': runtime.now()}
        report['stages'].append(row)
        stdout, stderr = out / (name + '.stdout'), out / (name + '.stderr')
        try:
            with stdout.open('xb') as a, stderr.open('xb') as b:
                result = subprocess.run(row['argv'], cwd=ROOT, env=env, stdout=a, stderr=b, timeout=900)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'Rust test stage failed: ' + name)
        finally:
            row.update(finished_at=runtime.now(), logs={p.name: sha(p) for p in [stdout, stderr] if p.is_file()})
        return stdout
    try:
        env, compiler = runtime.environment()
        for name in ['RUST_TEST_THREADS', 'RUST_TEST_NOCAPTURE', 'RUST_TEST_TIME_UNIT', 'RUST_TEST_TIME_INTEGRATION',
                     'RUST_TEST_TIME_DOCTEST', 'RUST_TEST_SHUFFLE', 'RUST_TEST_SHUFFLE_SEED']:
            env.pop(name, None)
        env['CARGO_TERM_COLOR'] = 'never'
        target = out / 'cargo-target'
        require(not target.exists(), 'Cargo target must be new')
        env['CARGO_TARGET_DIR'] = str(target)
        report.update(cargo_target_initially_absent=True, inputs_before=inputs(compiler),
                      environment_before=runtime.observed_environment(env))
        stage('verify-environment', ['bash', 'scripts/verify_environment.sh'])
        metadata = read(stage('metadata', METADATA))
        build = stage('build-tests', BUILD).read_text()
        binaries, docs = catalogue(metadata, build, target)
        report.update(binaries=binaries, doctest_targets=docs)
        for i, row in enumerate(binaries):
            stage(f'harness-{i:03d}-list', [row['binary'], '--list'])
            stage(f'harness-{i:03d}-run', [row['binary'], '--include-ignored', '--test-threads=1'])
        stage('doc-list', LIST_DOC)
        stage('doc-run', DOC)
        report['summary'] = inspect(out, report)
        report.update(inputs_after=inputs(compiler), environment_after=runtime.observed_environment(env))
        require(report['inputs_before'] == report['inputs_after'] and
                report['environment_before'] == report['environment_after'], 'Rust test inputs changed')
        report['status'] = 'local_rust_tests_passed'
        return 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        return 1
    finally:
        report['finished_at'] = runtime.now()
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        parent = ROOT / 'artifacts/boundary-check'
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='release-rust-tests-', dir=parent))
    print(out, flush=True)
    return run(out)


if __name__ == '__main__':
    sys.exit(main())
