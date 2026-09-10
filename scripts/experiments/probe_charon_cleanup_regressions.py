"""Compare baseline/candidate UI outcomes without overwriting upstream goldens.

Runs the actual ui_test commands in separate copied test trees. Reports both
comparison to goldens and pairwise differences; shared failures are not PASS.
This is differential regression evidence, not proof of compiler correctness.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def normalize(text):
    text = re.sub(r'\x1b\[[0-9;]*m', '', text.replace('\r\n', '\n'))
    return re.sub(r"thread '(\w+)' \(\d+\) (panicked|has overflowed)", r"thread '\1' \2", text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', required=True, type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    exp = args.experiment.resolve()
    source = exp / 'charon-src'
    out = Path(tempfile.mkdtemp(prefix='cleanup-regression-', dir=ROOT / 'artifacts/boundary-check'))
    report = {'status': 'running', 'directory': str(out), 'cases': {},
              'compiler_adopted': False, 'full_upstream_suite_passed': False,
              'normalization': 'ANSI SGR, CRLF, panic thread numeric ID only'}
    tracked = subprocess.check_output(['git', 'ls-files', 'charon/tests'], cwd=source, text=True).splitlines()
    extras = ['charon/tests/ui/control-flow/guarded-field-alternatives.rs',
              'charon/tests/ui/control-flow/guarded-field-alternatives.out',
              'charon/tests/ui/control-flow/guarded-owned-error.rs']
    files = sorted(set(tracked + extras))
    before = {p: sha(source / p) for p in files}
    report['fixtures_before'] = before
    report['binaries'] = {side: {name: sha(exp / (side + '-bin') / name)
        for name in ['charon', 'charon-driver']} for side in ['baseline', 'candidate']}
    report['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    report['source_patch_sha256'] = hashlib.sha256(subprocess.check_output(
        ['git', 'diff', '--', 'charon/src'], cwd=source)).hexdigest()
    for side in ['baseline', 'candidate']:
        for p in files:
            dst = out / side / Path(p).relative_to('charon')
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / p, dst)
    env = dict(os.environ, RUSTUP_TOOLCHAIN='nightly-2026-08-18', IN_CI='1')
    for key in ['CHARON_LOG', 'RUST_LOG', 'CHARON_ARGS', 'RUSTFLAGS']:
        env.pop(key, None)
    report['rustc_version'] = subprocess.check_output(['rustc', '-vV'], env=env, text=True)

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def case(p):
        relative = Path(p).relative_to('charon')
        text = (source / p).read_text()
        comments = []
        for line in text.splitlines():
            if not line.startswith('//@'):
                break
            comments.append(line[3:].strip())
        row = {'new_fixture': p not in tracked}
        if 'ignore' in comments or 'skip' in comments:
            return p, dict(row, status='ignored')
        stream = 'stderr' if 'known-failure' in comments or 'known-panic' in comments else 'stdout'
        row.update(stream=stream, check_golden='no-check-output' not in comments, results={})
        outputs = {}
        for side in ['baseline', 'candidate']:
            command = [str(exp / (side + '-bin') / 'charon'), 'ui_test', str(relative)]
            start = time.monotonic()
            try:
                proc = subprocess.run(command, cwd=out / side, env=env,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            except subprocess.TimeoutExpired:
                row['results'][side] = {'status': 'timeout-not-proof-evidence'}
                continue
            logdir = out / 'logs' / relative.with_suffix('') / side
            logdir.mkdir(parents=True, exist_ok=True)
            for s in ['stdout', 'stderr']:
                (logdir / (s + '.log')).write_text(getattr(proc, s))
            actual = normalize(getattr(proc, stream))
            outputs[side] = actual
            expected = (source / p).with_suffix('.out')
            golden = normalize(expected.read_text()) if expected.exists() else None
            result = {'exit_code': proc.returncode, 'elapsed_seconds': time.monotonic() - start,
                'normalized_output_sha256': hashlib.sha256(actual.encode()).hexdigest(),
                'stdout_sha256': sha(logdir / 'stdout.log'), 'stderr_sha256': sha(logdir / 'stderr.log')}
            if proc.returncode:
                result['status'] = 'command-failed'
            elif not row['check_golden']:
                result['status'] = 'success-output-not-checked'
            elif golden is None:
                result['status'] = 'missing-golden'
            elif golden == actual:
                result['status'] = 'golden-pass'
            else:
                result['status'] = 'golden-mismatch'
            row['results'][side] = result
        if len(outputs) == 2:
            row['same_exit_code'] = row['results']['baseline']['exit_code'] == row['results']['candidate']['exit_code']
            row['same_selected_output'] = outputs['baseline'] == outputs['candidate']
            row['status'] = 'pair-identical' if row['same_exit_code'] and row['same_selected_output'] else 'pair-different'
            if not row['same_selected_output']:
                diff = ''.join(difflib.unified_diff(outputs['baseline'].splitlines(True),
                    outputs['candidate'].splitlines(True), fromfile='baseline', tofile='candidate'))
                (out / 'logs' / relative.with_suffix('') / 'pair.diff').write_text(diff)
        else:
            row['status'] = 'incomplete'
        return p, row

    try:
        save()
        cases = [p for p in files if p.startswith('charon/tests/ui/') and p.endswith('.rs')]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(case, p) for p in cases]
            for f in as_completed(futures):
                p, row = f.result()
                report['cases'][p] = row
                if len(report['cases']) % 25 == 0 or row['status'] == 'pair-different':
                    print(f"{len(report['cases'])}/{len(cases)} {p}: {row['status']}", flush=True)
                save()
        report['fixtures_after'] = {p: sha(source / p) for p in files}
        if report['fixtures_before'] != report['fixtures_after']:
            raise RuntimeError('original fixture/golden changed')
        report['counts'] = {status: sum(row['status'] == status for row in report['cases'].values())
            for status in ['ignored', 'pair-identical', 'pair-different', 'incomplete']}
        report['status'] = 'DIFFERENTIAL_AUDIT_FINISHED_NOT_ADOPTED'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        raise
    finally:
        save()
        print('Report: ' + str(out / 'report.json'), flush=True)


if __name__ == '__main__':
    main()
