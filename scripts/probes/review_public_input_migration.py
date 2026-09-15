#!/usr/bin/env python3
"""Audit the installed-input migration without approving a proof/release run."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_proof as main
import public_decoder_gate as public
import ckb_source_baseline as baseline

OLD_MAIN = '079f22a9e9f04868d42c337a9eb02c083e5e6e1f3cb7a1b6cc1eaa8eba1e54c0'
CHANGED_PUBLIC = {
    'scripts/public_decoder_gate.py', 'scripts/public_decoder_acceptance.py',
    'scripts/decoder_public_source.py', 'scripts/decoder_public_clean.py',
    'scripts/probes/probe_decoder_public.py', 'scripts/tests/test_public_decoder_gate.py',
    'scripts/tests/test_public_decoder_acceptance.py', 'scripts/tests/test_decoder_public_clean.py'}
ADDED_PUBLIC = {
    'scripts/decoder_harness.py', 'scripts/decoder_model_identity.py',
    'scripts/decoder_input_bundle.py', 'scripts/decoder_input_locations.py',
    'scripts/tests/test_decoder_harness.py', 'scripts/tests/test_decoder_model_identity.py',
    'scripts/tests/test_decoder_iterator_identity.py', 'scripts/tests/test_decoder_input_bundle.py',
    'scripts/tests/test_decoder_input_locations.py',
    'proof/lean/decoder/toolchain/public-harness/Cargo.lock'}
CHANGED_MAIN = {'scripts/check_proof.py', 'scripts/tests/test_proof_check.py',
                'scripts/public_decoder_gate.py', 'scripts/public_decoder_acceptance.py',
                'proof/lean/decoder/public-policy.json'}


def compare_sources(old, new, changed, added):
    main.require_equal(set(old) - set(new), set(), 'removed source pins')
    main.require_equal(set(new) - set(old), added, 'added source pins')
    actual = {name for name in old if new[name] != old[name]}
    main.require_equal(actual, changed, 'changed source pins')
    return {'changed': sorted(actual), 'added': sorted(added), 'removed': []}


def audit(before):
    before = Path(before).resolve()
    old_main_path = before / main.POLICY.relative_to(ROOT)
    old_public_path = before / public.POLICY.relative_to(ROOT)
    main.require_equal(main.file_hash(old_main_path), OLD_MAIN, 'migration starting policy')
    old_main = json.loads(old_main_path.read_text())
    main.require_equal(main.file_hash(old_public_path),
        old_main['local_sources']['proof/lean/decoder/public-policy.json'], 'archived public policy')
    old_public = json.loads(old_public_path.read_text())
    new_main = json.loads(main.POLICY.read_text())
    new_public = json.loads(public.POLICY.read_text())
    main.require_equal({k: v for k, v in new_main.items() if k != 'local_sources'},
                       {k: v for k, v in old_main.items() if k != 'local_sources'},
                       'main theorem/contracts/tools/generated-model policy unchanged')
    ignored = {'inputs', 'input_layout', 'sources'}
    main.require_equal({k: v for k, v in new_public.items() if k not in ignored},
                       {k: v for k, v in old_public.items() if k not in ignored},
                       'public semantics/qualification/trust boundary unchanged')
    main.require_equal(new_public['inputs'], 'artifacts/decoder-inputs/public-v1', 'installed destination')
    changes = {
        'main': compare_sources(old_main['local_sources'], new_main['local_sources'], CHANGED_MAIN, set()),
        'public': compare_sources(old_public['sources'], new_public['sources'], CHANGED_PUBLIC, ADDED_PUBLIC)}
    # Validate the archived source copies as well as current pins.
    for name in CHANGED_MAIN | CHANGED_PUBLIC:
        old_sources = old_main['local_sources'] if name in old_main['local_sources'] else old_public['sources']
        main.require_equal(main.file_hash(before / name), old_sources[name], 'archived source ' + name)
    main.require_equal(main.local_sources(), new_main['local_sources'], 'current main sources')
    public.check_policy(new_public)  # Also reopens all installed inputs and qualification files.
    plans = {}
    for name in ['docs/plan/week5.md', 'docs/plan/week6.md']:
        main.require_equal(main.file_hash(ROOT / name), main.file_hash(before / name), 'unchanged plan ' + name)
        plans[name] = main.file_hash(ROOT / name)
    return {'status': 'MIGRATION_REVIEW_PASS_MAIN_RUN_PENDING', 'before': str(before),
            'script_sha256': main.file_hash(Path(__file__)), 'changes': changes,
            'old_main_policy_sha256': OLD_MAIN, 'main_policy_sha256': main.file_hash(main.POLICY),
            'public_policy_sha256': main.file_hash(public.POLICY), 'plan_sha256': plans,
            'production_baseline': baseline.check(ROOT),
            'theorem_contract_and_model_pins_unchanged': True,
            'proof_check_claimed': False, 'clean_room_claimed': False, 'release_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('migration report output already exists')
    result = audit(args.before)
    main.write_json(args.output, result)
    print(json.dumps(result, indent=2))
