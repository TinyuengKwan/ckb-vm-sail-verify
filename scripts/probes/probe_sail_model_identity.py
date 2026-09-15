#!/usr/bin/env python3
"""Compare fresh full-model generation by old/new Sail, without policy mutation.

Uses pinned upstream CMake generation targets, a fresh shared source clone and
separate empty build directories. Reuses the policy-bound materialized config
and host tools. No C++/Lean/Rocq compilation, proof-chain or clean-room claim.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import check_proof as proof
from source_snapshot import require, inventory, independent, canonical
from probes import probe_isolated_sail as install
from probes.probe_isolated_rust_lean import sha
from probes.probe_release_runtime import now

INSTALL_REPORT = ROOT/'artifacts/boundary-check/isolated-sail-nrdi23ds/report.json'
INSTALL_SHA = 'a765bc5f4cbaa9af62909ea9cd1e1d2af50a5b9f8437aaf80a7be0cf91b88739'
CONFIG = ROOT/'sail-model/build/ckb_vm_config.json'
ADAPTER = ROOT/'proof/lean/compat/sail-defs-computable.patch'
TOOLCHAIN = ROOT/'proof/lean/theorems/lean-toolchain'
TARGETS = {'cpp':'generated_sail_riscv_model', 'lean':'generated_lean_rv64d', 'rocq':'generated_rocq_rv64d'}


def files(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(),'missing or linked generation directory')
    result = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(),'symlink in generated output')
        if path.is_file(): result[path.relative_to(directory).as_posix()] = sha(path)
        else: require(path.is_dir(),'special generated output')
    require(result,'empty generated output')
    return result


def difference(left, right):
    require(left and right,'empty comparison inventory')
    return {'identical':left == right, 'left_count':len(left), 'right_count':len(right),
            'only_left':sorted(left.keys()-right.keys()), 'only_right':sorted(right.keys()-left.keys()),
            'changed':{key:{'left':left[key],'right':right[key]} for key in sorted(left.keys() & right.keys())
                       if left[key] != right[key]}}


def raw_outputs(build):
    cpp = {name:sha(build/name) for name in
           ['sail_riscv_model.cpp','sail_riscv_model.h','sail_riscv_config_schema.json']}
    lean = files(build/'model/Lean_RV64D')
    rocq = files(build/'rocq')
    require('LeanRV64D.lean' in lean and 'LeanRV64D/Defs.lean' in lean,'Lean model outputs missing')
    require({'rv64d.v','rv64d_types.v'} <= rocq.keys(),'Rocq model outputs missing')
    return {'cpp':cpp,'lean':lean,'rocq':rocq}


def compiler_environment(out, prefix):
    env = install.environment(out, os.environ)
    env.update(SAIL_DIR=str(prefix/'share/sail'),SAIL_PLUGIN_DIR=str(prefix/'share/libsail/plugins'))
    for key in list(env):
        if key.startswith(('CMAKE_', 'LEAN_', 'ELAN_')): env.pop(key)
    return env


def accepted_lean(directory, policy):
    result = proof.tree_files(directory,proof.lean_sources)
    require(proof.digest(canonical(result)) == policy['generated_sha256']['sail'],
            'adapted full Sail Lean model differs from existing policy')
    return result


def run_probe(out):
    report = {'schema_version':1,'status':'running','started_at':now(),'stages':[],
              'clean_room_claimed':False,'third_party_claimed':False,'release_claimed':False,
              'kernel_or_cpp_compilation_performed':False,'proof_chain_executed':False,
              'policy_changed':False,'new_tool_approved':False,'config_rematerialized':False,
              'old_generated_outputs_used_for_rebuild':False,'os_sandboxed':False}
    env = install.environment(out,os.environ)
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def stage(name,argv,cwd=out,timeout=1800,run_env=None):
        row = {'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'started_at':now()}
        report['stages'].append(row)
        save()
        print('==> sail-model-identity: '+name,flush=True)
        log = out/(name+'.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'],cwd=cwd,env=run_env or env,stdout=stream,
                                        stderr=subprocess.STDOUT,timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0,'generation stage failed: '+name)
        finally:
            row.update(finished_at=now(),log=log.name,log_sha256=sha(log))
            save()
        return log.read_text().strip()
    try:
        require(sha(INSTALL_REPORT) == INSTALL_SHA,'Sail install evidence changed')
        previous = json.loads(INSTALL_REPORT.read_text())
        require(previous['status'] == 'isolated_sail_rebuild_identity_review_required','unexpected install status')
        policy = json.loads(install.POLICY.read_text())
        require(proof.local_sources() == policy['local_sources'],'frozen proof source drift')
        require(sha(CONFIG) == policy['sail_config_sha256'],'materialized config drift')
        inputs = [Path(__file__),INSTALL_REPORT,install.POLICY,CONFIG,ADAPTER,TOOLCHAIN,
                  ROOT/'scripts/probes/probe_isolated_sail.py',ROOT/'scripts/probes/probe_isolated_rocq.py',
                  ROOT/'scripts/probes/probe_isolated_rust_lean.py',ROOT/'scripts/probes/probe_release_runtime.py',
                  ROOT/'scripts/source_snapshot.py',ROOT/'scripts/check_proof.py',
                  ROOT/'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
        for name,digest in previous['inputs_before'].items():
            require(sha(ROOT/name) == digest,'install input drift: '+name)
        require(install.rocq.installed_inventory(Path(previous['opam_root'])/install.SWITCH) ==
                previous['opam_installed_closure'],'new OPAM installed closure drift')
        require(install.check_source(Path(previous['source'])) == previous['source_after'],
                'Sail compiler source drift')
        prefixes = {'baseline':Path(previous['baseline_prefix']),'candidate':Path(previous['prefix'])}
        closure_keys = {'baseline':'baseline_closure_before','candidate':'installed_closure'}
        closures = {}
        report['compilers'] = {}
        for side,prefix in prefixes.items():
            closures[side] = install.rocq.installed_inventory(prefix)
            require(closures[side] == previous[closure_keys[side]],'Sail installation drift: '+side)
            report['compilers'][side] = {'prefix':str(prefix),'binary_sha256':sha(prefix/'bin/sail'),
                                        'closure_sha256':closures[side]['sha256']}
        report['tool_closure_difference'] = difference(closures['baseline']['files'],closures['candidate']['files'])
        source = ROOT/'deps/sail-riscv'
        before = inventory(source)
        require(before['head'] == policy['repositories']['deps/sail-riscv'] and
                not before['gitlinks'] and not before['changes_from_head'],'RISC-V source drift')
        report['model_source_before'] = before
        checkout = out/'sail-riscv'
        stage('clone',['git','clone','--no-hardlinks','--no-checkout',source,checkout])
        stage('checkout',['git','checkout','--detach',before['head']],cwd=checkout)
        independent(checkout)
        require(inventory(checkout) == before,'model clone differs')
        report['checkout'] = str(checkout)
        report['original_lean_before'] = accepted_lean(ROOT/'proof/lean/generated/sail',policy)
        report['outputs'] = {}
        report['adapted_lean'] = {}
        for side,prefix in prefixes.items():
            build = out/(side+'-build')
            require(not build.exists(),'build directory must be absent')
            run_env = compiler_environment(out,prefix)
            version = stage(side+'-version',[prefix/'bin/sail','--version'],run_env=run_env)
            require(version == install.VERSION,'incorrect Sail source version')
            stage(side+'-configure',['cmake','-S',checkout,'-B',build,'-DCMAKE_BUILD_TYPE=RelWithDebInfo',
                  '-DDOWNLOAD_GMP=TRUE','-DSAIL_BIN:FILEPATH='+str(prefix/'bin/sail')],run_env=run_env)
            # Replace only this fresh build's generated configuration. This is
            # the same materialized-config copy as generate_proof_model.sh.
            config = build/'config/rv64d_v256_e64.json'
            require(config.is_file() and not config.is_symlink(),'missing new CMake config')
            shutil.copyfile(CONFIG,config)
            for backend,target in TARGETS.items():
                stage(side+'-'+backend,['cmake','--build',build,'--parallel','1','--target',target],run_env=run_env)
                require(sha(config) == policy['sail_config_sha256'],'CMake config changed during generation')
            report['outputs'][side] = raw_outputs(build)
            adapted = out/(side+'-adapted-lean')
            shutil.copytree(build/'model/Lean_RV64D',adapted)
            stage(side+'-adapter',['patch','--batch','--forward','--fuzz=0','-p0',
                                  '--directory='+str(adapted),'--input='+str(ADAPTER)])
            shutil.copyfile(TOOLCHAIN,adapted/'lean-toolchain')
            report['adapted_lean'][side] = accepted_lean(adapted,policy)
            save()
        report['model_comparisons'] = {backend:difference(report['outputs']['baseline'][backend],
                    report['outputs']['candidate'][backend]) for backend in TARGETS}
        require(all(row['identical'] for row in report['model_comparisons'].values()),
                'raw full-model generation differs; inspect original outputs')
        require(report['adapted_lean']['baseline'] == report['adapted_lean']['candidate'] ==
                report['original_lean_before'],'adapted Lean source identity drift')
        for side,prefix in prefixes.items():
            require(install.rocq.installed_inventory(prefix) == closures[side],'tool changed during generation')
            require(raw_outputs(out/(side+'-build')) == report['outputs'][side],'generated output drift')
        report['model_source_after'] = inventory(checkout)
        require(inventory(source) == before == report['model_source_after'],'model source changed')
        require(accepted_lean(ROOT/'proof/lean/generated/sail',policy) == report['original_lean_before'],
                'original generated Lean changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'],'input drift')
        report['status'] = 'full_model_generation_identical_tool_admission_pending'
        code = 2  # review evidence, never automatic proof-policy acceptance
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
        out = Path(tempfile.mkdtemp(prefix='sail-model-identity-',dir=parent))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
