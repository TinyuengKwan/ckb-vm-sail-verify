#!/usr/bin/env python3
"""Fresh local runtime evidence and byte-identical relocated replay, not release.

Uses the Sail compiler selected in CMake, verifies the existing environment,
builds Rust into a new target, runs the corpus/matrix and replays every copy.
The existing Sail emulator is hashed, NOT rebuilt or attested by this probe.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import ckb_source_baseline as baseline
import release_runtime_evidence as evidence

SAIL_BIN = 'deps/sail-riscv/build/c_emulator/sail_riscv_sim'
CONFIG = 'sail-model/build/ckb_vm_config.json'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def environment():
    env = dict(os.environ)
    cache = ROOT / 'deps/sail-riscv/build/CMakeCache.txt'
    settings = dict(line.split('=', 1) for line in cache.read_text().splitlines()
                    if '=' in line and not line.startswith(('#', '//')))
    evidence.require(Path(settings['CMAKE_HOME_DIRECTORY:INTERNAL']).resolve() ==
                     ROOT / 'deps/sail-riscv', 'wrong CMake source checkout')
    compiler = Path(settings['SAIL_BIN:FILEPATH']).resolve(strict=True)
    env['PATH'] = str(compiler.parent) + os.pathsep + env['PATH']
    env.update(SAIL_BIN=str(ROOT / SAIL_BIN), SAIL_CONFIG=str(ROOT / CONFIG))
    for key in ['RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_RUSTFLAGS',
                'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER', 'RUSTC', 'RUSTDOC', 'CARGO_TARGET_DIR']:
        env.pop(key, None)
    return env, compiler


def observed_environment(env):
    def output(argv):
        return subprocess.check_output(argv, cwd=ROOT, env=env, text=True,
                                       stderr=subprocess.PIPE, timeout=30).strip()
    source = baseline.check(ROOT)
    return {'ckb_vm_commit': source['upstream_commit'], 'ckb_vm_source_baseline': source,
            'sail_riscv_commit': output(['git', '-C', 'deps/sail-riscv', 'rev-parse', 'HEAD']),
            'sail_model_version': output([SAIL_BIN, '--version']),
            'sail_bin': SAIL_BIN, 'sail_config': CONFIG, 'sail_config_sha256': evidence.sha(ROOT / CONFIG),
            'ckb_vm_isa_bits': 1, 'ckb_vm_isa': 'IMC+B', 'ckb_vm_version': 2,
            'rustc': output(['rustc', '--version']).splitlines()[0],
            'cargo': output(['cargo', '--version']).splitlines()[0],
            'sail_compiler': output(['sail', '--version']).splitlines()[0]}


def inputs(compiler):
    paths = set((ROOT / 'crates').rglob('*.rs')) | set((ROOT / 'crates').rglob('Cargo.toml'))
    paths.update(ROOT / name for name in ['Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml',
        CONFIG, SAIL_BIN, 'sail-model/ckb_vm_config.json', 'deps/sail-riscv/build/CMakeCache.txt',
        'scripts/verify_environment.sh', 'scripts/ckb_source_baseline.py',
        'scripts/release_runtime_evidence.py', 'scripts/probes/probe_release_runtime.py',
        'scripts/tests/test_release_runtime_evidence.py',
        'proof/lean/audit/step-policy.json', 'proof/lean/decoder/public-policy.json',
        'proof/lean/decoder/public-rebuilt-policy.json', 'proof/lean/decoder/raw-rebuilt-policy.json',
        'proof/lean/decoder/rebuilt-input-policy.json', 'proof/lean/decoder/rebuilt-input-catalogue.json',
        'proof/lean/extraction/ckb-source-baseline.json', 'patches/ckb-vm/runtime-container.patch'])
    paths.add(compiler)
    return {str(path): evidence.sha(path) for path in sorted(paths)}


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'release_claimed': False, 'clean_room_claimed': False,
              'third_party_claimed': False, 'sail_emulator_rebuilt': False}
    def run(name, argv, env, timeout=300):
        log, err = out / (name + '.stdout'), out / (name + '.stderr')
        stage = {'name': name, 'argv': list(map(str, argv)), 'started_at': now()}
        report['stages'].append(stage)
        try:
            with log.open('xb') as stdout, err.open('xb') as stderr:
                result = subprocess.run(stage['argv'], cwd=ROOT, env=env,
                                        stdout=stdout, stderr=stderr, timeout=timeout)
            stage['exit_code'] = result.returncode
            evidence.require(result.returncode == 0, 'stage failed: ' + name)
        finally:
            stage['finished_at'] = now()
            stage['logs'] = {str(p.relative_to(out)): evidence.sha(p) for p in [log, err] if p.is_file()}
        return log
    try:
        env, compiler = environment()
        report['inputs_before'] = inputs(compiler)
        report['environment_before'] = expected = observed_environment(env)
        run('verify-environment', ['bash', 'scripts/verify_environment.sh'], env)
        target = out / 'cargo-target'
        evidence.require(not target.exists(), 'Cargo output must be new')
        env['CARGO_TARGET_DIR'] = str(target)
        report['cargo_target_initially_absent'] = True
        run('build-cli', ['cargo', 'build', '--locked', '-p', 'ckb-vm-sail-diff'], env, 900)
        binary = target / 'debug/ckb-vm-sail-diff'
        report['binary_sha256'] = evidence.sha(binary)
        common = [binary, '--json', '--sail-bin', SAIL_BIN, '--sail-config', CONFIG]
        corpus = run('corpus-mutations', [*common, '--corpus', '--mutate',
                     '--artifact-dir', out / 'original'], env)
        report['runtime'] = evidence.validate(corpus, out / 'original', expected)
        copy_dir = out / 'relocated'
        copy_dir.mkdir()
        for name, digest in report['runtime']['artifact_sha256'].items():
            shutil.copyfile(out / 'original' / name, copy_dir / name)
            evidence.require(evidence.sha(copy_dir / name) == digest, 'copy changed bytes')
        evidence.require(evidence.validate(corpus, copy_dir, expected) == report['runtime'],
                         'relocated evidence changed')
        report['replays'] = []
        for row in evidence.read_json(corpus)['results']:
            name = row['id']
            source = copy_dir / (name + '.json')
            directory = out / 'replays' / name
            replay = run('replay-' + name, [*common, '--replay', source,
                         '--artifact-dir', directory], env)
            artifact = directory / (name + '.json')
            evidence.require({p.name for p in directory.iterdir()} == {artifact.name}, 'extra replay outputs')
            evidence.check_replay(evidence.read_json(replay), evidence.read_json(artifact),
                                  evidence.read_json(source), expected)
            report['replays'].append({'case_id': name, 'report': str(replay.relative_to(out)),
                'report_sha256': evidence.sha(replay), 'artifact': str(artifact.relative_to(out)),
                'artifact_sha256': evidence.sha(artifact), 'input_sha256': evidence.sha(source)})
        evidence.require(evidence.validate(corpus, out / 'original', expected) == report['runtime'] and
                         evidence.validate(corpus, copy_dir, expected) == report['runtime'],
                         'original/copied evidence changed during replay')
        report['environment_after'] = observed_environment(env)
        report['inputs_after'] = inputs(compiler)
        evidence.require(report['inputs_before'] == report['inputs_after'] and
                         expected == report['environment_after'] and
                         report['binary_sha256'] == evidence.sha(binary), 'inputs/tools changed during run')
        report['status'] = 'local_runtime_and_relocated_replay_passed'
        return report, 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        return report, 1
    finally:
        report['finished_at'] = now()
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='new directory only; default unique boundary-check directory')
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        parent = ROOT / 'artifacts/boundary-check'
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='release-runtime-', dir=parent))
    print(out, flush=True)
    report, code = run_probe(out)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
