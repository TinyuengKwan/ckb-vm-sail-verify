"""Produce public ADD decoder evidence; adoption belongs to the parent policy gate.

Regenerates models from pinned LLBC, or from production Rust with --reextract-rust,
and rebuilds all decoder proof modules. Main/raw dependencies are reused unless
--clean-dependencies is supplied. Does not update any policy or snapshot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

if not __debug__:
    raise RuntimeError('proof audit requires Python assertions; do not use -O')

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--inputs", required=True, type=Path)
parser.add_argument('--reextract-rust', action='store_true',
                    help='re-extract both Rust roots using a new Cargo target and pinned full-MIR std')
parser.add_argument('--clean-dependencies', action='store_true',
                    help='build support, main, raw and field Lean dependencies from source in this run')
args = parser.parse_args()
if args.clean_dependencies and not args.reextract_rust:
    parser.error('--clean-dependencies requires --reextract-rust')
HERE = args.inputs.resolve()
sys.path.insert(0, str(ROOT / 'scripts'))
from probe_decoder_full_mir import audit_summary, MODULES, GENERAL_MODULES
import decoder_rebuilt_locations as locations
import decoder_model_identity as model_identity

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

out = Path(tempfile.mkdtemp(prefix='public-check-', dir=ROOT / 'artifacts/boundary-check'))
models = out / 'models'
models.mkdir()
report = {'status': 'running', 'main_gate_adopted': False, 'stages': [],
          'adoption_decision_owner': 'public_decoder_gate.py and public-rebuilt-policy.json',
          'clean_dependency_build': False, 'rust_reextracted': False,
          'sysroot_rebuilt': False, 'directory': str(out),
          'scope': 'VERSION2 IMC+B, MOP off, fresh cache, arbitrary-PC original ADD word',
          'open': ['documented upstream full-suite failures', 'MOP-enabled semantics',
                   'physical memory coupling and actual SparseMemory implementation',
                   'opaque execution Machine inhabitation/reset reachability']}
protected = [ROOT / p for p in ['proof/lean/audit/step-policy.json',
    'proof/lean/decoder/public-rebuilt-policy.json', 'proof/lean/decoder/raw-rebuilt-policy.json',
    'proof/lean/decoder/rebuilt-input-policy.json',
    'proof/lean/decoder/raw-policy.json', 'artifacts/proof-check/report.json',
    'proof/lean/generated/rust/CkbVmProduction.lean']]
report['protected_before'] = {str(p.relative_to(ROOT)): sha(p) for p in protected}

def save():
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

def run(label, command, cwd=ROOT, env=None, reject=None, timeout=300):
    stage = {'stage': label, 'command': list(map(str, command)), 'cwd': str(cwd)}
    report['stages'].append(stage)
    save()
    start = time.monotonic()
    log = out / (label + '.log')
    with log.open('w') as stream:
        proc = subprocess.run(stage['command'], cwd=cwd, env=env,
            stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    stage.update(exit_code=proc.returncode, elapsed_seconds=time.monotonic()-start,
                 log_sha256=sha(log))
    save()
    output = log.read_text()
    if reject:
        if proc.returncode != 1 or reject not in output or re.search(
                'unknownIdentifier|maximum.*(heartbeats|recursion)|out of memory', output, re.I):
            raise RuntimeError(label + ': expected semantic rejection; see ' + str(log))
    elif proc.returncode or 'sorryAx' in output:
        raise RuntimeError(label + ': failed; see ' + str(log))
    print(label + (': expected rejection' if reject else ': PASS'), flush=True)
    return log.read_text()

try:
    report['installed_inputs'] = locations.load(HERE)
    payload = Path(report['installed_inputs']['payload'])
    config = json.loads((payload / 'candidate/extraction.json').read_bytes())
    binary = payload / 'bin/aeneas'
    llbc = payload / 'llbc/OuterClosedDepsV3.llbc'
    aeneas_source = HERE / 'sources/public/aeneas'
    patch = ROOT / 'proof/lean/decoder/toolchain/branch-experimental/aeneas-branch-v2.patch'
    assert sha(binary) == config['aeneas_binary_sha256']
    assert sha(llbc) == config['llbc_sha256']
    assert sha(patch) == '956a3b1b895c9ffee8376d7cc8f2440efcedba8592908bac8b58c4a07b7c387d'
    source_patch = subprocess.check_output(['git', 'diff', '--', 'src'], cwd=aeneas_source)
    assert hashlib.sha256(source_patch).hexdigest() == sha(patch)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=aeneas_source, text=True).strip()
    assert commit == '379890b54b4961dc7729e314c6eefdc09fe50981'
    report['tool'] = {'binary_sha256': sha(binary), 'patch_sha256': sha(patch), 'commit': commit,
        'env': {'AENEAS_FACTOR_RETURN_GUARDS': '1', 'AENEAS_EXTRACT_TRY_FROM_INT_ERROR': '1'}}
    sys.setrecursionlimit(100000)
    data = json.loads(llbc.read_bytes())
    assert not data['has_errors']
    report['input'] = {'sha256': sha(llbc), 'options': data['translated']['options']}
    public = ROOT / 'proof/lean/decoder/toolchain/full-entry'
    # Check both tool patches as applicable patches, not just opaque byte blobs.
    # A previous Charon archive omitted one trailing context line even though
    # the measured source and binary were correct.
    charon_bin = payload / 'bin'
    charon_source = HERE / 'sources/public/charon'
    charon_patch = ROOT / 'proof/lean/decoder/toolchain/cfg-experimental/charon-cleanup-suffix.patch'
    assert sha(charon_patch) == '17f5c34ca63f66987498331d9712b8affb00e25867e4746b5b660893d3d6eebf'
    charon_diff = subprocess.check_output(['git', 'diff', '--', 'charon/src'], cwd=charon_source)
    assert hashlib.sha256(charon_diff).hexdigest() == sha(charon_patch)
    charon_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=charon_source, text=True).strip()
    assert charon_commit == '89ac118194b978d8cf753222c19f313521377aa0'
    assert sha(charon_bin / 'charon') == config['charon_binary_sha256']
    assert sha(charon_bin / 'charon-driver') == config['charon_driver_sha256']
    report['charon_tool'] = {'commit': charon_commit, 'patch_sha256': sha(charon_patch),
        'binaries': {name: sha(charon_bin / name) for name in ['charon', 'charon-driver']}}
    run('charon-patch-applies-reverse', ['git', 'apply', '--reverse', '--check', charon_patch], charon_source)
    run('aeneas-patch-applies-reverse', ['git', 'apply', '--reverse', '--check', patch], aeneas_source)
    snapshot_path = public / 'audit-snapshot.json'
    snapshot = json.loads(snapshot_path.read_text())
    assert sha(snapshot_path) == '33b76c6791a874357ae9859b57ddb8c7b37e689e3c4a7b8edc900386a82e1135'
    report['snapshot_sha256'] = sha(snapshot_path)
    report['proof_sources'] = {str(p.relative_to(ROOT)): sha(p) for p in public.glob('*.lean')}
    report['script_sha256'] = sha(Path(__file__))
    run('source-baseline', [sys.executable, ROOT / 'scripts/ckb_source_baseline.py'])
    iterator_llbc = payload / 'llbc/FnPtrFullMir.llbc'
    assert sha(iterator_llbc) == 'a052ec7e21d68d6a618680d2df6bed7827d4f55096293563fe55de9df0cc308a'
    if args.reextract_rust:
        from decoder_public_source import reextract
        report['source_script_sha256'] = sha(ROOT / 'scripts/decoder_public_source.py')
        llbc, iterator_llbc = reextract(HERE, out, run, report, data,
                                        json.loads(iterator_llbc.read_bytes()))
    generated = out / 'generated'
    runtime = report['source_reextraction']['runtime_after'] if args.reextract_rust else locations.runtime(HERE)
    translate_env = dict(locations.environment(out, runtime, config), **report['tool']['env'])
    for key in ['AENEAS_BRANCH_DIAGNOSTIC', 'AENEAS_COLLAPSE_DIAGNOSTIC']:
        translate_env.pop(key, None)
    run('translate-public', locations.translator_command(runtime, binary, ['-backend', 'lean', '-abort-on-error',
        '-no-progress-bar', '-checks', '-sequential', '-namespace', 'OuterDecodeCandidate',
        '-dest', generated, llbc]), env=translate_env)
    run('translate-iterator', locations.translator_command(runtime, binary, ['-backend', 'lean', '-abort-on-error',
        '-no-progress-bar', '-checks', '-sequential', '-dest', generated, iterator_llbc]), env=translate_env)
    src = generated / 'OuterClosedDepsV3.lean'
    report['model_identities'] = {
        'public': model_identity.check(src, ROOT),
        'iterator': model_identity.check_iterator(generated / 'FnPtrFullMir.lean', ROOT, out)}
    text = src.read_text()
    assert text.count('import Aeneas\n') == 1
    linked = models / 'OuterRawLinked.lean'
    linked.write_text(text.replace('import Aeneas\n', 'import Aeneas\nimport CkbVmProduction\n', 1))
    iterator = models / 'FnPtrFullMir.lean'
    iterator.write_bytes((generated / 'FnPtrFullMir.lean').read_bytes())
    report['models'] = {str(p): sha(p) for p in [src, linked, iterator]}
    finish_clean = None
    if args.clean_dependencies:
        from decoder_public_clean import build
        report['clean_script_sha256'] = sha(ROOT / 'scripts/decoder_public_clean.py')
        project, lean, env, finish_clean = build(out, run, report, HERE)
    else:
        project = ROOT / 'proof/lean/theorems'
        lean = subprocess.check_output(['lake', 'env', 'which', 'lean'], cwd=project, text=True).strip()
        base = subprocess.check_output(['lake', 'env', 'printenv', 'LEAN_PATH'], cwd=project, text=True).strip()
        dependencies = [ROOT / 'artifacts/boundary-check/raw-add-0__trc1y/models',
                        ROOT / 'artifacts/boundary-check/raw-fields-6zf2keby/models']
        env = dict(os.environ, LEAN_PATH=os.pathsep.join(map(str, [models, *dependencies])) + os.pathsep + base)
    for model in [iterator, linked]:
        run('kernel-' + model.stem, [lean, '--root=' + str(models), '-o',
            models / (model.stem + '.olean'), model], project, env)
    fixtures = ROOT / 'proof/lean/decoder/toolchain/full-mir'
    public = ROOT / 'proof/lean/decoder/toolchain/full-entry'
    for module in MODULES + GENERAL_MODULES + ['OuterConversion', 'OuterPublic', 'OuterPublicStep', 'OuterPublicWitness']:
        folder = public if module in ['OuterConversion', 'OuterPublic', 'OuterPublicStep', 'OuterPublicWitness'] else fixtures
        run('kernel-' + module, [lean, '--root=' + str(folder), '-o',
            models / (module + '.olean'), folder / (module + '.lean')], project, env)
    report['audits'] = {}
    for name, folder, exporter, marker, snapshot_name in [
        ('full-mir', fixtures, 'ExportFullMirAudit', 'FULL_MIR_AUDIT_JSON=', 'audit-snapshot.json'),
        ('general', fixtures, 'ExportGeneralAudit', 'GENERAL_DECODER_AUDIT_JSON=', 'general-audit-snapshot.json'),
        ('public', public, 'ExportPublicAudit', 'PUBLIC_DECODER_AUDIT_JSON=', None)]:
        text = run('audit-' + name, [lean, folder / (exporter + '.lean')], project, env)
        rows = [line[len(marker):] for line in text.splitlines() if line.startswith(marker)]
        assert len(rows) == 1
        audit = json.loads(rows[0])
        summary = audit_summary(audit)
        for k, v in summary['theorems'].items():
            if any(re.search('sorryAx|_native|native_decide', a) for a in v['axioms']):
                raise RuntimeError(k + ': unaccepted proof dependency')
        if 'contracts' in audit:
            summary['contracts'] = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in audit['contracts'].items()}
        if summary != snapshot[name]:
            raise RuntimeError(name + ': candidate type/dependency/body/contract snapshot changed')
        (out / (name + '-audit.json')).write_text(json.dumps(audit, indent=2) + '\n')
        (out / (name + '-summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
        report['audits'][name] = {'theorem_count': len(audit['theorems']),
            'axiom_counts': {k: len(v['axioms']) for k, v in audit['theorems'].items()},
            'audit_sha256': sha(out / (name + '-audit.json'))}
        if snapshot_name:
            old_snapshot = json.loads((folder / snapshot_name).read_text())
            if summary['theorems'] != old_snapshot['theorems']:
                raise RuntimeError(name + ': existing theorem types/dependencies changed')
            if summary.get('contracts') != old_snapshot.get('contracts'):
                raise RuntimeError(name + ': existing contracts changed')
            changed = [k for k, v in summary['definitions'].items() if old_snapshot['definitions'].get(k) != v]
            report['audits'][name]['changed_definition_bodies_for_review'] = changed
        else:
            for k, v in summary['theorems'].items():
                if any('VERSION3' in a or 'TryFromU64' in a for a in v['axioms']):
                    raise RuntimeError(k + ': avoidable opaque dependency remains')
    run('negative-wrong-public', [lean, public / 'RejectWrongPublic.lean'], project, env,
        reject='Type mismatch')
    # This valid theorem is weakened by False; kernel success must not hide the
    # type change. Keep the proof term intact, and compare the audited type.
    weakened = out / 'weakened'
    weakened.mkdir()
    source_text = (public / 'OuterPublic.lean').read_text()
    anchor = 'theorem public_mop_off {M R : Type}'
    assert source_text.count(anchor) == 1
    # Only the standalone lemma is compiled, avoiding dependent uses of its
    # intentionally changed signature. The source before the next theorem is
    # retained exactly; this is a negative fixture, not the production module.
    prefix = source_text.split('/-- Original ADD word', 1)[0]
    prefix = prefix.replace(anchor, 'theorem public_mop_off (unused : False) {M R : Type}', 1)
    (weakened / 'OuterPublic.lean').write_text(prefix + '\nend\nend OuterAdd\n')
    bad_env = dict(env, LEAN_PATH=str(weakened) + os.pathsep + env['LEAN_PATH'])
    run('negative-weakened-compiles', [lean, '--root=' + str(weakened), '-o',
        weakened / 'OuterPublic.olean', weakened / 'OuterPublic.lean'], project, bad_env)
    exporter = weakened / 'ExportWeakening.lean'
    exporter.write_text('import OuterPublic\nimport Lean\nopen Lean Elab Command\n'
        'run_cmd do\n  let info ← getConstInfo ``OuterAdd.public_mop_off\n'
        '  liftIO <| IO.println ("TYPE=" ++ (Lean.Json.str (reprStr info.type)).compress)\n')
    output = run('negative-weakened-audit', [lean, exporter], project, bad_env)
    rows = [line[5:] for line in output.splitlines() if line.startswith('TYPE=')]
    assert len(rows) == 1
    altered_type_hash = hashlib.sha256(json.loads(rows[0]).encode()).hexdigest()
    assert altered_type_hash != snapshot['public']['theorems']['OuterAdd.public_mop_off']['type_sha256']
    report['weakened_premise_rejected_by_type_audit'] = True
    if finish_clean is not None:
        finish_clean()
    assert locations.load(HERE) == report['installed_inputs']
    run('source-baseline-after', [sys.executable, ROOT / 'scripts/ckb_source_baseline.py'])
    report['protected_after'] = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert report['protected_after'] == report['protected_before']
    report['status'] = 'EXPERIMENTAL_PUBLIC_CHECK_PASS'
except Exception as error:
    report.update(status='FAIL', error=str(error))
    raise
finally:
    save()
    print('Report: ' + str(out / 'report.json'), flush=True)
