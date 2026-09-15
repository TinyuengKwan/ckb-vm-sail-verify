#!/usr/bin/env python3
"""Reextract original owned-error/reference guards and run their original proofs.

New base tools for the factored reference, new public tools for the original
guard. Full-MIR explicit; model/proof cache empty, support cache verified/reused.
This fixture equivalence is not a general compiler transformation proof.
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
from probes import probe_rebuilt_public_kernel as kernel
from probes import probe_rebuilt_charon_ui as ui

chain, k, lower = kernel.chain, kernel.k, kernel.lower
require, sha, read = kernel.require, kernel.sha, kernel.read
FIXTURES = ROOT / 'proof/lean/decoder/toolchain/branch-experimental'
OWNED = ROOT / 'proof/lean/decoder/toolchain/cfg-experimental/GuardedOwnedError.rs'
OWNED_SHA = 'a2c6af305057d61aa01354f87502c9ea9e2ec9dd3b8024dfa01fe1cabe5281d2'
REFERENCE_SHA = '7def62b5f550d6e14e5fac3f2b3417b229c56e9a41b46d5fc135134f0e62f720'
PROOFS = ['GuardEquivalence', 'GuardCounterexample', 'RejectWrongGuard']
NEGATIVE = r'Tactic.*rfl.*failed'


def axioms(output, name):
    rows = re.findall(r"(?m)^'" + re.escape(name) + r"' (.*)$", output)
    require(len(rows) == 1, 'missing or duplicate guard theorem audit')
    if rows[0] == 'does not depend on any axioms':
        return []
    match = re.fullmatch(r'depends on axioms: \[(.*)\]', rows[0])
    require(match is not None, 'malformed guard theorem audit')
    values = match[1].split(', ') if match[1] else []
    require(set(values) <= k.STANDARD, 'unaccepted guard theorem axiom')
    return values


def options(llbc, sysroot, crate):
    require(llbc['has_errors'] is False and llbc['charon_version'] == '0.1.247', 'frontend error or format drift')
    translated = llbc['translated']
    require(translated['crate_name'] == crate, 'wrong guard crate')
    config = dict(translated['options'])
    require(config['sysroot'] == str(sysroot.resolve()) and config['preset'] == 'Aeneas', 'wrong extraction configuration')
    for name in ('start_from', 'start_from_if_exists', 'start_from_attribute', 'include', 'opaque', 'exclude', 'rustc_args'):
        require(config[name] == [], 'unexpected selection or compiler flags')
    for name in ('skip_borrowck', 'no_typecheck', 'no_normalize', 'ullbc', 'monomorphize', 'no_serialize'):
        require(config[name] is False, 'disabled check or wrong extraction mode')
    config.pop('dest_file')
    return {'options': config, 'target_information': translated['target_information']}


def mutant(model):
    # The only behavioral change is the first return guard. Rename the outer
    # namespace solely to allow simultaneous import; do not alter the original.
    require(model.splitlines().count('      if return_guard') == 1, 'return guard line not unique')
    renamed = k.archived_namespace(model.encode(), 'guarded_owned_error', 'GuardedMutant').decode()
    return kernel.negatives.mutate(renamed, '\n      if return_guard\n', '\n      if !return_guard\n')


def run(out):
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [], 'models': {},
              'rust_reextracted': False, 'kernel_executed': False, 'tool_adopted': False,
              'policy_changed': False, 'clean_room_claimed': False, 'release_claimed': False,
              'support_compiled_cache_reused': True, 'full_mir_sysroot_used': True,
              'general_transform_correctness_claimed': False, 'historical_llbc_or_model_identity_claimed': False,
              'reference_fixture_used_as_production_replacement': False}
    env = None

    def save():
        kernel.gate.write_json(out / 'report.json', report)

    def stage(name, args, run_env=None, reject=None):
        actual_env = run_env or env
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(out), 'started_at': chain.now(),
               'lean_path': actual_env.get('LEAN_PATH'), 'expected_rejection': reject,
               'aeneas_env': {key: value for key, value in actual_env.items() if key.startswith('AENEAS')}}
        report['stages'].append(row); save()
        print('==> rebuilt-guard: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=actual_env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = result.returncode
            output = log.read_text(errors='replace')
            if reject:
                kernel.check_rejection(result.returncode, output, reject)
            else:
                kernel.check_success(result.returncode, output)
        finally:
            row.update(finished_at=chain.now(), log=log.name, log_sha256=sha(log)); save()
        return output.strip()

    try:
        save()
        components = chain.verify_components(); report['components'] = components
        pp = kernel.pinned(kernel.public_gate.POLICY, kernel.PUBLIC_SHA)
        require(kernel.public_gate.sources() == pp['sources'], 'formal public source drift')
        old_ui = kernel.pinned(ui.OLD, ui.OLD_SHA)
        relative = Path('charon/tests/ui/control-flow/guarded-owned-error.rs')
        require(old_ui['fixtures_before'][relative.as_posix()] == OWNED_SHA == sha(OWNED), 'original owned fixture identity')
        reference = FIXTURES / 'GuardedFactored.rs'
        require(sha(reference) == REFERENCE_SHA, 'reference fixture identity')
        # Bind the reference to the main repository baseline, not an unbound
        # historical generated model or an arbitrary replacement Rust program.
        committed = subprocess.check_output(['git', 'show', '872d225dc4e16c449be37d92761b20c6aefe853c:' +
                                             str(reference.relative_to(ROOT))], cwd=ROOT, timeout=60)
        require(kernel.gate.digest(committed) == REFERENCE_SHA, 'committed reference differs')
        old_log = chain.PUBLIC / 'qualification/guard_equivalence.log'
        require(sha(old_log) == pp['qualification']['guard_equivalence']['sha256'], 'historical guard qualification log drift')
        expected = axioms(old_log.read_text(), 'guarded_equivalence')
        cache = kernel.pinned(kernel.negatives.ORIGIN / 'report.json', kernel.negatives.ORIGIN_SHA)
        paths = [Path(path) for path in cache['compiled_dependencies_before']]
        print('==> rebuilt-guard: verify-support-cache', flush=True)
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache drift')
        installation = read(chain.MIR.RUST_REPORT); elan = Path(installation['private_homes']['ELAN_HOME'])
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'private Lean closure drift')
        lean = Path(cache['lean']['path']); report['lean'] = cache['lean']
        require(sha(lean) == cache['lean']['sha256'], 'Lean compiler drift')
        inputs = {Path(__file__), Path(kernel.__file__), Path(ui.__file__), OWNED, reference, old_log, ui.OLD,
                  kernel.public_gate.POLICY, kernel.gate.POLICY, lower.raw.POLICY, lower.fields.POLICY,
                  kernel.negatives.ORIGIN / 'report.json'} | {FIXTURES / (stem + '.lean') for stem in PROOFS}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        report['formal_generated_before'] = kernel.gate.generated_evidence(read(kernel.gate.POLICY))
        env = chain.environment(out, components); env['CARGO_NET_OFFLINE'] = 'true'
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env['LEAN_ABORT_ON_PANIC'] = '1'
        report['environment'] = {key: env[key] for key in ('RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME',
            'CARGO_TARGET_DIR', 'OPAMROOT', 'OPAMSWITCH')}
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'initial Cargo state not empty')
        report['cargo_cache_and_target_initially_absent'] = True
        (out / relative).parent.mkdir(parents=True); shutil.copyfile(OWNED, out / relative)
        shutil.copyfile(reference, out / reference.name)
        models = out / 'models'; models.mkdir()
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        for side in ('base', 'public'):
            stage(side + '-charon-version', [components['tools'][side]['charon']['path'], 'version'])
            require(stage(side + '-aeneas-version', [*opam, components['tools'][side]['aeneas']['path'], '-version']) ==
                    components['tools'][side]['aeneas_version'], 'Aeneas version')
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) == components['rustc'], 'Rust compiler escape')
        configs = []
        for side, stem, source, namespace in [('base', 'GuardedFactored', Path(reference.name), 'GuardedFactored'),
                                             ('public', 'OwnedCleanup', relative, 'guarded_owned_error')]:
            llbc = out / (stem + '.llbc')
            stage('charon-' + stem, [components['tools'][side]['charon']['path'], 'rustc', '--preset=aeneas',
                  '--sysroot', components['sysroot'], '--dest-file', llbc, '--', source, '--crate-type=lib'])
            config = options(read(llbc), Path(components['sysroot']), namespace); configs.append(config)
            translating_env = dict(env)
            if side == 'public':
                translating_env.update(AENEAS_FACTOR_RETURN_GUARDS='1', AENEAS_EXTRACT_TRY_FROM_INT_ERROR='1')
            stage('aeneas-' + stem, [*opam, components['tools'][side]['aeneas']['path'], '-backend', 'lean',
                  '-abort-on-error', '-no-progress-bar', '-checks', '-namespace', namespace, '-dest', models, llbc],
                  run_env=translating_env)
            report['models'][stem] = {'llbc_sha256': sha(llbc), 'model_sha256': sha(models / (stem + '.lean')), 'metadata': config}
        require(configs[0] == configs[1], 'guard/reference target or extraction options differ')
        (models / 'OwnedGuardMutant.lean').write_text(mutant((models / 'OwnedCleanup.lean').read_text()))
        for stem in PROOFS:
            shutil.copyfile(FIXTURES / (stem + '.lean'), models / (stem + '.lean'))
        report['model_and_proof_sources_before'] = {path.name: sha(path) for path in sorted(models.glob('*.lean'))}
        require(kernel.compiled_files(models) == [], 'initial compiled models not empty'); report['initial_compiled_modules'] = 0
        env['LEAN_PATH'] = os.pathsep.join(map(str, [models, *paths])); report['lean_path'] = env['LEAN_PATH']
        audits = {}
        for stem in ('GuardedFactored', 'OwnedCleanup', 'OwnedGuardMutant', 'GuardEquivalence', 'GuardCounterexample'):
            output = stage('kernel-' + stem, [lean, '--root=' + str(models), models / (stem + '.lean'), '-o', models / (stem + '.olean')])
            if stem in ('GuardEquivalence', 'GuardCounterexample'):
                name = 'guarded_equivalence' if stem == 'GuardEquivalence' else 'wrong_guard_changes_result'
                audits[name] = axioms(output, name)
        require(audits['guarded_equivalence'] == expected, 'original guard theorem axiom list changed')
        report['regression_axioms'] = audits
        stage('negative-wrong-guard', [lean, models / 'RejectWrongGuard.lean'], reject=NEGATIVE)
        require(sha(out / relative) == OWNED_SHA and sha(out / reference.name) == REFERENCE_SHA, 'copied Rust source changed')
        require({path.name: sha(path) for path in models.glob('*.lean')} == report['model_and_proof_sources_before'], 'model/proof source changed')
        for stem, row in report['models'].items():
            require(sha(out / (stem + '.llbc')) == row['llbc_sha256'], 'LLBC changed')
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache changed')
        require(chain.verify_components() == components, 'tool/source/installation closure changed')
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean installation changed')
        require(kernel.gate.generated_evidence(read(kernel.gate.POLICY)) == report['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_after'] == report['inputs_before'], 'input/policy changed')
        report.update(status='rebuilt_guard_regression_checked_admission_pending', rust_reextracted=True, kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = chain.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-guard-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
