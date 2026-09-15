#!/usr/bin/env python3
"""Finalize the retained fresh dependency build after a CLI argument failure.

The original failed report/logs/source are immutable inputs. No package cache
copy or rebuild, no Aeneas compiler/qualification or full clean-room claim.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_aeneas_opam_dependencies as build
from probes.probe_release_runtime import now
from source_snapshot import require

BASE = ROOT / 'artifacts/boundary-check/aeneas-opam-qhtaephh/report.json'
BASE_SHA = '62fdda2673d42c2775ede24910439bcb13f1d41a543e04872d0b1aae8bc9539d'


def run(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': now(), 'stages': [],
              'base_report': str(BASE), 'base_report_sha256': BASE_SHA,
              'existing_fresh_package_build_reused': True, 'packages_rebuilt_in_finalization': False,
              'aeneas_compiler_built': False, 'charon_ml_built': False, 'kernel_executed': False,
              'clean_room_claimed': False, 'third_party_claimed': False, 'release_claimed': False,
              'policy_changed': False, 'os_sandboxed': False}
    env = None

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def stage(name, argv):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(out), 'started_at': now()}
        report['stages'].append(row)
        save()
        print('==> finalize-aeneas-opam: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=300)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'metadata finalization failed: ' + name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=build.sail.sha(log))
            save()
        return log.read_text().strip()

    try:
        require(build.sail.sha(BASE) == BASE_SHA, 'base report drift')
        old = json.loads(BASE.read_text())
        require(old['status'] == 'failed' and old['error'] == 'Aeneas dependency stage failed: pin-compiler',
                'unexpected base failure')
        expected = [('opam-version', 0), ('init', 0), ('import-build', 0), ('packages', 0), ('pin-compiler', 2)]
        require([(s['name'], s['exit_code']) for s in old['stages']] == expected, 'source build not completed')
        for s in old['stages']:
            require(build.sail.sha(BASE.parent / s['log']) == s['log_sha256'], 'base log drift')
        for name, digest in old['inputs_before'].items():
            path = BASE.parent / 'probe-source.py' if name == 'scripts/probes/probe_aeneas_opam_dependencies.py' else ROOT / name
            require(build.sail.sha(path) == digest, 'base input drift: ' + name)
        root = Path(old['opam_root'])
        require(root == BASE.parent / 'opam-root' and root.resolve() == root, 'unexpected retained root')
        env = build.environment(BASE.parent, os.environ)
        opam = Path(old['bootstrap']['path'])
        require(build.sail.sha(opam) == old['bootstrap']['sha256'], 'OPAM bootstrap drift')
        paths = [Path(__file__), Path(build.__file__), build.LOCK, BASE, BASE.parent / 'probe-source.py',
                 ROOT / 'scripts/probes/probe_isolated_sail.py', ROOT / 'scripts/probes/probe_isolated_rocq.py',
                 ROOT / 'scripts/probes/probe_isolated_rust_lean.py', ROOT / 'scripts/probes/probe_release_runtime.py',
                 ROOT / 'scripts/source_snapshot.py', ROOT / 'proof/lean/audit/step-policy.json',
                 ROOT / 'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)): build.sail.sha(p) for p in paths}
        report.update(opam_root=str(root), switch=build.SWITCH, bootstrap=old['bootstrap'],
                      constraint_note=old['constraint_note'], upstream_charon_visitors_constraint_satisfied=False)
        prefix = root / build.SWITCH
        before = build.sail.rocq.installed_inventory(prefix)
        report['installed_closure_before_sha256'] = before['sha256']
        build.check_packages(stage('packages-before', [opam, 'list', '--switch=' + build.SWITCH,
            '--installed', '--short', '--columns=name,version']))
        stage('pin-compiler', build.pin_command(opam))
        invariant = stage('invariant', [opam, 'switch', 'invariant', '--switch=' + build.SWITCH])
        export = out / 'switch.export'
        stage('export', [opam, 'switch', 'export', '--switch=' + build.SWITCH, '--full', export])
        report['export_review'] = build.check_export(export.read_text(), invariant)
        report['export_sha256'] = build.sail.sha(export)
        report['packages'] = build.check_packages(stage('packages-after', [opam, 'list', '--switch=' + build.SWITCH,
            '--installed', '--short', '--columns=name,version']))
        compiler = build.sail.rocq.private_binary(stage('compiler-path', [opam, 'exec', '--switch=' + build.SWITCH,
            '--', 'which', 'ocamlopt']), prefix)
        require(stage('compiler-version', [opam, 'exec', '--switch=' + build.SWITCH, '--', compiler, '-version']) == '5.2.1',
                'compiler version drift')
        report['compiler'] = {'path': str(compiler), 'sha256': build.sail.sha(compiler)}
        report['installed_closure'] = build.sail.rocq.installed_inventory(prefix)
        require(report['installed_closure'] == before, 'installed files changed during metadata repair')
        report['inputs_after'] = {str(p.relative_to(ROOT)): build.sail.sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        require(build.sail.sha(opam) == old['bootstrap']['sha256'], 'bootstrap changed')
        report['status'] = 'aeneas_dependencies_rebuilt_metadata_finalized_compiler_pending'
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='aeneas-opam-finalize-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
