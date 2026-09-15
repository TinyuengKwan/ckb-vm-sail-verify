#!/usr/bin/env python3
"""Original fnptr qualification with rebuilt tools and explicit installed std.

Not the full-MIR iterator-entry proof: that is a separate public kernel chain.
Fresh Rust extraction and model/proof compilation; pinned support cache reused.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_rebuilt_borrows as borrow
from probes import probe_rebuilt_public_kernel as kernel
from experiments import probe_decoder_fnptr as original

chain, lower, k = borrow.chain, borrow.lower, borrow.k
require, sha, read = borrow.require, borrow.sha, borrow.read
FIXTURES = original.FIXTURES
REASONS = {'borrow': 'locally quantified regions', 'abi': 'Unsupported function pointer signature',
           'static_result': 'Borrowed function pointer result', 'unsafe': 'Unsupported function pointer signature',
           'zero': 'Unsupported function pointer signature'}


def rejection(code, output, expected, wanted):
    require(type(code) is int and code == wanted and re.search(expected, output) is not None,
            'missing intended semantic rejection')
    # Intended Aeneas rejections themselves print an Uncaught exception: Failure.
    # Identifier names such as callback_panic are not panic diagnostics.
    require(not re.search(r'unknownIdentifier|unknown identifier|unknown namespace|unknown module|'
                          r'unknown constant|object file .* does not exist|failed to import|'
                          r'maximum.*(?:heartbeats|recursion)|out of memory|Stack overflow|'
                          r'deterministic timeout|timed out|Internal error', output, re.I) and
            'PANIC' not in output and not re.search(r'(?mi)^panic\b', output),
            'infrastructure/internal failure is not semantic rejection')


def axioms(output):
    result = {}
    for line in output.splitlines():
        match = re.fullmatch(r"'(FnPtrRegression\.[^']+)' (.*)", line)
        if not match:
            continue
        name, tail = match.groups()
        require(name not in result, 'duplicate theorem audit')
        if tail == 'does not depend on any axioms':
            row = []
        else:
            parsed = re.fullmatch(r'depends on axioms: \[(.*)\]', tail)
            require(parsed is not None, 'malformed theorem audit')
            row = parsed[1].split(', ') if parsed[1] else []
        require(set(row) <= original.STANDARD, 'unaccepted theorem axiom')
        result[name] = row
    require(len(result) == 16, 'incomplete fnptr theorem audit')
    return result


def swapped(model):
    return borrow.n.mutate(model, 'f bits version', 'f version bits')


def fixture_options(reference, fresh, sysroot, crate_name):
    """Shared original extraction flags; each fixture has its own crate name.

    The old qualification did not hash negative LLBC files. Do not use their
    present contents as historical evidence: the positive LLBC is hash-bound,
    and the original command uses identical flags for all six Rust fixtures.
    """
    require(fresh['has_errors'] is False and fresh['charon_version'] == reference['charon_version'],
            'frontend errors or format drift')
    old, new = reference['translated'], fresh['translated']
    require(old['crate_name'] == 'fnptr_cases' and new['crate_name'] == crate_name and
            new['target_information'] == old['target_information'], 'fixture crate/target changed')
    old_options, new_options = dict(old['options']), dict(new['options'])
    require(old_options.pop('sysroot') is None and new_options.pop('sysroot') == str(sysroot.resolve()),
            'unexpected std selection')
    old_options.pop('dest_file'); new_options.pop('dest_file')
    require(old_options == new_options, 'original common extraction flags changed')
    return {'actual_crate': crate_name, 'explicit_installed_std': str(sysroot.resolve()),
            'original_common_options_preserved': True, 'llbc_ast_equivalence_claimed': False,
            'unbound_historical_negative_llbc_used': False}


def run(out):
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [], 'llbc': {},
              'rust_reextracted': False, 'kernel_executed': False, 'tool_adopted': False,
              'policy_changed': False, 'clean_room_claimed': False, 'release_claimed': False,
              'support_compiled_cache_reused': True, 'full_mir_sysroot_used': False,
              'full_iterator_entry_proof_claimed': False, 'full_translator_qualification_claimed': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, args, run_env=None, reject=None, wanted=2):
        actual_env = run_env or env
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(out), 'started_at': chain.now(),
               'lean_path': actual_env.get('LEAN_PATH'), 'expected_rejection': reject,
               'expected_exit_code': wanted if reject else 0}
        report['stages'].append(row); save()
        print('==> rebuilt-fnptr: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                proc = subprocess.run(row['argv'], cwd=out, env=actual_env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = proc.returncode
            output = log.read_text(errors='replace')
            if reject:
                rejection(proc.returncode, output, reject, wanted)
            else:
                kernel.check_success(proc.returncode, output)
        finally:
            row.update(finished_at=chain.now(), log=log.name, log_sha256=sha(log)); save()
        return output.strip()

    try:
        save()
        components = chain.verify_components(); report['components'] = components
        pp = kernel.pinned(borrow.public.POLICY, kernel.PUBLIC_SHA)
        require(borrow.public.sources() == pp['sources'], 'formal public sources drift')
        baseline_path = chain.PUBLIC / 'qualification/fnptr.json'
        baseline = kernel.pinned(baseline_path, pp['qualification']['fnptr']['sha256'])
        require(baseline['status'] == 'experimental-regressions-pass' and baseline['open_iterator_entry'] is True,
                'original qualification boundary drift')
        fixture_names = {'FnPtrProof.lean', 'fnptr_cases.rs', 'aeneas-fnptr-experimental.patch'} | {
            'fnptr_' + label + '_rejected.rs' for label in REASONS}
        require(set(baseline['fixtures']) == fixture_names | {'README.md'}, 'fixture inventory changed')
        for name in fixture_names:
            digest = baseline['fixtures'][name]
            require(sha(FIXTURES / name) == digest, 'fnptr fixture drift: ' + name)
        report['historical_readme_not_used_as_compiler_or_proof_input'] = {
            'recorded_sha256': baseline['fixtures']['README.md'], 'current_sha256': sha(FIXTURES / 'README.md')}
        original_llbc = Path(baseline['directory']) / 'FnPtrCases.llbc'
        require(sha(original_llbc) == baseline['llbc_sha256'], 'original positive LLBC drift')
        reference = read(original_llbc)
        lr = kernel.pinned(k.ORIGIN / 'report.json', k.ORIGIN_SHA)
        join = Path(lr['join_binary']['path'])
        chain.executable(join, lr['join_binary']['sha256'])
        require(lower.check_join_source(k.ORIGIN / 'aeneas-source') == lr['join_source_before'], 'join source drift')
        cache = kernel.pinned(borrow.n.ORIGIN / 'report.json', borrow.n.ORIGIN_SHA)
        paths = [Path(path) for path in cache['compiled_dependencies_before']]
        print('==> rebuilt-fnptr: verify-support-cache', flush=True)
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache drift')
        install = read(chain.MIR.RUST_REPORT)
        elan = Path(install['private_homes']['ELAN_HOME'])
        require(chain.MIR.rust.inventory(elan) == install['installed_closures']['elan'], 'private Lean installation drift')
        lean = Path(cache['lean']['path'])
        require(sha(lean) == cache['lean']['sha256'], 'Lean binary drift')
        inputs = {Path(__file__), Path(kernel.__file__), Path(original.__file__), Path(borrow.__file__),
                  baseline_path, borrow.public.POLICY, lower.proof.POLICY, lower.raw.POLICY,
                  k.ORIGIN / 'report.json', borrow.n.ORIGIN / 'report.json', original_llbc}
        inputs |= {FIXTURES / name for name in baseline['fixtures']}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        report['formal_generated_before'] = lower.proof.generated_evidence(read(lower.proof.POLICY))
        env = chain.environment(out, components)
        env.update(baseline['experimental_env']); env['CARGO_NET_OFFLINE'] = 'true'
        require(baseline['experimental_env'] == {'AENEAS_FACTOR_RETURN_GUARDS': '1',
                'AENEAS_EXTRACT_TRY_FROM_INT_ERROR': '1'}, 'experimental flag drift')
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env['LEAN_ABORT_ON_PANIC'] = '1'
        report['environment'] = {key: env[key] for key in ['RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME',
            'CARGO_TARGET_DIR', 'OPAMROOT', 'OPAMSWITCH', 'AENEAS_FACTOR_RETURN_GUARDS', 'AENEAS_EXTRACT_TRY_FROM_INT_ERROR']}
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'old Cargo state reused')
        report['cargo_cache_and_target_initially_absent'] = True
        charon = components['tools']['base']['charon']['path']
        aeneas = components['tools']['public']['aeneas']['path']
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        stage('charon-version', [charon, 'version'])
        require(stage('aeneas-version', [*opam, aeneas, '-version']) == components['tools']['public']['aeneas_version'], 'Aeneas version drift')
        require(stage('join-version', [*opam, join, '-version']) == lr['join_binary']['version'], 'join version drift')
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) == components['rustc'], 'Rust compiler escape')
        sysroot = Path(components['rustc']).parent.parent
        require(Path(stage('installed-sysroot', [components['rustc'], '--print', 'sysroot'])).resolve() == sysroot.resolve(), 'installed sysroot escape')
        report['installed_std_sysroot'] = str(sysroot)
        report['std_identity_basis'] = 'entire private Rust installation closure; ordinary installed std, not full-MIR'
        source_dir = out / FIXTURES.relative_to(ROOT); source_dir.mkdir(parents=True)
        for name in fixture_names:
            shutil.copyfile(FIXTURES / name, source_dir / name)
        models = out / 'models'; models.mkdir()

        def extract(label, filename, stem):
            llbc = out / (stem + '.llbc')
            stage('charon-' + label, [charon, 'rustc', '--preset=aeneas', '--sysroot', sysroot,
                  '--include', 'core::option::_', '--dest-file', llbc, '--',
                  source_dir.relative_to(out) / filename, '--crate-type', 'lib'])
            require(read(llbc)['has_errors'] is False, 'frontend errors')
            options = fixture_options(reference, read(llbc), sysroot, Path(filename).stem)
            report['llbc'][label] = {'sha256': sha(llbc), 'common_options_reference_sha256': sha(original_llbc), 'options': options}
            return llbc

        def translate(name, llbc, destination, translator=aeneas, reject=None):
            return stage(name, [*opam, translator, '-backend', 'lean', '-abort-on-error', '-no-progress-bar',
                         '-checks', '-dest', destination, llbc], reject=reject)

        llbc = extract('cases', 'fnptr_cases.rs', 'FnPtrCases')
        translate('join-tool-negative', llbc, out / 'join-negative', join, 'Arrow types are not supported yet')
        translate('candidate', llbc, models)
        model = models / 'FnPtrCases.lean'
        require(sha(model) == baseline['model_sha256'], 'whole generated fnptr model changed')
        require(bool(re.search(r'axiom SharedAVec\..*into_iter', model.read_text())) is True, 'original opaque iterator boundary changed')
        report['model_sha256'] = sha(model); report['open_iterator_entry'] = True
        proof = models / 'FnPtrProof.lean'; shutil.copyfile(source_dir / proof.name, proof)
        require(kernel.compiled_files(models) == [], 'initial compiled models not empty')
        report['initial_compiled_modules'] = 0
        env['LEAN_PATH'] = os.pathsep.join(map(str, [models, *paths]))
        report['lean_path'] = env['LEAN_PATH']; report['lean'] = cache['lean']
        stage('kernel-model', [lean, '--root=' + str(models), model, '-o', models / 'FnPtrCases.olean'])
        audit = axioms(stage('kernel-regressions', [lean, proof]))
        require(audit == baseline['regression_axioms'], 'original theorem/axiom set changed')
        report['regression_axioms'] = audit
        bad = out / 'swapped-call-arguments'; bad.mkdir()
        (bad / model.name).write_text(swapped(model.read_text()))
        bad_env = dict(env, LEAN_PATH=str(bad) + os.pathsep + env['LEAN_PATH'])
        stage('kernel-mutated-model', [lean, '--root=' + str(bad), bad / model.name, '-o', bad / 'FnPtrCases.olean'], run_env=bad_env)
        stage('wrong-arguments-negative', [lean, proof], run_env=bad_env,
              reject=r'rfl.*failed|Tactic.*rfl.*failed|Type mismatch', wanted=1)
        report['mutated_model_sha256'] = sha(bad / model.name)
        # Translator stages do not load Lean cache, and the recorded environment
        # makes that distinction explicit.
        env.pop('LEAN_PATH')
        for label, reason in REASONS.items():
            negative = extract(label, 'fnptr_' + label + '_rejected.rs', label)
            translate('negative-' + label, negative, out / ('negative-' + label), reject=reason)
        report['rust_reextracted'] = True
        for name in fixture_names:
            digest = baseline['fixtures'][name]
            require(sha(source_dir / name) == digest, 'copied fixture changed')
        require(sha(model) == baseline['model_sha256'] and sha(proof) == baseline['fixtures'][proof.name], 'model/proof changed')
        for label, row in report['llbc'].items():
            require(sha(out / (('FnPtrCases' if label == 'cases' else label) + '.llbc')) == row['sha256'], 'LLBC changed')
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache changed')
        require(chain.verify_components() == components, 'component closure changed')
        require(lower.check_join_source(k.ORIGIN / 'aeneas-source') == lr['join_source_before'], 'join source changed')
        chain.executable(join, lr['join_binary']['sha256'])
        require(chain.MIR.rust.inventory(elan) == install['installed_closures']['elan'], 'Lean installation changed')
        require(lower.proof.generated_evidence(read(lower.proof.POLICY)) == report['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        report.update(status='rebuilt_fnptr_regressions_checked_admission_pending', kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = chain.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-fnptr-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
