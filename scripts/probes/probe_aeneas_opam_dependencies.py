#!/usr/bin/env python3
"""Rebuild Aeneas's 116 frozen OPAM dependencies in a new private root.

This prepares the compiler build; it does not build/adopt Aeneas itself, rerun
translator qualification, or claim a complete Week6 clean-room.
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
from probes import probe_isolated_sail as sail
from probes.probe_release_runtime import now
from source_snapshot import require

LOCK = ROOT / 'docs/release/aeneas-switch.export'
LOCK_SHA = 'bfa3265986b21625b49f8dec3713c078db1c3cd327da64ea9e775a70f6a46237'
SWITCH = 'isolated-aeneas'
FORMULA = '"ocaml-base-compiler" {= "5.2.1"}'
HEADER = 'compiler: ["ocaml-base-compiler.5.2.1"]\n'


def pin_command(opam):
    return [opam, 'switch', 'set-invariant', '--switch=' + SWITCH, '--yes', '--formula=' + FORMULA]


def packages():
    require(sail.sha(LOCK) == LOCK_SHA, 'Aeneas dependency lock drift')
    match = re.search(r'^installed: \[\n(.*?)^\]', LOCK.read_text(), re.M | re.S)
    require(match is not None, 'missing locked package list')
    rows = re.findall(r'^  "([^"\n]+)"$', match[1], re.M)
    pairs = [row.split('.', 1) for row in rows]
    result = dict(pairs)
    require(len(pairs) == len(result) == 116, 'invalid Aeneas package inventory')
    return result


def check_packages(text):
    rows = [line.split() for line in text.splitlines() if line.strip()]
    require(all(len(row) == 2 for row in rows), 'malformed installed package list')
    actual = dict(rows)
    require(len(rows) == len(actual) and actual == packages(), 'installed package set differs')
    return actual


def check_export(text, invariant):
    require(invariant.strip() == '[' + FORMULA + ']', 'compiler invariant is not exact')
    original = LOCK.read_text().strip()
    require(original.count(HEADER) == 1, 'unexpected compiler header')
    exact = text.strip() == original
    require(exact or text.strip() == original.replace(HEADER, '', 1), 'package metadata drift')
    return {'exact_export_bytes': exact, 'compiler_invariant': invariant.strip(),
            'only_export_difference': None if exact else 'top-level compiler list omitted',
            'all_other_export_bytes_identical': True}


def environment(out, original):
    env = sail.environment(out, original)
    for key in list(env):
        if key.startswith(('AENEAS', 'CHARON', 'ROCQ_SPIKE_', 'NIX_', 'SCCACHE', 'CCACHE')) or key in (
                'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'LD_PRELOAD'):
            env.pop(key)
    env['OPAMSWITCH'] = SWITCH
    return env


def run_probe(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'aeneas_compiler_built': False, 'charon_ml_built': False, 'kernel_executed': False,
              'policy_changed': False, 'clean_room_claimed': False, 'third_party_claimed': False,
              'release_claimed': False, 'os_sandboxed': False, 'old_build_cache_copied': False,
              'upstream_charon_visitors_constraint_satisfied': False,
              'constraint_note': 'Recorded build lock has visitors 20250212; pinned Charon opam metadata asks >=20260520. No silent upgrade; later source build/qualification must report this boundary.'}
    env = environment(out, os.environ)

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(out), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> aeneas-opam: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'Aeneas dependency stage failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=sail.sha(log))
            save()
        return log.read_text().strip()

    try:
        packages()
        paths = [LOCK, Path(__file__), ROOT / 'scripts/probes/probe_isolated_sail.py',
                 ROOT / 'scripts/probes/probe_isolated_rocq.py', ROOT / 'scripts/probes/probe_isolated_rust_lean.py',
                 ROOT / 'scripts/probes/probe_release_runtime.py', ROOT / 'scripts/source_snapshot.py',
                 ROOT / 'proof/lean/audit/step-policy.json', ROOT / 'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)): sail.sha(p) for p in paths}
        opam = Path(shutil.which('opam', path=env['PATH']) or '').resolve(strict=True)
        require(opam.is_file() and os.access(opam, os.X_OK), 'missing OPAM bootstrap')
        report['bootstrap'] = {'path': str(opam), 'sha256': sail.sha(opam)}
        root = out / 'opam-root'
        require(not root.exists() and not root.is_symlink(), 'OPAM root must be absent')
        report['opam_root_initially_absent'] = True
        report['opam_root'] = str(root)
        report['switch'] = SWITCH
        repo = out / 'empty-repository'
        repo.mkdir()
        (repo / 'repo').write_text('opam-version: "2.0"\n')
        stage('opam-version', [opam, '--version'])
        stage('init', [opam, 'init', '--bare', '--no-setup', '--no-opamrc', '--disable-sandboxing', '--yes', 'locked', repo])
        stage('import-build', [opam, 'switch', 'import', '--switch=' + SWITCH, '--no-switch', '--yes',
              '--jobs=4', '--require-checksums', '--assume-depexts', LOCK], 7200)
        report['packages'] = check_packages(stage('packages', [opam, 'list', '--switch=' + SWITCH,
            '--installed', '--short', '--columns=name,version']))
        stage('pin-compiler', pin_command(opam))
        invariant = stage('invariant', [opam, 'switch', 'invariant', '--switch=' + SWITCH])
        export = out / 'switch.export'
        stage('export', [opam, 'switch', 'export', '--switch=' + SWITCH, '--full', export])
        report['export_review'] = check_export(export.read_text(), invariant)
        report['export_sha256'] = sail.sha(export)
        prefix = root / SWITCH
        compiler = sail.rocq.private_binary(stage('compiler-path', [opam, 'exec', '--switch=' + SWITCH,
            '--', 'which', 'ocamlopt']), prefix)
        require(stage('compiler-version', [opam, 'exec', '--switch=' + SWITCH, '--', compiler, '-version']) == '5.2.1',
                'OCaml compiler version differs')
        report['compiler'] = {'path': str(compiler), 'sha256': sail.sha(compiler)}
        report['installed_closure'] = sail.rocq.installed_inventory(prefix)
        report['inputs_after'] = {str(p.relative_to(ROOT)): sail.sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        require(sail.sha(opam) == report['bootstrap']['sha256'], 'bootstrap drift')
        report['status'] = 'aeneas_dependencies_rebuilt_compiler_and_qualification_pending'
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
        destination = Path(tempfile.mkdtemp(prefix='aeneas-opam-', dir=ROOT / 'artifacts/boundary-check'))
    print(destination, flush=True)
    sys.exit(run_probe(destination))
