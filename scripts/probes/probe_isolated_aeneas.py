#!/usr/bin/env python3
"""Build base/public Aeneas and Charon ML from source with rebuilt OPAM deps.

Reuses verified existing LLBC for model comparisons. Does not reextract Rust,
build a new Lean proof, qualify/adopt translators, or claim full clean-room.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_proof as proof
import decoder_input_bundle as bundle
import decoder_model_identity as identity
from probes import probe_aeneas_opam_dependencies as deps
from probes import probe_isolated_charon as charon
from probes.probe_release_runtime import now
from source_snapshot import require, regular, safe, independent

COMMIT = '379890b54b4961dc7729e314c6eefdc09fe50981'
DEPENDENCIES = ROOT / 'artifacts/boundary-check/aeneas-opam-finalize-mj9dgb4h/report.json'
DEPENDENCIES_SHA = '64f4b5dfff7dbfe3d08d3a935de0e3942805d46fe277e2738ba654b6bb757b6e'
PUBLIC = ROOT / 'artifacts/decoder-inputs/public-v1/payload'
CONFIG = ROOT / 'proof/lean/decoder/toolchain/full-entry/extraction.json'


def dune_build_command(opam_exec, source):
    return [*opam_exec, 'dune', 'build', '--root', source / 'src',
            '--profile=dev', '--display=short', '-j', '4', 'main.exe']


def source_inventory(root):
    """Record committed links without following them; reject modified link text."""
    require(not bundle.git(root, 'ls-files', '--others', '--exclude-standard', '-z'), 'untracked Aeneas source')
    files, changed = {}, {}
    for row in bundle.git(root, 'ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not row:
            continue
        metadata, filename = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = safe(filename.decode())
        require(kind == 'blob' and mode in ('100644', '100755', '120000'), 'unexpected Aeneas Git entry')
        if mode == '120000':
            path = root / name
            require(path.is_symlink(), 'committed Aeneas link replaced')
            target = os.readlink(path)
            require(not Path(target).is_absolute() and
                    Path(os.path.normpath(path.parent / target)).is_relative_to(root), 'escaping committed link')
            data, actual_mode = target.encode(), mode
        else:
            path = regular(root, name)
            data = path.read_bytes()
            actual_mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if mode == '120000':
            require(blob == oid, 'modified committed Aeneas link text')
        files[name] = {'mode': actual_mode, 'sha256': proof.digest(data), 'size': len(data)}
        if blob != oid or mode != actual_mode:
            changed[name] = files[name]
    require(files, 'empty Aeneas source inventory')
    return {'commit': bundle.git(root, 'rev-parse', 'HEAD').decode().strip(), 'files': files, 'changed': changed}


def check_source(root, patched, patch_sha):
    state = source_inventory(root)
    require(state['commit'] == COMMIT, 'Aeneas commit drift')
    if patched:
        require(proof.digest(bundle.git(root, 'diff', '--', 'src')) == patch_sha, 'Aeneas patch drift')
        require(state['changed'] and all(name.startswith('src/') for name in state['changed']), 'unapproved Aeneas change')
    else:
        require(not state['changed'], 'base Aeneas source is dirty')
    return state


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [], 'sides': {},
              'old_build_cache_copied': False, 'existing_llbc_reused': True, 'rust_reextracted': False,
              'kernel_executed': False, 'new_tools_approved': False, 'policy_changed': False,
              'clean_room_claimed': False, 'third_party_claimed': False, 'release_claimed': False,
              'os_sandboxed': False, 'full_translator_qualification_executed': False}
    env = None

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv, cwd=out, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> isolated-aeneas: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'Aeneas rebuild stage failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=deps.sail.sha(log))
            save()
        return log.read_text().strip()

    try:
        require(deps.sail.sha(DEPENDENCIES) == DEPENDENCIES_SHA, 'dependency finalization evidence drift')
        built = json.loads(DEPENDENCIES.read_text())
        require(built['status'] == 'aeneas_dependencies_rebuilt_metadata_finalized_compiler_pending', 'dependencies incomplete')
        for s in built['stages']:
            require(s['exit_code'] == 0 and deps.sail.sha(DEPENDENCIES.parent / s['log']) == s['log_sha256'], 'dependency log drift')
        require(built['inputs_before'] == built['inputs_after'], 'dependency input drift')
        for name, digest in built['inputs_before'].items():
            require(deps.sail.sha(ROOT / name) == digest, 'dependency input changed: ' + name)
        prefix = Path(built['opam_root']) / built['switch']
        require(deps.sail.rocq.installed_inventory(prefix) == built['installed_closure'], 'new OPAM closure drift')
        manifest = bundle.verify_payload(PUBLIC)
        config = json.loads(CONFIG.read_text())
        policy = json.loads(proof.POLICY.read_text())
        main_input = ROOT / 'target/CkbVmProduction.llbc'
        provenance = json.loads((ROOT / 'proof/lean/generated/rust/SOURCE_BASELINE.json').read_text())
        require(deps.sail.sha(main_input) == provenance['llbc_sha256'], 'main LLBC provenance drift')
        main_model = ROOT / 'proof/lean/generated/rust/CkbVmProduction.lean'
        require(deps.sail.sha(main_model) == provenance['generated_lean_sha256'], 'main model provenance drift')
        paths = [Path(__file__), DEPENDENCIES, Path(deps.__file__), Path(charon.__file__), deps.LOCK,
                 PUBLIC / 'package.json', PUBLIC / 'sources/aeneas.bundle', PUBLIC / 'sources/charon.bundle',
                 PUBLIC / 'patches/aeneas.patch', PUBLIC / 'llbc/OuterClosedDepsV3.llbc', PUBLIC / 'llbc/FnPtrFullMir.llbc',
                 CONFIG, proof.POLICY, ROOT / 'proof/lean/decoder/public-policy.json', main_input, main_model,
                 ROOT / 'proof/lean/extraction/ckb-vm.json', ROOT / 'scripts/source_snapshot.py',
                 ROOT / 'scripts/decoder_input_bundle.py', ROOT / 'scripts/decoder_model_identity.py']
        report['inputs_before'] = {str(p.relative_to(ROOT)): deps.sail.sha(p) for p in paths}
        env = deps.environment(out, os.environ)
        env.update(OPAMROOT=built['opam_root'], OPAMSWITCH=built['switch'])
        report.update(dependency_report=str(DEPENDENCIES), dependency_report_sha256=DEPENDENCIES_SHA,
                      opam_prefix=str(prefix), upstream_charon_visitors_constraint_satisfied=False)
        opam = Path(built['bootstrap']['path'])
        require(deps.sail.sha(opam) == built['bootstrap']['sha256'], 'OPAM bootstrap drift')
        opam_exec = [opam, 'exec', '--switch=' + built['switch'], '--set-switch', '--']
        deps.check_packages(stage('packages', [opam, 'list', '--switch=' + built['switch'],
            '--installed', '--short', '--columns=name,version']))
        invariant = stage('invariant', [opam, 'switch', 'invariant', '--switch=' + built['switch']])
        deps.check_export(stage('export', [opam, 'switch', 'export', '--switch=' + built['switch'], '--full', '-']), invariant)
        for side in ('base', 'public'):
            directory = out / side
            directory.mkdir()
            source = directory / 'aeneas-source'
            row = report['sides'][side] = {'source': str(source), 'models': {}}
            stage(side + '-clone', ['git', 'clone', '--no-checkout', PUBLIC / 'sources/aeneas.bundle', source])
            stage(side + '-checkout', ['git', 'checkout', '--detach', COMMIT], source)
            independent(source)
            patch_sha = manifest['files']['patches/aeneas.patch']['sha256']
            check_source(source, False, patch_sha)
            if side == 'public':
                stage(side + '-patch-check', ['git', 'apply', '--check', PUBLIC / 'patches/aeneas.patch'], source)
                stage(side + '-patch', ['git', 'apply', PUBLIC / 'patches/aeneas.patch'], source)
            row['source_before'] = check_source(source, side == 'public', patch_sha)
            library = source / 'charon'
            stage(side + '-clone-charon-ml', ['git', 'clone', '--no-checkout', PUBLIC / 'sources/charon.bundle', library])
            stage(side + '-checkout-charon-ml', ['git', 'checkout', '--detach', charon.COMMIT], library)
            independent(library)
            row['charon_ml_source_before'] = charon.check_source(library, False, 'unused')
            require((source / 'src/charon').is_symlink() and (source / 'src/charon').resolve() == library, 'wrong vendored Charon ML')
            require(not (source / 'src/_build').exists() and not (library / '_build').exists(), 'old Dune cache present')
            row['dune_build_initially_absent'] = True
            stage(side + '-build', dune_build_command(opam_exec, source), source, 3600)
            binary = directory / 'aeneas'
            shutil.copy2(source / 'src/_build/default/main.exe', binary)
            row['binary_sha256'] = deps.sail.sha(binary)
            expected = policy['tool_binaries']['aeneas'] if side == 'base' else manifest['files']['bin/aeneas']['sha256']
            row['approved_binary_sha256'] = expected
            row['matches_approved_binary'] = row['binary_sha256'] == expected
            version = stage(side + '-version', [*opam_exec, binary, '-version'])
            require(version.startswith('aeneas ' + COMMIT[:7]), 'rebuilt Aeneas version does not name source commit')
            row['version'] = version
            generated = directory / 'models'
            generated.mkdir()
            if side == 'base':
                args = json.loads((ROOT / 'proof/lean/extraction/ckb-vm.json').read_text())['aeneas_args']
                stage(side + '-translate-main', [*opam_exec, binary, *args, '-dest', generated, main_input])
                digest = deps.sail.sha(generated / 'CkbVmProduction.lean')
                row['models']['main'] = {'raw_sha256': digest}
                save()
                require(digest == deps.sail.sha(main_model), 'rebuilt base Aeneas model differs')
            else:
                env.update(config['aeneas_env'])
                for name in ('OuterClosedDepsV3', 'FnPtrFullMir'):
                    args = config['aeneas_args'] if name == 'OuterClosedDepsV3' else [
                        '-backend', 'lean', '-abort-on-error', '-no-progress-bar', '-checks', '-sequential']
                    stage(side + '-translate-' + name, [*opam_exec, binary, *args, '-dest', generated,
                        PUBLIC / 'llbc' / (name + '.llbc')])
                    model = generated / (name + '.lean')
                    row['models'][name] = {'raw_sha256': deps.sail.sha(model)}
                    save()
                    row['models'][name]['identity'] = identity.check(model, ROOT) if name == 'OuterClosedDepsV3' else identity.check_iterator(model, ROOT, ROOT)
            require(check_source(source, side == 'public', patch_sha) == row['source_before'], 'Aeneas source changed during build')
            require(charon.check_source(library, False, 'unused') == row['charon_ml_source_before'], 'Charon ML source changed')
            independent(source)
            independent(library)
            save()
        require(bundle.verify_payload(PUBLIC) == manifest, 'approved package changed')
        require(deps.sail.rocq.installed_inventory(prefix) == built['installed_closure'], 'OPAM installation changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)): deps.sail.sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        report['status'] = 'base_and_public_aeneas_rebuilt_models_match_qualification_pending'
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='isolated-aeneas-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run_probe(out))
