#!/usr/bin/env python3
"""Rebuild pinned base/public Charon in independent source and Cargo directories.

Uses an already independently installed nightly and the approved source bundle.
No old compiled cache, policy migration, full test-suite or proof-chain claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import decoder_input_bundle as bundle
import check_proof as proof
from probes import probe_isolated_full_mir as mir
from probes.probe_release_runtime import now
from source_snapshot import require, independent, regular, safe

COMMIT = '89ac118194b978d8cf753222c19f313521377aa0'
NIGHTLY = 'nightly-2026-08-18'
PUBLIC = ROOT / 'artifacts/decoder-inputs/public-v1/payload'
FIXTURE = ROOT / 'scripts/fixtures/charon_rebuild_smoke.rs'
SOURCE_LINKS = {'rust-toolchain': 'charon/rust-toolchain',
                'doc-ml.html': './_build/default/_doc/_html/charon/index.html',
                'doc-rust.html': './charon/target/doc/charon/index.html'}


def source_link(root, name):
    path = root / name
    require(name in SOURCE_LINKS and path.is_symlink() and
            os.readlink(path) == SOURCE_LINKS[name], 'unexpected Charon source symlink')
    # Inventory the committed link text, never traverse generated documentation.
    return os.readlink(path).encode()


def inventory(path):
    files, changes, links, seen_links = {}, {}, {}, set()
    require(not bundle.git(path, 'ls-files', '--others', '--exclude-standard', '-z'), 'untracked Charon source')
    for row in bundle.git(path, 'ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not row:
            continue
        metadata, raw_name = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = safe(raw_name.decode())
        if mode == '160000':
            links[name] = oid
            continue
        require(kind == 'blob' and mode in ('100644', '100755', '120000'), 'unsupported Charon source entry')
        if mode == '120000':
            data = source_link(path, name)
            actual_mode = mode
            seen_links.add(name)
        else:
            source = regular(path, name)
            data = source.read_bytes()
            actual_mode = '100755' if source.stat().st_mode & 0o111 else '100644'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        files[name] = {'mode': actual_mode, 'sha256': proof.digest(data), 'size': len(data)}
        if blob != oid or actual_mode != mode:
            changes[name] = files[name]
    require(seen_links == set(SOURCE_LINKS), 'committed Charon symlink inventory differs')
    return {'head': bundle.git(path, 'rev-parse', 'HEAD').decode().strip(),
            'gitlinks': links, 'files': files, 'changes_from_head': changes}


def environment(out, rust_home, original):
    env = mir.environment(out, rust_home, original)
    for key in list(env):
        if key.startswith(('CHARON', 'AENEAS', 'GIT_', 'SCCACHE', 'CCACHE', 'NIX_')) or key in (
                'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'AR', 'RANLIB',
                'LD_PRELOAD', 'IN_NIX_SHELL'):
            env.pop(key)
    env.update(RUSTUP_TOOLCHAIN=NIGHTLY, CARGO_TARGET_DIR=str(out / 'target'),
               CARGO_PROFILE_RELEASE_DEBUG='true', CARGO_BUILD_JOBS='4',
               CARGO_INCREMENTAL='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
    return env


def check_source(path, patched, patch_sha):
    result = inventory(path)
    require(result['head'] == COMMIT and not result['gitlinks'], 'wrong Charon source commit')
    if patched:
        actual = bundle.git(path, 'diff', '--', 'charon/src')
        require(proof.digest(actual) == patch_sha, 'public Charon patch differs')
        require(result['changes_from_head'] and
                all(name.startswith('charon/src/') for name in result['changes_from_head']),
                'unapproved change outside public Charon patch')
    else:
        require(not result['changes_from_head'], 'unpatched Charon source is dirty')
    return result


def compare_binaries(directory, expected):
    actual = {}
    for name in ('charon', 'charon-driver'):
        path = directory / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and
                os.access(path, os.X_OK), 'missing or linked Charon executable')
        actual[name] = mir.rust.sha(path)
    return {'actual': actual, 'approved': expected, 'matches_approved': actual == expected,
            'new_tools_approved': False}


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'clean_room_claimed': False, 'third_party_claimed': False, 'release_claimed': False,
              'kernel_executed': False, 'policy_changed': False, 'os_sandboxed': False,
              'old_cargo_or_build_cache_copied': False, 'full_upstream_suite_executed': False,
              'aeneas_rebuilt': False, 'sides': {}}
    env = None

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv, cwd=out, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> isolated-charon: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'Charon rebuild stage failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=mir.rust.sha(log))
            save()
        return log.read_text().strip()

    try:
        require(mir.rust.sha(mir.RUST_REPORT) == mir.RUST_SHA, 'private Rust report drift')
        rust = json.loads(mir.RUST_REPORT.read_text())
        rust_home = Path(rust['private_homes']['RUSTUP_HOME'])
        require(mir.rust.inventory(rust_home) == rust['installed_closures']['rustup'], 'private Rust closure drift')
        manifest = bundle.verify_payload(PUBLIC)
        require(manifest['source_commits']['charon'] == COMMIT, 'source package commit drift')
        policy = json.loads(proof.POLICY.read_text())
        patch = PUBLIC / 'patches/charon.patch'
        patch_sha = manifest['files']['patches/charon.patch']['sha256']
        paths = [Path(__file__), FIXTURE, mir.RUST_REPORT, proof.POLICY,
                 ROOT / 'proof/lean/decoder/public-policy.json', PUBLIC / 'package.json',
                 PUBLIC / 'sources/charon.bundle', patch, ROOT / 'scripts/decoder_input_bundle.py',
                 ROOT / 'scripts/check_proof.py', ROOT / 'scripts/source_snapshot.py',
                 ROOT / 'scripts/probes/probe_isolated_full_mir.py',
                 ROOT / 'scripts/probes/probe_isolated_rust_lean.py',
                 ROOT / 'scripts/probes/probe_release_runtime.py']
        report['inputs_before'] = {str(p.relative_to(ROOT)): mir.rust.sha(p) for p in paths}
        report['private_rustup_home'] = str(rust_home)
        for side in ('base', 'public'):
            directory = out / side
            directory.mkdir()
            env = environment(directory, rust_home, os.environ)
            env['CARGO_HOME'] = str(directory / 'cargo')
            cargo_home = directory / 'cargo'
            cargo_home.mkdir()
            checkout = directory / 'charon-source'
            row = report['sides'][side] = {'directory': str(directory), 'cargo_initially_empty': True,
                'target_initially_absent': not (directory / 'target').exists(), 'source': str(checkout)}
            row['build_environment'] = {key: env[key] for key in ('PATH', 'CARGO_HOME', 'RUSTUP_HOME',
                'RUSTUP_TOOLCHAIN', 'CARGO_TARGET_DIR', 'CARGO_PROFILE_RELEASE_DEBUG', 'CARGO_BUILD_JOBS',
                'CARGO_INCREMENTAL')}
            require(row['target_initially_absent'], 'old target exists')
            stage(side + '-clone', ['git', 'clone', '--no-checkout', PUBLIC / 'sources/charon.bundle', checkout])
            stage(side + '-checkout', ['git', 'checkout', '--detach', COMMIT], checkout)
            independent(checkout)
            check_source(checkout, False, patch_sha)
            if side == 'public':
                stage(side + '-patch-check', ['git', 'apply', '--check', patch], checkout)
                stage(side + '-patch', ['git', 'apply', patch], checkout)
            row['source_before'] = check_source(checkout, side == 'public', patch_sha)
            require(not list(checkout.rglob('target')) and not (checkout / '_build').exists(), 'old source build cache')
            rustc = Path(stage(side + '-rustc-path', ['rustup', 'which', '--toolchain', NIGHTLY, 'rustc']))
            require(rustc.resolve().is_relative_to(rust_home / 'toolchains'), 'Rust compiler escaped private root')
            row['rustc_sha256'] = mir.rust.sha(rustc)
            stage(side + '-rust-version', [rustc, '-vV'])
            stage(side + '-fetch', ['cargo', 'fetch', '--locked', '--target', 'x86_64-unknown-linux-gnu'], checkout / 'charon')
            stage(side + '-build', ['cargo', 'build', '--locked', '--offline', '--release', '--bins'], checkout / 'charon', 3600)
            installed = directory / 'bin'
            installed.mkdir()
            for name in ('charon', 'charon-driver'):
                shutil.copy2(directory / 'target/release' / name, installed / name)
            expected = {name: policy['tool_binaries'][name] if side == 'base' else
                        manifest['files']['bin/' + name]['sha256'] for name in ('charon', 'charon-driver')}
            row['binary_comparison'] = compare_binaries(installed, expected)
            version = stage(side + '-version', [installed / 'charon', 'version'])
            require(version == policy['translator_versions']['charon'], 'rebuilt Charon version mismatch')
            llbc = directory / 'Smoke.llbc'
            stage(side + '-smoke', [installed / 'charon', 'rustc', '--sysroot', 'default',
                  '--dest-file', llbc, '--', '--crate-type=lib', '--crate-name=charon_rebuild_smoke', FIXTURE], directory)
            require(llbc.is_file() and llbc.stat().st_size > 100, 'missing Charon smoke output')
            json.loads(llbc.read_text())
            row['smoke_llbc_sha256'] = mir.rust.sha(llbc)
            row['source_after'] = check_source(checkout, side == 'public', patch_sha)
            require(row['source_before'] == row['source_after'], 'source/lock changed during Charon build')
            independent(checkout)
            save()
        require(bundle.verify_payload(PUBLIC) == manifest, 'approved input package changed')
        require(mir.rust.inventory(rust_home) == rust['installed_closures']['rustup'], 'private Rust changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)): mir.rust.sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'probe or policy drift')
        report['status'] = 'independent_base_and_public_charon_built_qualification_pending'
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        destination = args.out.resolve()
        destination.mkdir(parents=True, exist_ok=False)
    else:
        destination = Path(tempfile.mkdtemp(prefix='isolated-charon-', dir=ROOT / 'artifacts/boundary-check'))
    print(destination, flush=True)
    sys.exit(run_probe(destination))
