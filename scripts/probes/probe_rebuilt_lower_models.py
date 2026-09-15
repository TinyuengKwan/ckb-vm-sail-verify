#!/usr/bin/env python3
"""Build join-only Aeneas and reextract the three lower decoder models.

Uses the already recorded joint-chain source candidate, rebuilt base Charon,
base Aeneas and full-MIR. Strict existing model identities, no new normalizer,
no policy adoption, kernel execution or complete clean-room claim.
"""
import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_raw_add as raw
import check_raw_add_fields as fields
from probes import probe_rebuilt_extraction_chain as chain

require, sha, read = chain.require, chain.sha, chain.read
proof, snapshot, aeneas, charon = chain.proof, chain.snapshot, chain.aeneas, chain.charon
ORIGIN = ROOT / 'artifacts/boundary-check/rebuilt-extraction-chain-18z20fdd'
ORIGIN_SHA = 'db0ddb324274e9ab1fa69650eed19ea661ef5b4f68face18aa72113c96414c9e'
PATCH = ROOT / 'proof/lean/decoder/toolchain/aeneas-join-recovery.patch'
PATCH_SHA = '5a924e2a6e38696eae8211f6e01b1b181bc85b1c5ce0cbf5fb44766e915f0dd9'
PATCH_FILES = {'src/interp/' + name for name in (
    'InterpBorrows.ml', 'InterpBorrows.mli', 'InterpJoin.ml', 'InterpReduceCollapse.ml')}
FIELD_DIR = ROOT / 'artifacts/boundary-check/raw-fields-6zf2keby'
RAW_DIR = ROOT / 'artifacts/boundary-check/raw-add-0__trc1y'
PINS = {
    fields.POLICY: '2fd824db64328972468ddb76fd7cdfb4d0cfbf86e8614ab88ee10169b9b40673',
    raw.POLICY: '407909ee4584c3d1a45dcbf123fa2019d70b2eaac4f22b962caf3dea37596951',
    raw.CONFIG: '777a8127bb1febab3f3ed1f2c09e0b45c995e20ae4a4fafb83d64100e11b0309',
    PATCH: PATCH_SHA,
    FIELD_DIR / 'report.json': '22d6d80938b34c20a7da27e9ecbf1bbc42a9f2d984f1047bb8a3248befe7379a',
    RAW_DIR / 'report.json': '6ff01460e94998f354f75514115a9933dbe135b6b3b30cfd156fab2def99bc60',
    FIELD_DIR / 'LocalFields.llbc': 'f702e57e1a9946de0f69462cdeaf5f3b541448f6b009d24b3882b95f917eadf1',
    RAW_DIR / 'FactoryScoped.llbc': '25094f587b104998fa48529dbb94cce6a2a012d232f3e1a61c0362a34ec78b23',
    RAW_DIR / 'MiniComplete.llbc': 'c07c50f85c76d5530033cc3d8cc250d5e920dc4e47d808ad87ffe3c140e5372d',
    RAW_DIR / 'crate/Cargo.lock': 'd45baf8a111163b31ac2cf482aee65aad146c042f3da695b0880681aedac812a',
    ROOT / 'deps/ckb-vm/Cargo.lock': 'b10b35cb6b00285720372c1df09b0e6fde7b8fa8b12fee18a4068e8d7ad1294f',
}
STEMS = ('LocalFields', 'FactoryScoped', 'MiniComplete')
STRICT_REASON = 'Context collapse does not support concrete shared borrows'


def check_join_source(source):
    state = aeneas.check_source(source, True, PATCH_SHA)
    require(set(state['changed']) == PATCH_FILES, 'join-only patch file set drift')
    return state


def install_ignored_lock(checkout, expected):
    """An explicit, policy-pinned build input excluded by Git source snapshots."""
    original = ROOT / 'deps/ckb-vm/Cargo.lock'
    require(sha(original) == expected, 'original CKB lock drift')
    destination = checkout / 'deps/ckb-vm/Cargo.lock'
    existed = destination.exists() or destination.is_symlink()
    require(not destination.is_symlink(), 'candidate CKB lock is linked')
    if not existed:
        with destination.open('xb') as stream:
            stream.write(original.read_bytes())
    require(destination.is_file() and destination.stat().st_nlink == 1 and sha(destination) == expected,
            'candidate CKB lock drift')
    return {'path': str(destination), 'source': str(original), 'sha256': expected,
            'already_present': existed, 'excluded_from_git_snapshot': True,
            'dependency_resolution_performed': False}


def check_outer_workspace(checkout):
    require(not any((parent / 'Cargo.toml').exists() for parent in checkout.parents),
            'candidate has an enclosing Cargo manifest')


