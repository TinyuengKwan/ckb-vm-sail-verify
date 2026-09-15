#!/usr/bin/env python3
"""Restore candidate bundled tool sources and reextract all six packaged roots.

Uses the actually unpacked, pinned candidate payload and fixed CKB checkpoint.
Fresh Cargo/Charon caches and harnesses; no old LLBC is translated. This is not
tool adoption, compiler rebuilding, a kernel run or a full clean-room claim.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rebuilt_input_candidate as package
import decoder_harness as harness
import decoder_model_identity as identity

k = package.kernel
chain, lower = k.chain, k.lower
require, sha, read = package.require, package.sha, package.read
PACK = package.BASE / 'rebuilt-input-candidate-z2k9y4hg'
PACK_SHA = '326ae28c839496192a98e411fb03f1c00b09a9f77ad357b6c88070267b4a25e1'
CATALOGUE_SHA = 'b9015281f8a2c4d30aabd0b91eb6993d492b87e15eb83dcf93a8a66df8daa523'
SOURCE_SHA = '99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12'
VARIANTS = (('base/charon', 'charon', None), ('public/charon', 'charon', 'charon.patch'),
            ('base/aeneas', 'aeneas', None), ('public/aeneas', 'aeneas', 'aeneas.patch'),
            ('join/aeneas', 'aeneas', 'aeneas-join.patch'))


def tool_source(path, family, patch):
    digest = '' if patch is None else sha(patch)
    state = (chain.charon.check_source(path, patch is not None, digest) if family == 'charon' else
             chain.aeneas.check_source(path, patch is not None, digest))
    chain.snapshot.independent(path)
    if family == 'aeneas':
        ml = path / 'charon'
        state = {'source': state, 'charon_ml': chain.charon.check_source(ml, False, '')}
        chain.snapshot.independent(ml)
        require((path / 'src/charon').is_symlink() and (path / 'src/charon').resolve() == ml,
                'Aeneas Charon ML source link drift')
    return state


def clear_public_flags(env, public):
    result = {key: value for key, value in env.items() if not key.startswith('AENEAS')}
    result.update(public)
    return result


def model_check(stem, model, archived, checkout, cwd):
    if stem == 'OuterClosedDepsV3':
        return identity.check(model, checkout)
    if stem == 'FnPtrFullMir':
        return identity.check_iterator(model, checkout, cwd)
    if stem in ('CkbVmProduction', 'LocalFields'):
        require(sha(model) == sha(archived), 'whole candidate model differs: ' + stem)
        return {'raw_sha256': sha(model), 'whole_file_identical': True}
    require(stem in ('FactoryScoped', 'MiniComplete'), 'unknown candidate root')
    actual, expected = lower.raw.normalized_model(model), lower.raw.normalized_model(archived)
    require(actual == expected, 'candidate lower model differs beyond existing source-path rule')
    return {'raw_sha256': sha(model), 'candidate_normalized_sha256': actual,
            'candidate_reference_normalized_sha256': expected, 'new_normalization_used': False,
            'old_formal_raw_policy_adopted': False}


def run(out):
    # The archived and freshly emitted LLBC contain deeply nested type trees.
    # Match the existing extraction probes; never change or flatten those trees.
    sys.setrecursionlimit(100000)
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [], 'models': {},
              'unpacked_candidate_payload_reused': True, 'fixed_ckb_checkpoint_reused': True,
              'old_cargo_or_charon_cache_reused': False, 'old_llbc_translated': False,
              'rust_reextracted': False, 'tool_sources_restored': False, 'compilers_rebuilt': False,
              'tool_adopted': False, 'policy_changed': False, 'kernel_executed': False,
              'generated_models_edited': False, 'clean_room_claimed': False, 'release_claimed': False,
              'full_upstream_suite_passed': False, 'upstream_visitors_constraint_satisfied': False}
    env = None

    def save():
        k.gate.write_json(out / 'report.json', report)

    def stage(name, args, cwd=out, strict=False):
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(cwd), 'started_at': chain.now(),
               'strict_join_rejection_expected': strict,
               'public_environment': {key: value for key, value in env.items() if key.startswith('AENEAS')}}
        report['stages'].append(row); save()
        print('==> candidate-input-reextraction: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=900)
            row['exit_code'] = result.returncode
            if strict:
                require(result.returncode == 2, 'strict join must reject with original exit code')
                lower.check_result(result.returncode, log.read_text(), strict=True)
            else:
                require(type(result.returncode) is int and result.returncode == 0, 'stage failed: ' + name)
        finally:
            row.update(log=log.name, log_sha256=sha(log), finished_at=chain.now()); save()
        return log.read_text().strip()

    try:
        packed = k.pinned(PACK / 'report.json', PACK_SHA)
        require(packed['status'] == 'rebuilt_candidate_inputs_packaged_unpacked_admission_pending' and
                packed['inputs_before'] == packed['inputs_after'], 'candidate package incomplete')
        catalogue = k.pinned(PACK / 'catalogue.json', CATALOGUE_SHA)
        require(packed['catalogue_sha256'] == CATALOGUE_SHA and
                sha(PACK / 'rebuilt-decoder-candidate.tar.gz') == packed['archive_sha256'], 'candidate archive drift')
        payload = PACK / 'unpacked/payload'
        report['payload_before'] = package.verify(payload, catalogue)
        components = chain.verify_components()
        env = chain.environment(out, components)
        env['CHARON_CACHE_DIR'] = str(out / 'charon-cache')
        require(all(not (out / name).exists() for name in ('cargo', 'cargo-target', 'charon-cache')), 'old extraction cache')
        report['environment'] = {key: env[key] for key in ('PATH', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN',
                              'CARGO_HOME', 'CARGO_TARGET_DIR', 'CHARON_CACHE_DIR', 'OPAMROOT', 'OPAMSWITCH')}
        low = read(payload / 'evidence/lower_extraction.json')
        checkout = Path(low['checkout']); state = chain.snapshot.capture(checkout)
        lower.check_outer_workspace(checkout)
        require(state['snapshot_sha256'] == SOURCE_SHA == low['source_snapshot_sha256'], 'fixed CKB checkpoint drift')
        for repo in chain.snapshot.REPOS:
            chain.snapshot.independent(checkout if repo == '.' else checkout / repo)
        report.update(checkout=str(checkout), source_snapshot_sha256=SOURCE_SHA, candidate_report_sha256=PACK_SHA,
                      candidate_catalogue_sha256=CATALOGUE_SHA, payload=str(payload))
        main, public, raw = read(chain.MAIN_CONFIG), read(payload / 'candidate/extraction.json'), read(lower.raw.CONFIG)
        require(public['status'] == 'candidate-rv64-add-public-rebuilt-v2', 'not the candidate configuration')
        fp, rp = read(lower.fields.POLICY), read(lower.raw.POLICY)
        require(sha(checkout / 'deps/ckb-vm/Cargo.lock') == fp['ckb_cargo_lock_sha256'], 'CKB ignored lock drift')
        paths = {Path(__file__), PACK / 'report.json', PACK / 'catalogue.json', chain.MAIN_CONFIG,
                 lower.raw.CONFIG, lower.raw.POLICY, lower.fields.POLICY, chain.proof.POLICY,
                 k.public_gate.POLICY, checkout / 'deps/ckb-vm/Cargo.lock', lower.RAW_DIR / 'crate/Cargo.lock'}
        paths.update(Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                     and Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
        report['inputs_before'] = {str(path): sha(path) for path in sorted(paths)}
        report['tool_sources_before'] = {}
        for label, family, patch_name in VARIANTS:
            dest = out / 'sources' / label; dest.parent.mkdir(parents=True, exist_ok=True)
            stage('clone-' + label.replace('/', '-'), ['git', 'clone', '--no-hardlinks', '--no-checkout',
                  payload / 'sources' / (family + '.bundle'), dest])
            stage('checkout-' + label.replace('/', '-'), ['git', 'checkout', '--detach', catalogue['source_commits'][family]], dest)
            stage('fsck-' + label.replace('/', '-'), ['git', 'fsck', '--full', '--strict'], dest)
            patch = payload / 'patches' / patch_name if patch_name else None
            if patch:
                stage('patch-' + label.replace('/', '-'), ['git', 'apply', patch], dest)
            if family == 'aeneas':
                ml = dest / 'charon'
                stage('clone-ml-' + label.replace('/', '-'), ['git', 'clone', '--no-hardlinks', '--no-checkout',
                      payload / 'sources/charon.bundle', ml])
                stage('checkout-ml-' + label.replace('/', '-'), ['git', 'checkout', '--detach', chain.charon.COMMIT], ml)
                stage('fsck-ml-' + label.replace('/', '-'), ['git', 'fsck', '--full', '--strict'], ml)
            report['tool_sources_before'][label] = tool_source(dest, family, patch)
        report['tool_sources_restored'] = True
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', public['rust_toolchain'], 'rustc']) == components['rustc'], 'private Rust path drift')
        require('commit-hash: ' + public['rust_commit'] in stage('rust-version', [components['rustc'], '-vV']), 'private Rust version drift')
        for side, prefix in (('base', payload / 'bin/base'), ('public', payload / 'bin')):
            require(stage(side + '-charon-version', [prefix / 'charon', 'version']) == main['charon'], 'packaged Charon version drift')
            require(stage(side + '-aeneas-version', [*opam, prefix / 'aeneas', '-version']) == components['tools'][side]['aeneas_version'], 'packaged Aeneas version drift')
        require(stage('join-aeneas-version', [*opam, payload / 'bin/join/aeneas', '-version']) == low['join_binary']['version'], 'packaged join version drift')
        outer = out / 'outer'; outer.mkdir()
        for name in ('lib.rs', 'Cargo.lock'): shutil.copyfile(payload / 'harness' / name, outer / name)
        (outer / 'Cargo.toml').write_text(harness.manifest(outer, checkout))
        report['outer_before'] = harness.verify(outer, checkout)
        factory = out / 'factory'; factory.mkdir()
        (factory / 'Cargo.toml').write_text('[package]\nname = "raw-add-decoder-connection"\nversion = "0.0.0"\nedition = "2024"\n[workspace]\n[dependencies]\nckb-vm = { path = ' +
            json.dumps(str(checkout / 'deps/ckb-vm')) + ' }\n[lib]\npath = ' + json.dumps(str(checkout / 'proof/lean/decoder/FactoryRoot.rs')) + '\n')
        shutil.copyfile(lower.RAW_DIR / 'crate/Cargo.lock', factory / 'Cargo.lock')
        require(sha(factory / 'Cargo.lock') == rp['extraction_cargo_lock_sha256'], 'factory lock drift')
        report['factory_before'] = {n: sha(factory / n) for n in ('Cargo.toml', 'Cargo.lock')}
        for label, cwd in (('main', checkout), ('public', outer), ('fields', checkout / 'deps/ckb-vm'), ('factory', factory)):
            stage('fetch-' + label, ['cargo', 'fetch', '--locked', '--target', public['target']], cwd)
        env['CARGO_NET_OFFLINE'] = 'true'
        iterator = read(payload / 'llbc/FnPtrFullMir.llbc'); sysroot = payload / 'sysroot'
        roots = [('main', 'CkbVmProduction'), ('public', 'OuterClosedDepsV3'), ('iterator', 'FnPtrFullMir'),
                 ('fields', 'LocalFields'), ('factory', 'FactoryScoped'), ('mini', 'MiniComplete')]
        for kind, stem in roots:
            is_public = kind in ('public', 'iterator')
            env = clear_public_flags(env, public['aeneas_env'] if is_public else {})
            folder = out / 'extraction' / kind; folder.mkdir(parents=True)
            llbc = folder / (stem + '.llbc')
            cwd = checkout / 'crates/proof-extract' if kind == 'main' else outer if kind == 'public' else checkout / 'deps/ckb-vm' if kind == 'fields' else factory if kind == 'factory' else out
            frontend = payload / ('bin/charon' if is_public else 'bin/base/charon')
            command = (chain.extraction_command(kind, frontend, llbc, sysroot, checkout, main, public, iterator)
                       if kind in ('main', 'public', 'iterator') else lower.extraction_command(stem, frontend, llbc, sysroot, checkout, raw))
            stage('extract-' + kind, command, cwd)
            options = chain.previous.candidate_options(read(payload / 'llbc' / (stem + '.llbc')), read(llbc), sysroot)
            if kind in ('main', 'public'):
                args = (main if kind == 'main' else public)['aeneas_args']
            elif kind == 'iterator': args = ['-backend', 'lean', '-abort-on-error', '-no-progress-bar', '-checks', '-sequential']
            elif kind == 'fields': args = ['-backend', 'lean', '-abort-on-error', '-no-progress-bar', '-namespace', 'RawDecodeExtract']
            else: args = [*raw['aeneas_args'], *(['-namespace', raw['namespace']] if kind == 'factory' else [])]
            translator = payload / ('bin/aeneas' if is_public else 'bin/join/aeneas' if kind in ('factory', 'mini') else 'bin/base/aeneas')
            stage('translate-' + kind, [*opam, translator, *args, '-dest', folder / 'generated', llbc], cwd)
            model = folder / 'generated' / (stem + '.lean')
            row = {'llbc': str(llbc), 'llbc_sha256': sha(llbc), 'model': str(model), 'raw_sha256': sha(model), 'option_comparison': options}
            report['models'][stem] = row; save()
            row['identity'] = model_check(stem, model, payload / 'models' / (stem + '.lean'), checkout, cwd)
        env = clear_public_flags(env, {})
        stage('strict-join-negative', [*opam, payload / 'bin/join/aeneas', *raw['aeneas_args'], '-strict-joins',
              '-dest', out / 'strict-negative', out / 'extraction/mini/MiniComplete.llbc'], strict=True)
        report.update(rust_reextracted=True, strict_join_rejected=True)
        require(chain.snapshot.capture(checkout) == state and harness.verify(outer, checkout) == report['outer_before'], 'CKB/harness drift')
        require({n: sha(factory / n) for n in report['factory_before']} == report['factory_before'], 'factory harness drift')
        for label, family, patch_name in VARIANTS:
            require(tool_source(out / 'sources' / label, family, payload / 'patches' / patch_name if patch_name else None) ==
                    report['tool_sources_before'][label], 'restored tool source drift')
        require(package.verify(payload, catalogue) == report['payload_before'], 'candidate payload drift')
        require(chain.verify_components() == components, 'private tool installation drift')
        report['inputs_after'] = {str(path): sha(path) for path in sorted(paths)}
        require(report['inputs_before'] == report['inputs_after'], 'input/config/policy drift')
        report['status'] = 'candidate_payload_six_roots_reextracted_sources_restored_admission_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = chain.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-input-reextraction-', dir=package.BASE))
    print(out, flush=True)
    sys.exit(run(out))
