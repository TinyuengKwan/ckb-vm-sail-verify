#!/usr/bin/env python3
"""Fresh Rust CLI + rebuilt Sail corpus, mutations and byte-copied replays.

Requires an explicitly hash-bound completed C++ build report. Reuses the fixed
joint-chain source checkout and independently installed stable Rust, but no
Cargo cache/target or old runtime evidence. Not tool admission or clean-room.
"""
import argparse
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
import ckb_source_baseline as baseline
import release_runtime_evidence as runtime
import source_snapshot as snapshot
from probes import probe_rebuilt_sail_cpp as cpp
from probes import probe_isolated_full_mir as mir

require, sha = runtime.require, runtime.sha
LOWER = ROOT / 'artifacts/boundary-check/rebuilt-lower-models-tt2j7xeu/report.json'
LOWER_SHA = '5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35'
SOURCE_SHA = '99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12'
RUST = '1.97.1-x86_64-unknown-linux-gnu'


def check_build(path, digest):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None and sha(path) == digest, 'C++ report identity drift')
    report = runtime.read_json(path)
    require(report['status'] == 'rebuilt_sail_cpp_compiled_config_checked_admission_pending' and
            report['cpp_compiled'] is True and report['emulator_config_executed'] is True and
            report['inputs_before'] == report['inputs_after'], 'incomplete C++ build')
    require(Path(report['binary']) == path.parent / 'build/c_emulator/sail_riscv_sim' and
            Path(report['config']) == path.parent / 'ckb_vm_config.json', 'C++ output escaped recorded build')
    names = ['clone', 'checkout', 'sail-version', 'configure', 'generate', 'compile',
             'emulator-version', 'default-config', 'merge-config', 'validate-config']
    require([r['name'] for r in report['stages']] == names, 'C++ stage inventory differs')
    for row in report['stages']:
        require(type(row['exit_code']) is int and row['exit_code'] == 0, 'failed C++ stage')
        require(set(row['logs']) == {row['name'] + '.stdout', row['name'] + '.stderr'}, 'missing C++ stage logs')
        for name, value in row['logs'].items():
            require(sha(path.parent / name) == value, 'C++ stage log drift')
    for name, value in report['inputs_after'].items():
        require(sha(Path(name)) == value, 'C++ build input drift: ' + name)
    for name, value in report['build_metadata'].items():
        require(sha(path.parent / name) == value, 'C++ build metadata drift')
    for name in ('binary', 'config'):
        output = Path(report[name])
        require(output.is_file() and not output.is_symlink() and output.stat().st_nlink == 1 and
                sha(output) == report[name + '_sha256'], 'C++ executable/config drift')
    require(cpp.generated(path.parent / 'build') == report['generated_before_compile'], 'C++ generated model drift')
    require(sha(path.parent / 'correspondence.json') == report['correspondence_sha256'], 'C++ map drift')
    source = Path(report['source'])
    require(snapshot.inventory(source) == report['model_source_before'], 'C++ model source drift')
    snapshot.independent(source)
    return report


def environment(out, rust_home, prefix):
    env = cpp.environment(out, prefix)
    for key in list(env):
        if key.startswith(('RUST', 'CARGO', 'MIRI', 'AENEAS')):
            env.pop(key)
    env.update(PATH=str(rust_home / 'toolchains' / RUST / 'bin') + ':' + str(prefix / 'bin') + ':/usr/bin:/bin',
               RUSTUP_HOME=str(rust_home), RUSTUP_TOOLCHAIN='1.97.1', RUSTUP_NO_UPDATE_CHECK='1',
               CARGO_HOME=str(out / 'cargo'), CARGO_TARGET_DIR=str(out / 'target'),
               CARGO_BUILD_JOBS='4', CARGO_INCREMENTAL='0', CARGO_TERM_COLOR='never')
    return env


