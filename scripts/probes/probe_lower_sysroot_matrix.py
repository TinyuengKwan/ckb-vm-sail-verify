#!/usr/bin/env python3
"""Diagnostic Charon x sysroot matrix for the actual shared-closure fixture.

Explicit installed Rust std versus rebuilt full-MIR; never retroactively claims
which implicit sysroot an old run used. No kernel or tool/policy adoption.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_lower_translation_matrix as previous

lower = previous.lower
require, sha, read = lower.require, lower.sha, lower.read
ORIGIN, ORIGIN_SHA = previous.ORIGIN, previous.ORIGIN_SHA


def command(binary, sysroot, llbc, fixture):
    return [binary, 'rustc', '--preset=aeneas', '--sysroot', sysroot,
            '--include', 'core::option::_', '--dest-file', llbc, '--', fixture, '--crate-type', 'lib']


def check_options(original, fresh, sysroot):
    require(fresh['translated']['options']['sysroot'] == str(sysroot), 'wrong explicit sysroot')
    # Diagnostic option comparison only. Neither library identity is adopted.
    copied = {**fresh, 'translated': {**fresh['translated'], 'options': {**fresh['translated']['options'],
              'sysroot': original['translated']['options']['sysroot']}}}
    from decoder_public_source import check_reextraction
    check_reextraction(original, copied)


def run(out):
    report = {'status': 'running', 'started_at': lower.chain.now(), 'stages': [], 'cells': {},
              'kernel_executed': False, 'policy_changed': False, 'tool_adopted': False,
              'clean_room_claimed': False, 'release_claimed': False, 'rust_reextracted': False,
              'historical_implicit_sysroot_identified': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, args, cwd=out):
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(cwd), 'started_at': lower.chain.now()}
        report['stages'].append(row)
        save()
        print('==> lower-sysroot-matrix: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'sysroot matrix stage failed')
        finally:
            row.update(finished_at=lower.chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()

    try:
        require(sha(ORIGIN / 'report.json') == ORIGIN_SHA, 'lower report drift')
        origin = read(ORIGIN / 'report.json')
        components = lower.chain.verify_components()
        require(origin['components'] == components, 'component drift')
        config, policy = read(lower.raw.CONFIG), read(lower.proof.POLICY)
        old_env, old_binaries, _, _ = lower.proof.tools_and_environment(policy)
        del old_env
        tools = {'old': old_binaries['charon'], 'new': Path(components['tools']['base']['charon']['path'])}
        tool_hashes = {}
        for side in tools:
            for name in ('charon', 'charon-driver'):
                path = tools[side].with_name(name)
                expected = policy['tool_binaries'][name] if side == 'old' else components['tools']['base'][name]['sha256']
                require(sha(path) == expected, 'Charon executable drift')
                tool_hashes[str(path)] = expected
        translator = Path(origin['join_binary']['path'])
        lower.chain.executable(translator, origin['join_binary']['sha256'])
        require(lower.check_join_source(ORIGIN / 'aeneas-source') == origin['join_source_before'], 'join source drift')
        fixture = Path(origin['checkout']) / 'proof/lean/decoder/toolchain/decoder_shared_closure.rs'
        expected_fixture = read(lower.raw.POLICY)['sources']['proof/lean/decoder/toolchain/decoder_shared_closure.rs']
        require(sha(fixture) == expected_fixture, 'fixture source drift')
        report['fixture'] = {'path': str(fixture), 'sha256': expected_fixture}
        inputs = {Path(__file__), ORIGIN / 'report.json', lower.raw.CONFIG, lower.raw.POLICY,
                  lower.proof.POLICY, ORIGIN / 'MiniComplete.llbc', lower.RAW_DIR / 'MiniComplete.llbc'}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        report['tools'] = tool_hashes | {str(translator): origin['join_binary']['sha256']}
        env = lower.chain.environment(out, components)
        env['CARGO_NET_OFFLINE'] = 'true'
        rustc = stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc'])
        require(rustc == components['rustc'], 'wrong Rust compiler')
        default_root = stage('default-sysroot', [rustc, '--print', 'sysroot'])
        require(Path(default_root) == Path(rustc).parents[1], 'wrong installed std root')
        roots = {'installed': 'default', 'full-mir': components['sysroot']}
        report['sysroots'] = {'installed': default_root, 'full-mir': components['sysroot']}
        report['installed_rust_report_sha256'] = components['rust_report_sha256']
        report['full_mir_report_sha256'] = components['sysroot_report_sha256']
        opam = [components['opam']['bootstrap']['path'], 'exec',
                '--switch=' + components['opam']['switch'], '--set-switch', '--']
        archived = read(lower.RAW_DIR / 'MiniComplete.llbc')
        for root_side, sysroot in roots.items():
            for tool_side, binary in tools.items():
                label = root_side + '-' + tool_side
                directory = out / label
                directory.mkdir()
                llbc = directory / 'MiniComplete.llbc'
                stage('extract-' + label, command(binary, sysroot, llbc, fixture), directory)
                check_options(archived, read(llbc), sysroot)
                models = directory / 'models'
                stage('translate-' + label, [*opam, translator, *config['aeneas_args'], '-dest', models, llbc], directory)
                model = models / 'MiniComplete.lean'
                report['cells'][label] = {'llbc': str(llbc), 'llbc_sha256': sha(llbc), 'model': str(model),
                    'identity': lower.model_identity('MiniComplete', model, {}, read(lower.raw.POLICY))}
                save()
        report['same_sysroot_output_identical'] = {side:
            report['cells'][side + '-old']['identity']['raw_sha256'] == report['cells'][side + '-new']['identity']['raw_sha256']
            for side in roots}
        require(lower.chain.verify_components() == components, 'component changed')
        for path, digest in report['tools'].items():
            require(sha(Path(path)) == digest, 'tool changed')
        require(sha(fixture) == expected_fixture, 'fixture changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_before'] == report['inputs_after'], 'input changed')
        report.update(status='sysroot_matrix_completed_no_adoption', rust_reextracted=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = lower.chain.now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='lower-sysroot-matrix-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
