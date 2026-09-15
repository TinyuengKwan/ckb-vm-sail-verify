#!/usr/bin/env python3
"""Use rebuilt base/public Charon + Aeneas + full-MIR in one source candidate.

Reextract all three production/decoder/iterator roots; compare whole Lean files.
No policy update, tool adoption, kernel, OS sandbox or full clean-room claim.
"""
import argparse
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
import decoder_harness as harness
import decoder_input_bundle as bundle
import decoder_input_locations as locations
import decoder_model_identity as identity
import release_evidence as evidence
import source_snapshot as snapshot
from probes import probe_isolated_aeneas as aeneas
from probes import probe_isolated_charon as charon
from probes import probe_full_mir_reextraction as previous
from probes import review_sail_install_migration as migration
from probes.probe_release_runtime import now

require, sha, read = evidence.require, evidence.sha, evidence.read
MIR = previous.mir
PUBLIC = aeneas.PUBLIC
CONFIG = aeneas.CONFIG
MAIN_CONFIG = ROOT / 'proof/lean/extraction/ckb-vm.json'
MIGRATION = ROOT / 'artifacts/boundary-check/sail-install-migration-vv_mytr1'
NEW_POLICY = '9308acea6d1dd3d6d1a3be2b4c9e7b6cb7e0f8bc34d698dcdf9705c740e5fb9a'
BUILDS = {
    'charon': ('isolated-charon-oy65t8ts',
        '691c805d3d9c8b5f17e68b32774d15dcb2facc483693ace1ab5abacfdb72e3c3',
        'independent_base_and_public_charon_built_qualification_pending', 18),
    'aeneas': ('isolated-aeneas-hksgq6ho',
        '6e9bdc1e7f98691ad0d1953f68bb9f57a1a5ea9b60afd49d5f847cd22d98b1a5',
        'base_and_public_aeneas_rebuilt_models_match_qualification_pending', 20),
}


def input_identity(name, digest, *, historical_policy=False):
    """One explicitly reviewed historical policy, never arbitrary stale inputs."""
    path = evidence.member(ROOT, name)
    if historical_policy and name == 'proof/lean/audit/step-policy.json':
        require(digest == migration.OLD_POLICY and sha(path) == NEW_POLICY, 'unreviewed policy transition')
        path = evidence.member(MIGRATION / 'source', name)
    require(sha(path) == digest, 'build input drift: ' + name)


def check_record(path, digest, status, count):
    require(sha(path) == digest, 'rebuilt component report drift')
    report = read(path)
    require(report['status'] == status and len(report['stages']) == count, 'incomplete component build')
    require(report['inputs_before'] == report['inputs_after'], 'component input drift during build')
    for name, expected in report['inputs_before'].items():
        input_identity(name, expected)
    for row in report['stages']:
        require(type(row['exit_code']) is int and row['exit_code'] == 0, 'component build stage failed')
        evidence.linked(path.parent, row['log'], row['log_sha256'])
    return report


def executable(path, digest):
    require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and
            os.access(path, os.X_OK) and sha(path) == digest, 'rebuilt executable drift: ' + str(path))