def candidate():
    require(sha(ORIGIN / 'report.json') == ORIGIN_SHA, 'joint-chain report drift')
    report = read(ORIGIN / 'report.json')
    require(report['status'] == 'rebuilt_tools_three_models_match_qualification_pending' and
            len(report['stages']) == 20, 'joint-chain incomplete')
    for row in report['stages']:
        require(type(row['exit_code']) is int and row['exit_code'] == 0, 'joint-chain stage failed')
        chain.evidence.linked(ORIGIN, row['log'], row['log_sha256'])
    state = read(ORIGIN / 'source-snapshot.json')
    require(state['snapshot_sha256'] == report['source_snapshot_sha256'], 'candidate snapshot record drift')
    checkout = ORIGIN / 'checkout'
    require(snapshot.capture(checkout) == state, 'candidate source drift')
    for repo in snapshot.REPOS:
        snapshot.independent(checkout if repo == '.' else checkout / repo)
    return checkout, state


def extraction_command(stem, binary, llbc, sysroot, checkout, config):
    require(stem in STEMS, 'unknown lower model')
    command = [binary, 'rustc' if stem == 'MiniComplete' else 'cargo', '--preset=aeneas',
               '--sysroot', sysroot, '--dest-file', llbc]
    if stem == 'LocalFields':
        for root in fields.ROOTS:
            command += ['--start-from', root]
    elif stem == 'FactoryScoped':
        command += ['--start-from', config['root']]
        for key in ('include', 'opaque'):
            for value in config[key]:
                command += ['--' + key, value]
    else:
        command += ['--include', 'core::option::_']
    return command + (['--', checkout / 'proof/lean/decoder/toolchain/decoder_shared_closure.rs',
                       '--crate-type', 'lib'] if stem == 'MiniComplete' else ['--', '--lib', '--locked'])


def model_identity(stem, path, field_policy, raw_policy):
    require(stem in STEMS, 'unknown lower model')
    expected = field_policy['generated_sha256'] if stem == 'LocalFields' else raw_policy[
        'generated_normalized_sha256' if stem == 'FactoryScoped' else 'regression_model_normalized_sha256']
    actual = sha(path) if stem == 'LocalFields' else raw.normalized_model(path)
    return {'raw_sha256': sha(path), 'existing_policy_expected_sha256': expected,
            'existing_policy_actual_sha256': actual, 'matches_existing_policy': actual == expected,
            'generated_file_edited': False, 'new_normalization_used': False}


def check_result(code, output, strict=False):
    if strict:
        # Aeneas prints an uncaught Failure for this intended rejection too.
        require(type(code) is int and code in (1, 2) and STRICT_REASON in output,
                'strict join did not reject for the intended reason')
        require(not re.search(r'unknown module|unknownIdentifier|out of memory|Stack overflow|'
                              r'maxHeartbeats|maximum recursion depth|timeout|Internal error|PANIC',
                              output, re.I), 'strict join resource/import/internal failure')
    else:
        require(type(code) is int and code == 0, 'lower-model stage failed')