def install_cli(out):
    """Cargo hardlinks debug/foo to debug/deps/foo-HASH in its fresh target.

    Account for every link inside that target, then install a byte-identical
    independent executable; do not unlink/mutate the actual Cargo outputs.
    """
    target = out / 'target'
    built = target / 'debug/ckb-vm-sail-diff'
    require(built.is_file() and not built.is_symlink() and os.access(built, os.X_OK), 'missing fresh Rust CLI')
    state = built.stat()
    links = sorted(p for p in target.rglob('*') if p.is_file() and not p.is_symlink() and
                   (p.stat().st_dev, p.stat().st_ino) == (state.st_dev, state.st_ino))
    require(built in links and len(links) == state.st_nlink and all(p.resolve().is_relative_to(target.resolve())
            for p in links), 'Cargo executable has links outside fresh target')
    digest = sha(built)
    binary_dir = out / 'bin'; binary_dir.mkdir()
    cli = binary_dir / 'ckb-vm-sail-diff'
    shutil.copy2(built, cli)
    require(cli.stat().st_nlink == 1 and sha(cli) == digest == sha(built) and os.access(cli, os.X_OK),
            'installed CLI differs from Cargo output')
    return cli, {'path': str(built), 'sha256': digest, 'links_inside_fresh_target': [str(p) for p in links],
                 'installed_copy_byte_identical': True, 'cargo_outputs_edited': False}


