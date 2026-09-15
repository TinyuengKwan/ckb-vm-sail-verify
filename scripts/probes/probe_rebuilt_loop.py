#!/usr/bin/env python3
"""Reextract the original loop-jump regression with both rebuilt Charons.

Same rebuilt public Aeneas and explicit full-MIR on both sides. Original Lean
proof bytes, fresh model/proof compilation, explicitly reused support cache.
No claim of general compiler correctness, tool adoption or clean-room release.
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
FIXTURES = ROOT / 'proof/lean/decoder/toolchain/cfg-experimental'
SOURCE = Path('charon/tests/ui/control-flow/issue-1051-missing-loop-jump.rs')
SOURCE_SHA = '74978d0bf2d45f8246166e37ebd66646c680606d085042b6fe0a381831208dce'
NAMES = ['CleanupRegression.' + name for name in ('loop_body_equal', 'loop_equal', 'entry_equal', 'entry_returns')]


def axioms(output):
    rows = re.findall(r"(?m)^'(CleanupRegression\.[^']+)' depends on axioms: \[([^\n]*)\]$", output)
    require(len(rows) == 4 and [name for name, _ in rows] == NAMES, 'loop theorem audit incomplete or duplicate')
    result = {name: value.split(', ') for name, value in rows}
    require(all(set(value) <= k.STANDARD for value in result.values()), 'unaccepted loop axiom')
    return result


def options(llbc, sysroot):
    require(llbc['has_errors'] is False and llbc['charon_version'] == '0.1.247', 'frontend error or format drift')
    translated = llbc['translated']
    require(translated['crate_name'] == 'issue_1051_missing_loop_jump', 'wrong loop crate')
    config = dict(translated['options'])
    require(config['sysroot'] == str(sysroot.resolve()) and config['preset'] == 'Aeneas', 'wrong extraction configuration')
    for name in ('start_from', 'start_from_if_exists', 'start_from_attribute', 'include', 'opaque', 'exclude', 'rustc_args'):
        require(config[name] == [], 'unexpected selection or compiler flags')
    for name in ('skip_borrowck', 'no_typecheck', 'no_normalize', 'ullbc', 'monomorphize', 'no_serialize'):
        require(config[name] is False, 'disabled check or wrong extraction mode')
    config.pop('dest_file')
    return {'options': config, 'target_information': translated['target_information']}


def run(out):
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [], 'models': {},
              'rust_reextracted': False, 'kernel_executed': False, 'tool_adopted': False,
              'policy_changed': False, 'clean_room_claimed': False, 'release_claimed': False,
              'support_compiled_cache_reused': True, 'full_mir_sysroot_used': True,
              'general_transform_correctness_claimed': False, 'historical_llbc_or_model_identity_claimed': False}
    env = None

    def save():
        kernel.gate.write_json(out / 'report.json', report)

    def stage(name, args, reject=None):
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(out), 'started_at': chain.now(),
               'lean_path': env.get('LEAN_PATH'), 'expected_rejection': reject}
        report['stages'].append(row); save()
        print('==> rebuilt-loop: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=env, stdout=stream,
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
        require(old_ui['fixtures_before'][SOURCE.as_posix()] == SOURCE_SHA, 'original loop fixture identity')
        old_log = chain.PUBLIC / 'qualification/loop_equivalence.log'
        require(sha(old_log) == pp['qualification']['loop_equivalence']['sha256'], 'historical qualification log drift')
        expected_axioms = axioms(old_log.read_text())
        charon_report = read(Path(components['reports']['charon']['path']))
        source = Path(charon_report['sides']['base']['source']) / SOURCE
        require(sha(source) == SOURCE_SHA, 'actual rebuilt compiler fixture drift')
        cache = kernel.pinned(kernel.negatives.ORIGIN / 'report.json', kernel.negatives.ORIGIN_SHA)
        paths = [Path(path) for path in cache['compiled_dependencies_before']]
        print('==> rebuilt-loop: verify-support-cache', flush=True)
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache drift')
        installation = read(chain.MIR.RUST_REPORT)
        elan = Path(installation['private_homes']['ELAN_HOME'])
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'private Lean closure drift')
        lean = Path(cache['lean']['path']); report['lean'] = cache['lean']
        require(sha(lean) == cache['lean']['sha256'], 'Lean compiler drift')
        inputs = {Path(__file__), Path(kernel.__file__), Path(ui.__file__), source, old_log, ui.OLD,
                  kernel.public_gate.POLICY, kernel.gate.POLICY, lower.raw.POLICY, lower.fields.POLICY,
                  kernel.negatives.ORIGIN / 'report.json', FIXTURES / 'LoopJumpProof.lean', FIXTURES / 'LoopJumpNegative.lean'}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        report['formal_generated_before'] = kernel.gate.generated_evidence(read(kernel.gate.POLICY))
        env = chain.environment(out, components)
        env.update(AENEAS_FACTOR_RETURN_GUARDS='1', AENEAS_EXTRACT_TRY_FROM_INT_ERROR='1', CARGO_NET_OFFLINE='true')
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env['LEAN_ABORT_ON_PANIC'] = '1'
        report['environment'] = {key: env[key] for key in ('RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME',
            'CARGO_TARGET_DIR', 'OPAMROOT', 'OPAMSWITCH', 'AENEAS_FACTOR_RETURN_GUARDS', 'AENEAS_EXTRACT_TRY_FROM_INT_ERROR')}
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'initial Cargo state not empty')
        report['cargo_cache_and_target_initially_absent'] = True
        relative = Path(*SOURCE.parts[1:]); fixture = out / relative
        fixture.parent.mkdir(parents=True); shutil.copyfile(source, fixture)
        models = out / 'models'; models.mkdir()
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        aeneas = components['tools']['public']['aeneas']['path']
        stage('base-charon-version', [components['tools']['base']['charon']['path'], 'version'])
        stage('public-charon-version', [components['tools']['public']['charon']['path'], 'version'])
        require(stage('aeneas-version', [*opam, aeneas, '-version']) == components['tools']['public']['aeneas_version'], 'Aeneas version')
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) == components['rustc'], 'Rust compiler escape')
        configs = []
        for side, label, namespace in [('base', 'Baseline', 'BaselineCfg'), ('public', 'Candidate', 'CandidateCfg')]:
            stem = 'LoopJump' + label; llbc = out / (stem + '.llbc')
            stage('charon-' + label, [components['tools'][side]['charon']['path'], 'rustc', '--preset=aeneas',
                  '--sysroot', components['sysroot'], '--dest-file', llbc, '--', relative, '--crate-type=lib'])
            config = options(read(llbc), Path(components['sysroot'])); configs.append(config)
            stage('aeneas-' + label, [*opam, aeneas, '-backend', 'lean', '-abort-on-error', '-no-progress-bar',
                  '-checks', '-namespace', namespace, '-dest', models, llbc])
            report['models'][stem] = {'llbc_sha256': sha(llbc), 'model_sha256': sha(models / (stem + '.lean')), 'metadata': config}
        require(configs[0] == configs[1], 'two sides used different target or extraction options')
        for stem in ('LoopJumpProof', 'LoopJumpNegative'):
            shutil.copyfile(FIXTURES / (stem + '.lean'), models / (stem + '.lean'))
        report['model_and_proof_sources_before'] = {path.name: sha(path) for path in sorted(models.glob('*.lean'))}
        require(kernel.compiled_files(models) == [], 'initial compiled models not empty')
        report['initial_compiled_modules'] = 0
        env['LEAN_PATH'] = os.pathsep.join(map(str, [models, *paths])); report['lean_path'] = env['LEAN_PATH']
        for stem in ('LoopJumpBaseline', 'LoopJumpCandidate', 'LoopJumpProof'):
            output = stage('kernel-' + stem, [lean, '--root=' + str(models), models / (stem + '.lean'), '-o', models / (stem + '.olean')])
        actual = axioms(output)
        require(actual == expected_axioms, 'original four theorem/axiom records changed')
        report['regression_axioms'] = actual
        stage('negative-wrong-loop-result', [lean, models / 'LoopJumpNegative.lean'], reject='Type mismatch')
        require(sha(fixture) == SOURCE_SHA, 'copied Rust source changed')
        require({path.name: sha(path) for path in sorted(models.glob('*.lean'))} == report['model_and_proof_sources_before'], 'model/proof source changed')
        for stem, row in report['models'].items():
            require(sha(out / (stem + '.llbc')) == row['llbc_sha256'], 'LLBC changed')
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache changed')
        require(chain.verify_components() == components, 'tool/source/installation closure changed')
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean installation changed')
        require(kernel.gate.generated_evidence(read(kernel.gate.POLICY)) == report['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_after'] == report['inputs_before'], 'input/policy changed')
        report.update(status='rebuilt_loop_regression_checked_admission_pending', rust_reextracted=True, kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = chain.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-loop-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
