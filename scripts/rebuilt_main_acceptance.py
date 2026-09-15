#!/usr/bin/env python3
"""Independent validation of the fixed main-tool candidate, not its adoption.

The original strict evidence checker is reused only after requiring its exact
old stage/test inventory; four new mandatory groups are added in memory. No
stage, axiom, theorem/type check, generation or public dependency check is cut.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/checkout'
PREPARATION = CANDIDATE.parent
REVIEW = ROOT / 'artifacts/boundary-check/rebuilt-main-candidate-review-u34780fb/report.json'
REVIEW_SHA = '7c2819ab1766ebb0580cedc5142d2aec3c6723c5e7ee7e3f35bf6abcb4d1df25'
POLICY_SHA = '697883be2675b6997910690011c5d30b45d07987a80006c7811da517ac9c5000'
OLD_POLICY_SHA = 'ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f'
SNAPSHOT_SHA = '71c87fea71324295bcce8e4a9e1c6433b6cc0d1e0134d5d99537855aa1911931'
OLD_TESTS = dict(zip([
    'test_lean_imports', 'test_lean_step', 'test_proof_check', 'test_ckb_source_baseline',
    'test_lean_clean', 'test_decoder_public_source', 'test_decoder_public_clean',
    'test_public_decoder_acceptance', 'test_public_decoder_gate', 'test_decoder_harness',
    'test_decoder_model_identity', 'test_decoder_iterator_identity', 'test_decoder_input_bundle',
    'test_decoder_input_locations', 'test_sail_model_transaction', 'test_decoder_rebuilt_inputs',
    'test_decoder_rebuilt_locations'], [19, 18, 18, 12, 6, 10, 7, 26, 14, 10, 9, 10, 21, 7, 21, 15, 13]))
EXTRA_TESTS = {'test_rebuilt_main_tools': 12, 'test_generate_rebuilt_rust': 10,
               'test_rebuilt_production_rust': 12, 'test_source_snapshot': 17}
PREFIX = ['sail-config', 'environment', 'generate-rust', 'generate-sail', 'kernel-step', 'theorem-audit']


def require(value, message):
    if not value: raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def stamp():
    return datetime.now(timezone.utc).isoformat()


def inventories(tests, stages):
    require(list(tests.items()) == list(OLD_TESTS.items()), 'old mandatory tests/counts changed')
    require(stages == [*PREFIX, *OLD_TESTS, 'public-decoder'], 'old mandatory stages changed')
    combined = {**tests, **EXTRA_TESTS}
    return combined, [*PREFIX, *combined, 'public-decoder']


def terminal_report(report):
    require(report['status'] == 'passed', 'candidate full proof-check is not complete and passed')
    require(report['policy_sha256'] == POLICY_SHA, 'candidate main policy identity differs')
    require([s['name'] for s in report['stages']] == [*PREFIX, *OLD_TESTS, *EXTRA_TESTS, 'public-decoder'],
            'candidate omitted or reordered mandatory stage')


def policy_delta(old, actual, binaries, versions, sources, profile):
    expected = copy.deepcopy(old)
    expected.update(main_toolchain=profile, tool_binaries=binaries, translator_versions=versions)
    expected['local_sources'].update(sources)
    require(actual == expected, 'candidate changes theorem/contracts/configuration or unreviewed fields')


def validate(checkout, report_path):
    # Called in this fresh CLI process, before importing any repository module.
    sys.path.insert(0, str(checkout / 'scripts'))
    import release_evidence as evidence
    import rebuilt_main_tools as tools
    import source_snapshot as snapshot
    require(evidence.ROOT == checkout, 'validator imported the wrong project')
    require(sha(REVIEW) == REVIEW_SHA and sha(PREPARATION / 'candidate-source-snapshot.json') == SNAPSHOT_SHA,
            'candidate preparation/review identity drift')
    review = read(REVIEW)
    require(review['status'] == 'rebuilt_main_candidate_ready_full_execution_pending' and
            review['candidate_policy_sha256'] == POLICY_SHA, 'candidate preparation was not independently accepted')
    state = read(PREPARATION / 'candidate-source-snapshot.json')
    require(snapshot.capture(checkout) == state, 'candidate source changed since reviewed preparation')
    # Validate every actually imported project module against the frozen source
    # snapshot, including evidence code not part of Lean's own source inventory.
    def imported_sources():
        result = {}
        for module in list(sys.modules.values()):
            if not getattr(module, '__file__', None): continue
            path = Path(module.__file__).resolve()
            if path.is_relative_to(checkout / 'scripts'):
                relative = str(path.relative_to(checkout))
                require(sha(path) == state['repositories']['.']['files'][relative]['sha256'], 'candidate evidence module drift')
                result[relative] = sha(path)
        return result
    imported = imported_sources()
    old_path = PREPARATION / 'source-payload/proof/lean/audit/step-policy.json'
    require(sha(old_path) == OLD_POLICY_SHA and sha(evidence.proof.POLICY) == POLICY_SHA,
            'policy reference drift')
    old, actual = read(old_path), read(evidence.proof.POLICY)
    changed_sources = {name: sha(checkout / name) for name in tools.SOURCES}
    changed_sources['scripts/tests/test_proof_check.py'] = sha(checkout / 'scripts/tests/test_proof_check.py')
    policy_delta(old, actual, tools.BINARIES, tools.VERSIONS, changed_sources, tools.PROFILE)
    tools.policy_identity(actual)
    result = read(report_path)
    terminal_report(result)
    original_counts, original_stages = evidence.TEST_COUNTS, evidence.LEAN_STAGES
    counts, stages = inventories(original_counts, original_stages)
    try:
        evidence.TEST_COUNTS, evidence.LEAN_STAGES = counts, stages
        details = evidence.check_lean(report_path)
    finally:
        evidence.TEST_COUNTS, evidence.LEAN_STAGES = original_counts, original_stages
    require(details['main_stages'] == 28 and details['tests'] == 287 and details['public_theorems'] == 68,
            'candidate completed inventory differs')
    require(snapshot.capture(checkout) == state, 'candidate source drift during independent acceptance')
    after_imports = imported_sources()
    require(all(after_imports.get(name) == digest for name, digest in imported.items()), 'candidate checker import drift')
    return {'details': details, 'candidate_evidence_sources': after_imports,
            'public_report': result['public_decoder']['report'],
            'public_report_sha256': result['public_decoder']['report_sha256'],
            'candidate_source_snapshot_sha256': state['snapshot_sha256']}


def main():
    require(len(sys.argv) == 1, 'usage: rebuilt_main_acceptance.py (fixed candidate only)')
    out = Path(tempfile.mkdtemp(prefix='rebuilt-main-acceptance-', dir=ROOT / 'artifacts/boundary-check'))
    report = {'status': 'running', 'started_at': stamp(), 'candidate': str(CANDIDATE),
              'fresh_kernel_run_claimed': False, 'formal_adoption_claimed': False,
              'clean_room_claimed': False, 'release_claimed': False, 'week6_closed': False}
    def save(): (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    try:
        source = CANDIDATE / 'artifacts/proof-check/report.json'
        observed_bytes = source.read_bytes()
        observed = json.loads(observed_bytes)
        report['observed_main_report'] = {'path': str(source),
            'sha256': hashlib.sha256(observed_bytes).hexdigest(), 'status': observed.get('status')}
        terminal_report(observed)  # A running/failed producer is never reusable as success.
        inputs = [Path(__file__).resolve(), ROOT / 'scripts/tests/test_rebuilt_main_acceptance.py',
                  ROOT / 'proof/lean/audit/step-policy.json', REVIEW,
                  PREPARATION / 'candidate-source-snapshot.json', source]
        report['inputs_before'] = {str(path): sha(path) for path in inputs}
        require(sha(ROOT / 'proof/lean/audit/step-policy.json') == OLD_POLICY_SHA, 'formal policy already changed')
        save()
        report.update(validate(CANDIDATE, source))
        report['inputs_after'] = {str(path): sha(path) for path in inputs}
        require(report['inputs_before'] == report['inputs_after'], 'independent checker/input drift')
        report['status'] = 'candidate_full_main_evidence_verified_formal_adoption_pending'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
