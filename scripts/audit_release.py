#!/usr/bin/env python3
"""Week6 evidence aggregation v8 with a fail-closed all-slot success path.

Revalidates local components plus strict clean-room, CI-download, release-package and signed
third-party schemas. Missing reports and unapproved policy fields remain fail-closed. Recorded
build/replay commands are never executed; provenance and SSH signature checks are read-only.
Source and historical generation review components leave their full slot incomplete unless
v4 carries explicit profile-A approval and its formal execution join closes. Exit 1 means
invalid evidence/input; exit 2 means incomplete acceptance; exit 0 is reachable only when
all twelve slots are verified. The aggregator does not publish, refresh policy or rerun proofs.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import release_evidence as evidence
import release_rust_tests as rust_tests
import release_mismatch_evidence as mismatches
import release_demo as demo
import release_worktree_source as worktree_source
import release_worktree_evidence as worktree_evidence
import release_public_claims as public_claims
import release_external_evidence as external

ROOT = evidence.ROOT
CHECKERS = {'runtime': evidence.check_runtime, 'lean': evidence.check_lean, 'rocq': evidence.check_rocq,
            'rust_tests': rust_tests.check, 'mismatches': mismatches.check_inventory,
            'maintainer_demo': demo.check, 'public_claims': public_claims.check}
EXTERNAL_CHECKERS = {
    'clean_room': external.check_clean_room,
    'ci_download': external.check_ci_download,
    'release_package': external.check_release_package,
    'third_party': external.check_third_party,
}
# These components validate useful evidence but do not discharge the whole slot.
PARTIAL_CHECKERS = {'worktree_audit': worktree_evidence.check}
PENDING = {
    'clean_room': 'fresh recursive checkout, pinned tool installation and complete regeneration/execution chain',
    'worktree_audit': 'candidate identity and all generated/source differences explicitly audited',
    'ci_download': 'full CI execution plus actual uploaded/downloaded artifact replay',
    'release_package': 'versioned package, hashes, coverage, non-goals and actual publication/download records',
    'third_party': 'independent performer reproduces from documentation with original records',
    'public_claims': 'coverage, semantic gaps, TCB and every public assurance claim traced to evidence',
}
SLOTS = [*CHECKERS, *EXTERNAL_CHECKERS,
         *(name for name in PENDING if name not in CHECKERS and name not in EXTERNAL_CHECKERS)]
PINS = {'main_policy': 'proof/lean/audit/step-policy.json',
        'public_policy': 'proof/lean/decoder/public-rebuilt-policy.json',
        'raw_policy': 'proof/lean/decoder/raw-rebuilt-policy.json',
        'input_admission': 'proof/lean/decoder/rebuilt-input-policy.json',
        'input_catalogue': 'proof/lean/decoder/rebuilt-input-catalogue.json',
        'week5_plan': 'docs/plan/week5.md', 'week6_plan': 'docs/plan/week6.md',
        'overview_plan': 'docs/plan/overview.md'}
CHECKER_FILES = ['scripts/audit_release.py', 'scripts/release_evidence.py',
                 'scripts/tests/test_audit_release.py', 'scripts/release.mk',
                 'scripts/release_runtime_evidence.py', 'scripts/probes/probe_release_runtime.py',
                 'scripts/rocq_spike.py', 'scripts/ckb_source_baseline.py']
CHECKER_FILES += ['scripts/release_rust_tests.py', 'scripts/tests/test_release_rust_tests.py',
                  'scripts/release_mismatch_evidence.py', 'scripts/tests/test_release_mismatch_evidence.py',
                  'scripts/minimize_mismatch.py', 'scripts/tests/test_minimize_mismatch.py']
CHECKER_FILES += ['scripts/paired_negative_evidence.py', 'scripts/fixtures/paired_runner.rs',
                  'scripts/tests/test_paired_negative_evidence.py']
CHECKER_FILES += ['scripts/decoder_rebuilt_inputs.py', 'scripts/decoder_rebuilt_locations.py',
                  'scripts/tests/test_decoder_rebuilt_inputs.py', 'scripts/tests/test_decoder_rebuilt_locations.py']
CHECKER_FILES += ['scripts/release_demo.py', 'scripts/tests/test_release_demo.py']
CHECKER_FILES += ['scripts/rocq_context.py', 'scripts/tests/test_rocq_context.py', 'scripts/tests/test_rocq_spike.py']
CHECKER_FILES += ['scripts/release_worktree_source.py', 'scripts/tests/test_release_worktree_source.py',
                  'scripts/source_snapshot.py']
CHECKER_FILES += ['scripts/release_generation_review.py', 'scripts/release_worktree_evidence.py',
                  'scripts/tests/test_release_generation_review.py', 'scripts/tests/test_release_worktree_evidence.py',
                  'scripts/record_generation.py', 'scripts/generated_output_inventory.py']
CHECKER_FILES += ['scripts/release_formal_generation_review.py',
                  'scripts/tests/test_release_formal_generation_review.py']
CHECKER_FILES += ['scripts/release_source_increment_review.py',
                  'scripts/tests/test_release_source_increment_review.py']
CHECKER_FILES += ['scripts/release_current_output_review.py',
                  'scripts/tests/test_release_current_output_review.py']
CHECKER_FILES += ['scripts/release_public_claims.py',
                  'scripts/tests/test_release_public_claims.py']
CHECKER_FILES += ['scripts/release_external_evidence.py',
                  'scripts/tests/test_release_external_evidence.py',
                  'scripts/week6_ci_archive.py', 'scripts/tests/test_week6_ci_archive.py',
                  'scripts/week6_release_ci_gate.py', 'scripts/tests/test_week6_release_ci_gate.py',
                  'scripts/week6_collect_ci.py', 'scripts/tests/test_week6_collect_ci.py',
                  'scripts/week6_release_package.py', 'scripts/tests/test_week6_release_package.py',
                  'scripts/week6_review_materialize.py', 'scripts/tests/test_week6_review_materialize.py',
                  'scripts/week6_formal_record.py', 'scripts/tests/test_week6_formal_record.py',
                  'scripts/week6_formal_review.py', 'scripts/tests/test_week6_formal_review_logic.py',
                  'scripts/tests/test_week6_formal_review.py',
                  'scripts/week6_output_projection.py', 'scripts/tests/test_week6_output_projection.py',
                  'scripts/week6_output_observe.py', 'scripts/tests/test_week6_output_observe.py',
                  'scripts/week6_output_review.py', 'scripts/tests/test_week6_output_review.py',
                  'scripts/week6_output_confirm.py', 'scripts/tests/test_week6_output_confirm.py',
                  'scripts/week6_native_record.py', 'scripts/tests/test_week6_native_record.py',
                  'scripts/week6_clean_room.py', 'scripts/tests/test_week6_clean_room.py',
                  'scripts/week6_ephemeral_vm.py', 'scripts/tests/test_week6_ephemeral_vm.py',
                  'scripts/week6_vm_evidence_bundle.py', 'scripts/tests/test_week6_vm_evidence_bundle.py',
                  'docs/release/week6-review-policy-v1.json',
                  'docs/release/external-acceptance-policy-v1.json',
                  'docs/release/release-allowed-signers',
                  'docs/release/third-party-allowed-signers']


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def snapshot():
    return {'files': {name: evidence.sha(ROOT / name) for name in [*PINS.values(), *CHECKER_FILES]},
            'formal_sources': evidence.proof.local_sources(),
            'public_sources': evidence.public_gate.sources(),
            'ckb_source_baseline': evidence.proof.ckb_source_baseline.check(ROOT)}


def reference(row):
    evidence.require(type(row) is dict and set(row) == {'path', 'sha256'}, 'invalid evidence reference')
    return evidence.linked(ROOT, row['path'], row['sha256'])


def validate_manifest(manifest):
    evidence.require(type(manifest) is dict and set(manifest) ==
                     {'schema_version', 'candidate', 'pins', 'evidence'}, 'unknown/missing manifest fields')
    evidence.require(evidence.same(manifest['schema_version'], 1), 'unknown manifest schema')
    evidence.require(isinstance(manifest['candidate'], str) and manifest['candidate'].strip(), 'candidate absent')
    evidence.require(type(manifest['pins']) is dict and set(manifest['pins']) == set(PINS), 'pin inventory')
    for key, path in PINS.items():
        evidence.require(manifest['pins'][key] == evidence.sha(ROOT / path), 'stale pin: ' + key)
    evidence.require(type(manifest['evidence']) is dict and set(manifest['evidence']) == set(SLOTS),
                     'mandatory evidence slots cannot be omitted or renamed')


def aggregate(manifest):
    validate_manifest(manifest)
    checks = {}
    for name in SLOTS:
        row = manifest['evidence'][name]
        if row is None:
            checks[name] = {'status': 'missing', 'reason': PENDING.get(name, 'required report absent')}
            continue
        try:
            path = reference(row)
            if name in CHECKERS:
                if name == 'mismatches':
                    inventory = evidence.read(path)
                    for dependency in ['runtime', 'rust_tests']:
                        evidence.require(inventory[dependency] == manifest['evidence'][dependency],
                                         'mismatch inventory linked to a different ' + dependency + ' report')
                elif name == 'maintainer_demo':
                    recorded = evidence.read(path)
                    plan = evidence.read(evidence.linked(path.parent, 'plan.json', recorded['plan_sha256']))
                    evidence.require(plan['runtime'] == manifest['evidence']['runtime'],
                                     'demo linked to a different runtime report')
                    inventory = evidence.read(reference(manifest['evidence']['mismatches']))
                    evidence.require(plan['trap'] == inventory['semantic_negative_cases'][mismatches.CASES[-1]],
                                     'demo linked to a different trap report')
                result = (CHECKERS[name](path, candidate=manifest['candidate'])
                          if name == 'public_claims' else CHECKERS[name](path))
                # Check the top-level report again after nested evidence is read.
                evidence.require(evidence.sha(path) == row['sha256'], 'report changed during validation')
                checks[name] = {'status': 'verified_existing_evidence', 'reference': row, 'details': result}
            elif name in EXTERNAL_CHECKERS:
                if name == 'ci_download':
                    recorded = evidence.read(path)
                    evidence.require(recorded['clean_room'] == manifest['evidence']['clean_room'],
                                     'CI report linked to a different clean-room report')
                if name == 'third_party':
                    recorded = evidence.read(path)
                    evidence.require(recorded['release_package'] == manifest['evidence']['release_package'],
                                     'third-party report linked to a different release package report')
                result = EXTERNAL_CHECKERS[name](path, manifest['candidate'], root=ROOT)
                if name == 'clean_room' and result.get('provider') == external.VM_PROVIDER:
                    # An independent ephemeral VM report is self-described; the slot stays
                    # incomplete until the host launcher's operator-attested record binds it.
                    try:
                        result['host_provenance'] = external.check_vm_provenance(path)
                    except external.VmProvenanceAbsent as absent:
                        evidence.require(evidence.sha(path) == row['sha256'], 'report changed during validation')
                        checks[name] = {'status': 'incomplete', 'reference': row, 'details': result,
                                        'reason': str(absent)}
                        continue
                evidence.require(evidence.sha(path) == row['sha256'], 'report changed during validation')
                checks[name] = {'status': 'verified_existing_evidence', 'reference': row, 'details': result}
            elif name in PARTIAL_CHECKERS:
                result = PARTIAL_CHECKERS[name](path, manifest['candidate'], root=ROOT)
                evidence.require(evidence.sha(path) == row['sha256'], 'report changed during validation')
                checks[name] = {'status': 'incomplete', 'reference': row, 'details': result,
                    'reason': 'Partial worktree records checked; see remaining source/output/delivery obligations.'}
            else:
                checks[name] = {'status': 'unimplemented', 'reference': row,
                    'reason': 'No acceptance validator yet; a hash or PASS statement is insufficient. ' + PENDING[name]}
        except mismatches.IncompleteEvidence as error:
            evidence.require(evidence.sha(path) == row['sha256'], 'inventory changed during validation')
            checks[name] = {'status': 'incomplete', 'reason': str(error), 'details': error.details, 'reference': row}
        except Exception as error:
            checks[name] = {'status': 'invalid', 'reason': str(error), 'error_type': type(error).__name__}
    worktree = checks.get('worktree_audit', {})
    if worktree.get('status') == 'incomplete' and 'details' in worktree:
        try:
            worktree['details'] = worktree_evidence.connect_formal_execution(worktree['details'], checks, root=ROOT)
            # Do not let a report changed after partial validation acquire a
            # linkage conclusion. Only v4's separately validated explicit approval
            # plus an empty connected obligation list promotes the slot.
            reference(worktree['reference'])
            if worktree['details'].get('worktree_audit_closed') is True:
                evidence.require(worktree['details']['remaining'] == [] and
                                 worktree['details'].get('delivery_approval_verified') is True,
                                 'closed worktree still has obligations or lacks approval')
                worktree['status'] = 'verified_existing_evidence'
                worktree.pop('reason', None)
        except Exception as error:
            checks['worktree_audit'] = {'status': 'invalid', 'reason': str(error), 'error_type': type(error).__name__}
    invalid = [name for name, row in checks.items() if row['status'] == 'invalid']
    outstanding = [name for name, row in checks.items() if row['status'] != 'verified_existing_evidence']
    if invalid:
        status, code, closed = 'invalid', 1, False
    elif outstanding:
        status, code, closed = 'incomplete', 2, False
    else:
        clean_room = checks['clean_room'].get('details', {})
        ci_download = checks['ci_download'].get('details', {})
        release_package = checks['release_package'].get('details', {})
        third_party = checks['third_party'].get('details', {})
        public_claims = checks['public_claims'].get('details', {})
        worktree = checks['worktree_audit'].get('details', {})
        worktree_components = worktree.get('components', {})
        approved_profile = worktree_components.get('approval', {}).get('delivery_profile')
        source_snapshots = [clean_room.get('source_snapshot_sha256'),
                            ci_download.get('source_snapshot_sha256'),
                            release_package.get('source_snapshot_sha256'),
                            third_party.get('source_snapshot_sha256'),
                            public_claims.get('source_snapshot_sha256'),
                            worktree_components.get('source', {}).get('source_snapshot_sha256')]
        evidence.require(clean_room.get('clean_room_verified') is True and
                         clean_room.get('fresh_execution_claimed') is True and
                         (clean_room.get('provider') != external.VM_PROVIDER or
                          clean_room.get('host_provenance', {}).get('operator_attested') is True) and
                         ci_download.get('ci_download_verified') is True and
                         ci_download.get('remote_state_queried') is True and
                         release_package.get('release_package_built') is True and
                         release_package.get('publication_verified') is True and
                         release_package.get('download_verified') is True and
                         release_package.get('remote_state_queried') is True and
                         release_package.get('delivery_profile') == approved_profile == 'A' and
                         third_party.get('third_party_reproduced') is True and
                         third_party.get('independent_third_party') is True and
                         public_claims.get('public_claims_slot_closed') is True and
                         worktree.get('delivery_approval_verified') is True and
                         worktree.get('candidate_identity_approved') is True and
                         worktree.get('current_outputs_verified') is True and
                         worktree.get('generated_outputs_audited') is True and
                         worktree.get('worktree_audit_closed') is True and
                         worktree.get('remaining') == [] and
                         None not in source_snapshots and len(set(source_snapshots)) == 1,
                         'all-slot inventory lacks a required Week6 completion fact')
        status, code, closed = 'passed', 0, True
    return {'status': status, 'candidate': manifest['candidate'], 'checks': checks,
            'outstanding': outstanding, 'release_claimed': closed, 'week6_closed': closed,
            'fresh_execution_claimed': closed}, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--out', type=Path, help='new report directory only')
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        parent = ROOT / 'artifacts/release-audit'
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'schema_version': 1, 'started_at': stamp(), 'status': 'running',
              'release_claimed': False, 'week6_closed': False, 'fresh_execution_claimed': False}
    code = 1
    try:
        report['manifest_sha256'] = evidence.sha(args.manifest)
        report['inputs_before'] = snapshot()
        report['project_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                         text=True, timeout=30).strip()
        report['project_worktree_status'] = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=ROOT, text=True, timeout=30).strip()
        result, code = aggregate(evidence.read(args.manifest))
        report.update(result)
        report['inputs_after'] = snapshot()
        evidence.require(report['inputs_before'] == report['inputs_after'] and
                         report['manifest_sha256'] == evidence.sha(args.manifest), 'audit inputs changed')
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='invalid', error=str(error), error_type=type(error).__name__)
        code = 1
    finally:
        report['finished_at'] = stamp()
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'),
                      'release_claimed': report['release_claimed'],
                      'outstanding': report.get('outstanding', [])}))
    return code


if __name__ == '__main__':
    sys.exit(main())
