"""Main-gate adapter for the explicitly scoped public ADD decoder policy.

No optional fallback and no reuse-report switch. The adapter always invokes the
fresh producer, then validates its evidence. This module never writes policy.
"""
import json
from pathlib import Path
import sys

import check_proof as main
import public_decoder_acceptance as acceptance
import decoder_rebuilt_locations as locations

POLICY = main.ROOT / 'proof/lean/decoder/public-rebuilt-policy.json'
CONFIGURATION = {
    'instruction': 'normal 32-bit RV64 ADD', 'version': 2, 'isa': 'IMC+B',
    'mop': False, 'cache': 'actual fresh decoder',
    'pc': 'arbitrary, subject to explicit size/fetch contracts',
    'theorem': 'OuterAdd.cold_public_add_step',
}
LIMITATIONS = [
    'tool transforms remain trusted, not generally formally verified',
    'upstream full test suite has documented failures; not claimed all-pass',
    'MOP-on fusion and non-ADD instruction correctness not proved',
    'physical memory coupling and actual SparseMemory implementation not proved',
    'opaque Rust Machine inhabitation and platform reset reachability not proved',
    'rebuilt visitors package remains below the upstream declared constraint',
    'historical diagnostic classifier source identity not established',
]


def sources():
    paths = [
        'scripts/public_decoder_gate.py', 'scripts/public_decoder_acceptance.py',
        'scripts/probes/probe_decoder_public.py', 'scripts/decoder_public_source.py',
        'scripts/decoder_public_clean.py', 'scripts/probes/probe_decoder_full_mir.py',
        'scripts/decoder_harness.py', 'scripts/decoder_model_identity.py',
        'scripts/decoder_input_bundle.py', 'scripts/decoder_input_locations.py',
        'scripts/decoder_rebuilt_inputs.py', 'scripts/decoder_rebuilt_locations.py',
        'scripts/tests/test_decoder_rebuilt_inputs.py', 'scripts/tests/test_decoder_rebuilt_locations.py',
        'proof/lean/decoder/rebuilt-input-policy.json', 'proof/lean/decoder/rebuilt-input-catalogue.json',
        'proof/lean/decoder/raw-rebuilt-policy.json',
        'scripts/tests/test_decoder_harness.py', 'scripts/tests/test_decoder_model_identity.py',
        'scripts/tests/test_decoder_iterator_identity.py', 'scripts/tests/test_decoder_input_bundle.py',
        'scripts/tests/test_decoder_input_locations.py',
        'proof/lean/decoder/toolchain/public-harness/Cargo.lock',
        'scripts/tests/test_public_decoder_acceptance.py', 'scripts/tests/test_public_decoder_gate.py',
        'scripts/tests/test_decoder_public_clean.py', 'scripts/tests/test_decoder_public_source.py',
        'proof/lean/decoder/raw-policy.json', 'proof/lean/decoder/field-policy.json',
        'proof/lean/decoder/toolchain/full-entry/extraction.json',
        'proof/lean/decoder/toolchain/full-entry/audit-snapshot.json',
        'proof/lean/decoder/toolchain/full-mir/audit-snapshot.json',
        'proof/lean/decoder/toolchain/full-mir/general-audit-snapshot.json',
        'proof/lean/decoder/toolchain/full-mir/OuterRoot.rs',
        'proof/lean/decoder/toolchain/fnptr-experimental/fnptr_cases.rs',
        'proof/lean/decoder/toolchain/cfg-experimental/charon-cleanup-suffix.patch',
        'proof/lean/decoder/toolchain/branch-experimental/aeneas-branch-v2.patch',
        'proof/lean/decoder/toolchain/branch-experimental/borrow-audit-snapshot.json',
    ]
    for folder in ['full-entry', 'full-mir']:
        paths.extend(str(p.relative_to(main.ROOT)) for p in sorted(
            (main.ROOT / 'proof/lean/decoder/toolchain' / folder).glob('*.lean')))
    for folder, modules in [
            ('branch-experimental', ['BorrowProof', 'SharedEffectProof', 'ExportBorrowAudit',
                                     'GuardEquivalence', 'GuardCounterexample', 'RejectWrongGuard']),
            ('cfg-experimental', ['LoopJumpProof', 'LoopJumpNegative'])]:
        paths.extend('proof/lean/decoder/toolchain/' + folder + '/' + name + '.lean' for name in modules)
    return {p: main.file_hash(main.ROOT / p) for p in sorted(set(paths))}


