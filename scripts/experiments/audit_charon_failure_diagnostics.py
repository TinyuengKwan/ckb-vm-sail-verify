"""Classify archived failed UI diagnostics; never turn a failed test into PASS."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from probe_charon_cleanup_regressions import normalize

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = re.compile(r'translation for target ([a-z0-9_-]+) failed with status exit status: 2')


def classify(left, right):
    left, right = normalize(left), normalize(right)
    if left == right:
        return 'identical'
    a, b = Counter(left.splitlines()), Counter(right.splitlines())
    if a == b:
        return 'line-order-only'
    summaries = []
    for text, counts in [(left, a), (right, b)]:
        rows = [(line, SUMMARY.fullmatch(line)) for line in text.splitlines()]
        rows = [(line, match.group(1)) for line, match in rows if match]
        if len(rows) != 1:
            return 'unclassified'
        line, target = rows[0]
        # Only explain a summary naming a target whose actual missing-std
        # diagnostic is also present. Other errors/statuses are not normalized.
        if "error[E0463]: can't find crate for `std`" not in text or (
                '= note: the `' + target + '` target may not be installed') not in text:
            return 'unclassified'
        counts.subtract([line])
        summaries.append(target)
    if a == b and summaries[0] != summaries[1]:
        return 'first-failed-target-and-line-order'
    return 'unclassified'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    source_report = args.report.resolve()
    if sha(source_report) != 'a6d337c88c81de996d077215f65c9fca4cc6f618217dbdc6986572716463945c':
        raise RuntimeError('unreviewed differential report')
    archived = json.loads(source_report.read_text())
    source = ROOT / 'artifacts/boundary-check/charon-cfg-OYcaoK/charon-src'
    relative = 'charon/src/bin/charon/main.rs'
    main_hash = sha(source / relative)
    if main_hash != '4ea2d4194fa72657ac1284ce7b483a5b185ec56267d2b96c1d69ba325d4d6d1a':
        raise RuntimeError('multi-target driver source changed')
    original = subprocess.check_output(['git', 'show',
        '89ac118194b978d8cf753222c19f313521377aa0:' + relative], cwd=source)
    if hashlib.sha256(original).hexdigest() != main_hash:
        raise RuntimeError('multi-target driver differs from baseline')
    result = {'source_report_sha256': sha(source_report), 'driver_source_sha256': main_hash,
              'driver_unchanged_from_baseline': True, 'failed_cases': {},
              'full_upstream_suite_passed': False, 'tool_adopted': False,
              'script_sha256': sha(Path(__file__))}
    for name, row in archived['cases'].items():
        if row.get('results', {}).get('candidate', {}).get('status') != 'command-failed':
            continue
        texts = []
        hashes = {}
        for side in ['baseline', 'candidate']:
            record = row['results'][side]
            if record['status'] != 'command-failed' or record['exit_code'] != row['results']['candidate']['exit_code']:
                raise RuntimeError('not a shared failure: ' + name)
            log = source_report.parent / 'logs' / Path(name).relative_to('charon').with_suffix('') / side / 'stderr.log'
            if sha(log) != record['stderr_sha256']:
                raise RuntimeError('archived diagnostic changed: ' + str(log))
            texts.append(log.read_text())
            hashes[side] = sha(log)
        result['failed_cases'][name] = {'classification': classify(*texts), 'log_sha256': hashes}
    result['counts'] = dict(Counter(row['classification'] for row in result['failed_cases'].values()))
    if result['counts'] != {'identical': 9, 'line-order-only': 10, 'first-failed-target-and-line-order': 7}:
        raise RuntimeError('failed diagnostic classification changed: ' + str(result['counts']))
    result['status'] = 'DIAGNOSTICS_CLASSIFIED_TESTS_STILL_FAILED'
    out = Path(tempfile.mkdtemp(prefix='cleanup-diagnostics-', dir=ROOT / 'artifacts/boundary-check'))
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['counts'], sort_keys=True))
    print('Report: ' + str(out / 'report.json'))


if __name__ == '__main__':
    main()
