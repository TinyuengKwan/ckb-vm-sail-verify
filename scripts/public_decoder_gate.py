"""Main-gate adapter for the explicitly scoped public ADD decoder policy.

No optional fallback and no reuse-report switch. The adapter always invokes the
fresh producer, then validates its evidence. This module never writes policy.
"""
import json
from pathlib import Path
import sys

import check_proof as main
import public_decoder_acceptance as acceptance

POLICY = main.ROOT / 'proof/lean/decoder/public-policy.json'
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
]


def sources():
    paths = [
        'scripts/public_decoder_gate.py', 'scripts/public_decoder_acceptance.py',
        'scripts/probes/probe_decoder_public.py', 'scripts/decoder_public_source.py',
        'scripts/decoder_public_clean.py', 'scripts/probes/probe_decoder_full_mir.py',
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


def check_policy(policy):
    main.require_equal(policy['schema_version'], 1, 'public policy schema')
    main.require_equal(policy['status'], 'adopted-rv64-add-public-v1', 'public tool adoption')
    main.require_equal(policy['configuration'], CONFIGURATION, 'public decoder configuration')
    main.require_equal(policy['limitations'], LIMITATIONS, 'public decoder trust boundary')
    main.require_equal(policy['production_baseline'], 'ckb-vm-1ffba3977da9-runtime-container-v1',
                       'public production baseline')
    main.require_equal(policy['sources'], sources(), 'public checker/proof sources')
    # Immutable qualification evidence is separate from the fresh run. A caller
    # may not substitute these historical results for current kernel checking.
    required = {'public_clean', 'borrow', 'fnptr', 'charon_ui', 'charon_diagnostics',
                'guard_equivalence', 'loop_equivalence'}
    main.require_equal(set(policy['qualification']), required, 'tool qualification evidence set')
    for label, entry in policy['qualification'].items():
        path = (main.ROOT / entry['path']).resolve()
        if not path.is_relative_to(main.ROOT / 'artifacts/boundary-check'):
            raise RuntimeError('qualification report outside evidence tree')
        main.require_equal(main.file_hash(path), entry['sha256'], 'qualification ' + label)
    return policy


def command(policy):
    inputs = (main.ROOT / policy['inputs']).resolve()
    if not inputs.is_relative_to(main.ROOT / 'artifacts/boundary-check'):
        raise RuntimeError('public inputs outside isolated tool tree')
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