def verify_components():
    """Read-only recheck of concrete build artifacts and their source/install closures."""
    review = migration.audit(MIGRATION)
    require(review['live_model_matches_new_policy'] and sha(proof.POLICY) == NEW_POLICY,
            'exact-install migration no longer matches')
    package = bundle.verify_payload(PUBLIC)
    reports, result = {}, {'reports': {}, 'tools': {}, 'policy_transition': review}
    for name, (directory, digest, status, count) in BUILDS.items():
        path = ROOT / 'artifacts/boundary-check' / directory / 'report.json'
        reports[name] = check_record(path, digest, status, count)
        result['reports'][name] = {'path': str(path), 'sha256': digest}
    deps = check_record(aeneas.DEPENDENCIES, aeneas.DEPENDENCIES_SHA,
        'aeneas_dependencies_rebuilt_metadata_finalized_compiler_pending', 7)
    prefix = Path(deps['opam_root']) / deps['switch']
    require(aeneas.deps.sail.rocq.installed_inventory(prefix) == deps['installed_closure'], 'OPAM closure drift')
    executable(Path(deps['bootstrap']['path']), deps['bootstrap']['sha256'])
    result['opam'] = {'root': deps['opam_root'], 'switch': deps['switch'], 'bootstrap': deps['bootstrap'],
                     'report_sha256': aeneas.DEPENDENCIES_SHA,
                     'closure_sha256': proof.digest(snapshot.canonical(deps['installed_closure']))}
    policy = read(proof.POLICY)
    for side in ('base', 'public'):
        cr, ar = reports['charon']['sides'][side], reports['aeneas']['sides'][side]
        cs, ads = Path(cr['source']), Path(ar['source'])
        require(charon.check_source(cs, side == 'public', package['files']['patches/charon.patch']['sha256']) ==
                cr['source_before'] == cr['source_after'], 'Charon source drift')
        require(aeneas.check_source(ads, side == 'public', package['files']['patches/aeneas.patch']['sha256']) ==
                ar['source_before'], 'Aeneas source drift')
        require(charon.check_source(ads / 'charon', False, 'unused') == ar['charon_ml_source_before'], 'Charon ML drift')
        require((ads / 'src/charon').is_symlink() and (ads / 'src/charon').resolve() == ads / 'charon', 'Charon ML link drift')
        for source in (cs, ads, ads / 'charon'):
            snapshot.independent(source)
        support = proof.tree_files(ads / 'backends/lean', proof.lean_sources)
        require(proof.digest(proof.canonical(support)) == policy['aeneas_lean_sources_sha256'], 'Lean support source drift')
        tools = result['tools'][side] = {}
        for name in ('charon', 'charon-driver', 'aeneas'):
            if name == 'aeneas':
                path, built, digest = ads.parent / name, ads / 'src/_build/default/main.exe', ar['binary_sha256']
            else:
                path = Path(cr['directory']) / 'bin' / name
                built = Path(cr['directory']) / 'target/release' / name
                digest = cr['binary_comparison']['actual'][name]
            executable(path, digest)
            require(sha(built) == digest, 'installed compiler differs from build output')
            tools[name] = {'path': str(path), 'sha256': digest}
        tools['aeneas_version'] = ar['version']
    require(sha(MIR.RUST_REPORT) == MIR.RUST_SHA, 'Rust installation report drift')
    rust = read(MIR.RUST_REPORT)
    rust_home = Path(rust['private_homes']['RUSTUP_HOME'])
    require(MIR.rust.inventory(rust_home) == rust['installed_closures']['rustup'], 'Rust installation closure drift')
    require(sha(previous.MIR_REPORT) == previous.MIR_SHA, 'full-MIR report drift')
    mir = read(previous.MIR_REPORT)
    require(mir['status'] == 'isolated_full_mir_identity_review_required' and
            mir['inputs_before'] == mir['inputs_after'], 'full-MIR build incomplete')
    for name, digest in mir['inputs_before'].items():
        input_identity(name, digest, historical_policy=True)
    row = mir['build_stage']
    require(type(row['exit_code']) is int and row['exit_code'] == 0, 'full-MIR builder failed')
    evidence.linked(previous.MIR_REPORT.parent, row['log'], row['log_sha256'])
    child = Path(mir['child_report'])
    require(sha(child) == mir['child_report_sha256'] and sha(child.parent / 'build.log') == mir['child_build_log_sha256'],
            'full-MIR child evidence drift')
    built = read(child)
    require(built['status'] == 'PASS' and built['exit_code'] == 0 and built['rustflags'] == MIR.builder.FLAGS and
            built['libraries'] == mir['libraries'] and built['rustc_sha256'] == mir['rustc_sha256'], 'full-MIR child mismatch')
    require(MIR.libraries(Path(mir['sysroot']) / MIR.LIB_SUFFIX) == mir['libraries'], 'full-MIR installed library drift')
    require(sha(Path(mir['rustc_path'])) == mir['rustc_sha256'] and
            sha(Path(mir['bootstrap']['path'])) == mir['bootstrap']['sha256'], 'Rust compiler/bootstrap drift')
    result.update(rustup_home=str(rust_home), rustc=mir['rustc_path'], rustc_sha256=mir['rustc_sha256'],
                  sysroot=mir['sysroot'], libraries=mir['libraries'],
                  sysroot_report_sha256=previous.MIR_SHA, rust_report_sha256=MIR.RUST_SHA)
    return result


