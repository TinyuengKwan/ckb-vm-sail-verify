#!/usr/bin/env python3
"""Fresh candidate generation against retained fresh baseline generation.

The baseline probe stopped on a stale extra policy-inventoried Lean file.
This follow-up records that exact mismatch; it never fills in the stale file
or declares the existing policy matched. No kernel/policy migration performed.
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
from probes import probe_sail_model_identity as model
from source_snapshot import require, inventory, independent
from probes.probe_release_runtime import now

BASE_REPORT = ROOT/'artifacts/boundary-check/sail-model-identity-v1weq3h5/report.json'
BASE_SHA = 'd1e781d3fd31700364597a295566cdf64842af49e8c7207d83abaa5efa4a5dde'
STALE = 'LeanRV64D/Specialization.lean'
STALE_SHA = '4ff811a4e3c8f24ae26b03b34afcfcae9020e32caf0b99701c908c4d3478b72e'


def policy_difference(original,fresh):
    result = model.difference(original,fresh)
    require(result['only_left'] == [STALE] and not result['only_right'] and not result['changed']
            and original[STALE] == STALE_SHA,'unexpected model difference beyond recorded stale file')
    return {**result,'existing_policy_matched':False,'stale_file_reintroduced':False,
            'stale_file_absence_authorized_by_policy':False}


def run_probe(out):
    report = {'schema_version':1,'status':'running','started_at':now(),'stages':[],
              'clean_room_claimed':False,'third_party_claimed':False,'release_claimed':False,
              'kernel_executed':False,'policy_changed':False,'new_tool_approved':False,
              'baseline_generation_reused':True,'candidate_generated_outputs_reused':False,
              'existing_policy_matched':False,'os_sandboxed':False}
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    env = None
    def stage(name,argv,cwd=out,timeout=1800):
        row = {'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'started_at':now()}
        report['stages'].append(row)
        save()
        print('==> sail-candidate-model: '+name,flush=True)
        log = out/(name+'.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0,'candidate generation failed: '+name)
        finally:
            row.update(finished_at=now(),log=log.name,log_sha256=model.sha(log))
            save()
        return log.read_text().strip()
    try:
        require(model.sha(BASE_REPORT) == BASE_SHA,'baseline report drift')
        old = json.loads(BASE_REPORT.read_text())
        require(old['status'] == 'failed' and old['error'] ==
                'adapted full Sail Lean model differs from existing policy','unexpected baseline failure')
        for row in old['stages']:
            require(row['exit_code'] == 0 and model.sha(BASE_REPORT.parent/row['log']) == row['log_sha256'],
                    'baseline generation was not successful or log drifted')
        for name,digest in old['inputs_before'].items():
            require(model.sha(ROOT/name) == digest,'baseline input drift: '+name)
        baseline_outputs = model.raw_outputs(BASE_REPORT.parent/'baseline-build')
        require(baseline_outputs == old['outputs']['baseline'],'baseline output drift')
        policy = json.loads(model.install.POLICY.read_text())
        original = model.accepted_lean(ROOT/'proof/lean/generated/sail',policy)
        fresh_baseline = model.proof.tree_files(BASE_REPORT.parent/'baseline-adapted-lean',model.proof.lean_sources)
        report['baseline_policy_difference'] = policy_difference(original,fresh_baseline)
        require(original == old['original_lean_before'],'original generated Lean drift')
        source = Path(old['checkout'])
        require(inventory(source) == old['model_source_before'] == inventory(ROOT/'deps/sail-riscv'),
                'model source drift')
        independent(source)
        install = json.loads(model.INSTALL_REPORT.read_text())
        prefix = Path(install['prefix'])
        require(model.sha(model.INSTALL_REPORT) == model.INSTALL_SHA,'installation report drift')
        require(model.install.rocq.installed_inventory(prefix) == install['installed_closure'],
                'candidate Sail installation drift')
        require(model.install.rocq.installed_inventory(Path(install['baseline_prefix'])) ==
                install['baseline_closure_before'],'baseline Sail installation drift')
        inputs = [Path(__file__),BASE_REPORT,model.INSTALL_REPORT,model.install.POLICY,model.CONFIG,
                  model.ADAPTER,model.TOOLCHAIN,ROOT/'scripts/probes/probe_sail_model_identity.py',
                  ROOT/'scripts/probes/probe_isolated_sail.py',ROOT/'scripts/probes/probe_isolated_rocq.py',
                  ROOT/'scripts/probes/probe_isolated_rust_lean.py',ROOT/'scripts/probes/probe_release_runtime.py',
                  ROOT/'scripts/source_snapshot.py',ROOT/'scripts/check_proof.py',
                  ROOT/'proof/lean/decoder/public-policy.json']
        report['inputs_before'] = {str(p.relative_to(ROOT)):model.sha(p) for p in inputs}
        report['baseline_outputs'] = baseline_outputs
        report['model_source'] = str(source)
        report['model_source_before'] = old['model_source_before']
        report['candidate_prefix'] = str(prefix)
        report['candidate_binary_sha256'] = model.sha(prefix/'bin/sail')
        env = model.compiler_environment(out,prefix)
        require(stage('version',[prefix/'bin/sail','--version']) == model.install.VERSION,'Sail version drift')
        build = out/'candidate-build'
        require(not build.exists(),'candidate build directory must be absent')
        report['candidate_build_initially_absent'] = True
        stage('configure',['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=RelWithDebInfo',
                           '-DDOWNLOAD_GMP=TRUE','-DSAIL_BIN:FILEPATH='+str(prefix/'bin/sail')])
        config = build/'config/rv64d_v256_e64.json'
        require(config.is_file() and not config.is_symlink(),'missing new CMake config')
        shutil.copyfile(model.CONFIG,config)
        for backend,target in model.TARGETS.items():
            stage(backend,['cmake','--build',build,'--parallel','1','--target',target])
            require(model.sha(config) == policy['sail_config_sha256'],'materialized config changed')
        report['candidate_outputs'] = model.raw_outputs(build)
        report['model_comparisons'] = {name:model.difference(baseline_outputs[name],report['candidate_outputs'][name])
                                        for name in model.TARGETS}
        save()
        require(all(v['identical'] for v in report['model_comparisons'].values()),'raw candidate model differs')
        adapted = out/'candidate-adapted-lean'
        shutil.copytree(build/'model/Lean_RV64D',adapted)
        stage('adapter',['patch','--batch','--forward','--fuzz=0','-p0',
                         '--directory='+str(adapted),'--input='+str(model.ADAPTER)])
        shutil.copyfile(model.TOOLCHAIN,adapted/'lean-toolchain')
        report['candidate_adapted_lean'] = model.proof.tree_files(adapted,model.proof.lean_sources)
        require(report['candidate_adapted_lean'] == fresh_baseline,'candidate adapted model differs from fresh baseline')
        report['candidate_policy_difference'] = policy_difference(original,report['candidate_adapted_lean'])
        require(model.install.rocq.installed_inventory(prefix) == install['installed_closure'],'candidate installation changed')
        require(inventory(source) == old['model_source_before'] == inventory(ROOT/'deps/sail-riscv'),'model source changed')
        require(model.accepted_lean(ROOT/'proof/lean/generated/sail',policy) == original,'original generated Lean changed')
        require(model.raw_outputs(BASE_REPORT.parent/'baseline-build') == baseline_outputs,'baseline outputs changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)):model.sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'],'input/policy drift')
        report['status'] = 'raw_models_identical_stale_file_and_tool_admission_pending'
        code = 2
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
        out = Path(tempfile.mkdtemp(prefix='sail-candidate-model-',dir=ROOT/'artifacts/boundary-check'))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
