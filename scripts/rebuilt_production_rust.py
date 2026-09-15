#!/usr/bin/env python3
"""Stage production extraction with admitted base tools, without installing it.

Preserves the baseline-bound selection config (including its historical tool
label). Rebuilt tool identities come separately from the admitted catalogue.
This local fresh-source/cache run is not tool adoption or a clean-room proof.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import decoder_rebuilt_locations as locations
import source_snapshot as snapshot

ROOT = snapshot.ROOT
CONFIG = 'proof/lean/extraction/ckb-vm.json'
CONFIG_SHA = '376381a95376b9fdf39c12b930f921f321243bb01f66b71bf3c7fb81dde2d0db'
MODEL_SHA = '9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e'
STATUS = 'production_rust_staged_identity_verified_main_adoption_pending'
BOUNDARIES = ('formal_outputs_installed', 'main_tools_adopted', 'kernel_executed',
              'compilers_rebuilt', 'old_llbc_translated', 'old_project_cache_copied',
              'os_sandboxed', 'clean_room_claimed', 'third_party_claimed', 'release_claimed')
require, sha, read = locations.require, locations.sha, locations.read


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def configuration(root):
    require(sha(root / CONFIG) == CONFIG_SHA, 'baseline-bound production selection changed')
    return read(root / CONFIG)


def extraction_command(binary, llbc, sysroot, config):
    require(config['preset'] == 'aeneas', 'unexpected production preset')
    result = [str(binary), 'cargo', '--preset=aeneas', '--sysroot', str(sysroot),
              '--dest-file', str(llbc), '--start-from', config['root']]
    for flag in ('include', 'opaque'):
        for name in config[flag]:
            result.extend(['--' + flag, name])
    return result + ['--', '--lib']


def model_identity(fresh, archived):
    require(sha(fresh) == sha(archived) == MODEL_SHA,
            'production whole-file identity differs; no normalization permitted')
    return {'sha256': MODEL_SHA, 'whole_file_identical': True, 'normalization_used': False}


def input_state():
    files = {Path(__file__).resolve(), ROOT / 'scripts/tests/test_rebuilt_production_rust.py',
             ROOT / CONFIG, locations.admitted.POLICY, locations.admitted.CATALOGUE,
             ROOT / 'proof/lean/audit/step-policy.json',
             ROOT / 'proof/lean/decoder/public-rebuilt-policy.json'}
    files.update(Path(m.__file__).resolve() for m in list(sys.modules.values())
                 if getattr(m, '__file__', None) and
                 Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
    return {str(path): sha(path) for path in sorted(files)}


def stage(report, out, name, command, cwd, env):
    row = {'name': name, 'argv': list(map(str, command)), 'cwd': str(cwd),
           'started_at': now(), 'log': name + '.log'}
    report['stages'].append(row)
    write(out / 'report.json', report)
    print('==> rebuilt-production-rust: ' + name, flush=True)
    log = out / row['log']
    try:
        with log.open('xb') as stream:
            result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=900)
        row['exit_code'] = result.returncode
        require(result.returncode == 0, 'stage failed: ' + name)
        return log.read_text().strip()
    finally:
        row.update(finished_at=now(), log_sha256=sha(log))
        write(out / 'report.json', report)


def clone_source(out, state, execute):
    checkout = out / 'checkout'
    snapshot.export(ROOT, state, out / 'source-payload')
    write(out / 'source-snapshot.json', state)
    for repo, info in state['repositories'].items():
        label = 'root' if repo == '.' else repo.replace('/', '-')
        dest = checkout if repo == '.' else checkout / repo
        execute('clone-' + label, ['git', 'clone', '--no-hardlinks', '--no-checkout', ROOT / repo, dest], out)
        execute('checkout-' + label, ['git', 'checkout', '--detach', info['head']], dest)
        snapshot.independent(dest)
    snapshot.restore(checkout, out / 'source-payload', state)
    return checkout


def run(out, directory):
    sys.setrecursionlimit(100000)
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              **dict.fromkeys(BOUNDARIES, False)}
    try:
        report['inputs_before'] = input_state()
        installed, public = locations.configuration(directory)
        runtime = locations.runtime(directory)
        payload = Path(installed['payload'])
        components = read(payload / 'evidence/joint_extraction.json')['components']
        base = components['tools']['base']
        config = configuration(ROOT)
        source = snapshot.capture(ROOT)
        report.update(installed_before=installed, runtime_before=runtime,
                      production_selection_sha256=CONFIG_SHA,
                      historical_aeneas_label=config['aeneas'],
                      source_snapshot_sha256=source['snapshot_sha256'])
        env = locations.environment(out, runtime, public)
        for folder in ('cargo', 'cargo-target', 'charon-cache'):
            require(not (out / folder).exists(), 'old extraction cache')
        require(not any(k.startswith('AENEAS') for k in env), 'public translation flags leaked')
        report['environment'] = {k: env[k] for k in ('PATH', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN',
            'CARGO_HOME', 'CARGO_TARGET_DIR', 'CHARON_CACHE_DIR', 'OPAMROOT', 'OPAMSWITCH')}

        def execute(name, args, cwd=out):
            return stage(report, out, name, args, cwd, env)

        checkout = clone_source(out, source, execute)
        require(configuration(checkout) == config, 'cloned selection differs')
        report['checkout'] = str(checkout)
        require(execute('rustc-path', ['rustup', 'which', '--toolchain', public['rust_toolchain'], 'rustc']) ==
                runtime['rustc'], 'private Rust path differs')
        require('commit-hash: ' + public['rust_commit'] in execute('rust-version', [runtime['rustc'], '-vV']),
                'private Rust version differs')
        charon, aeneas = payload / 'bin/base/charon', payload / 'bin/base/aeneas'
        require(execute('charon-version', [charon, 'version']) == config['charon'], 'base Charon version differs')
        actual = execute('aeneas-version', locations.translator_command(runtime, aeneas, ['-version']))
        require(actual == base['aeneas_version'], 'rebuilt base Aeneas version differs')
        report['rebuilt_aeneas_version'] = actual
        report['tools'] = {name: {'path': str(payload / 'bin/base' / name),
                                 'sha256': sha(payload / 'bin/base' / name)}
                           for name in ('charon', 'charon-driver', 'aeneas')}
        execute('fetch-production', ['cargo', 'fetch', '--locked', '--target', public['target']], checkout)
        env['CARGO_NET_OFFLINE'] = 'true'
        llbc, generated = out / 'CkbVmProduction.llbc', out / 'generated'
        cwd = checkout / 'crates/proof-extract'
        execute('extract-production', extraction_command(charon, llbc, payload / 'sysroot', config), cwd)
        report['extraction_metadata'] = locations.legacy._compare_metadata(
            read(payload / 'llbc/CkbVmProduction.llbc'), read(llbc), payload / 'sysroot')
        execute('translate-production', locations.translator_command(runtime, aeneas,
                [*config['aeneas_args'], '-dest', generated, llbc]), cwd)
        report['model_identity'] = model_identity(generated / 'CkbVmProduction.lean',
                                                  payload / 'models/CkbVmProduction.lean')
        report['llbc_sha256'] = sha(llbc)
        require(snapshot.capture(checkout) == source == snapshot.capture(ROOT), 'source changed during staging')
        report['installed_after'] = locations.load(directory)
        report['runtime_after'] = locations.runtime(directory)
        report['inputs_after'] = input_state()
        require(report['installed_before'] == report['installed_after'] and
                report['runtime_before'] == report['runtime_after'] and
                report['inputs_before'] == report['inputs_after'], 'staging input drift')
        report['status'] = STATUS
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    write(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=ROOT / 'artifacts/decoder-inputs/rebuilt-v2')
    parser.add_argument('--out', type=Path, help='new directory only; formal outputs are never installed')
    args = parser.parse_args()
    if args.out:
        out = args.out.absolute()
        require(not out.exists() and not out.is_symlink(), 'output directory already exists')
        require(not any(p.is_symlink() for p in out.parents), 'linked output ancestor')
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix='rebuilt-production-rust-', dir=ROOT / 'artifacts/boundary-check'))
    return run(out, args.inputs.absolute())


if __name__ == '__main__':
    sys.exit(main())
