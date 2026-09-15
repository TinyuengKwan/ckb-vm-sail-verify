#!/usr/bin/env python3
"""Regenerate and publish an exact Sail model tree, retaining recoverable backups.

Generation starts without the previous backend output directory. Adaptation is
performed in a new staging directory; failed generation/adaptation never replaces
the published model. This is installation hygiene, not a proof or policy update.
"""
import json
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def directory_path(path):
    path = Path(path).absolute()
    require(path == path.resolve(), 'symlink or noncanonical directory: ' + str(path))
    require(path != Path('/') and path != Path.home().resolve(), 'broad directory target')
    require(not path.exists() or path.is_dir(), 'directory target is not a directory')
    return path


def regular_tree(path):
    """Reject links, special files and cached compiler inputs in fresh outputs."""
    require(path.is_dir() and not path.is_symlink(), 'missing fresh generated directory')
    files = []
    for base, dirs, names in os.walk(path, followlinks=False):
        for name in dirs + names:
            entry = Path(base) / name
            mode = entry.lstat().st_mode
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'nonregular generated entry: ' + str(entry))
            require(name not in ('.lake', '.git', 'target', '__pycache__') and
                    entry.suffix not in ('.olean', '.ilean', '.o', '.so', '.a', '.vo', '.vos', '.vok'),
                    'cached/generated binary input: ' + str(entry))
            if stat.S_ISREG(mode):
                require(entry.stat().st_nlink == 1, 'hardlinked generated file: ' + str(entry))
                files.append(entry.relative_to(path).as_posix())
    require(files, 'empty fresh generated directory')
    return sorted(files)


def replace_model(source, destination, generate, adapt):
    """Callbacks: generate() must recreate source; adapt(stage) edits only stage.

    The caller must serialize generation for this build directory. No directory
    is recursively deleted. Backups and failed outputs are retained beside the
    corresponding directory, including on exceptions, for explicit recovery.
    """
    source, destination = directory_path(source), directory_path(destination)
    require(source != destination and not source.is_relative_to(destination) and
            not destination.is_relative_to(source), 'overlapping model directories')
    require(source.parent.is_dir(), 'missing configured generation parent')
    destination.parent.mkdir(parents=True, exist_ok=True)
    generated_backup = Path(tempfile.mkdtemp(prefix='.sail-generation-', dir=source.parent))
    install = Path(tempfile.mkdtemp(prefix='.sail-install-', dir=destination.parent))
    previous_source = generated_backup / 'previous'
    previous_destination = install / 'previous'
    stage = install / 'staged'
    record = {'status': 'running', 'source': str(source), 'destination': str(destination),
              'generation_backup': str(generated_backup), 'installation_backup': str(install),
              'old_source_saved': False, 'old_destination_saved': False,
              'published': False, 'policy_changed': False}
    generation_started = False

    def save():
        (install / 'transaction.json').write_text(json.dumps(record, indent=2) + '\n')

    save()
    try:
        if source.exists():
            source.rename(previous_source)
            record['old_source_saved'] = True
            save()
        # Missing CMake output forces actual generation, including when upstream
        # custom commands omit the configuration from their dependency list.
        generation_started = True
        generate()
        record['raw_files'] = regular_tree(source)
        shutil.copytree(source, stage)
        adapt(stage)
        record['installed_files'] = regular_tree(stage)
        # Recheck directory identities before moving an existing publication.
        require(directory_path(destination) == destination, 'destination changed')
        if destination.exists():
            destination.rename(previous_destination)
            record['old_destination_saved'] = True
            save()
        stage.rename(destination)
        record['published'] = True
        record['status'] = 'installed'
        save()
        return record
    except BaseException as error:
        record.update(status='failed', error=str(error), error_type=type(error).__name__)
        # If publication did not happen, restore both original names without
        # discarding any generated or adapted diagnostic output.
        if not record['published']:
            if record['old_destination_saved'] and not destination.exists():
                previous_destination.rename(destination)
                record['destination_restored'] = True
            if generation_started and (source.exists() or source.is_symlink()):
                source.rename(generated_backup / 'failed-output')
            if record['old_source_saved']:
                previous_source.rename(source)
                record['source_restored'] = True
        save()
        error.add_note('Recoverable Sail transaction: ' + str(install / 'transaction.json'))
        raise


def run_backend(root, backend, sail_directory=None, runner=subprocess.run):
    root = directory_path(root)
    require(backend in ('lean', 'rocq', 'coq'), 'backend must be lean or rocq')
    backend = 'rocq' if backend == 'coq' else backend
    sail = directory_path(sail_directory or root / 'deps/sail-riscv')
    build = directory_path(sail / 'build')
    require(build.is_dir(), 'Sail CMake build is not configured; run make sail-emu')
    cache = build / 'CMakeCache.txt'
    require(cache.is_file() and not cache.is_symlink(), 'missing regular CMake cache')
    settings = dict(line.split('=', 1) for line in cache.read_text().splitlines()
                    if '=' in line and not line.startswith(('#', '//')))
    require(settings.get('CMAKE_HOME_DIRECTORY:INTERNAL') == str(sail), 'CMake source directory mismatch')
    source = build / ('model/Lean_RV64D' if backend == 'lean' else 'rocq')
    destination = root / ('proof/lean/generated/sail' if backend == 'lean' else 'proof/rocq/generated/sail')
    config = root / 'sail-model/build/ckb_vm_config.json'
    build_config = build / 'config/rv64d_v256_e64.json'

    def command(argv):
        runner(list(map(str, argv)), cwd=root, check=True)

    # Serialize both backends because they share the materialized configuration.
    lock = build / '.sail-proof-generation.lock'
    require(not lock.is_symlink(), 'linked generation lock')
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not config.is_file():
            command(['bash', root / 'scripts/prepare_sail_config.sh'])
        require(config.is_file() and not config.is_symlink(), 'missing regular materialized config')
        require(build_config.is_file() and not build_config.is_symlink(), 'missing regular CMake config')
        config_bytes = config.read_bytes()
        config_sha = hashlib.sha256(config_bytes).hexdigest()

        def generate():
            shutil.copyfile(config, build_config)
            command(['cmake', '--build', build, '--target', 'generated_' + backend + '_rv64d'])
            require(config.read_bytes() == config_bytes and build_config.read_bytes() == config_bytes,
                    'configuration changed during generation')
            required = ('LeanRV64D.lean', 'LeanRV64D/Defs.lean', 'lakefile.toml') if backend == 'lean' else (
                'rv64d.v', 'rv64d_types.v')
            require(all((source / name).is_file() for name in required), 'missing generated backend outputs')

        def adapt(stage):
            shutil.copyfile(config, stage / 'ckb_vm_config.json')
            (stage / 'ckb_vm_config.json.sha256').write_text(config_sha + '  ' +
                str(destination / 'ckb_vm_config.json') + '\n')
            if backend == 'lean':
                command(['bash', root / 'scripts/configure_lean_project.sh', 'lean', stage])
            require(config.read_bytes() == config_bytes and
                    (stage / 'ckb_vm_config.json').read_bytes() == config_bytes,
                    'configuration changed during adaptation')

        return replace_model(source, destination, generate, adapt)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=['lean', 'rocq', 'coq'])
    args = parser.parse_args()
    result = run_backend(Path(__file__).resolve().parents[1], args.backend, os.environ.get('SAIL_RISCV_DIR'))
    print('SAIL_INSTALL_JSON=' + json.dumps(result, sort_keys=True))
