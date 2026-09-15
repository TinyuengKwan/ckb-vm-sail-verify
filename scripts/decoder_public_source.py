"""Source re-extraction for the isolated public decoder check (not adoption)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_reextraction(archived, fresh):
    """Allow the output filename to move, never silently relax extraction flags.

    This is not an AST equivalence claim. The caller separately requires exact
    generated Lean bytes and kernel theorem/body/contract snapshots.
    """
    require(not fresh['has_errors'], 'fresh LLBC has frontend errors')
    require(fresh['charon_version'] == archived['charon_version'], 'Charon format changed')
    for key in ['crate_name', 'target_information']:
        require(fresh['translated'][key] == archived['translated'][key], key + ' changed')
    old = dict(archived['translated']['options'])
    new = dict(fresh['translated']['options'])
    old.pop('dest_file')
    new.pop('dest_file')
    require(new == old, 'fresh LLBC extraction options changed')


def reextract(inputs, out, run, report, archived_public, archived_iterator):
    """Use verified installed inputs and a new harness/target, never old builds."""
    import decoder_rebuilt_locations as locations
    import decoder_harness as harness
    installed = locations.load(inputs)
    payload = Path(installed['payload'])
    fixtures = ROOT / 'proof/lean/decoder/toolchain'
    config_path = payload / 'candidate/extraction.json'
    config = json.loads(config_path.read_text())
    outer = out / 'outer'
    harness_before = harness.prepare(outer, ROOT)
    iterator_source = fixtures / 'fnptr-experimental/fnptr_cases.rs'
    paths = {
        outer / 'lib.rs': config['outer_root_source_sha256'],
        fixtures / 'full-mir/OuterRoot.rs': config['outer_root_source_sha256'],
        outer / 'Cargo.lock': config['outer_cargo_lock_sha256'],
        outer / 'Cargo.toml': sha(outer / 'Cargo.toml'),
        iterator_source: '030b33d30abb63491fa97017fc1d558f2d3bf3c49c53eff38792704cf101272e',
    }
    for path, digest in paths.items():
        require(sha(path) == digest, 'Rust input identity changed: ' + str(path))
    sysroot = payload / 'sysroot'
    # This earlier, immutable report recorded every library in this sysroot.
    # Recording the current files alone would not pin the standard library.
    previous = payload / 'qualification/sysroot.json'
    require(sha(previous) == '13d82971a424442ea3fc4fbd4deda0672cb1725c0cda9e32817465830a618516',
            'sysroot identity report changed')
    libraries = {p.name: sha(p) for p in sorted(
        (sysroot / 'lib/rustlib/x86_64-unknown-linux-gnu/lib').iterdir()) if p.is_file()}
    require(libraries == json.loads(previous.read_text())['libraries'],
            'full-MIR standard library changed')
    runtime = locations.runtime(inputs)
    env = locations.environment(out, runtime, config)
    for key in ['RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_RUSTFLAGS',
                'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER', 'RUSTC', 'RUSTDOC',
                'CHARON_ARGS', 'CHARON_LOG', 'RUST_LOG']:
        env.pop(key, None)
    target = out / 'cargo-target'
    require(all(not (out / name).exists() for name in ['cargo', 'cargo-target', 'charon-cache']), 'Cargo target/cache is not new')
    env['CARGO_TARGET_DIR'] = str(target)
    version = subprocess.check_output(['rustc', '-vV'], env=env, text=True)
    require('commit-hash: ' + config['rust_commit'] in version, 'Rust compiler changed')
    info = {'configuration_sha256': sha(config_path), 'source_before': {str(p): sha(p) for p in paths},
            'runtime_before': runtime,
            'sysroot_libraries': libraries, 'rustc_version': version,
            'cargo_target_initially_absent': True, 'sysroot_rebuilt': False,
            'installed_inputs': installed, 'harness_before': harness_before}
    report['source_reextraction'] = info
    run('fetch-public-rust', ['cargo', 'fetch', '--locked', '--target', config['target']], outer, env)
    env['CARGO_NET_OFFLINE'] = 'true'
    charon = payload / 'bin/charon'
    public = out / 'OuterClosedDepsV3.llbc'
    iterator = out / 'FnPtrFullMir.llbc'
    command = [charon, 'cargo', '--preset=aeneas', '--sysroot', sysroot, '--dest-file', public]
    for option, key in [('start-from', 'outer_start_from'), ('include', 'outer_include'),
                        ('opaque', 'outer_opaque')]:
        for pattern in config[key]:
            command.extend(['--' + option, pattern])
    run('extract-public-rust', command + ['--', *config['outer_cargo_args']], outer, env)
    command = [charon, 'rustc', '--preset=aeneas', '--sysroot', sysroot, '--dest-file', iterator]
    for pattern in archived_iterator['translated']['options']['include']:
        command.extend(['--include', pattern])
    # Keep compiler output inside the new directory, not the source checkout.
    run('extract-iterator-rust', command + ['--', iterator_source, '--crate-type=lib'], out, env)
    info['inputs'] = {}
    for path, archived in [(public, archived_public), (iterator, archived_iterator)]:
        data = json.loads(path.read_bytes())
        mapping = locations.check_extraction(data, inputs, path.name)
        info['inputs'][path.name] = {'sha256': sha(path), 'options': data['translated']['options'],
                                    'location_mapping': mapping}
    info['harness_after'] = harness.verify(outer, ROOT)
    require(info['harness_after'] == harness_before, 'harness changed during extraction')
    require(locations.load(inputs) == installed, 'installed inputs changed during extraction')
    info['source_after'] = {str(p): sha(p) for p in paths}
    require(info['source_after'] == info['source_before'], 'Rust extraction inputs changed during run')
    info['runtime_after'] = locations.runtime(inputs)
    require(info['runtime_after'] == runtime, 'runtime installation changed')
    report['rust_reextracted'] = True
    return public, iterator