def environment(out, components):
    env = charon.environment(out, Path(components['rustup_home']), os.environ)
    # Explicit --sysroot is mandatory for every extraction. No ambient Miri cache.
    for key in list(env):
        if key.startswith(('MIRI', 'AENEAS')):
            env.pop(key)
    env.update(CARGO_TARGET_DIR=str(out / 'cargo-target'), OPAMROOT=components['opam']['root'],
               OPAMSWITCH=components['opam']['switch'])
    return env


def extraction_command(kind, binary, llbc, sysroot, checkout, main, public, iterator):
    require(kind in ('main', 'public', 'iterator'), 'unknown extraction root')
    command = [binary, 'rustc' if kind == 'iterator' else 'cargo', '--preset=aeneas',
               '--sysroot', sysroot, '--dest-file', llbc]
    if kind == 'main':
        require(main['preset'] == 'aeneas', 'main preset drift')
        choices = [('start-from', [main['root']]), ('include', main['include']), ('opaque', main['opaque'])]
    elif kind == 'public':
        choices = [(flag, public[key]) for flag, key in
                   [('start-from', 'outer_start_from'), ('include', 'outer_include'), ('opaque', 'outer_opaque')]]
    else:
        choices = [('include', iterator['translated']['options']['include'])]
    for flag, values in choices:
        for value in values:
            command.extend(['--' + flag, value])
    command.append('--')
    if kind == 'main':
        command += ['--lib']
    elif kind == 'public':
        command += public['outer_cargo_args']
    else:
        command += [checkout / identity.ITERATOR_RELATIVE, '--crate-type=lib']
    return command


def main_model(path):
    digest = sha(path)
    require(digest == sha(ROOT / 'proof/lean/generated/rust/CkbVmProduction.lean'),
            'main model differs; no new normalization is permitted')
    return {'raw_sha256': digest, 'whole_file_identical': True, 'generated_file_edited': False}


