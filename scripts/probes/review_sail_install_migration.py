#!/usr/bin/env python3
"""Archive/review the exact stale-file and transactional-install policy delta.

Never edits policy, approves new translators, or claims a completed proof run.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_proof as gate
import source_snapshot as snapshot
from probes import probe_sail_candidate_model as candidate

OLD_POLICY = 'c8315684cf73d118703f98982e79303943d8c52d49e72d99117de25301b3a1af'
PUBLIC_POLICY = 'e2643499ef13d20ed1797dca4d2e6192851fdad0b0e6e53ffc41247ce85fd0b4'
KERNEL_REPORT = ROOT / 'artifacts/boundary-check/sail-stale-cleanup-w3osvf64/report.json'
KERNEL_SHA = '90f6557852fb9f68b771307f014f0763f1a528d4d35d71e167bae477fd0fd9c2'
OLD_PROOF_SHA = '66fb26d92860e6dde6198d1657a9aaf85b3d18f2c608033cb0340d69628a0dab'
CHANGED = {'scripts/generate_proof_model.sh', 'scripts/configure_lean_project.sh',
           'scripts/check_proof.py', 'scripts/tests/test_proof_check.py'}
ADDED = {'scripts/sail_model_transaction.py', 'scripts/tests/test_sail_model_transaction.py'}


def kernel_evidence():
    gate.require_equal(gate.file_hash(KERNEL_REPORT), KERNEL_SHA, 'cleanup kernel report')
    report = json.loads(KERNEL_REPORT.read_text())
    gate.require_equal(report['status'], 'isolated_stale_file_removal_main_kernel_and_boundary_match', 'kernel status')
    for stage in report['stages']:
        gate.require_equal(stage['exit_code'], 0, 'kernel stage ' + stage['name'])
        gate.require_equal(gate.file_hash(KERNEL_REPORT.parent / stage['log']), stage['log_sha256'], 'kernel log')
    snapshot.require(report['initial_compiled_modules'] == 0 and
                     'LeanRV64D.Specialization' not in report['imported_modules'] and
                     'LeanRV64D.SpecializationV1' in report['imported_modules'], 'cleanup module boundary')
    return report


def prepare():
    gate.require_equal(gate.file_hash(gate.POLICY), OLD_POLICY, 'migration starting policy')
    gate.require_equal(gate.file_hash(ROOT / 'proof/lean/decoder/public-policy.json'), PUBLIC_POLICY, 'public policy')
    policy = json.loads(gate.POLICY.read_text())
    gate.require_equal(gate.local_sources(), policy['local_sources'], 'old source identities')
    generated = gate.generated_evidence(policy)
    kernel = kernel_evidence()
    gate.check_audit(kernel['theorem_audit'], policy)
    candidate.policy_difference(generated['models']['sail'], kernel['clean_sail_sources'])
    old_proof = gate.ARTIFACTS / 'report.json'
    gate.require_equal(gate.file_hash(old_proof), OLD_PROOF_SHA, 'previous proof report')
    out = Path(tempfile.mkdtemp(prefix='sail-install-migration-', dir=ROOT / 'artifacts/boundary-check'))
    state = snapshot.capture(ROOT)
    snapshot.export(ROOT, state, out / 'source')
    gate.write_json(out / 'source-snapshot.json', state)
    gate.write_json(out / 'generated-before.json', generated)
    logs = out / 'previous-proof-check'
    logs.mkdir()
    # The main checker overwrites these top-level files; preserve all of them.
    # Unique child build/report directories remain in their original locations.
    for file in gate.ARTIFACTS.iterdir():
        if file.is_file() and file.name != '.lock':
            snapshot.require(not file.is_symlink(), 'linked previous report/log')
            shutil.copyfile(file, logs / file.name)
    record = {'status': 'archived_before_migration', 'old_policy_sha256': OLD_POLICY,
              'previous_proof_sha256': OLD_PROOF_SHA, 'kernel_report_sha256': KERNEL_SHA,
              'source_snapshot_sha256': state['snapshot_sha256'],
              'generated_before_sha256': gate.file_hash(out / 'generated-before.json'),
              'archived_proof_files': gate.tree_files(logs), 'policy_changed': False}
    gate.write_json(out / 'archive.json', record)
    print(out)
    return out


def audit(before):
    before = Path(before).resolve()
    old_file = before / 'source/proof/lean/audit/step-policy.json'
    gate.require_equal(gate.file_hash(old_file), OLD_POLICY, 'archived policy')
    old = json.loads(old_file.read_text())
    new = json.loads(gate.POLICY.read_text())
    gate.require_equal({k: v for k, v in new.items() if k not in ('local_sources', 'generated_sha256')},
                       {k: v for k, v in old.items() if k not in ('local_sources', 'generated_sha256')},
                       'theorem/contracts/tools/dependencies/boundaries unchanged')
    for name, digest in old['local_sources'].items():
        gate.require_equal(gate.file_hash(before / 'source' / name), digest, 'archived source ' + name)
    gate.require_equal(set(new['local_sources']) - set(old['local_sources']), ADDED, 'added source pins')
    gate.require_equal(set(old['local_sources']) - set(new['local_sources']), set(), 'removed source pins')
    changed = {name for name in old['local_sources'] if old['local_sources'][name] != new['local_sources'][name]}
    gate.require_equal(changed, CHANGED, 'changed source pins')
    gate.require_equal(gate.local_sources(), new['local_sources'], 'current source pins')
    kernel = kernel_evidence()
    gate.check_audit(kernel['theorem_audit'], new)
    generated = json.loads((before / 'generated-before.json').read_text())
    archive = json.loads((before / 'archive.json').read_text())
    gate.require_equal(gate.file_hash(before / 'generated-before.json'), archive['generated_before_sha256'], 'old generated inventory')
    old_sail = generated['models']['sail']
    fresh = kernel['clean_sail_sources']
    gate.require_equal(gate.digest(gate.canonical(old_sail)), old['generated_sha256']['sail'], 'old generated identity')
    difference = candidate.policy_difference(old_sail, fresh)
    expected = {**old['generated_sha256'], 'sail': gate.digest(gate.canonical(fresh))}
    gate.require_equal(new['generated_sha256'], expected, 'exact single-file generated identity migration')
    for name in ['docs/plan/week5.md', 'docs/plan/week6.md', 'docs/plan/overview.md']:
        gate.require_equal(gate.file_hash(ROOT / name), gate.file_hash(before / 'source' / name), 'plan unchanged')
    gate.require_equal(gate.file_hash(ROOT / 'proof/lean/decoder/public-policy.json'), PUBLIC_POLICY, 'public policy unchanged')
    gate.require_equal(gate.file_hash(before / 'previous-proof-check/report.json'), OLD_PROOF_SHA, 'previous proof preserved')
    gate.require_equal(gate.tree_files(before / 'previous-proof-check'), archive['archived_proof_files'], 'previous logs preserved')
    actual = gate.tree_files(ROOT / 'proof/lean/generated/sail', gate.lean_sources)
    snapshot.require(actual in (old_sail, fresh), 'unexpected live generated model')
    return {'status': 'MIGRATION_REVIEW_PASS_FULL_PROOF_PENDING', 'before': str(before),
            'old_policy_sha256': OLD_POLICY, 'new_policy_sha256': gate.file_hash(gate.POLICY),
            'script_sha256': gate.file_hash(Path(__file__)), 'changed_sources': sorted(CHANGED),
            'added_sources': sorted(ADDED), 'model_difference': difference,
            'new_sail_source_sha256': expected['sail'], 'live_model_matches_new_policy': actual == fresh,
            'kernel_report_sha256': KERNEL_SHA, 'translator_identity_changed': False,
            'public_policy_changed': False, 'full_proof_check_completed': False,
            'clean_room_claimed': False, 'release_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--before', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        snapshot.require(args.before is None and args.output is None, 'prepare cannot accept audit arguments')
        prepare()
    else:
        snapshot.require(args.before is not None and args.output is not None, 'audit requires before and output')
        snapshot.require(not args.output.exists(), 'audit output already exists')
        result = audit(args.before)
        gate.write_json(args.output, result)
        print(json.dumps(result, indent=2))
