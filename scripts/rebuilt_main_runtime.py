#!/usr/bin/env python3
"""Run existing native evidence producers against the fixed reviewed candidate.

No source adapters, formal adoption, kernel acceptance or clean-room claim.
The main report may still be running: only its completed generation prefix is
used, with immutable logs and bookended source/model/tool identities.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import rebuilt_main_acceptance as anchors

require, sha, read = anchors.require, anchors.sha, anchors.read
PREFIX = anchors.PREFIX[:4]
STABLE = '1.97.1-x86_64-unknown-linux-gnu'
MARKER = 'REBUILT_NATIVE_CHECK_JSON='


def ready(report, directory):
    require(report.get('status') in ('running', 'passed'), 'candidate main run failed or absent')
    require(report.get('policy_sha256') == anchors.POLICY_SHA, 'candidate main policy differs')
    stages = report.get('stages', [])[:4]
    require([s['name'] for s in stages] == PREFIX, 'generation prefix missing or reordered')
    for row in stages:
        require(row.get('status') == 'passed' and type(row.get('exit_code')) is int and
                row['exit_code'] == 0, 'generation is not complete: ' + row['name'])
        name = row['name'] + '.log'
        path = directory / name
        require(row.get('log') == name and not path.is_symlink() and path.is_file() and
                sha(path) == row.get('sha256'), 'generation log identity differs')
    return stages


def native_environment(env, installation, out):
    home = Path(installation['private_homes']['RUSTUP_HOME'])
    require(env.get('RUSTUP_HOME') == str(home), 'native Rust home differs from verified installation')
    prefix = home / 'toolchains' / STABLE / 'bin'
    binaries = {}
    for name in ('rustc', 'cargo', 'rustdoc'):
        path = prefix / name
        relative = str(path.relative_to(home))
        expected = installation['installed_closures']['rustup']['files'][relative]
        require(path.is_file() and not path.is_symlink() and os.access(path, os.X_OK) and
                sha(path) == expected['sha256'], 'native Rust binary differs: ' + name)
        binaries[name] = {'path': str(path), 'sha256': sha(path)}
    result = dict(env)
    result.update(PATH=str(prefix) + os.pathsep + env['PATH'], RUSTUP_TOOLCHAIN=STABLE,
                  CARGO_HOME=str(out / 'cargo-home'))
    result.pop('CARGO_TARGET_DIR', None)  # Each original producer allocates its own fresh target.
    return result, binaries


def parse_check(text):
    rows = [line[len(MARKER):] for line in text.splitlines() if line.startswith(MARKER)]
    require(len(rows) == 1, 'missing or duplicate independent native check')
    result = json.loads(rows[0])
    require(set(result) == {'runtime', 'rust_tests'}, 'independent native result inventory differs')
    require(result['runtime']['cases'] == 32 and result['runtime']['replays'] == 32 and
            result['runtime']['mutations']['applied'] == 188 and
            result['runtime']['mutations']['skipped'] == 4, 'native corpus inventory differs')
    tests = result['rust_tests']
    expected = {'test_binaries': 7, 'tests_passed': 78, 'engine_tests': 10,
                'doctest_targets': 5, 'doctests_passed': 0, 'ignored': 0, 'filtered_out': 0}
    require(all(type(tests.get(k)) is int and tests[k] == v for k, v in expected.items()),
            'native test inventory differs')
    return result


def main():
    require(len(sys.argv) == 1, 'usage: rebuilt_main_runtime.py (fixed candidate only)')
    root = anchors.CANDIDATE
    out = Path(tempfile.mkdtemp(prefix='rebuilt-main-runtime-', dir=anchors.ROOT / 'artifacts/boundary-check'))
    report = {'status': 'running', 'started_at': anchors.stamp(), 'candidate': str(root), 'stages': [],
              'formal_adoption_claimed': False, 'clean_room_claimed': False,
              'kernel_acceptance_claimed': False, 'release_claimed': False, 'week6_closed': False}
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def stage(name, argv):
        row = {'name': name, 'argv': argv, 'started_at': anchors.stamp()}
        report['stages'].append(row)
        save()
        print('==> rebuilt candidate native: ' + name, flush=True)
        logs = [out / (name + '.' + ext) for ext in ('stdout', 'stderr')]
        try:
            with logs[0].open('xb') as stdout, logs[1].open('xb') as stderr:
                result = subprocess.run(argv, cwd=root, env=env, stdout=stdout, stderr=stderr, timeout=2400)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'candidate native stage failed: ' + name)
        finally:
            row.update(finished_at=anchors.stamp(), logs={p.name: sha(p) for p in logs if p.is_file()})
            save()
        return logs[0]
    save()
    print(out, flush=True)
    try:
        main_path = root / 'artifacts/proof-check/report.json'
        observed = main_path.read_bytes()
        report['observed_main_report'] = {'path': str(main_path), 'sha256': hashlib.sha256(observed).hexdigest(),
                                          'status': json.loads(observed)['status']}
        report['completed_generation_prefix'] = ready(json.loads(observed), main_path.parent)
        inputs = [Path(__file__).resolve(), anchors.ROOT / 'scripts/tests/test_rebuilt_main_runtime.py',
                  Path(anchors.__file__).resolve(), anchors.REVIEW,
                  anchors.PREPARATION / 'candidate-source-snapshot.json',
                  anchors.ROOT / 'proof/lean/audit/step-policy.json', root / 'proof/lean/audit/step-policy.json']
        report['inputs_before'] = {str(p): sha(p) for p in inputs}
        require(sha(anchors.REVIEW) == anchors.REVIEW_SHA and sha(inputs[4]) == anchors.SNAPSHOT_SHA and
                sha(inputs[5]) == anchors.OLD_POLICY_SHA and sha(inputs[6]) == anchors.POLICY_SHA,
                'review/source/policy anchor drift')
        require(read(anchors.REVIEW)['status'] == 'rebuilt_main_candidate_ready_full_execution_pending',
                'candidate review not accepted')
        sys.path.insert(0, str(root / 'scripts'))
        import check_proof as proof
        import rebuilt_main_tools as tools
        import source_snapshot as snapshot
        require(proof.ROOT == root, 'wrong candidate module root')
        source = read(inputs[4])
        require(snapshot.capture(root) == source, 'reviewed candidate source drift')
        policy = read(proof.POLICY)
        env, _, _, _ = tools.resolve(root, policy)
        installation = read(tools.locations.RUST_REPORT)
        env, report['native_binaries'] = native_environment(env, installation, out)
        report['native_environment'] = {k: env[k] for k in ('PATH', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME')}
        report['source_snapshot_sha256'] = source['snapshot_sha256']
        report['generated_before'] = proof.generated_evidence(policy)
        save()
        stage('runtime', ['/usr/bin/python3', '-O', 'scripts/probes/probe_release_runtime.py', '--out', str(out / 'runtime')])
        stage('rust-tests', ['/usr/bin/python3', '-O', 'scripts/release_rust_tests.py', '--out', str(out / 'rust-tests')])
        children = [out / name / 'report.json' for name in ('runtime', 'rust-tests')]
        report['child_reports_before'] = {str(p): sha(p) for p in children}
        code = ('import json,sys; from pathlib import Path; sys.path.insert(0,"scripts"); '
                'import release_evidence as e; import release_rust_tests as r; '
                'print(' + repr(MARKER) + '+json.dumps({"runtime":e.check_runtime(Path(sys.argv[1])), '
                '"rust_tests":r.check(Path(sys.argv[2]))},sort_keys=True))')
        log = stage('independent-check', ['/usr/bin/python3', '-O', '-c', code, *map(str, children)])
        report['details'] = parse_check(log.read_text())
        report['child_reports_after'] = {str(p): sha(p) for p in children}
        require(report['child_reports_before'] == report['child_reports_after'], 'child evidence drift')
        # Rehash the full private installation closures, not just version output.
        checked_env, _, _, _ = tools.resolve(root, policy)
        _, binaries_after = native_environment(checked_env, read(tools.locations.RUST_REPORT), out)
        require(binaries_after == report['native_binaries'], 'native compiler drift')
        report['generated_after'] = proof.generated_evidence(policy)
        require(report['generated_before'] == report['generated_after'] and snapshot.capture(root) == source,
                'candidate model/source changed during native tests')
        require(ready(read(main_path), main_path.parent) == report['completed_generation_prefix'],
                'main generation prefix changed')
        report['inputs_after'] = {str(p): sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'], 'runner or anchor drift')
        report['status'] = 'candidate_native_runtime_and_rust_verified_formal_adoption_pending'
        result = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        result = 1
    report['finished_at'] = anchors.stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return result


if __name__ == '__main__':
    sys.exit(main())
