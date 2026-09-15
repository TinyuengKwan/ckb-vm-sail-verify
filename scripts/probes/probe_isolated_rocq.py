#!/usr/bin/env python3
"""Rebuild the frozen Rocq switch in a fresh OPAM root, then rerun NO-GO.

Reuses host OS/build tools, OPAM bootstrap and existing extraction inputs and
translators. Package builds are NOT OS-sandboxed. Never a full clean-room claim.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rocq_spike as spike
from source_snapshot import require, canonical
from probes.probe_isolated_rust_lean import sha
from probes.probe_release_runtime import now

LOCK = ROOT / 'docs/release/rocq-switch.export'
LOCK_SHA = '07f9b97b579da3d67f99d50e0815aa764b36b998e13e0b0221ce38168814691f'
SWITCH = 'isolated-rocq'
COMPILER_FORMULA = '"ocaml-base-compiler" {= "5.2.1"}'
COMPILER_HEADER = 'compiler: ["ocaml-base-compiler.5.2.1"]\n'
PACKAGES = {
    **{name: 'base' for name in ['base-bigarray','base-domains','base-nnp','base-threads','base-unix']},
    'conf-gmp':'5', 'conf-linux-libc-dev':'0', 'conf-pkg-config':'5', 'dune':'3.23.1',
    'ocaml':'5.2.1', 'ocaml-base-compiler':'5.2.1', 'ocaml-config':'3',
    'ocaml-options-vanilla':'1', 'ocamlfind':'1.9.8', 'rocq-core':'9.1.1',
    'rocq-runtime':'9.1.1', 'rocq-sail-stdpp':'0.20.2', 'rocq-stdlib':'9.0.0',
    'rocq-stdpp':'1.13.0', 'rocq-stdpp-bitvector':'1.13.0', 'zarith':'1.14'}
STRIP = ['COQPATH','ROCQPATH','OCAMLPATH','OCAMLLIB','OCAML_TOPLEVEL_PATH',
         'CAML_LD_LIBRARY_PATH','CAML_LD_LIBRARY','LD_LIBRARY_PATH','DUNE_CACHE',
         'DUNE_CACHE_ROOT','DUNE_CACHE_STORAGE_MODE','MAKEFLAGS']


def environment(out, original):
    env = {k:v for k,v in original.items() if not k.startswith('OPAM') and k not in STRIP}
    # Remove old switch search paths; opam exec supplies the new prefix itself.
    env['PATH'] = os.pathsep.join(p for p in env.get('PATH','').split(os.pathsep)
        if p and '/.opam/' not in p and '/_opam/' not in p and not p.endswith('/ocaml-switch/bin'))
    env.update(OPAMROOT=str(out/'opam-root'), OPAMSWITCH=SWITCH, OPAMJOBS='4',
               OPAMDOWNLOADJOBS='4', OPAMNOENVNOTICE='true', DUNE_CACHE='disabled',
               ROCQ_SPIKE_SWITCH=SWITCH, ROCQ_SPIKE_WORK=str(out/'spike'))
    return env


def check_packages(text):
    actual = spike.check_packages(text)
    require(actual == PACKAGES, 'full installed package inventory differs from lock')
    return actual


def check_export(text, invariant):
    # OPAM 2.1.5's import/export omits the top-level compiler list even
    # after an exact switch invariant is explicitly installed. Require the
    # real invariant separately; all other export bytes must match the lock.
    require(invariant.strip() == '['+COMPILER_FORMULA+']', 'compiler invariant is not exact')
    original = LOCK.read_text().strip()
    require(original.count(COMPILER_HEADER) == 1, 'unexpected lock compiler header')
    exact = text.strip() == original
    require(exact or text.strip() == original.replace(COMPILER_HEADER,'',1),
            'package definitions or switch metadata differ from frozen export')
    return {'exact_export_bytes':exact, 'compiler_invariant':invariant.strip(),
            'only_export_difference':None if exact else 'top-level compiler list omitted',
            'all_other_export_bytes_identical':True}


def private_binary(text, prefix):
    path = Path(text.strip()).resolve(strict=True)
    require(path.is_relative_to(prefix.resolve()) and path.is_file() and os.access(path, os.X_OK),
            'compiler is outside the private switch or not executable')
    require(path.stat().st_nlink == 1, 'shared/hardlinked compiler')
    return path


def installed_inventory(prefix):
    """Installed files only; build/download caches are retained separately."""
    prefix = prefix.resolve()
    files = {}
    for folder in ['bin','sbin','lib','libexec','share','etc','doc','man','include']:
        directory = prefix / folder
        require(not directory.is_symlink(), 'external installed directory')
        if not directory.exists(): continue
        for path in sorted(directory.rglob('*')):
            name = path.relative_to(prefix).as_posix()
            if path.is_symlink():
                require(path.resolve(strict=True).is_relative_to(prefix), 'external installed symlink')
                files[name] = {'symlink':os.readlink(path)}
            elif path.is_file():
                files[name] = {'sha256':sha(path), 'size':path.stat().st_size, 'mode':path.stat().st_mode & 0o777}
            else: require(path.is_dir(), 'special installed file')
    require(files, 'empty installed switch')
    return {'files':files, 'sha256':hashlib.sha256(canonical(files)).hexdigest()}


def run_probe(out):
    env = environment(out, os.environ)
    report = {'schema_version':1, 'status':'running', 'started_at':now(), 'stages':[],
        'clean_room_claimed':False, 'release_claimed':False, 'third_party_claimed':False,
        'extra_proof_coverage':False, 'os_sandboxed':False, 'old_switch_binaries_copied':False,
        'host_tools_and_package_metadata_reused':True, 'rust_llbc_and_sail_sources_regenerated':False}
    def save():
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def stage(name, argv, cwd=out, timeout=900):
        row = {'name':name, 'argv':list(map(str,argv)), 'cwd':str(cwd), 'started_at':now()}
        report['stages'].append(row)
        save()
        log = out/(name+'.log')
        print('==> isolated-rocq: '+name, flush=True)
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'isolated Rocq stage failed: '+name)
        finally:
            row.update(finished_at=now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()
    try:
        require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'unsupported host')
        require(sha(LOCK) == LOCK_SHA, 'frozen OPAM metadata changed; review required')
        require(all(PACKAGES.get(k) == v for k,v in spike.PACKAGES.items()), 'spike package pin drift')
        opam = Path(shutil.which('opam') or '').resolve(strict=True)
        require(opam.is_file() and os.access(opam,os.X_OK), 'OPAM bootstrap missing')
        report['opam_bootstrap'] = {'path':str(opam),'sha256':sha(opam)}
        paths = [LOCK, Path(__file__), ROOT/'scripts/rocq_spike.py', ROOT/'scripts/release_evidence.py',
                 ROOT/'scripts/probes/probe_isolated_rust_lean.py', ROOT/'scripts/source_snapshot.py',
                 ROOT/'scripts/probes/probe_release_runtime.py', ROOT/'proof/lean/audit/step-policy.json',
                 ROOT/'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)):sha(p) for p in paths}
        report['existing_spike_inputs_before'] = spike.inputs(ROOT)
        root = out/'opam-root'
        require(not root.exists() and not root.is_symlink(), 'OPAM root must be absent')
        report['opam_root_initially_absent'] = True
        report['opam_root'] = str(root)
        report['switch'] = SWITCH
        # No live package repository is consulted: full export embeds metadata
        # for all 21 packages, including versioned URLs and archive checksums.
        repo = out/'empty-repository'
        repo.mkdir()
        (repo/'repo').write_text('opam-version: "2.0"\n')
        report['repository_descriptor_sha256'] = sha(repo/'repo')
        stage('bootstrap-version',[opam,'--version'],timeout=30)
        stage('init',[opam,'init','--bare','--no-setup','--no-opamrc','--disable-sandboxing',
                      '--yes','locked',str(repo)])
        stage('import-build',[opam,'switch','import','--switch='+SWITCH,'--no-switch','--yes',
              '--jobs=4','--require-checksums','--assume-depexts',LOCK],timeout=3600)
        report['packages'] = check_packages(stage('packages',[opam,'list','--switch='+SWITCH,
                                              '--installed','--short','--columns=name,version']))
        stage('pin-compiler-invariant',[opam,'switch','set-invariant','--switch='+SWITCH,
                                       '--yes','--formula='+COMPILER_FORMULA])
        invariant = stage('compiler-invariant',[opam,'switch','invariant','--switch='+SWITCH])
        exported = stage('export-metadata',[opam,'switch','export','--switch='+SWITCH,'--full','--freeze','-'])
        report['metadata_audit'] = check_export(exported,invariant)
        prefix = root/SWITCH
        opam_exec = [opam,'exec','--switch='+SWITCH,'--set-switch','--']
        report['binaries'] = {}
        for name in ['ocamlc','rocq']:
            path = private_binary(stage(name+'-path',opam_exec+['which',name]),prefix)
            report['binaries'][name] = {'path':str(path),'sha256':sha(path)}
        require(stage('ocaml-version',opam_exec+['ocamlc','-version']) == '5.2.1','OCaml version differs')
        require(stage('rocq-version',opam_exec+['rocq','--version']) ==
                'The Rocq Prover, version 9.1.1\ncompiled with OCaml 5.2.1','Rocq version differs')
        stage('spike',['python3','scripts/rocq_spike.py'],cwd=ROOT,timeout=1800)
        # Revalidation runs under this same OPAMROOT/switch; it never refreshes policy.
        validation = "import json,sys; from pathlib import Path; sys.path.insert(0,'scripts'); import release_evidence as e; print(json.dumps(e.check_rocq(Path(sys.argv[1]))))"
        report['spike_validation'] = json.loads(stage('validate-spike',['python3','-O','-c',validation,
                                               out/'spike/report.json'],cwd=ROOT))
        report['spike_report_sha256'] = sha(out/'spike/report.json')
        report['installed_closure'] = installed_inventory(prefix)
        report['inputs_after'] = {str(p.relative_to(ROOT)):sha(p) for p in paths}
        report['existing_spike_inputs_after'] = spike.inputs(ROOT)
        require(report['inputs_before'] == report['inputs_after'] and
                report['existing_spike_inputs_before'] == report['existing_spike_inputs_after'], 'input drift')
        require(sha(opam) == report['opam_bootstrap']['sha256'] and
                sha(repo/'repo') == report['repository_descriptor_sha256'], 'bootstrap/repository changed')
        report['status'] = 'isolated_rocq_rebuild_and_existing_input_nogo_passed'
        code = 0
    except (Exception,KeyboardInterrupt) as error:
        report.update(status='failed',error=str(error),error_type=type(error).__name__)
        code = 1
    report['finished_at'] = now()
    save()
    print(json.dumps({'status':report['status'],'report':str(out/'report.json')}),flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True,exist_ok=False)
    else:
        parent = ROOT/'artifacts/boundary-check'
        parent.mkdir(parents=True,exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='isolated-rocq-',dir=parent))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
