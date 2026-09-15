#!/usr/bin/env python3
"""Materialize the rebuilt UI failure-diagnostic qualification, still failed.

Reopens all UI streams/fixtures, replays the historical classification with the
fixed committed classifier, classifies 24 new paired failures, and binds rebuilt
tools. Historical classifier source identity is not assumed. No test is rerun,
no golden is changed, and no failure becomes PASS.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/experiments'))
import audit_charon_failure_diagnostics as diagnostics
from probes import probe_rebuilt_charon_ui as ui

require, sha, read = ui.require, ui.sha, ui.read
ORIGIN = ROOT / 'artifacts/boundary-check/rebuilt-charon-ui-jtet5h5k/report.json'
ORIGIN_SHA = '325e6f340bd365dcea0992309d38a6635b264a198ce70afd8999c9cd8b563e00'
CLASSIFIER_SHA = '774557fed888a31f730f497d97c449de04584397a8ad85db6010b42cab5e301f'
HISTORICAL = ROOT / 'artifacts/boundary-check/cleanup-diagnostics-68visubv/report.json'
HISTORICAL_SHA = 'ffd67769dec2b843a16a78a2518071e6c9863c7a3e71c418ea44a5a4e5b04fd3'
HISTORICAL_SCRIPT_SHA = 'c841d005c15cbf4a9f2af3a9947595c4c55b41d506a350ae01c4d0ab29684dc5'
PROJECT_COMMIT = '872d225dc4e16c449be37d92761b20c6aefe853c'
DRIVER_SHA = '4ea2d4194fa72657ac1284ce7b483a5b185ec56267d2b96c1d69ba325d4d6d1a'
COUNTS = {'identical': 12, 'line-order-only': 4, 'first-failed-target-and-line-order': 8}


def missing_crates(text):
    errors = re.findall(r'^error(?:\[[^\]\n]+\])?:.*$', text, re.M)
    require(errors, 'no rustc error diagnostic')
    crates = []
    for line in errors:
        match = re.fullmatch(r"error\[E0463\]: can't find crate for `(std|core)`", line)
        if match:
            crates.append(match[1])
        else:
            require(re.fullmatch(r'error: aborting due to \d+ previous errors?', line) is not None,
                    'additional compiler error: ' + line)
    require(crates, 'no missing std/core diagnostic')
    return dict(Counter(crates))


def replay_historical(archived, historical):
    """Compare every old case/log/category, not just aggregate counts."""
    actual = {}
    for name, row in archived['cases'].items():
        sides = row.get('results', {})
        if not any(r['status'] == 'command-failed' for r in sides.values()):
            continue
        require(set(sides) == {'baseline', 'candidate'} and all(r['status'] == 'command-failed'
                for r in sides.values()), 'unpaired historical failure')
        texts, hashes = {}, {}
        for side, record in sides.items():
            relative = Path('logs') / Path(name).relative_to('charon').with_suffix('') / side / 'stderr.log'
            path = ui.chain.evidence.linked(ui.OLD.parent, relative.as_posix(), record['stderr_sha256'])
            texts[side], hashes[side] = path.read_text(), sha(path)
        actual[name] = {'classification': diagnostics.classify(texts['baseline'], texts['candidate']),
                        'log_sha256': hashes}
    require(actual == historical['failed_cases'], 'historical per-case classification changed')
    counts = dict(Counter(r['classification'] for r in actual.values()))
    require(counts == historical['counts'] and len(actual) == 26, 'historical failure inventory changed')
    return {'counts': counts, 'case_count': len(actual), 'every_case_and_log_matched': True,
            'historical_classifier_source_identity_matched': False}


def run(out):
    report = {'status': 'running', 'started_at': ui.now(), 'tests_rerun': False,
              'full_upstream_suite_passed': False, 'tool_adopted': False, 'policy_changed': False,
              'goldens_updated': False, 'kernel_executed': False, 'clean_room_claimed': False,
              'release_claimed': False}
    try:
        require(sha(ORIGIN) == ORIGIN_SHA, 'rebuilt UI report drift')
        require(sha(Path(diagnostics.__file__)) == CLASSIFIER_SHA, 'committed diagnostic classifier drift')
        original = ui.chain.bundle.git(ROOT, 'show', PROJECT_COMMIT + ':scripts/experiments/audit_charon_failure_diagnostics.py')
        require(ui.chain.proof.digest(original) == CLASSIFIER_SHA, 'classifier differs from fixed project Git blob')
        require(sha(HISTORICAL) == HISTORICAL_SHA, 'historical diagnostic report drift')
        historical = read(HISTORICAL)
        require(historical['source_report_sha256'] == ui.OLD_SHA and
                historical['script_sha256'] == HISTORICAL_SCRIPT_SHA, 'historical provenance differs')
        origin = read(ORIGIN)
        require(origin['status'] == 'rebuilt_charon_ui_differential_completed_qualification_pending' and
                origin['inputs_before'] == origin['inputs_after'], 'incomplete rebuilt UI run')
        paths = {Path(__file__), Path(diagnostics.__file__), ORIGIN, ui.OLD, HISTORICAL, Path(ui.__file__),
                 ui.chain.proof.POLICY, ROOT / 'proof/lean/decoder/public-policy.json'}
        for name, digest in origin['inputs_after'].items():
            require(sha(ROOT / name) == digest, 'UI input drift: ' + name)
            paths.add(ROOT / name)
        for row in origin['stages']:
            require(type(row['exit_code']) is int and row['exit_code'] == 0, 'UI orchestration failed')
            ui.chain.evidence.linked(ORIGIN.parent, row['log'], row['log_sha256'])
        child = Path(origin['child_report'])
        require(sha(child) == origin['child_report_sha256'], 'UI child report drift')
        paths.add(child)
        require(sha(ui.OLD) == ui.OLD_SHA, 'original fixture report drift')
        report['inputs_before'] = {str(p): sha(p) for p in sorted(paths)}
        report['historical_replay'] = replay_historical(read(ui.OLD), historical)
        report['historical_classifier_sha256'] = HISTORICAL_SCRIPT_SHA
        source = Path(origin['test_source'])
        report['ui_summary'] = ui.inspect(child, source, read(ui.OLD))
        require(report['ui_summary'] == origin['summary'], 'UI result drift')
        components = ui.chain.verify_components()
        require(components == origin['components'], 'rebuilt UI component drift')
        driver = source / 'charon/src/bin/charon/main.rs'
        blob = ui.chain.bundle.git(source, 'show', ui.chain.charon.COMMIT + ':charon/src/bin/charon/main.rs')
        require(sha(driver) == ui.chain.proof.digest(blob) == DRIVER_SHA, 'multi-target driver differs from baseline')
        report.update(driver_source_sha256=DRIVER_SHA, driver_unchanged_from_baseline=True,
                      source_report_sha256=sha(child), rebuilt_ui_report_sha256=ORIGIN_SHA,
                      classifier_sha256=CLASSIFIER_SHA, failed_cases={})
        archived = read(child)
        for name, row in archived['cases'].items():
            sides = row.get('results', {})
            if not any(r['status'] == 'command-failed' for r in sides.values()):
                continue
            require(set(sides) == {'baseline', 'candidate'} and all(r['status'] == 'command-failed' and
                    type(r['exit_code']) is int and r['exit_code'] == 2 for r in sides.values()), 'unpaired failure')
            texts, hashes, missing = [], {}, {}
            for side, record in sides.items():
                relative = Path('logs') / Path(name).relative_to('charon').with_suffix('') / side / 'stderr.log'
                path = ui.chain.evidence.linked(child.parent, relative.as_posix(), record['stderr_sha256'])
                text = path.read_text(); texts.append((side, text)); hashes[side] = sha(path)
                missing[side] = missing_crates(text)
            selected = dict(texts)
            category = diagnostics.classify(selected['baseline'], selected['candidate'])
            require(category in COUNTS, 'unclassified paired failure: ' + name)
            report['failed_cases'][name] = {'classification': category, 'log_sha256': hashes,
                                           'rustc_missing_crates': missing, 'tests_still_failed': True}
        report['counts'] = dict(Counter(row['classification'] for row in report['failed_cases'].values()))
        require(report['counts'] == COUNTS and len(report['failed_cases']) == 24, 'failure classification inventory changed')
        require(ui.inspect(child, source, read(ui.OLD)) == report['ui_summary'], 'UI evidence changed during audit')
        require(ui.chain.verify_components() == components and sha(driver) == DRIVER_SHA, 'tool/source drift during audit')
        report['inputs_after'] = {str(p): sha(p) for p in sorted(paths)}
        require(report['inputs_before'] == report['inputs_after'], 'diagnostic audit input drift')
        report['status'] = 'rebuilt_diagnostics_classified_tests_still_failed_admission_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = ui.now()
    ui.chain.proof.write_json(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-charon-diagnostics-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
