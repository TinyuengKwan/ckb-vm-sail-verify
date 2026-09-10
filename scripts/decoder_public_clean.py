"""Build the public decoder's complete Lean dependency graph from source.

Reuses only the pinned Lean compiler/standard library as compiled input. Existing
generated Rust/Sail/field/factory *sources* remain policy-checked inputs; this does
not claim to regenerate those four lower-level models or adopt candidate tools.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import check_lean_clean as clean
import check_proof as gate
import check_raw_add as raw
import check_raw_add_fields as fields


def build(out, run, report):
    policy = json.loads(gate.POLICY.read_text())
    raw_policy = json.loads(raw.POLICY.read_text())
    field_policy = json.loads(fields.POLICY.read_text())
    gate.require_equal(gate.file_hash(raw.POLICY),
        '407909ee4584c3d1a45dcbf123fa2019d70b2eaac4f22b962caf3dea37596951', 'raw policy identity')
    gate.require_equal(gate.file_hash(fields.POLICY), raw_policy['field_policy_sha256'], 'field policy identity')
    gate.require_equal(raw.source_hashes(), raw_policy['sources'], 'raw sources')
    gate.require_equal(fields.source_hashes(), field_policy['sources'], 'field sources')
    env, binaries, aeneas, lake = gate.tools_and_environment(policy)
    before = gate.source_evidence(policy, binaries, aeneas)
    generated = gate.generated_evidence(policy)
    clean_root = out / 'clean'
    project, revisions = clean.prepare(clean_root, aeneas)
    dependencies = out / 'dependencies'
    dependencies.mkdir()
    # Never copy a directory containing archived .oleans. Each source is checked
    # against its existing policy, then copied individually into the new tree.
    boundary = gate.ROOT / 'artifacts/boundary-check'
    originals = {
        'LocalFields': boundary / 'raw-fields-6zf2keby/models/LocalFields.lean',
        'FactoryScoped': boundary / 'raw-add-0__trc1y/models/FactoryScoped.lean',
        'MiniComplete': boundary / 'raw-add-0__trc1y/models/MiniComplete.lean',
    }
    gate.require_equal(gate.file_hash(originals['LocalFields']), field_policy['generated_sha256'], 'field model')
    gate.require_equal(raw.normalized_model(originals['FactoryScoped']),
                       raw_policy['generated_normalized_sha256'], 'factory model')
    gate.require_equal(raw.normalized_model(originals['MiniComplete']),
                       raw_policy['regression_model_normalized_sha256'], 'mini model')
    for module in ['RawFields', *raw.MODULES, 'ExportFieldAudit', 'ExportRawAudit']:
        originals[module] = raw.PROOF / (module + '.lean')
    source_hashes = {name: gate.file_hash(path) for name, path in originals.items()}
    for name, path in originals.items():
        shutil.copyfile(path, dependencies / (name + '.lean'))
    initial = list(out.rglob('*.olean')) + list(out.rglob('*.ilean'))
    gate.require_equal(initial, [], 'empty entire public-check compilation tree')
    compiler = Path(subprocess.check_output([lake, 'env', 'lean', '--print-prefix'],
                                           cwd=project, env=env, text=True).strip()).resolve()
    lean = subprocess.check_output([lake, 'env', 'which', 'lean'], cwd=project, env=env, text=True).strip()
    base = subprocess.check_output([lake, 'env', 'printenv', 'LEAN_PATH'],
                                   cwd=project, env=env, text=True).strip()
    paths = clean.check_paths(base, out, compiler)
    info = {'directory': str(clean_root), 'initial_compiled_modules': 0,
            'reused_compiled_inputs': 'pinned Lean compiler and its standard library only',
            'reused_generated_sources': source_hashes, 'dependency_revisions': revisions,
            'lean_path': paths, 'main_policy_sha256': gate.file_hash(gate.POLICY),
            'source_models': generated, 'status': 'building'}
    report['clean_dependencies'] = info
    env['LEAN_NUM_THREADS'] = '8'
    run('clean-main-build', [lake, '--no-cache', 'build', 'LeanRV64D', 'CkbVmProduction',
        'SmokeImports', 'AddRegisterAxioms', 'RegisterRegression', 'AddStepAxioms',
        'StepRegression', 'ProductionAdd', 'ProductionAddWitness', '+Mathlib.Tactic.IntervalCases'],
        project, env, timeout=3600)
    # Lake sets its import path for build children; direct Lean invocations do
    # not inherit that child environment. Pass the already validated clean path.
    env['LEAN_PATH'] = base
    output = run('clean-main-audit', [lean, clean_root / 'proof/lean/audit/ExportStepAudit.lean'],
                 project, env)
    audit = gate.parse_audit(output)
    gate.check_audit(audit, policy)
    gate.write_json(out / 'clean-main-audit.json', audit)
    info['main_axiom_count'] = len(audit['axioms'])
    env['LEAN_PATH'] = os.pathsep.join([str(out / 'models'), str(dependencies), base])
    info['public_lean_path'] = clean.check_paths(env['LEAN_PATH'], out, compiler)
    for module in ['LocalFields', 'RawFields', 'FactoryScoped', 'MiniComplete', *raw.MODULES]:
        run('clean-kernel-' + module, [lean, '--root=' + str(dependencies),
            '-o', dependencies / (module + '.olean'), dependencies / (module + '.lean')], project, env)
    for name, checker, check_policy, exporter in [
            ('field', fields, field_policy, 'ExportFieldAudit'),
            ('raw', raw, raw_policy, 'ExportRawAudit')]:
        output = run('clean-' + name + '-audit', [lean, dependencies / (exporter + '.lean')], project, env)
        audit = checker.audit_from(output)
        checker.check_audit(audit, check_policy)
        gate.write_json(out / ('clean-' + name + '-audit.json'), audit)
        info[name + '_theorem_count'] = len(audit['theorems'])
    info['status'] = 'built-audited'

    def finish():
        # Recheck source identity after all public proofs, not only before build.
        gate.require_equal(gate.source_evidence(policy, binaries, aeneas), before, 'main sources changed')
        gate.require_equal(gate.generated_evidence(policy), generated, 'main models changed')
        gate.require_equal(gate.file_hash(gate.POLICY), info['main_policy_sha256'], 'main policy changed')
        gate.require_equal(raw.source_hashes(), raw_policy['sources'], 'raw sources changed')
        gate.require_equal(fields.source_hashes(), field_policy['sources'], 'field sources changed')
        for name, source in originals.items():
            gate.require_equal(gate.file_hash(source), source_hashes[name], 'original decoder source changed')
            gate.require_equal(gate.file_hash(dependencies / (name + '.lean')), source_hashes[name],
                               'copied decoder source changed')
        for relative in ['proof/lean/theorems', 'proof/lean/generated/rust', 'proof/lean/generated/sail']:
            gate.require_equal(gate.tree_files(clean_root / relative, gate.lean_sources),
                               gate.tree_files(gate.ROOT / relative, gate.lean_sources), 'clean source copy')
        gate.require_equal(gate.tree_files(clean_root / 'support/Aeneas', gate.lean_sources),
                           gate.tree_files(aeneas / 'backends/lean', gate.lean_sources), 'clean support copy')
        gate.require_equal(gate.file_hash(project / 'lake-manifest.json'),
                           gate.file_hash(gate.THEOREMS / 'lake-manifest.json'), 'clean dependency lock')
        clean.check_paths(env['LEAN_PATH'], out, compiler)
        info['compiled_modules_after'] = len(list(out.rglob('*.olean')))
        info['status'] = 'passed'
        report['clean_dependency_build'] = True
    return project, lean, env, finish
