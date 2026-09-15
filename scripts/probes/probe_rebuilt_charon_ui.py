#!/usr/bin/env python3
"""Rerun the declared Charon UI differential with rebuilt tools and private Rust.

Reuse the original UI driver and exact fixtures/goldens. Record failures, not a
whole-suite PASS. New full-MIR is supplied only for its native target; other
targets may remain unavailable. No upstream source/golden or policy is edited.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_rebuilt_extraction_chain as chain
from probes.probe_release_runtime import now
from experiments import probe_charon_cleanup_regressions as driver

require, sha, read = chain.require, chain.sha, chain.read
OLD = ROOT / 'artifacts/boundary-check/cleanup-regression-g6y486ux/report.json'
OLD_SHA = 'a6d337c88c81de996d077215f65c9fca4cc6f618217dbdc6986572716463945c'
FIXTURES = ROOT / 'artifacts/boundary-check/charon-cfg-OYcaoK/charon-src'
EXTRAS = ['charon/tests/ui/control-flow/guarded-field-alternatives.rs',
          'charon/tests/ui/control-flow/guarded-field-alternatives.out',
          'charon/tests/ui/control-flow/guarded-owned-error.rs']


def environment(out, components):
    env = chain.environment(out, components)
    env.update(CHARON_CACHE_DIR=str(out / 'charon-cache'),
               CHARON_MIRI_SYSROOTS=components['sysroot'],
               CARGO_NET_OFFLINE='true', IN_CI='1')
    return env


def inspect_case(name, row, out, source, tracked):
    """Recompute classification from both complete streams and unchanged goldens."""
    path = source / name
    comments = []
    for line in path.read_text().splitlines():
        if not line.startswith('//@'):
            break
        comments.append(line[3:].strip())
    new = name not in tracked
    if 'ignore' in comments or 'skip' in comments:
        require(row == {'new_fixture': new, 'status': 'ignored'}, 'unexpected ignored-case record')
        return row
    stream = 'stderr' if 'known-failure' in comments or 'known-panic' in comments else 'stdout'
    check = 'no-check-output' not in comments
    require(row['new_fixture'] is new and row['stream'] == stream and row['check_golden'] is check,
            'fixture directives changed')
    require(set(row['results']) == {'baseline', 'candidate'}, 'missing UI side')
    outputs, codes = {}, {}
    for side in ('baseline', 'candidate'):
        result = row['results'][side]
        require(type(result.get('exit_code')) is int, 'UI execution missing or timed out')
        codes[side] = result['exit_code']
        texts = {}
        for channel in ('stdout', 'stderr'):
            relative = Path('logs') / Path(name).relative_to('charon').with_suffix('') / side / (channel + '.log')
            path = chain.evidence.linked(out, relative.as_posix(), result[channel + '_sha256'])
            texts[channel] = path.read_text()
        outputs[side] = driver.normalize(texts[stream])
        require(chain.proof.digest(outputs[side].encode()) == result['normalized_output_sha256'], 'selected UI output drift')
        golden = (source / name).with_suffix('.out')
        status = 'command-failed' if codes[side] else 'success-output-not-checked' if not check else 'missing-golden' if not golden.exists() else 'golden-pass' if driver.normalize(golden.read_text()) == outputs[side] else 'golden-mismatch'
        require(result['status'] == status, 'UI failure/golden result misclassified')
    same_code, same_output = codes['baseline'] == codes['candidate'], outputs['baseline'] == outputs['candidate']
    require(row['same_exit_code'] is same_code and row['same_selected_output'] is same_output and
            row['status'] == ('pair-identical' if same_code and same_output else 'pair-different'), 'pair comparison drift')
    return row


def inspect(report_path, source, old):
    report = read(report_path)
    require(report['status'] == 'DIFFERENTIAL_AUDIT_FINISHED_NOT_ADOPTED' and
            report['compiler_adopted'] is False and report['full_upstream_suite_passed'] is False,
            'UI driver overclaimed/incomplete')
    require(report['fixtures_before'] == report['fixtures_after'] == old['fixtures_before'], 'UI fixture inventory differs')
    tracked = set(chain.bundle.git(source, 'ls-files', 'charon/tests').decode().splitlines())
    cases = {name for name in old['fixtures_before'] if name.startswith('charon/tests/ui/') and name.endswith('.rs')}
    require(set(report['cases']) == cases and len(cases) == 435, 'UI case inventory incomplete')
    for name, digest in old['fixtures_before'].items():
        require(sha(source / name) == digest, 'source fixture/golden changed')
        for side in ('baseline', 'candidate'):
            chain.evidence.linked(report_path.parent / side, Path(name).relative_to('charon').as_posix(), digest)
    for name, row in report['cases'].items():
        inspect_case(name, row, report_path.parent, source, tracked)
    counts = Counter(row['status'] for row in report['cases'].values())
    require(report['counts'] == {status: counts[status] for status in ['ignored', 'pair-identical', 'pair-different', 'incomplete']}, 'UI count drift')
    return {'pair_counts': report['counts'],
            'sides': {side: dict(Counter(row['results'][side]['status'] for row in report['cases'].values() if row['status'] != 'ignored'))
                      for side in ('baseline', 'candidate')},
            'changed_exit_cases': sorted(name for name, row in report['cases'].items()
                                         if row['status'] != 'ignored' and not row['same_exit_code']),
            'pair_different_cases': sorted(name for name, row in report['cases'].items() if row['status'] == 'pair-different'),
            'full_upstream_suite_passed': False}


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'new_tools_approved': False, 'full_upstream_suite_passed': False, 'goldens_updated': False,
              'kernel_executed': False, 'clean_room_claimed': False, 'release_claimed': False,
              'policy_changed': False, 'os_sandboxed': False}
    env = None

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv, cwd=out, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> rebuilt-charon-ui: ' + name, flush=True)
        path = out / (name + '.log')
        try:
            with path.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'UI orchestration failed: ' + name)
        finally:
            row.update(log=path.name, log_sha256=sha(path), finished_at=now())
            save()
        return path.read_text()

    try:
        require(sha(OLD) == OLD_SHA, 'original UI fixture evidence drift')
        old = read(OLD)
        require(old['fixtures_before'] == old['fixtures_after'], 'old fixtures changed')
        components = chain.verify_components()
        report['components'] = components
        env = environment(out, components)
        paths = [Path(__file__), Path(driver.__file__), Path(chain.__file__), OLD,
                 ROOT / 'scripts/tests/test_rebuilt_charon_ui.py', chain.proof.POLICY]
        report['inputs_before'] = {str(p.relative_to(ROOT)): sha(p) for p in paths}
        report['environment'] = {key: env[key] for key in ('PATH', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN',
            'CARGO_HOME', 'CARGO_TARGET_DIR', 'CARGO_NET_OFFLINE', 'CHARON_CACHE_DIR', 'CHARON_MIRI_SYSROOTS')}
        experiment = out / 'experiment'
        experiment.mkdir()
        source = experiment / 'charon-src'
        stage('clone-test-source', ['git', 'clone', '--no-checkout', chain.PUBLIC / 'sources/charon.bundle', source])
        stage('checkout-test-source', ['git', 'checkout', '--detach', chain.charon.COMMIT], source)
        stage('apply-reviewed-patch', ['git', 'apply', chain.PUBLIC / 'patches/charon.patch'], source)
        chain.snapshot.independent(source)
        patch_sha = chain.bundle.verify_payload(chain.PUBLIC)['files']['patches/charon.patch']['sha256']
        chain.charon.check_source(source, True, patch_sha)
        for name in EXTRAS:
            src = chain.snapshot.regular(FIXTURES, name)
            require(sha(src) == old['fixtures_before'][name] and not (source / name).exists(), 'extra fixture drift/existing target')
            shutil.copyfile(src, source / name)
        report['test_source'] = str(source)
        for name, digest in old['fixtures_before'].items():
            require(sha(source / name) == digest, 'restored fixture differs: ' + name)
        for side, tool_side in [('baseline', 'base'), ('candidate', 'public')]:
            folder = experiment / (side + '-bin')
            folder.mkdir()
            for name in ('charon', 'charon-driver'):
                tool = components['tools'][tool_side][name]
                shutil.copy2(tool['path'], folder / name)
                chain.executable(folder / name, tool['sha256'])
        output = stage('ui-differential', [sys.executable, driver.__file__, '--experiment', experiment, '--jobs', '4'], timeout=7200)
        rows = re.findall(r'^Report: (.+)$', output, re.M)
        require(len(rows) == 1, 'ambiguous UI child report')
        child = Path(rows[0])
        require(child.is_absolute() and child.parent.parent == ROOT / 'artifacts/boundary-check' and
                child.parent.name.startswith('cleanup-regression-') and child.name == 'report.json', 'unexpected UI child path')
        report.update(child_report=str(child), child_report_sha256=sha(child))
        result = read(child)
        require(result['source_commit'] == chain.charon.COMMIT and result['source_patch_sha256'] == patch_sha,
                'UI source identity differs')
        expected = {side: {name: components['tools'][tool_side][name]['sha256'] for name in ('charon', 'charon-driver')}
                    for side, tool_side in [('baseline', 'base'), ('candidate', 'public')]}
        require(result['binaries'] == expected, 'UI did not use rebuilt tools')
        for side in expected:
            for name, digest in expected[side].items():
                chain.executable(experiment / (side + '-bin') / name, digest)
        report['summary'] = inspect(child, source, old)
        report['historical_pair_counts'] = old['counts']
        require(chain.verify_components() == components, 'rebuilt inputs changed during UI run')
        report['inputs_after'] = {str(p.relative_to(ROOT)): sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'UI probe/policy drift')
        report['status'] = 'rebuilt_charon_ui_differential_completed_qualification_pending'
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='rebuilt-charon-ui-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