def run_probe(out):
    sys.setrecursionlimit(100000)
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [], 'models': {},
              'rust_reextracted': False, 'existing_llbc_reused_for_translation': False,
              'new_tools_approved': False, 'policy_changed': False, 'kernel_executed': False,
              'full_translator_qualification_executed': False, 'upstream_visitors_constraint_satisfied': False,
              'clean_room_claimed': False, 'third_party_claimed': False, 'release_claimed': False,
              'old_cargo_cache_or_target_copied': False, 'os_sandboxed': False}
    env = None

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv, cwd=out, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> rebuilt-chain: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                process = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = process.returncode
            require(process.returncode == 0, 'chain stage failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()

    try:
        components = verify_components()
        report['components'] = components
        policy = read(proof.POLICY)
        proof.require_equal(proof.local_sources(), policy['local_sources'], 'formal sources')
        report['formal_generated_before'] = proof.generated_evidence(policy)
        state = snapshot.capture(ROOT)
        report['source_snapshot_sha256'] = state['snapshot_sha256']
        proof.write_json(out / 'source-snapshot.json', state)
        snapshot.export(ROOT, state, out / 'source-payload')
        env = environment(out, components)
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'old Cargo outputs present')
        (out / 'cargo').mkdir()
        report.update(cargo_home_initially_empty=True, cargo_target_initially_absent=True)
        checkout = out / 'checkout'
        for repo in snapshot.REPOS:
            source = ROOT if repo == '.' else ROOT / repo
            target = checkout if repo == '.' else checkout / repo
            label = 'project' if repo == '.' else Path(repo).name
            stage('clone-' + label, ['git', 'clone', '--no-hardlinks', '--no-checkout', source, target])
            stage('checkout-' + label, ['git', 'checkout', '--detach', state['repositories'][repo]['head']], target)
        snapshot.restore(checkout, out / 'source-payload', state)
        report['checkout'] = str(checkout)
        public, main = read(CONFIG), read(MAIN_CONFIG)
        require(sha(CONFIG) == 'aaed2661ab316b0cf959034fa8b3e9c836aa88ad52da7746b3b648c707771b1c', 'public config drift')
        outer = out / 'outer'
        report['harness_before'] = harness.prepare(outer, checkout)
        report['environment'] = {key: env[key] for key in ['PATH', 'CARGO_HOME', 'CARGO_TARGET_DIR',
            'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'OPAMROOT', 'OPAMSWITCH']}
        actual = stage('rustc-path', ['rustup', 'which', '--toolchain', public['rust_toolchain'], 'rustc'])
        require(actual == components['rustc'], 'Rust compiler escaped verified installation')
        require('commit-hash: ' + public['rust_commit'] in stage('rust-version', [actual, '-vV']), 'Rust version drift')
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        for side in ('base', 'public'):
            tools = components['tools'][side]
            require(stage(side + '-charon-version', [tools['charon']['path'], 'version']) == main['charon'], 'Charon version drift')
            require(stage(side + '-aeneas-version', [*opam, tools['aeneas']['path'], '-version']) == tools['aeneas_version'], 'Aeneas version drift')
        stage('main-fetch-locked', ['cargo', 'fetch', '--locked', '--target', public['target']], checkout)
        stage('public-fetch-locked', ['cargo', 'fetch', '--locked', '--target', public['target']], outer)
        env['CARGO_NET_OFFLINE'] = 'true'
        archive_iterator = read(PUBLIC / 'llbc/FnPtrFullMir.llbc')
        for kind, stem in [('main', 'CkbVmProduction'), ('public', 'OuterClosedDepsV3'), ('iterator', 'FnPtrFullMir')]:
            side = 'base' if kind == 'main' else 'public'
            tools = components['tools'][side]
            env.update(public['aeneas_env'] if side == 'public' else {})
            folder = out / kind
            folder.mkdir()
            llbc = folder / (stem + '.llbc')
            cwd = checkout / 'crates/proof-extract' if kind == 'main' else outer if kind == 'public' else out
            command = extraction_command(kind, tools['charon']['path'], llbc, components['sysroot'],
                                         checkout, main, public, archive_iterator)
            stage('extract-' + kind, command, cwd)
            fresh = read(llbc)
            archived = read(ROOT / 'target/CkbVmProduction.llbc') if kind == 'main' else read(PUBLIC / 'llbc' / (stem + '.llbc'))
            row = report['models'][kind] = {'llbc': str(llbc), 'llbc_sha256': sha(llbc), 'tool_side': side}
            row['option_comparison'] = previous.candidate_options(archived, fresh, Path(components['sysroot']))
            args = main['aeneas_args'] if kind == 'main' else public['aeneas_args'] if kind == 'public' else [
                '-backend', 'lean', '-abort-on-error', '-no-progress-bar', '-checks', '-sequential']
            generated = folder / 'generated'
            stage('translate-' + kind, [*opam, tools['aeneas']['path'], *args, '-dest', generated, llbc], cwd)
            model = generated / (stem + '.lean')
            row.update(model=str(model), raw_sha256=sha(model))
            save()  # Preserve exact mismatching bytes/identity before failing comparison.
            row['model_identity'] = main_model(model) if kind == 'main' else identity.check(model, checkout) if kind == 'public' else identity.check_iterator(model, checkout, cwd)
        require(snapshot.capture(checkout) == state == snapshot.capture(ROOT), 'candidate/original source drift')
        require(harness.verify(outer, checkout) == report['harness_before'], 'harness drift')
        require(verify_components() == components, 'rebuilt component drift during extraction')
        require(proof.generated_evidence(policy) == report['formal_generated_before'], 'formal model changed')
        report.update(status='rebuilt_tools_three_models_match_qualification_pending',
                      rust_reextracted=True, source_snapshot_unchanged=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='rebuilt-extraction-chain-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