def run_probe(out):
    sys.setrecursionlimit(100000)
    report = {'schema_version': 1, 'status': 'running', 'started_at': chain.now(), 'stages': [], 'models': {},
              'new_tools_approved': False, 'policy_changed': False, 'kernel_executed': False,
              'rust_reextracted': False, 'existing_llbc_reused_for_translation': False,
              'clean_room_claimed': False, 'release_claimed': False, 'third_party_claimed': False,
              'os_sandboxed': False, 'old_build_cache_copied': False,
              'full_translator_qualification_executed': False, 'upstream_visitors_constraint_satisfied': False}
    env = None

    def save():
        proof.write_json(out / 'report.json', report)

    def stage(name, argv, cwd=out, timeout=900, strict=False):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
               'started_at': chain.now(), 'expected_strict_rejection': strict}
        report['stages'].append(row)
        save()
        print('==> rebuilt-lower: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            output = log.read_text(errors='replace')
            check_result(result.returncode, output, strict)
        finally:
            row.update(finished_at=chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return output.strip()

    try:
        components = chain.verify_components()
        report['components'] = components
        original, state = candidate()
        # Excluded CKB crates must not discover the real repository's workspace
        # above an artifacts/.../checkout. Restore identical source outside it;
        # never edit a production Cargo.toml merely to make extraction work.
        env = chain.environment(out, components)
        container = Path(tempfile.mkdtemp(prefix='rebuilt-lower-source-', dir='/tmp'))
        checkout = container / 'checkout'
        check_outer_workspace(checkout)
        report['candidate_source_container'] = str(container)
        for repo in snapshot.REPOS:
            source_repo = original if repo == '.' else original / repo
            target = checkout if repo == '.' else checkout / repo
            label = 'project' if repo == '.' else Path(repo).name
            stage('clone-candidate-' + label, ['git', 'clone', '--no-hardlinks', '--no-checkout', source_repo, target])
            stage('checkout-candidate-' + label, ['git', 'checkout', '--detach', state['repositories'][repo]['head']], target)
        snapshot.restore(checkout, ORIGIN / 'source-payload', state)
        report.update(checkout=str(checkout), source_snapshot_sha256=state['snapshot_sha256'],
                      origin_report_sha256=ORIGIN_SHA)
        for path, digest in PINS.items():
            require(sha(path) == digest, 'lower-model pinned input drift: ' + str(path))
        fp, rp, config = read(fields.POLICY), read(raw.POLICY), read(raw.CONFIG)
        require(fields.source_hashes() == fp['sources'] and raw.source_hashes() == rp['sources'], 'lower source drift')
        require(fp['roots'] == fields.ROOTS and rp['field_policy_sha256'] == sha(fields.POLICY), 'field scope drift')
        require(config['aeneas_source_commit'] == aeneas.COMMIT and
                config['charon_source_commit'] == charon.COMMIT, 'translator source commit drift')
        inputs = set(PINS) | {Path(__file__), Path(chain.__file__), proof.POLICY,
            ROOT / 'proof/lean/decoder/public-policy.json', aeneas.PUBLIC / 'package.json',
            aeneas.PUBLIC / 'sources/aeneas.bundle', aeneas.PUBLIC / 'sources/charon.bundle'}
        inputs |= {ROOT / name for name in set(fp['sources']) | set(rp['sources'])}
        inputs |= {aeneas.PUBLIC / 'models' / (stem + '.lean') for stem in STEMS}
        report['inputs_before'] = {str(p.relative_to(ROOT)): sha(p) for p in sorted(inputs)}
        report['candidate_ignored_lock'] = install_ignored_lock(checkout, fp['ckb_cargo_lock_sha256'])
        for stem in STEMS:
            require(model_identity(stem, aeneas.PUBLIC / 'models' / (stem + '.lean'), fp, rp)[
                'matches_existing_policy'], 'approved comparison model drift')
        policy = read(proof.POLICY)
        report['formal_generated_before'] = proof.generated_evidence(policy)
        env = chain.environment(out, components)
        report['environment'] = {key: env[key] for key in ('PATH', 'CARGO_HOME', 'CARGO_TARGET_DIR',
            'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'OPAMROOT', 'OPAMSWITCH')}
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'old Cargo outputs present')
        (out / 'cargo').mkdir()
        opam = [components['opam']['bootstrap']['path'], 'exec',
                '--switch=' + components['opam']['switch'], '--set-switch', '--']
        source = out / 'aeneas-source'
        stage('clone-aeneas', ['git', 'clone', '--no-checkout', aeneas.PUBLIC / 'sources/aeneas.bundle', source])
        stage('checkout-aeneas', ['git', 'checkout', '--detach', aeneas.COMMIT], source)
        snapshot.independent(source)
        aeneas.check_source(source, False, PATCH_SHA)
        stage('check-join-patch', ['git', 'apply', '--check', PATCH], source)
        stage('apply-join-patch', ['git', 'apply', PATCH], source)
        report['join_source_before'] = check_join_source(source)
        library = source / 'charon'
        stage('clone-charon-ml', ['git', 'clone', '--no-checkout', aeneas.PUBLIC / 'sources/charon.bundle', library])
        stage('checkout-charon-ml', ['git', 'checkout', '--detach', charon.COMMIT], library)
        snapshot.independent(library)
        report['charon_ml_before'] = charon.check_source(library, False, 'unused')
        require((source / 'src/charon').is_symlink() and (source / 'src/charon').resolve() == library,
                'wrong Charon ML symlink')
        require(not (source / 'src/_build').exists() and not (library / '_build').exists(), 'old Dune cache present')
        stage('build-join-aeneas', aeneas.dune_build_command(opam, source), source, timeout=3600)
        binary = out / 'aeneas-join'
        shutil.copy2(source / 'src/_build/default/main.exe', binary)
        report['join_binary'] = {'path': str(binary), 'sha256': sha(binary),
                                'approved_sha256': rp['tool_binary_sha256']}
        chain.executable(binary, sha(binary))
        version = stage('join-version', [*opam, binary, '-version'])
        require(version == 'aeneas ' + aeneas.COMMIT[:8] + '-dirty', 'join Aeneas version drift')
        report['join_binary']['version'] = version
        base = components['tools']['base']
        stage('base-charon-version', [base['charon']['path'], 'version'])
        require(stage('base-aeneas-version', [*opam, base['aeneas']['path'], '-version']) ==
                base['aeneas_version'], 'base Aeneas version drift')
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) ==
                components['rustc'], 'Rust compiler escaped verified installation')
        crate = out / 'crate'
        crate.mkdir()
        (crate / 'Cargo.toml').write_text('[package]\nname = "raw-add-decoder-connection"\n'
            'version = "0.0.0"\nedition = "2024"\n[workspace]\n[dependencies]\nckb-vm = { path = ' +
            json.dumps(str(checkout / 'deps/ckb-vm')) + ' }\n[lib]\npath = ' +
            json.dumps(str(checkout / 'proof/lean/decoder/FactoryRoot.rs')) + '\n')
        shutil.copy2(RAW_DIR / 'crate/Cargo.lock', crate / 'Cargo.lock')
        require(sha(crate / 'Cargo.lock') == rp['extraction_cargo_lock_sha256'] and
                sha(checkout / 'deps/ckb-vm/Cargo.lock') == fp['ckb_cargo_lock_sha256'], 'Cargo lock drift')
        harness = {name: sha(crate / name) for name in ('Cargo.toml', 'Cargo.lock')}
        report['harness_before'] = harness
        for label, cwd in [('fields', checkout / 'deps/ckb-vm'), ('factory', crate)]:
            stage('fetch-' + label, ['cargo', 'fetch', '--locked', '--target', 'x86_64-unknown-linux-gnu'], cwd)
        env['CARGO_NET_OFFLINE'] = 'true'
        models = out / 'models'
        for stem in STEMS:
            llbc = out / (stem + '.llbc')
            cwd = checkout / 'deps/ckb-vm' if stem == 'LocalFields' else crate if stem == 'FactoryScoped' else out
            stage('extract-' + stem, extraction_command(stem, base['charon']['path'], llbc,
                components['sysroot'], checkout, config), cwd)
            archived = (FIELD_DIR if stem == 'LocalFields' else RAW_DIR) / (stem + '.llbc')
            row = report['models'][stem] = {'llbc': str(llbc), 'llbc_sha256': sha(llbc)}
            row['option_comparison'] = chain.previous.candidate_options(read(archived), read(llbc),
                                                                       Path(components['sysroot']))
            args = ['-backend', 'lean', '-abort-on-error', '-no-progress-bar', '-namespace',
                    'RawDecodeExtract'] if stem == 'LocalFields' else list(config['aeneas_args'])
            if stem == 'FactoryScoped':
                args += ['-namespace', config['namespace']]
            translator = base['aeneas']['path'] if stem == 'LocalFields' else binary
            stage('translate-' + stem, [*opam, translator, *args, '-dest', models, llbc], cwd)
            row.update(model=str(models / (stem + '.lean')), translator=str(translator))
            row['identity'] = model_identity(stem, models / (stem + '.lean'), fp, rp)
            save()  # Compare every model; do not discard later evidence after the first mismatch.
        report['rust_reextracted'] = True
        stage('strict-join-negative', [*opam, binary, *config['aeneas_args'], '-strict-joins',
              '-dest', out / 'strict-negative', out / 'MiniComplete.llbc'], strict=True)
        report['strict_join_rejected'] = True
        require(snapshot.capture(checkout) == state, 'candidate source changed')
        require(sha(Path(report['candidate_ignored_lock']['path'])) == fp['ckb_cargo_lock_sha256'],
                'candidate ignored lock changed')
        require(check_join_source(source) == report['join_source_before'], 'join source changed')
        require(charon.check_source(library, False, 'unused') == report['charon_ml_before'], 'Charon ML changed')
        require(sha(source / 'src/_build/default/main.exe') == report['join_binary']['sha256'], 'build output changed')
        chain.executable(binary, report['join_binary']['sha256'])
        require({name: sha(crate / name) for name in harness} == harness, 'harness changed')
        require(chain.verify_components() == components, 'component closure changed')
        require(proof.generated_evidence(policy) == report['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)): sha(p) for p in sorted(inputs)}
        require(report['inputs_after'] == report['inputs_before'], 'input/policy drift')
        report['mismatching_models'] = [stem for stem in STEMS if not report['models'][stem]['identity']['matches_existing_policy']]
        report['status'] = ('lower_models_reextracted_identity_review_required' if report['mismatching_models'] else
                            'lower_models_reextracted_match_kernel_qualification_pending')
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = chain.now()
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
        out = Path(tempfile.mkdtemp(prefix='rebuilt-lower-models-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
