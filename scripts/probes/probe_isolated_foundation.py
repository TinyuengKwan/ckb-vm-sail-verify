#!/usr/bin/env python3
"""Snapshot/clone/rebuild foundation with reused host tools, NOT full clean-room.

No commits/index updates in the source workspace. No copied binaries/models in
the checkout. Explicitly retains the HEAD-plus-overlay source identity and all
logs. Rust/Sail/Lean/Rocq tool installation and the proof chain remain separate.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import source_snapshot as snapshot
import release_runtime_evidence as evidence
from probes import probe_release_runtime as runtime


def check_initial_outputs(checkout):
    absent = ['target', 'deps/sail-riscv/build', 'sail-model/build',
              'proof/lean/generated', 'proof/rocq/generated']
    snapshot.require(all(not (checkout / p).exists() and not (checkout / p).is_symlink()
                         for p in absent), 'generated/build inputs were copied')
    # artifacts/README.md is versioned documentation, not historical evidence.
    # Permit that exact file only; no cached reports, directories or symlinks.
    artifacts = checkout / 'artifacts'
    snapshot.require(not artifacts.is_symlink(), 'artifact directory symlink')
    if artifacts.exists():
        snapshot.require(artifacts.is_dir() and
                         all(p.name == 'README.md' and p.is_file() and not p.is_symlink()
                             for p in artifacts.iterdir()), 'historical evidence was copied')
    return absent


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': runtime.now(), 'stages': [],
        'clean_room_claimed': False, 'release_claimed': False, 'third_party_claimed': False,
        'tool_installation_performed': False, 'proof_chain_executed': False,
        'source_identity_kind': 'HEAD-plus-byte-inventoried-working-tree-not-a-commit'}
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    def stage(name, argv, cwd=ROOT, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': runtime.now()}
        report['stages'].append(row)
        save()
        log = out / (name + '.log')
        print('==> isolated-foundation: ' + name, flush=True)
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            snapshot.require(result.returncode == 0, 'isolated stage failed: ' + name)
        finally:
            row.update(finished_at=runtime.now(), log=log.name, log_sha256=evidence.sha(log))
            save()
        return log.read_text()
    try:
        env, compiler = runtime.environment()
        identity = snapshot.capture(ROOT)
        report['source_snapshot'] = identity
        report['original_directory'] = str(ROOT)
        report['original_git_status'] = {repo: snapshot.git(ROOT / repo, 'status', '--porcelain', '--untracked-files=all').decode()
                                         for repo in snapshot.REPOS}
        report['driver_sha256'] = evidence.sha(Path(__file__))
        report['snapshot_script_sha256'] = evidence.sha(ROOT / 'scripts/source_snapshot.py')
        report['reused_host_tools'] = {'sail_compiler': str(compiler), 'sail_compiler_sha256': evidence.sha(compiler),
            'rustc': subprocess.check_output(['rustc', '--version'], env=env, text=True).strip(),
            'cargo': subprocess.check_output(['cargo', '--version'], env=env, text=True).strip(),
            'cargo_home': env.get('CARGO_HOME', str(Path.home() / '.cargo')),
            'rustup_home': env.get('RUSTUP_HOME', str(Path.home() / '.rustup'))}
        snapshot.export(ROOT, identity, out / 'source-payload')
        checkout = out / 'checkout'
        report['checkout'] = str(checkout)
        for i, repo in enumerate(snapshot.REPOS):
            source, destination = ROOT / repo, checkout if repo == '.' else checkout / repo
            stage(f'clone-{i}', ['git', 'clone', '--no-hardlinks', '--no-checkout', source, destination])
            stage(f'checkout-{i}', ['git', 'checkout', '--detach', identity['repositories'][repo]['head']], destination)
            snapshot.independent(destination)
        snapshot.restore(checkout, out / 'source-payload', identity)
        report['restored_source_snapshot_sha256'] = snapshot.capture(checkout)['snapshot_sha256']
        report['initially_absent_paths'] = check_initial_outputs(checkout)
        report['initial_artifacts_allowed_source_files'] = ['artifacts/README.md']
        env.update(SAIL_BIN=str(checkout / runtime.SAIL_BIN), SAIL_CONFIG=str(checkout / runtime.CONFIG),
                   SAIL_CONFIG_OVERRIDE=str(checkout / 'sail-model/ckb_vm_config.json'),
                   SAIL_RISCV_DIR=str(checkout / 'deps/sail-riscv'))
        env['CARGO_TERM_COLOR'] = 'never'
        for key in ['CARGO_TARGET_DIR', 'CMAKE_PREFIX_PATH', 'CMAKE_TOOLCHAIN_FILE']:
            env.pop(key, None)
        stage('configure-sail', ['cmake', '-S', 'deps/sail-riscv', '-B', 'deps/sail-riscv/build',
              '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DDOWNLOAD_GMP=TRUE', '-DSAIL_BIN:FILEPATH=' + str(compiler)], checkout)
        stage('build-sail', ['cmake', '--build', 'deps/sail-riscv/build', '--parallel', '4',
                            '--target', 'sail_riscv_sim'], checkout, 3600)
        stage('materialize-config', ['bash', 'scripts/prepare_sail_config.sh'], checkout)
        stage('verify-environment', ['bash', 'scripts/verify_environment.sh'], checkout)
        stage('rust-tests', ['python3', 'scripts/release_rust_tests.py', '--out',
                            'artifacts/boundary-check/isolated-rust-tests'], checkout)
        stage('runtime', ['python3', 'scripts/probes/probe_release_runtime.py', '--out',
                         'artifacts/boundary-check/isolated-runtime'], checkout)
        # Validators must run with the relocated module ROOT, not the original
        # path. No producer-supplied shell/code is evaluated.
        validation = (
            "import sys,json; from pathlib import Path; sys.path.insert(0,'scripts'); "
            "import release_evidence as e; import release_rust_tests as r; "
            "print(json.dumps({'rust_tests':r.check(Path('artifacts/boundary-check/isolated-rust-tests/report.json').resolve()),"
            "'runtime':e.check_runtime(Path('artifacts/boundary-check/isolated-runtime/report.json').resolve())}))")
        report['foundation_validation'] = json.loads(stage('validate-foundation', ['python3', '-c', validation], checkout))
        report['rebuilt_files'] = {p: evidence.sha(checkout / p) for p in [runtime.SAIL_BIN, runtime.CONFIG]}
        report['foundation_reports'] = {p: evidence.sha(checkout / p) for p in [
            'artifacts/boundary-check/isolated-rust-tests/report.json',
            'artifacts/boundary-check/isolated-runtime/report.json']}
        after = snapshot.capture(checkout)
        snapshot.require(after == identity, 'isolated source drift after generation/tests')
        snapshot.require(snapshot.capture(ROOT) == identity, 'original source changed during isolated run')
        snapshot.require(report['original_git_status'] == {repo: snapshot.git(ROOT / repo, 'status', '--porcelain',
                         '--untracked-files=all').decode() for repo in snapshot.REPOS}, 'original Git/index status changed')
        snapshot.require(evidence.sha(compiler) == report['reused_host_tools']['sail_compiler_sha256'], 'host compiler changed')
        report['source_after_snapshot_sha256'] = after['snapshot_sha256']
        report['source_changes_during_foundation'] = []
        report['status'] = 'isolated_foundation_passed_with_reused_host_tools'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = runtime.now()
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
        parent = ROOT / 'artifacts/boundary-check'
        parent.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='isolated-foundation-', dir=parent))
    print(out, flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