def run(out, build_path, build_sha):
    report = {'schema_version': 1, 'status': 'running', 'started_at': cpp.model.now(), 'stages': [],
              'build_report': str(build_path), 'build_report_sha256': build_sha,
              'runtime_differential_executed': False, 'rust_cli_rebuilt': False,
              'old_cargo_cache_or_target_reused': False, 'fixed_candidate_source_reused': True,
              'new_sail_cpp_build_reused': True, 'tool_adopted': False, 'policy_changed': False,
              'kernel_executed': False, 'clean_room_claimed': False, 'third_party_claimed': False,
              'release_claimed': False, 'os_sandboxed': False}
    env, checkout = None, out

    def save():
        cpp.model.proof.write_json(out / 'report.json', report)

    def stage(name, argv, timeout=600):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(checkout), 'started_at': cpp.model.now()}
        report['stages'].append(row); save()
        print('==> rebuilt-sail-runtime: ' + name, flush=True)
        stdout, stderr = out / (name + '.stdout'), out / (name + '.stderr')
        try:
            with stdout.open('xb') as output, stderr.open('xb') as errors:
                process = subprocess.run(row['argv'], cwd=checkout, env=env, stdout=output, stderr=errors, timeout=timeout)
            row['exit_code'] = process.returncode
            require(type(process.returncode) is int and process.returncode == 0, 'runtime stage failed: ' + name)
        finally:
            row.update(finished_at=cpp.model.now(), logs={p.name: sha(p) for p in (stdout, stderr) if p.exists()})
            save()
        return stdout

    try:
        build = check_build(build_path, build_sha)
        require(sha(cpp.model.INSTALL_REPORT) == cpp.model.INSTALL_SHA, 'Sail install report drift')
        install = runtime.read_json(cpp.model.INSTALL_REPORT)
        prefix = cpp.check_install(install)
        require(sha(LOWER) == LOWER_SHA, 'fixed source report drift')
        origin = runtime.read_json(LOWER)
        checkout = Path(origin['checkout'])
        source = snapshot.capture(checkout)
        require(source['snapshot_sha256'] == origin['source_snapshot_sha256'] == SOURCE_SHA, 'fixed source drift')
        for repo in snapshot.REPOS:
            snapshot.independent(checkout if repo == '.' else checkout / repo)
        require(not any((parent / 'Cargo.toml').exists() for parent in checkout.parents), 'enclosing Cargo workspace')
        require(sha(mir.RUST_REPORT) == mir.RUST_SHA, 'private Rust report drift')
        rust = runtime.read_json(mir.RUST_REPORT)
        rust_home = Path(rust['private_homes']['RUSTUP_HOME'])
        require(mir.rust.inventory(rust_home) == rust['installed_closures']['rustup'], 'private Rust closure drift')
        env = environment(out, rust_home, prefix)
        require(all(not p.exists() and not p.is_symlink() for p in (out / 'cargo', out / 'target')), 'old Rust build cache')
        report.update(checkout=str(checkout), source_snapshot_sha256=SOURCE_SHA,
                      rust_install_report_sha256=mir.RUST_SHA, rust_home=str(rust_home),
                      cargo_destinations_initially_absent=True, environment=env_subset(env))
        paths = {Path(__file__), build_path, LOWER, mir.RUST_REPORT, cpp.model.INSTALL_REPORT,
                 checkout / 'deps/ckb-vm/Cargo.lock'}
        paths.update(Path(m.__file__).resolve() for m in list(sys.modules.values())
                     if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
        report['inputs_before'] = {str(p): sha(p) for p in sorted(paths)}
        binary, config = Path(build['binary']), Path(build['config'])
        expected = {'ckb_vm_commit': source['repositories']['deps/ckb-vm']['head'],
                    'ckb_vm_source_baseline': baseline.check(checkout),
                    'sail_riscv_commit': source['repositories']['deps/sail-riscv']['head'],
                    'sail_model_version': stage('emulator-version', [binary, '--version']).read_text().strip(),
                    'sail_bin': str(binary), 'sail_config': str(config), 'sail_config_sha256': sha(config),
                    'ckb_vm_isa_bits': 1, 'ckb_vm_isa': 'IMC+B', 'ckb_vm_version': 2,
                    'rustc': stage('rustc-version', ['rustc', '--version']).read_text().strip(),
                    'cargo': stage('cargo-version', ['cargo', '--version']).read_text().strip(),
                    'sail_compiler': stage('sail-version', ['sail', '--version']).read_text().strip()}
        require(expected['sail_model_version'] == build['emulator_version'] and
                expected['sail_compiler'] == cpp.model.install.VERSION, 'runtime tool version drift')
        report['observed_environment'] = expected
        stage('build-cli', ['cargo', 'build', '--locked', '-p', 'ckb-vm-sail-diff'], timeout=900)
        cli, cargo_output = install_cli(out)
        report.update(rust_cli_rebuilt=True, cli=str(cli), cli_sha256=sha(cli), cargo_output=cargo_output)
        common = [cli, '--json', '--sail-bin', binary, '--sail-config', config]
        corpus = stage('corpus-mutations', [*common, '--corpus', '--mutate', '--artifact-dir', out / 'original'])
        report['runtime'] = runtime.validate(corpus, out / 'original', expected)
        relocated = out / 'relocated'; relocated.mkdir()
        for name, digest in report['runtime']['artifact_sha256'].items():
            shutil.copyfile(out / 'original' / name, relocated / name)
            require(sha(relocated / name) == digest, 'relocated artifact byte drift')
        require(runtime.validate(corpus, relocated, expected) == report['runtime'], 'relocated corpus differs')
        report['replays'] = []
        for row in runtime.read_json(corpus)['results']:
            name = row['id']; artifact = relocated / (name + '.json'); directory = out / 'replays' / name
            replay = stage('replay-' + name, [*common, '--replay', artifact, '--artifact-dir', directory])
            output = directory / artifact.name
            require({p.name for p in directory.iterdir()} == {output.name}, 'extra replay outputs')
            runtime.check_replay(runtime.read_json(replay), runtime.read_json(output), runtime.read_json(artifact), expected)
            report['replays'].append({'case_id': name, 'report': str(replay.relative_to(out)), 'report_sha256': sha(replay),
                                      'artifact': str(output.relative_to(out)), 'artifact_sha256': sha(output),
                                      'input_sha256': sha(artifact)})
        require(runtime.validate(corpus, out / 'original', expected) == report['runtime'] ==
                runtime.validate(corpus, relocated, expected), 'runtime evidence changed during replay')
        report['runtime_differential_executed'] = True
        require(check_build(build_path, build_sha) == build and cpp.check_install(install) == prefix, 'Sail input drift')
        require(snapshot.capture(checkout) == source and sha(cli) == report['cli_sha256'], 'Rust source or CLI drift')
        require(all(sha(Path(p)) == cargo_output['sha256'] for p in cargo_output['links_inside_fresh_target']),
                'original Cargo executable changed')
        require(mir.rust.inventory(rust_home) == rust['installed_closures']['rustup'], 'private Rust closure changed')
        report['inputs_after'] = {str(p): sha(p) for p in sorted(paths)}
        require(report['inputs_before'] == report['inputs_after'], 'runtime helper/build input drift')
        report['status'] = 'rebuilt_sail_runtime_mutations_replays_checked_admission_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = cpp.model.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


def env_subset(env):
    return {k: env[k] for k in ('PATH', 'SAIL_DIR', 'SAIL_PLUGIN_DIR', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN',
                               'CARGO_HOME', 'CARGO_TARGET_DIR', 'CARGO_BUILD_JOBS', 'CARGO_INCREMENTAL')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-report', required=True, type=Path)
    parser.add_argument('--build-report-sha256', required=True)
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='rebuilt-sail-runtime-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out, args.build_report.resolve(strict=True), args.build_report_sha256))
