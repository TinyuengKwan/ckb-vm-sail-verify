#!/usr/bin/env python3
"""Revalidate one completed candidate preparation after its JSON framing failed.

Does not rewrite the failed report, candidate sources/policy, or formal inputs.
Re-executes candidate tool resolution with a framed record and no premature
runtime configuration override; checks archived tests and source transformations.
"""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import prepare_rebuilt_main_candidate as preparation

tools, snapshot = preparation.tools, preparation.snapshot
require, sha, read = preparation.require, preparation.sha, preparation.read
BEFORE = ROOT / 'artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y'
FAILED_SHA = '10d5b747cc5a0facc7082888ccea9235445e685feeda3ccfedfe7f79de2a9742'
SNAPSHOT_SHA = '71c87fea71324295bcce8e4a9e1c6433b6cc0d1e0134d5d99537855aa1911931'


def run(out):
    report = {'status': 'running', 'started_at': preparation.extraction.now(), 'stages': [],
              'prior_report_changed': False, 'candidate_sources_changed': False,
              'formal_policy_changed': False, 'proof_check_executed': False,
              'main_tools_adopted': False, 'clean_room_claimed': False, 'release_claimed': False}
    try:
        require(sha(BEFORE / 'report.json') == FAILED_SHA and
                sha(BEFORE / 'candidate-source-snapshot.json') == SNAPSHOT_SHA, 'failed candidate evidence drift')
        previous = read(BEFORE / 'report.json')
        require(previous['status'] == 'failed' and previous['error_type'] == 'JSONDecodeError' and
                previous['error'] == 'Expecting value: line 1 column 1 (char 0)', 'unexpected preparation failure')
        require(len(previous['stages']) == 40 and previous['stages'][-1]['name'] == 'resolve-candidate-tools',
                'preparation did not complete every subprocess')
        for row in previous['stages']:
            require(type(row['exit_code']) is int and row['exit_code'] == 0 and
                    sha(BEFORE / row['log']) == row['log_sha256'], 'preparation subprocess/log failed')
        counts = {'test_proof_check': 18, 'test_rebuilt_main_tools': 12,
                  'test_generate_rebuilt_rust': 10, 'test_rebuilt_production_rust': 12, 'test_source_snapshot': 17}
        for name, count in counts.items():
            for suffix in ('', '-optimized'):
                log = (BEFORE / (name + suffix + '.log')).read_text()
                require(re.findall(r'(?m)^Ran (\d+) tests? in ', log) == [str(count)] and
                        re.search(r'(?m)^OK\s*\Z', log), 'candidate tests incomplete')
        state = read(BEFORE / 'source-snapshot.json')
        require(state['snapshot_sha256'] == previous['original_snapshot_sha256'], 'original snapshot link differs')
        for repo, info in state['repositories'].items():
            for name, expected in info['files'].items():
                require(sha(BEFORE / 'source-payload' / repo / name) == expected['sha256'], 'archived source changed')
        checkout = Path(previous['checkout'])
        expected_snapshot = read(BEFORE / 'candidate-source-snapshot.json')
        require(snapshot.capture(checkout) == expected_snapshot, 'candidate source snapshot differs')
        old = read(BEFORE / 'source-payload/proof/lean/audit/step-policy.json')
        require(sha(tools.proof.POLICY) == preparation.OLD_POLICY and
                sha(BEFORE / 'source-payload/proof/lean/audit/step-policy.json') == preparation.OLD_POLICY,
                'formal starting policy changed')
        require(tools.proof.generated_evidence(old) == read(preparation.PROOF)['generated'], 'formal generated outputs changed')
        for name, transform in [('scripts/check_proof.py', preparation.adapter),
                                ('scripts/tests/test_proof_check.py', preparation.test_adapter)]:
            require((checkout / name).read_text() == transform((BEFORE / 'source-payload' / name).read_text()),
                    'candidate adapter differs')
        actual = read(checkout / 'proof/lean/audit/step-policy.json')
        expected = copy.deepcopy(old)
        expected.update(main_toolchain=tools.PROFILE, tool_binaries=tools.BINARIES.copy(),
                        translator_versions=tools.VERSIONS.copy())
        expected['local_sources'].update({name: sha(checkout / name) for name in tools.SOURCES})
        expected['local_sources']['scripts/tests/test_proof_check.py'] = sha(checkout / 'scripts/tests/test_proof_check.py')
        require(actual == expected, 'candidate policy differs beyond exact tool/adapter changes')
        for repo in snapshot.REPOS: snapshot.independent(checkout / repo)
        require(not list(checkout.rglob('*.olean')) and not list(checkout.rglob('*.ilean')),
                'candidate contains old Lean compiled modules')
        require(all(not (checkout / name).exists() for name in ('target', 'proof/lean/generated',
                    'proof/rocq/generated', 'sail-model/build')), 'candidate already executed generation')
        inputs = {Path(__file__).resolve(), Path(preparation.__file__).resolve(), BEFORE / 'report.json',
                  BEFORE / 'candidate-source-snapshot.json', checkout / 'proof/lean/audit/step-policy.json', tools.proof.POLICY}
        inputs.update(ROOT / name for name in tools.SOURCES)
        report['inputs_before'] = {str(path): sha(path) for path in sorted(inputs)}
        env = {k: v for k, v in os.environ.items() if not k.startswith(('SAIL_', 'LEAN', 'ELAN', 'AENEAS', 'OCAML',
                    'OPAM', 'GIT_', 'CARGO', 'RUST', 'CHARON', 'MIRI', 'DUNE_')) and
                    k not in ('BASH_ENV', 'ENV', 'LD_PRELOAD', 'LD_LIBRARY_PATH')}
        env.update(PATH='/usr/bin:/bin', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
        command = ['python3', '-O', '-c', 'import sys,json;sys.path.insert(0,"scripts");import check_proof as p;'
            'q=json.loads(p.POLICY.read_text());e,b,h,l=p.tools_and_environment(q);s=p.source_evidence(q,b,h);'
            'keys=("PATH","ELAN_HOME","ELAN_TOOLCHAIN","AENEAS_HOME","AENEAS","CHARON",'
            '"SAIL_DIR","SAIL_PLUGIN_DIR","SAIL_BIN","RUSTUP_HOME","RUSTUP_TOOLCHAIN");'
            'print("REBUILT_MAIN_TOOLS_JSON="+json.dumps({"source":s,"lake":l,"environment":{k:e[k] for k in keys}}))']
        result = preparation.extraction.stage(report, out, 'resolve-candidate-tools', command, checkout, env)
        resolved = preparation.parse_tools_log(result)
        require(resolved['source']['local_sources'] == expected['local_sources'], 'resolved candidate source differs')
        require(snapshot.capture(checkout) == expected_snapshot and sha(BEFORE / 'report.json') == FAILED_SHA,
                'candidate or failed report changed during review')
        report['inputs_after'] = {str(path): sha(path) for path in sorted(inputs)}
        require(report['inputs_after'] == report['inputs_before'], 'review input drift')
        report.update(status='rebuilt_main_candidate_ready_full_execution_pending', checkout=str(checkout),
                      resolved_tools=resolved, candidate_policy_sha256=sha(checkout / 'proof/lean/audit/step-policy.json'),
                      candidate_source_snapshot_sha256=expected_snapshot['snapshot_sha256'],
                      previous_failure_sha256=FAILED_SHA, verified_preparation_stages=40,
                      tested_cases_per_mode=sum(counts.values()), planned_main_stages=28,
                      planned_tests=287, planned_public_stages=48)
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = preparation.extraction.now()
    preparation.extraction.write(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-main-candidate-review-', dir=ROOT / 'artifacts/boundary-check'))
    sys.exit(run(out))
