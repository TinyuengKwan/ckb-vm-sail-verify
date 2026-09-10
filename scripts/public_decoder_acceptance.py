"""Validate public decoder evidence before main-gate integration.

This validator does not adopt tools, change policy, or accept a cached replay as
a fresh check. A future caller must invoke the producer itself before using it.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

import check_proof as main
import check_raw_add as raw
import check_raw_add_fields as fields
sys.path.insert(0, str(Path(__file__).resolve().parent / 'probes'))
from probe_decoder_full_mir import MODULES, GENERAL_MODULES, audit_summary

PUBLIC = main.ROOT / 'proof/lean/decoder/toolchain/full-entry'
PUBLIC_MODULES = ['OuterConversion', 'OuterPublic', 'OuterPublicStep', 'OuterPublicWitness']
MODELS = {
    'OuterClosedDepsV3.lean': 'b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061',
    'OuterRawLinked.lean': '4168fe7fbbe3b0e70091b12de31b01aca1ea9931e559ac373066445ec88ed584',
    'FnPtrFullMir.lean': '3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3',
}
STAGES = ['charon-patch-applies-reverse', 'aeneas-patch-applies-reverse', 'source-baseline',
          'extract-public-rust', 'extract-iterator-rust', 'translate-public', 'translate-iterator',
          'clean-main-build', 'clean-main-audit'] + [
    'clean-kernel-' + name for name in ['LocalFields', 'RawFields', 'FactoryScoped', 'MiniComplete', *raw.MODULES]
] + ['clean-field-audit', 'clean-raw-audit', 'kernel-FnPtrFullMir', 'kernel-OuterRawLinked'] + [
    'kernel-' + name for name in MODULES + GENERAL_MODULES + PUBLIC_MODULES
] + ['audit-full-mir', 'audit-general', 'audit-public', 'negative-wrong-public',
     'negative-weakened-compiles', 'negative-weakened-audit', 'source-baseline-after']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_shape(report, main_policy_sha256):
    require(report['status'] == 'EXPERIMENTAL_PUBLIC_CHECK_PASS', 'public run did not pass')
    for key in ['rust_reextracted', 'clean_dependency_build', 'weakened_premise_rejected_by_type_audit']:
        require(report[key] is True, 'missing required public evidence: ' + key)
    clean = report['clean_dependencies']
    require(clean['status'] == 'passed', 'clean dependency audit incomplete')
    require(type(clean['initial_compiled_modules']) is int and clean['initial_compiled_modules'] == 0,
            'clean build started with compiled input')
    require(clean['main_policy_sha256'] == main_policy_sha256, 'stale main policy in public check')
    require(clean['main_axiom_count'] == 137 and clean['field_theorem_count'] == 9 and
            clean['raw_theorem_count'] == 15, 'lower-level audit incomplete')
    require([s['stage'] for s in report['stages']] == STAGES, 'public stages missing, duplicated or reordered')
    for stage in report['stages']:
        expected = 1 if stage['stage'] == 'negative-wrong-public' else 0
        require(type(stage['exit_code']) is int and stage['exit_code'] == expected,
                'unexpected stage exit: ' + stage['stage'])
    require(report['protected_before'] and report['protected_before'] == report['protected_after'],
            'protected source/policy drift')
    source = report['source_reextraction']
    require(source['cargo_target_initially_absent'] is True, 'Cargo target was reused')
    require(source['source_before'] and source['source_before'] == source['source_after'],
            'Rust extraction source drift')


def check_models(models, directory):
    directory = Path(directory).resolve()
    require(len(models) == len(MODELS) and {Path(p).name for p in models} == set(MODELS),
            'public model set incomplete or duplicated')
    for filename, digest in models.items():
        path = Path(filename).resolve()
        require(path.is_relative_to(directory), 'model outside evidence directory')
        require(digest == MODELS[path.name], 'unreviewed generated model identity')
        require(main.file_hash(path) == digest, 'generated public model changed')


def validate(report_path):
    """Recheck the evidence files, not just PASS flags or axiom counts."""
    report_path = Path(report_path).resolve()
    directory = report_path.parent
    report = json.loads(report_path.read_text())
    main_policy = json.loads(main.POLICY.read_text())
    check_shape(report, main.file_hash(main.POLICY))
    require(Path(report['directory']).resolve() == directory, 'report directory mismatch')
    for key, source in [('script_sha256', 'probes/probe_decoder_public.py'),
                        ('source_script_sha256', 'decoder_public_source.py'),
                        ('clean_script_sha256', 'decoder_public_clean.py')]:
        require(report[key] == main.file_hash(main.ROOT / 'scripts' / source), 'checker source changed: ' + source)
    for stage in report['stages']:
        log = directory / (stage['stage'] + '.log')
        require(main.file_hash(log) == stage['log_sha256'], 'stage log changed: ' + stage['stage'])
    main_audit_path = directory / 'clean-main-audit.json'
    main_audit = json.loads(main_audit_path.read_text())
    main.check_audit(main_audit, main_policy)
    for name, checker in [('field', fields), ('raw', raw)]:
        checker.check_audit(json.loads((directory / ('clean-' + name + '-audit.json')).read_text()),
                            json.loads(checker.POLICY.read_text()))
    snapshot_path = PUBLIC / 'audit-snapshot.json'
    require(main.file_hash(snapshot_path) == '33b76c6791a874357ae9859b57ddb8c7b37e689e3c4a7b8edc900386a82e1135',
            'public audit snapshot changed')
    require(report['snapshot_sha256'] == main.file_hash(snapshot_path), 'stale public snapshot')
    snapshot = json.loads(snapshot_path.read_text())
    for name in ['full-mir', 'general', 'public']:
        path = directory / (name + '-audit.json')
        require(main.file_hash(path) == report['audits'][name]['audit_sha256'], 'public audit file changed')
        audit = json.loads(path.read_text())
        summary = audit_summary(audit)
        if 'contracts' in audit:
            summary['contracts'] = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in audit['contracts'].items()}
        require(summary == snapshot[name], 'public theorem type/body/contract/dependency drift: ' + name)
        for row in summary['theorems'].values():
            require(not any(re.search('sorryAx|_native|native_decide', a) for a in row['axioms']),
                    'unaccepted public proof axiom')
    check_models(report['models'], directory)
    # Recheck the actual negative output; infrastructure failure is not evidence
    # against an incorrect decoded result.
    negative = (directory / 'negative-wrong-public.log').read_text()
    require('Type mismatch' in negative and not re.search(
        'unknownIdentifier|maximum.*(heartbeats|recursion)|out of memory', negative, re.I),
        'wrong-result negative was not a semantic rejection')
    weakened = (directory / 'negative-weakened-audit.log').read_text()
    rows = [line[5:] for line in weakened.splitlines() if line.startswith('TYPE=')]
    require(len(rows) == 1, 'missing weakened theorem type')
    require(hashlib.sha256(json.loads(rows[0]).encode()).hexdigest() !=
            snapshot['public']['theorems']['OuterAdd.public_mop_off']['type_sha256'],
            'False premise weakening was not detected')
    info = report['clean_dependencies']
    clean_root = Path(info['directory']).resolve()
    require(clean_root == directory / 'clean', 'clean source directory mismatch')
    main_build = next(s for s in report['stages'] if s['stage'] == 'clean-main-build')
    clean_build = {'status': 'passed', 'directory': str(clean_root),
        'policy_sha256': info['main_policy_sha256'], 'initial_compiled_modules': 0,
        'reused': info['reused_compiled_inputs'], 'lean_path': info['lean_path'],
        'dependency_revisions': info['dependency_revisions'], 'source_models': info['source_models'],
        'build_log_sha256': main_build['log_sha256'], 'theorem': main_audit['theorem'],
        'axiom_count': len(main_audit['axioms']), 'audit_sha256': main.file_hash(main_audit_path),
        'built_olean_count': len(list(clean_root.rglob('*.olean'))),
        'witness_axiom_counts': {name: len(items) for name, items in main_audit['witness_axioms'].items()}}
    return {'report': str(report_path), 'report_sha256': main.file_hash(report_path),
            'theorem': 'OuterAdd.cold_public_add_step', 'axiom_count': 158,
            'public_theorem_count': 68, 'clean_dependency_build': True,
            'clean_build': clean_build, 'tool_adoption_claimed': False}
