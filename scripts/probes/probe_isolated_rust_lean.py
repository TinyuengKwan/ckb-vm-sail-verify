#!/usr/bin/env python3
"""Install pinned Rust/Lean into fresh private homes; not full clean-room.

Reuses existing rustup/elan bootstrap executables and host OS/network stack.
Never updates global defaults, copies old toolchains, or changes proof policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes.probe_release_runtime import now
from source_snapshot import require, canonical

PINS = ROOT / 'docs/release/rust-lean-install-pins.json'
HOST = 'x86_64-unknown-linux-gnu'
HOMES = {'RUSTUP_HOME': 'rustup', 'CARGO_HOME': 'cargo', 'ELAN_HOME': 'elan'}
STRIP = ['RUSTUP_TOOLCHAIN', 'ELAN_TOOLCHAIN', 'RUSTUP_DIST_SERVER', 'RUSTUP_UPDATE_ROOT',
         'ELAN_DIST_SERVER', 'ELAN_UPDATE_ROOT', 'LEAN_PATH', 'LEAN_SYSROOT',
         'RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_RUSTFLAGS', 'RUSTC', 'RUSTDOC',
         'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER', 'CARGO_TARGET_DIR']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def environment(out, original):
    env = dict(original)
    for key in STRIP:
        env.pop(key, None)
    env.update({key: str(out / name) for key, name in HOMES.items()})
    env.update(RUSTUP_NO_UPDATE_CHECK='1', LEAN_ABORT_ON_PANIC='1', CARGO_TERM_COLOR='never')
    return env


def create_homes(out):
    # Preflight all destinations before creating any, never reuse partial runs.
    require(all(not (out / name).exists() and not (out / name).is_symlink()
                for name in HOMES.values()), 'tool homes must be absent')
    for name in HOMES.values():
        (out / name).mkdir()


def installed_binary(path, home, expected):
    path, home = Path(path), Path(home).resolve()
    resolved = path.resolve(strict=True)
    require(resolved.is_relative_to(home / 'toolchains'), 'tool escaped private installation')
    require(resolved.is_file() and os.access(resolved, os.X_OK), 'tool is not executable')
    require(resolved.stat().st_nlink == 1, 'tool is hardlinked')
    require(sha(resolved) == expected, 'installed executable differs from pinned baseline')
    return resolved


def rust_identity(output, pin):
    fields = dict(line.split(': ', 1) for line in output.splitlines() if ': ' in line)
    require(fields.get('commit-hash') == pin['commit'] and fields.get('release') == pin['release']
            and fields.get('host') == HOST, 'Rust compiler identity differs')


def components(output, extra):
    expected = {name + '-' + HOST for name in ['cargo', 'rustc', 'rust-std', *extra] if name != 'rust-src'}
    if 'rust-src' in extra:
        expected.add('rust-src')
    lines = output.splitlines()
    require(len(lines) == len(set(lines)) and set(lines) == expected, 'installed component inventory differs')


def inventory(home):
    """Hash the newly installed closure, including libraries, not just launchers."""
    files = {}
    home = home.resolve()
    for path in sorted((home / 'toolchains').rglob('*')):
        name = path.relative_to(home).as_posix()
        if path.is_symlink():
            require(path.resolve(strict=True).is_relative_to(home / 'toolchains'), 'external installed symlink')
            files[name] = {'symlink': os.readlink(path)}
        elif path.is_file():
            files[name] = {'sha256': sha(path), 'size': path.stat().st_size,
                           'mode': path.stat().st_mode & 0o777}
        else:
            require(path.is_dir(), 'special installed file')
    require(files, 'empty installed toolchain closure')
    return {'files': files, 'sha256': hashlib.sha256(canonical(files)).hexdigest()}


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'clean_room_claimed': False, 'release_claimed': False, 'third_party_claimed': False,
              'proof_chain_executed': False, 'extra_vm_proof_coverage': False,
              'copied_old_toolchains': False, 'host_os_and_bootstrap_reused': True}
    env = environment(out, os.environ)
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    def stage(name, argv, timeout=1800):
        row = {'name': name, 'argv': list(map(str, argv)), 'started_at': now()}
        report['stages'].append(row)
        save()
        log = out / (name + '.log')
        print('==> isolated-rust-lean: ' + name, flush=True)
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'installation stage failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()
    try:
        require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'unsupported host')
        pins = json.loads(PINS.read_text())
        require(pins['schema_version'] == 1, 'pin schema')
        stable = tomllib.loads((ROOT / 'rust-toolchain.toml').read_text())['toolchain']
        require(stable['channel'] in pins['rust'] and
                sorted(stable['components']) == pins['rust'][stable['channel']]['components'], 'repository Rust pin drift')
        require((ROOT / 'proof/lean/theorems/lean-toolchain').read_text().strip() == pins['lean']['toolchain'],
                'repository Lean pin drift')
        sources = [PINS, Path(__file__), ROOT / 'scripts/source_snapshot.py',
                   ROOT / 'scripts/probes/probe_release_runtime.py', ROOT / 'rust-toolchain.toml',
                   ROOT / 'proof/lean/theorems/lean-toolchain',
                   ROOT / 'scripts/fixtures/tool_install_smoke.rs', ROOT / 'scripts/fixtures/ToolInstallSmoke.lean',
                   ROOT / 'proof/lean/audit/step-policy.json', ROOT / 'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)): sha(p) for p in sources}
        managers = {name: Path(shutil.which(name) or '').resolve(strict=True) for name in ['rustup', 'elan']}
        require(all(p.is_file() and os.access(p, os.X_OK) for p in managers.values()), 'bootstrap manager missing')
        report['bootstrap'] = {name: {'path': str(path), 'sha256': sha(path)} for name, path in managers.items()}
        report['private_homes'] = {key: env[key] for key in HOMES}
        report['pins'] = pins
        create_homes(out)
        report['tool_homes_initially_empty'] = True
        # rustup --version can resolve the ancestor rust-toolchain.toml and
        # auto-install before our explicit minimal-profile installation stage.
        # Record bootstrap bytes without invoking an ambient toolchain proxy.
        report['installed_binaries'] = {}
        for i, (toolchain, pin) in enumerate(pins['rust'].items()):
            argv = [managers['rustup'], 'toolchain', 'install', toolchain, '--profile', 'minimal', '--no-self-update']
            for component in pin['components']:
                argv += ['--component', component]
            stage(f'rust-{i}-install', argv)
            components(stage(f'rust-{i}-components', [managers['rustup'], 'component', 'list',
                       '--toolchain', toolchain, '--installed'], 30), pin['components'])
            binaries = {}
            for name, digest in pin['binaries'].items():
                path = stage(f'rust-{i}-{name}-path', [managers['rustup'], 'which', '--toolchain', toolchain, name], 30)
                binaries[name] = installed_binary(path, out / 'rustup', digest)
                report['installed_binaries'][f'{toolchain}/{name}'] = {'path': str(binaries[name]), 'sha256': digest}
            rust_identity(stage(f'rust-{i}-identity', [binaries['rustc'], '-vV'], 30), pin)
            program = out / f'rust-{i}-smoke'
            stage(f'rust-{i}-compile', [binaries['rustc'], ROOT / 'scripts/fixtures/tool_install_smoke.rs', '-o', program], 120)
            require(stage(f'rust-{i}-run', [program], 30) == 'rust-toolchain-smoke:42', 'Rust smoke output')
        toolchain = pins['lean']['toolchain']
        stage('lean-install', [managers['elan'], 'toolchain', 'install', toolchain])
        env['ELAN_TOOLCHAIN'] = toolchain
        lean = {}
        for name, digest in pins['lean']['binaries'].items():
            path = stage(name + '-path', [managers['elan'], 'which', name], 30)
            lean[name] = installed_binary(path, out / 'elan', digest)
            report['installed_binaries'][name] = {'path': str(lean[name]), 'sha256': digest}
            expected = pins['lean']['version' if name == 'lean' else 'lake_version']
            require(stage(name + '-identity', [lean[name], '--version'], 30) == expected, 'Lean/Lake version differs')
        # Keep the compiled output outside the source workspace.
        source = out / 'ToolInstallSmoke.lean'
        shutil.copyfile(ROOT / 'scripts/fixtures/ToolInstallSmoke.lean', source)
        stage('lean-kernel-smoke', [lean['lean'], '-o', out / 'ToolInstallSmoke.olean', source], 120)
        require((out / 'ToolInstallSmoke.olean').is_file(), 'Lean smoke output missing')
        report['installed_closures'] = {name: inventory(out / name) for name in ['rustup', 'elan']}
        report['smoke_outputs'] = {name: sha(out / name) for name in ['rust-0-smoke', 'rust-1-smoke', 'ToolInstallSmoke.olean']}
        report['inputs_after'] = {str(p.relative_to(ROOT)): sha(p) for p in sources}
        require(report['inputs_before'] == report['inputs_after'], 'source/pin/policy changed during installation')
        require(all(sha(Path(row['path'])) == row['sha256'] for row in report['bootstrap'].values()), 'bootstrap changed')
        report['status'] = 'isolated_rust_lean_installation_and_smoke_passed'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
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
        out = Path(tempfile.mkdtemp(prefix='isolated-rust-lean-', dir=parent))
    print(out, flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
