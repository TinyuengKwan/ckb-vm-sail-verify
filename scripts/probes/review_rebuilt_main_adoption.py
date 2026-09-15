#!/usr/bin/env python3
"""Read-only review of the fixed accepted candidate before formal cutover.

Revalidates both main evidence chains, the prospective exact source inventory,
and actual local CMake/OPAM selection. Records integration gaps; adopts nothing.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rebuilt_main_acceptance as candidate
import rebuilt_main_tools as tools
import audit_release as release
import source_snapshot as snapshot

require, sha, read = candidate.require, candidate.sha, candidate.read
ACCEPTANCE = ROOT / 'artifacts/boundary-check/rebuilt-main-acceptance-b7f_p_zm/report.json'
ACCEPTANCE_SHA = 'd478e39edbf43b6c540d58565c0d923fe445fbcec407211f6662e4cdc902e51d'
FORMAL = ROOT / 'artifacts/boundary-check/approved-rebuilt-proof-YQTKZPMC/report.json'
FORMAL_SHA = '4385aea4114c1aedc07d7db392d641d46089ed12842ded83bcd4e0b2396ac4a6'
V8 = ROOT / 'artifacts/release-audit/run-na0_m08b/report.json'
V8_SHA = '506b0859dc0653b56de601a4086dd9db349de20d1fd50169af8a60d07ff40ca7'
CORE_CHANGES = ['scripts/check_proof.py', 'scripts/tests/test_proof_check.py', 'proof/lean/audit/step-policy.json']


def prospective_sources(old, actual, installed, replacements, extra_names):
    require(actual == old, 'current formal source inventory drift')
    require(set(replacements) == set(CORE_CHANGES[:2]), 'unexpected core source replacement')
    expected = {**actual, **{name: installed[name] for name in extra_names}, **replacements}
    require(expected == installed, 'candidate requires unreviewed additional formal source changes')
    return expected


def old_cmake_rejection(resolve):
    try:
        resolve()
    except RuntimeError as error:
        require(str(error) == 'Sail CMake compiler differs', 'unexpected rebuilt preflight failure: ' + str(error))
        return str(error)
    raise RuntimeError('expected old CMake selection is no longer current; review anew')


def main():
    require(len(sys.argv) == 1, 'usage: review_rebuilt_main_adoption.py (fixed transition only)')
    out = Path(tempfile.mkdtemp(prefix='rebuilt-main-adoption-review-', dir=ROOT / 'artifacts/boundary-check'))
    report = {'status': 'running', 'started_at': candidate.stamp(), 'stages': [],
              'formal_policy_changed': False, 'formal_sources_changed': False, 'formal_outputs_changed': False,
              'kernel_reexecution_claimed': False, 'main_tools_adopted': False,
              'clean_room_claimed': False, 'release_claimed': False, 'week6_closed': False}
    def save(): (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def stage(name, command, cwd=ROOT):
        row = {'name': name, 'argv': list(map(str, command)), 'cwd': str(cwd), 'started_at': candidate.stamp()}
        report['stages'].append(row)
        save()
        log = out / (name + '.log')
        print('==> formal adoption review: ' + name, flush=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('OPAM', 'OCAML', 'CAML'))}
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'adoption review stage failed: ' + name)
        finally:
            row.update(finished_at=candidate.stamp(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text()
    save()
    print(out, flush=True)
    try:
        inputs = [Path(__file__), ROOT / 'scripts/tests/test_rebuilt_main_adoption.py', ACCEPTANCE, FORMAL, V8,
                  candidate.REVIEW, candidate.PREPARATION / 'candidate-source-snapshot.json',
                  ROOT / 'deps/sail-riscv/build/CMakeCache.txt', ROOT / 'artifacts/proof-check/report.json']
        report['inputs_before'] = {str(p): sha(p) for p in inputs}
        require(sha(ACCEPTANCE) == ACCEPTANCE_SHA and sha(FORMAL) == FORMAL_SHA and sha(V8) == V8_SHA,
                'accepted evidence anchor drift')
        require(sha(ROOT / 'artifacts/proof-check/report.json') == FORMAL_SHA and
                sha(tools.proof.POLICY) == candidate.OLD_POLICY_SHA, 'formal starting state drift')
        accepted = read(ACCEPTANCE)
        require(accepted['status'] == 'candidate_full_main_evidence_verified_formal_adoption_pending' and
                accepted['inputs_before'] == accepted['inputs_after'] and
                all(sha(Path(p)) == h for p, h in accepted['inputs_after'].items()), 'candidate acceptance input drift')
        before = snapshot.capture(ROOT)
        report['formal_source_snapshot_before'] = before['snapshot_sha256']
        v8 = read(V8)
        require(release.snapshot() == v8['inputs_before'] == v8['inputs_after'], 'v8 scoped input snapshot drift')
        old, new = read(tools.proof.POLICY), read(candidate.CANDIDATE / 'proof/lean/audit/step-policy.json')
        changes = {}
        for name in CORE_CHANGES:
            source, target = ROOT / name, candidate.CANDIDATE / name
            require(source.read_bytes() == (candidate.PREPARATION / 'source-payload' / name).read_bytes(),
                    'formal core no longer matches reviewed starting bytes: ' + name)
            changes[name] = {'before': sha(source), 'candidate': sha(target)}
        report['core_source_delta'] = changes
        for name, digest in new['local_sources'].items():
            require(sha(candidate.CANDIDATE / name) == digest, 'candidate local source drift')
            if name not in CORE_CHANGES:
                require(sha(ROOT / name) == digest, 'shared formal/candidate code drift: ' + name)
        replacements = {name: changes[name]['candidate'] for name in CORE_CHANGES[:2]}
        report['prospective_local_sources'] = prospective_sources(old['local_sources'], tools.proof.local_sources(),
                                                                 new['local_sources'], replacements, tools.SOURCES)
        candidate.policy_delta(old, new, tools.BINARIES, tools.VERSIONS,
            {**{name: sha(candidate.CANDIDATE / name) for name in tools.SOURCES},
             CORE_CHANGES[1]: changes[CORE_CHANGES[1]]['candidate']}, tools.PROFILE)
        # Separate processes are essential: each validator imports its own ROOT.
        code = ('import sys,json; from pathlib import Path; sys.path.insert(0,"scripts"); '
                'import release_evidence as e; print("FORMAL_CHECK_JSON="+json.dumps(e.check_lean(Path(sys.argv[1]))))')
        stage('revalidate-formal-v8-main', ['/usr/bin/python3', '-O', '-c', code, str(FORMAL)])
        code = ('import sys,json; sys.path.insert(0,"scripts"); import rebuilt_main_acceptance as a; '
                'print("CANDIDATE_CHECK_JSON="+json.dumps(a.validate(a.CANDIDATE,a.CANDIDATE/"artifacts/proof-check/report.json")))')
        stage('revalidate-complete-candidate', ['/usr/bin/python3', '-O', '-c', code])
        counts, stages = candidate.inventories(release.evidence.TEST_COUNTS, release.evidence.LEAN_STAGES)
        report['release_inventory_gap'] = {'current_stages': len(release.evidence.LEAN_STAGES),
            'current_tests': sum(release.evidence.TEST_COUNTS.values()), 'required_stages': len(stages),
            'required_tests': sum(counts.values()), 'new_mandatory_groups': candidate.EXTRA_TESTS}
        report['actual_rebuilt_root_preflight_rejection'] = old_cmake_rejection(lambda: tools.resolve(ROOT, new))
        opam = read(tools.locations.OPAM_REPORT)
        opam_root, switch = opam['opam_root'], opam['switch']
        packages = stage('query-aeneas-opam-packages', [opam['bootstrap']['path'], 'list', '--root=' + opam_root,
            '--switch=' + switch, '--installed', '--short', '--columns=name,version'])
        packages = dict(line.split() for line in packages.splitlines() if line.strip())
        switches = stage('query-aeneas-opam-switches', [opam['bootstrap']['path'], 'switch', 'list',
            '--root=' + opam_root, '--short']).splitlines()
        require('rocq-core' not in packages and 'rocq-spike' not in switches, 'expected separate Rocq installation changed')
        report['rocq_context_gap'] = {'aeneas_opam_root': opam_root, 'aeneas_switch': switch,
            'installed_switches': switches, 'rocq_core_installed_in_aeneas_switch': False,
            'formal_rocq_driver_sha256': sha(ROOT / 'scripts/rocq_spike.py'),
            'explicit_rocq_context_and_primitives_binding_required': True}
        report['required_cutover_work'] = [
            'integrate mandatory 28-stage/287-test release validation without dropping old checks',
            'integrate explicit private Rocq/Aeneas contexts and source-bound Primitives.v into formal entry/validation',
            'review final code and policy hashes, including updated helper documentation and tests',
            'retain old formal policy/code/evidence/model/build inputs; configure and cold-build new Sail explicitly',
            'apply reviewed main entry/test/policy delta and rerun full formal generation/proof/native/Rocq evidence',
            'refresh dependent mismatch/demo/readiness evidence for the final identity without relabelling v8 or candidate PASS',
        ]
        require(snapshot.capture(ROOT) == before and release.snapshot() == v8['inputs_after'], 'formal sources drift during review')
        report['formal_source_snapshot_after'] = before['snapshot_sha256']
        report['inputs_after'] = {str(p): sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'], 'review input/output drift')
        report['status'] = 'accepted_candidate_revalidated_formal_integration_gaps_confirmed'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = candidate.stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
