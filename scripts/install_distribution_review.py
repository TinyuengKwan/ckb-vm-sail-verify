"""Inventory fixed installation inputs and test a copied Sail prefix.

This is distribution preparation, not a complete package, policy migration,
OS sandbox, clean-room execution or proof. Original installations are read only.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import audit_release as audit
import rebuilt_main_tools as tools

ROOT = tools.proof.ROOT
REPORTS = {
    'rust_lean': ('artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/report.json',
        '80058acabeef59e0eb424aa2028a28a7018e4acad0da8531da83db9b4bc9cbad'),
    'aeneas': ('artifacts/boundary-check/aeneas-opam-finalize-mj9dgb4h/report.json',
        '64f4b5dfff7dbfe3d08d3a935de0e3942805d46fe277e2738ba654b6bb757b6e'),
    'sail': (tools.SAIL_REPORT, tools.SAIL_REPORT_SHA),
    'rocq': ('artifacts/boundary-check/isolated-rocq-ac54t6f8/report.json',
        '3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540'),
}
require, sha, read = tools.require, tools.sha, tools.read


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def anchored(root, raw):
    """Fixed report paths must be real descendants, not aliases or external paths."""
    root, path = Path(root).resolve(), Path(raw)
    require(path.is_absolute() and path != root and path.is_relative_to(root), 'unscoped installation path')
    require(path.resolve(strict=True) == path, 'aliased installation path')
    return path


def inventory_summary(closure):
    files = closure['files']
    links = {name: row['symlink'] for name, row in files.items() if 'symlink' in row}
    return {'entries': len(files), 'regular_bytes': sum(row.get('size', 0) for row in files.values()),
            'symlinks': len(links), 'absolute_symlinks': sorted(name for name, value in links.items()
                                                            if Path(value).is_absolute()),
            'closure_sha256': closure['sha256']}


def control_files(prefix, switch):
    """Observe selected OPAM state outside installed-folder hashes; not a complete closure."""
    prefix = Path(prefix)
    names = ['config', 'repo/repos-config'] + [switch + '/.opam-switch/' + name for name in
        ['config', 'environment', 'switch-config', 'switch-state', 'install', 'packages']]
    result, missing = {}, []
    for name in names:
        path = prefix / name
        if not path.exists() and not path.is_symlink():
            missing.append(name)
            continue
        anchored(prefix, path)
        for child in sorted(path.rglob('*')) if path.is_dir() else [path]:
            anchored(prefix, child)
            if child.is_dir(): continue
            require(child.is_file(), 'special OPAM control file')
            result[str(child.relative_to(prefix))] = {'sha256': sha(child), 'size': child.stat().st_size}
    return {'files': result, 'missing_selected_paths': missing,
            'complete_runtime_closure_claimed': False,
            'excluded': ['locks', 'logs', 'download caches', 'build trees', 'sources', 'other repository state']}


def copy_prefix(source, target, expected, folders):
    source, target = Path(source), Path(target)
    require(not target.exists() and not target.is_symlink(), 'copy destination already exists')
    require(tools.locations.installation_inventory(source, folders) == expected, 'source installation drift')
    target.mkdir()
    for name in folders:
        if (source / name).exists(): shutil.copytree(source / name, target / name, symlinks=True)
    require(tools.locations.installation_inventory(target, folders) == expected, 'copied installation differs')
    for name, row in expected['files'].items():
        if 'symlink' in row: continue
        old, new = (source / name).stat(), (target / name).stat()
        require((old.st_dev, old.st_ino) != (new.st_dev, new.st_ino) and new.st_nlink == 1,
                'copied file shares storage identity')


def smoke_environment(prefix, temporary):
    return {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'TMPDIR': str(temporary),
            'SAIL_DIR': str(prefix / 'share/sail'),
            'SAIL_PLUGIN_DIR': str(prefix / 'share/libsail/plugins')}


def run(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': stamp(), 'stages': [],
              'complete_distribution_claimed': False, 'formal_relocation_adopted': False,
              'clean_room_claimed': False, 'release_claimed': False, 'kernel_executed': False,
              'os_sandboxed': False, 'original_path_access_excluded': False}
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def stage(name, command, env):
        start = stamp()
        result = subprocess.run([str(x) for x in command], cwd=out, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        log = out / (name + '.log')
        log.write_bytes(result.stdout)
        report['stages'].append({'name': name, 'argv': [str(x) for x in command], 'cwd': str(out),
            'started_at': start, 'finished_at': stamp(), 'exit_code': result.returncode,
            'log': log.name, 'log_sha256': sha(log)})
        save()
        require(result.returncode == 0, 'Sail smoke failed: ' + name)
        return result.stdout.decode().strip()
    code = 1
    try:
        report['inputs_before'] = audit.snapshot()
        source_files = [Path(__file__), ROOT / 'scripts/tests/test_install_distribution_review.py',
                        ROOT / 'scripts/fixtures/tool_install_smoke.sail']
        report['review_sources_before'] = {str(p.relative_to(ROOT)): sha(p) for p in source_files}
        records = {}
        for name, (relative, expected) in REPORTS.items():
            path = ROOT / relative
            require(sha(path) == expected, 'installation report drift: ' + name)
            records[name] = read(path)
        report['installation_reports'] = {name: {'path': path, 'sha256': digest}
                                           for name, (path, digest) in REPORTS.items()}
        rust = records['rust_lean']
        groups = [(name, rust['private_homes'][key], ['toolchains'], rust['installed_closures'][name])
                  for name, key in [('rustup', 'RUSTUP_HOME'), ('elan', 'ELAN_HOME')]]
        groups += [(name + '_opam', str(Path(records[name]['opam_root']) / records[name]['switch']),
                    tools.INSTALL_FOLDERS, records[name]['opam_installed_closure' if name == 'sail'
                                                       else 'installed_closure'])
                   for name in ['aeneas', 'sail', 'rocq']]
        groups += [('sail_prefix', records['sail']['prefix'], tools.INSTALL_FOLDERS,
                    records['sail']['installed_closure'])]
        report['installations'] = {}
        for name, raw, folders, expected in groups:
            prefix = anchored(ROOT, raw)
            require(tools.locations.installation_inventory(prefix, folders) == expected,
                    'installation drift: ' + name)
            report['installations'][name] = {'absolute_path': str(prefix),
                'relative_to_checkout': str(prefix.relative_to(ROOT)), 'folders': folders,
                **inventory_summary(expected)}
        controls = {name: control_files(anchored(ROOT, records[name]['opam_root']), records[name]['switch'])
                    for name in ['aeneas', 'sail', 'rocq']}
        report['opam_control_observation'] = controls
        report['regular_bytes'] = sum(row['regular_bytes'] for row in report['installations'].values())
        report['closure_scope_note'] = ('Six installation inventories only; excludes admitted v2 payload, '
            'compiler source Git trees, bootstrap/system libraries, and complete OPAM root state.')
        save()
        original = Path(records['sail']['prefix'])
        copied = out / 'sail-prefix'
        copy_prefix(original, copied, records['sail']['installed_closure'], tools.INSTALL_FOLDERS)
        (out / 'tmp').mkdir()
        env = smoke_environment(copied, out / 'tmp')
        report['smoke_environment'] = env
        binary = copied / 'bin/sail'
        require(sha(binary) == tools.BINARIES['sail'], 'copied Sail binary differs')
        require(stage('version', [binary, '--version'], env) == tools.VERSIONS['sail'], 'copied Sail version')
        require(stage('support-directory', [binary, '--dir'], env) == str(copied / 'share/sail'),
                'copied Sail reports another support directory')
        fixture = ROOT / 'scripts/fixtures/tool_install_smoke.sail'
        stage('generate-c', [binary, '-c', fixture, '-o', out / 'smoke'], env)
        (out / 'smoke-lean').mkdir()
        stage('generate-lean', [binary, '--lean', '--lean-single-file', fixture,
              '--lean-output-dir', out / 'smoke-lean'], env)
        outputs = [out / 'smoke.c', *sorted((out / 'smoke-lean').rglob('*.lean'))]
        require(len(outputs) > 1 and all(p.is_file() and p.stat().st_size > 0 for p in outputs), 'empty smoke output')
        report['smoke_outputs'] = {str(p.relative_to(out)): sha(p) for p in outputs}
        report['old_smoke_output_comparison'] = {name: digest == records['sail']['smoke_outputs'].get(name)
                                                for name, digest in report['smoke_outputs'].items()}
        for name, raw, folders, expected in groups:
            require(tools.locations.installation_inventory(Path(raw), folders) == expected,
                    'original installation changed: ' + name)
        require(tools.locations.installation_inventory(copied, tools.INSTALL_FOLDERS) ==
                records['sail']['installed_closure'], 'copied installation changed during smoke')
        require(controls == {name: control_files(Path(records[name]['opam_root']), records[name]['switch'])
                            for name in controls}, 'observed OPAM control changed')
        for name, (relative, digest) in REPORTS.items():
            require(sha(ROOT / relative) == digest, 'installation report changed: ' + name)
        report['inputs_after'] = audit.snapshot()
        report['review_sources_after'] = {str(p.relative_to(ROOT)): sha(p) for p in source_files}
        require(report['inputs_before'] == report['inputs_after'] and
                report['review_sources_before'] == report['review_sources_after'], 'review input drift')
        report['status'] = 'installation_inventory_and_copied_sail_smoke_passed_distribution_incomplete'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    report['finished_at'] = stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'),
                      'error': report.get('error')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix='install-distribution-', dir=ROOT / 'artifacts/boundary-check'))
    return run(out)


if __name__ == '__main__':
    raise SystemExit(main())
