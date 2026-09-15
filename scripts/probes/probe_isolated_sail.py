#!/usr/bin/env python3
"""Fresh Sail/OPAM source rebuild and identity comparison, never policy approval.

Reuses host tools and local Git history, not old compiled libraries or caches.
Not OS-sandboxed, not an entire proof-chain or third-party clean-room run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from source_snapshot import require, canonical, inventory, independent
from probes import probe_isolated_rocq as rocq
from probes.probe_isolated_rust_lean import sha
from probes.probe_release_runtime import now

LOCK = ROOT/'docs/release/sail-switch.export'
LOCK_SHA = 'caca2799b1c6e6a79c9d9d03d6843f195ebcbdbf0521caebfbf31631ed576948'
COMMIT = '8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1'
VERSION = 'Sail 0.20.2 (HEAD @ '+COMMIT+')'
POLICY = ROOT/'proof/lean/audit/step-policy.json'
SOURCE = Path('/home/clair/.local/src/sail')
BASELINE = Path('/home/clair/.local/share/sail-src')
FIXTURE = ROOT/'scripts/fixtures/tool_install_smoke.sail'
SWITCH = 'isolated-sail'
COMPILER_FORMULA = '"ocaml-base-compiler" {= "5.4.1"}'
COMPILER_HEADER = 'compiler: ["ocaml-base-compiler.5.4.1"]\n'


def environment(out, original):
    env = rocq.environment(out, original)
    # Dune/OCaml and Sail environment overrides must not redirect this build.
    for key in list(env):
        if key.startswith(('SAIL_', 'DUNE_', 'OCAML', 'ROCQ_SPIKE_', 'GIT_')):
            env.pop(key)
    env.update(OPAMSWITCH=SWITCH, DUNE_CACHE='disabled', OPAMKEEPLOGS='true',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
    env['PATH'] = '/usr/bin:/bin'  # host build tools; opam exec adds only the fresh switch
    return env


def locked_packages():
    require(sha(LOCK) == LOCK_SHA, 'frozen Sail OPAM lock changed')
    block = re.search(r'^installed: \[\n(.*?)^\]', LOCK.read_text(), re.M | re.S)
    require(block is not None, 'missing installed inventory')
    rows = re.findall(r'^  "([^"\n]+)"$', block[1], re.M)
    pairs = [row.split('.', 1) for row in rows]
    require(len(pairs) == 56 and len(dict(pairs)) == len(pairs), 'invalid lock inventory')
    return dict(pairs)


def check_packages(text):
    pairs = [line.split() for line in text.splitlines() if line.strip()]
    require(all(len(p) == 2 for p in pairs), 'malformed package list')
    actual = dict(pairs)
    require(len(actual) == len(pairs) and actual == locked_packages(), 'package inventory drift')
    return actual


def check_export(text, invariant):
    require(invariant.strip() == '['+COMPILER_FORMULA+']', 'compiler invariant is not exact')
    original = LOCK.read_text().strip()
    require(original.count(COMPILER_HEADER) == 1, 'unexpected compiler header')
    exact = text.strip() == original
    require(exact or text.strip() == original.replace(COMPILER_HEADER, '', 1),
            'package metadata differs from frozen export')
    return {'exact_export_bytes':exact, 'compiler_invariant':invariant.strip(),
            'only_export_difference':None if exact else 'top-level compiler list omitted',
            'all_other_export_bytes_identical':True}


def check_source(path):
    result = inventory(path)
    require(result['head'] == COMMIT and not result['gitlinks'] and not result['changes_from_head'],
            'Sail source is not clean pinned commit')
    return result


def identity(version, binary, policy):
    require(version == VERSION, 'Sail is not the pinned source-built version')
    actual, expected = sha(binary), policy['tool_binaries']['sail']
    return {'sha256':actual, 'policy_sha256':expected, 'matches_policy_binary':actual == expected,
            'policy_changed':False, 'new_tool_approved':False}


def run_probe(out, source=SOURCE, baseline=BASELINE):
    env = environment(out, os.environ)
    report = {'schema_version':1, 'status':'running', 'started_at':now(), 'stages':[],
              'clean_room_claimed':False, 'third_party_claimed':False, 'release_claimed':False,
              'os_sandboxed':False, 'proof_chain_executed':False, 'extra_vm_proof_coverage':False,
              'copied_old_binaries_or_build_caches':False, 'host_tools_and_local_git_reused':True,
              'policy_changed':False}
    def save():
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def stage(name, argv, cwd=out, timeout=900, run_env=None):
        row = {'name':name, 'argv':list(map(str,argv)), 'cwd':str(cwd), 'started_at':now()}
        report['stages'].append(row)
        save()
        print('==> isolated-sail: '+name, flush=True)
        log = out/(name+'.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=run_env or env,
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'isolated Sail stage failed: '+name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()
    try:
        require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'unsupported host')
        locked_packages()
        paths = [LOCK, POLICY, FIXTURE, Path(__file__), ROOT/'scripts/source_snapshot.py',
                 ROOT/'scripts/probes/probe_isolated_rocq.py', ROOT/'scripts/probes/probe_isolated_rust_lean.py',
                 ROOT/'scripts/probes/probe_release_runtime.py', ROOT/'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)):sha(p) for p in paths}
        policy = json.loads(POLICY.read_text())
        report['original_source_path'] = str(source)
        report['source_before'] = check_source(source)
        report['baseline_prefix'] = str(baseline)
        report['baseline_closure_before'] = rocq.installed_inventory(baseline)
        require(sha(baseline/'bin/sail') == policy['tool_binaries']['sail'], 'baseline Sail binary drift')
        opam = Path(shutil.which('opam',path=env['PATH']) or '').resolve(strict=True)
        require(opam.is_file() and os.access(opam, os.X_OK), 'missing OPAM bootstrap')
        report['opam_bootstrap'] = {'path':str(opam), 'sha256':sha(opam)}
        root, checkout, prefix = out/'opam-root', out/'sail-source', out/'sail-install'
        require(all(not p.exists() and not p.is_symlink() for p in [root,checkout,prefix]),
                'build destinations must be absent')
        report.update(opam_root=str(root), switch=SWITCH, source=str(checkout), prefix=str(prefix),
                      build_destinations_initially_absent=True)
        stage('clone',['git','clone','--no-hardlinks','--no-checkout',source,checkout])
        stage('checkout',['git','checkout','--detach',COMMIT],cwd=checkout)
        independent(checkout)
        require(check_source(checkout) == report['source_before'], 'cloned source differs')
        require(not (checkout/'_build').exists(), 'old Sail build directory reused')
        repo = out/'empty-repository'
        repo.mkdir()
        (repo/'repo').write_text('opam-version: "2.0"\n')
        report['repository_descriptor_sha256'] = sha(repo/'repo')
        stage('opam-version',[opam,'--version'])
        stage('init',[opam,'init','--bare','--no-setup','--no-opamrc','--disable-sandboxing',
                      '--yes','locked',repo])
        # The lock also contains the release Sail packages from the original
        # dependency switch. They are rebuilt, but NEVER selected for the smoke
        # or substituted for the separately built pinned-commit installation.
        stage('import-build',[opam,'switch','import','--switch='+SWITCH,'--no-switch','--yes',
              '--jobs=4','--require-checksums','--assume-depexts',LOCK],timeout=3600)
        report['packages'] = check_packages(stage('packages',[opam,'list','--switch='+SWITCH,
                                              '--installed','--short','--columns=name,version']))
        stage('pin-compiler-invariant',[opam,'switch','set-invariant','--switch='+SWITCH,
                                       '--yes','--formula='+COMPILER_FORMULA])
        invariant = stage('compiler-invariant',[opam,'switch','invariant','--switch='+SWITCH])
        report['metadata_audit'] = check_export(stage('export-metadata',[opam,'switch','export',
                                           '--switch='+SWITCH,'--full','--freeze','-']),invariant)
        opam_exec = [opam,'exec','--switch='+SWITCH,'--set-switch','--']
        report['build_binaries'] = {}
        for name in ['ocamlc','dune']:
            path = rocq.private_binary(stage(name+'-path',opam_exec+['which',name]),root/SWITCH)
            report['build_binaries'][name] = {'path':str(path), 'sha256':sha(path)}
        require(stage('ocaml-version',opam_exec+['ocamlc','-version']) == '5.4.1', 'OCaml version drift')
        stage('sail-build',opam_exec+['dune','build','@install','-j','4'],cwd=checkout,timeout=3600)
        stage('sail-install',opam_exec+['dune','install','--prefix='+str(prefix)],cwd=checkout)
        binary = rocq.private_binary(str(prefix/'bin/sail'),prefix)
        runtime_env = dict(env, SAIL_DIR=str(prefix/'share/sail'),
                           SAIL_PLUGIN_DIR=str(prefix/'share/libsail/plugins'))
        report['runtime_environment'] = {k:runtime_env[k] for k in ['SAIL_DIR','SAIL_PLUGIN_DIR','PATH']}
        version = stage('sail-version',[binary,'--version'],run_env=runtime_env)
        report['identity'] = identity(version,binary,policy)
        require(Path(stage('sail-dir',[binary,'--dir'],run_env=runtime_env)).resolve() == prefix/'share/sail',
                'Sail support directory escaped new prefix')
        # Generation only: no inference that this is an ADD theorem or full model check.
        stage('smoke-c',[binary,'-c',FIXTURE,'-o',out/'smoke'],run_env=runtime_env)
        (out/'smoke-lean').mkdir()
        stage('smoke-lean',[binary,'--lean','--lean-single-file',FIXTURE,
                           '--lean-output-dir',out/'smoke-lean'],run_env=runtime_env)
        generated = [out/'smoke.c', *sorted((out/'smoke-lean').rglob('*.lean'))]
        require(len(generated) > 1 and all(p.is_file() and p.stat().st_size > 0 for p in generated),
                'empty backend generation smoke')
        report['smoke_outputs'] = {str(p.relative_to(out)):sha(p) for p in generated}
        report['generation_smoke_passed'] = True
        report['installed_closure'] = rocq.installed_inventory(prefix)
        report['opam_installed_closure'] = rocq.installed_inventory(root/SWITCH)
        report['source_after'] = check_source(checkout)
        require(check_source(source) == report['source_before'] == report['source_after'], 'source drift')
        require(rocq.installed_inventory(baseline) == report['baseline_closure_before'], 'original installation changed')
        report['baseline_unchanged'] = True
        report['inputs_after'] = {str(p.relative_to(ROOT)):sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'probe/policy/input drift')
        require(sha(opam) == report['opam_bootstrap']['sha256'] and
                sha(repo/'repo') == report['repository_descriptor_sha256'], 'bootstrap/repository drift')
        report['status'] = ('isolated_sail_rebuild_policy_binary_match' if report['identity']['matches_policy_binary']
                            else 'isolated_sail_rebuild_identity_review_required')
        code = 0 if report['identity']['matches_policy_binary'] else 2
    except (Exception,KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status':report['status'],'report':str(out/'report.json')}),flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--baseline',type=Path,default=BASELINE)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True,exist_ok=False)
    else:
        parent = ROOT/'artifacts/boundary-check'
        parent.mkdir(parents=True,exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='isolated-sail-',dir=parent))
    print(out,flush=True)
    return run_probe(out,args.source.resolve(),args.baseline.resolve())


if __name__ == '__main__':
    sys.exit(main())