def check_main_policy_link(policy):
    """The declared public gate must be the one this adapter actually executes."""
    main.require_equal(policy.get('configuration', {}).get('required_public_decoder_policy'),
                       str(POLICY.relative_to(main.ROOT)), 'main/public policy link')


def check_policy(policy):
    main.require_equal(policy['schema_version'], 1, 'public policy schema')
    main.require_equal(policy['status'], 'adopted-rv64-add-public-rebuilt-v2', 'public tool adoption')
    main.require_equal(policy['configuration'], CONFIGURATION, 'public decoder configuration')
    main.require_equal(policy['limitations'], LIMITATIONS, 'public decoder trust boundary')
    main.require_equal(policy['production_baseline'], 'ckb-vm-1ffba3977da9-runtime-container-v1',
                       'public production baseline')
    check_main_policy_link(json.loads(main.POLICY.read_text()))
    main.require_equal(policy['sources'], sources(), 'public checker/proof sources')
    installed = locations.load(input_directory(policy))
    main.require_equal(policy['input_admission_sha256'], installed['policy_sha256'], 'input admission policy')
    main.require_equal(policy['raw_policy_sha256'], main.file_hash(locations.RAW_POLICY), 'rebuilt lower policy')
    locations.lower_policy(input_directory(policy))
    payload = Path(installed['payload'])
    # Immutable qualification evidence is separate from the fresh run. A caller
    # may not substitute these historical results for current kernel checking.
    required = {'public_clean', 'borrow', 'fnptr', 'charon_ui', 'charon_diagnostics',
                'guard_equivalence', 'loop_equivalence'}
    main.require_equal(set(policy['qualification']), required, 'tool qualification evidence set')
    for label, entry in policy['qualification'].items():
        path = payload / 'qualification' / (label + Path(entry['path']).suffix)
        main.require_equal(main.file_hash(path), entry['sha256'], 'qualification ' + label)
    return policy


def input_directory(policy):
    main.require_equal(policy['input_layout'], 'public-decoder-rebuilt-inputs-v2', 'public input layout')
    inputs = (main.ROOT / policy['inputs']).resolve()
    if not inputs.is_relative_to(main.ROOT / 'artifacts/decoder-inputs'):
        raise RuntimeError('public inputs outside isolated tool tree')
    return inputs


def command(policy):
    inputs = input_directory(policy)
    return [sys.executable, str(main.ROOT / 'scripts/probes/probe_decoder_public.py'),
            '--inputs', str(inputs), '--reextract-rust', '--clean-dependencies']


def execute(run_stage, env, report):
    """Use the parent gate's log/timeout/process-group handling, not a new runner."""
    policy_sha = main.file_hash(POLICY)
    policy = check_policy(json.loads(POLICY.read_text()))
    output = run_stage('public-decoder', command(policy), env, report)
    rows = [line[len('Report: '):] for line in output.splitlines() if line.startswith('Report: ')]
    if len(rows) != 1:
        raise RuntimeError('expected one fresh public decoder report')
    path = Path(rows[0]).resolve()
    if not path.is_relative_to(main.ROOT / 'artifacts/boundary-check'):
        raise RuntimeError('public producer reported a path outside evidence tree')
    result = acceptance.validate(path)
    main.require_equal(main.file_hash(POLICY), policy_sha, 'public policy changed during check')
    check_policy(policy)
    result.update(main_gate_adopted=True, public_policy_sha256=policy_sha,
                  configuration=policy['configuration'], limitations=policy['limitations'])
    # Validator deliberately makes no adoption claim; this adapter owns that
    # claim only after checking the explicit policy and invoking the producer.
    result['tool_adoption_claimed'] = True
    report['public_decoder'] = result
    return result
