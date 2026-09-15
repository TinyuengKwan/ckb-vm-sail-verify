#!/usr/bin/env python3
"""Isolated single-stale-file removal and fresh main ADD kernel audit.

No production source, policy or original generated file is changed. Uses
source-only project/support copies and the independently installed Lean.
Does not rerun public-decoder theorems or claim full Week6 clean-room.
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
import check_proof as gate
import check_lean_clean as clean
from probes import probe_sail_candidate_model as candidate
from probes import probe_isolated_rust_lean as rust
from probes import probe_isolated_full_mir as mir
from probes.probe_release_runtime import now
from source_snapshot import require

FIXTURE = ROOT/'scripts/fixtures/SailModuleAudit.lean'
TARGETS = ['LeanRV64D','CkbVmProduction','SmokeImports','AddRegisterAxioms','RegisterRegression',
           'AddStepAxioms','StepRegression','ProductionAdd','ProductionAddWitness']


def quarantine_stale(model,quarantine):
    path = model/candidate.STALE
    require(path.is_file() and not path.is_symlink() and rust.sha(path) == candidate.STALE_SHA,
            'unexpected stale source file')
    require(not quarantine.exists() and not quarantine.is_symlink(),'quarantine must be new')
    quarantine.mkdir(parents=True)
    target = quarantine/path.name
    path.rename(target)
    return {'original_relative_path':candidate.STALE,'quarantined_copy':str(target),
            'sha256':rust.sha(target),'recoverable':True,'original_workspace_file_changed':False}


def run_probe(out):
    report = {'schema_version':1,'status':'running','started_at':now(),'stages':[],
              'clean_room_claimed':False,'third_party_claimed':False,'release_claimed':False,
              'public_decoder_kernel_executed':False,'policy_changed':False,
              'original_generated_file_removed':False,'production_generator_fixed':False,
              'source_only_support_copied':True,'support_git_history_shared':True}
    env = None
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def stage(name,argv,cwd,timeout=3600):
        row = {'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'started_at':now()}
        report['stages'].append(row)
        save()
        print('==> sail-stale-cleanup: '+name,flush=True)
        log = out/(name+'.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'],cwd=cwd,env=env,stdout=stream,
                                        stderr=subprocess.STDOUT,timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0 and not gate.INTERNAL_FAILURE.search(log.read_text()),
                    'cleanup kernel stage failed: '+name)
        finally:
            row.update(finished_at=now(),log=log.name,log_sha256=rust.sha(log))
            save()
        return log.read_text().strip()
    try:
        require(rust.sha(candidate.BASE_REPORT) == candidate.BASE_SHA,'baseline generation report drift')
        require(rust.sha(mir.RUST_REPORT) == mir.RUST_SHA,'Lean installation evidence drift')
        installed = json.loads(mir.RUST_REPORT.read_text())
        elan_home = Path(installed['private_homes']['ELAN_HOME'])
        require(rust.inventory(elan_home) == installed['installed_closures']['elan'],'private Lean installation drift')
        toolchain = elan_home/'toolchains/leanprover--lean4---v4.31.0'
        lake = toolchain/'bin/lake'
        report['lean_compiler'] = {'prefix':str(toolchain),'lake_sha256':rust.sha(lake),
                                   'lean_sha256':rust.sha(toolchain/'bin/lean')}
        policy = json.loads(gate.POLICY.read_text())
        env,binaries,aeneas,_ = gate.tools_and_environment(policy)
        env = dict(env,LEAN_NUM_THREADS='8',LEAN_ABORT_ON_PANIC='1')
        env.pop('LEAN_PATH',None)
        env.pop('LEAN_SYSROOT',None)
        report['source_before'] = gate.source_evidence(policy,binaries,aeneas)
        report['generated_before'] = gate.generated_evidence(policy)
        inputs = [Path(__file__),FIXTURE,candidate.BASE_REPORT,mir.RUST_REPORT,gate.POLICY,
                  ROOT/'proof/lean/decoder/public-policy.json',ROOT/'scripts/check_lean_clean.py',
                  ROOT/'scripts/check_proof.py',ROOT/'scripts/probes/probe_sail_candidate_model.py',
                  ROOT/'scripts/probes/probe_isolated_rust_lean.py',ROOT/'scripts/source_snapshot.py',
                  ROOT/'scripts/probes/probe_release_runtime.py']
        report['inputs_before'] = {str(p.relative_to(ROOT)):rust.sha(p) for p in inputs}
        work = out/'clean'
        project,dependencies = clean.prepare(work,aeneas)
        report['dependency_revisions'] = dependencies
        model = work/'proof/lean/generated/sail'
        report['quarantine'] = quarantine_stale(model,out/'quarantine')
        fresh = gate.tree_files(model,gate.lean_sources)
        expected = gate.tree_files(candidate.BASE_REPORT.parent/'baseline-adapted-lean',gate.lean_sources)
        require(fresh == expected,'isolated model differs from actual clean generation')
        report['model_policy_difference'] = candidate.policy_difference(report['generated_before']['models']['sail'],fresh)
        report['clean_sail_sources'] = fresh
        report['initial_compiled_modules'] = len(list(work.rglob('*.olean')))+len(list(work.rglob('*.ilean')))
        require(report['initial_compiled_modules'] == 0,'old compiled modules copied')
        modules = project/'SailModuleAudit.lean'
        shutil.copyfile(FIXTURE,modules)
        report['clean_directory'] = str(work)
        compiler = Path(stage('compiler-prefix',[lake,'env','lean','--print-prefix'],project,120)).resolve()
        require(compiler == toolchain.resolve(),'Lean compiler escaped private installation')
        report['lean_path'] = clean.check_paths(stage('lean-path',[lake,'env','printenv','LEAN_PATH'],project,120),work,compiler)
        stage('kernel',[lake,'--no-cache','build',*TARGETS],project)
        audit = gate.parse_audit(stage('theorem-audit',[lake,'env','lean','../audit/ExportStepAudit.lean'],project,300))
        gate.check_audit(audit,policy)
        report['theorem_audit'] = audit
        output = stage('module-audit',[lake,'env','lean','SailModuleAudit.lean'],project,300)
        marker = 'SAIL_MODULE_AUDIT='
        rows = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
        require(len(rows) == 1,'missing or duplicate module audit')
        report['imported_modules'] = json.loads(rows[0])
        require('LeanRV64D.Specialization' not in report['imported_modules'] and
                'LeanRV64D.SpecializationV1' in report['imported_modules'],'unexpected imported specialization')
        require(gate.tree_files(model,gate.lean_sources) == fresh,'clean model changed during kernel check')
        require(rust.sha(modules) == rust.sha(FIXTURE),'module audit source drift')
        require(rust.sha(out/'quarantine/Specialization.lean') == candidate.STALE_SHA,'quarantine changed')
        require(gate.source_evidence(policy,binaries,aeneas) == report['source_before'],'original source drift')
        require(gate.generated_evidence(policy) == report['generated_before'],'original generated model drift')
        require(rust.inventory(elan_home) == installed['installed_closures']['elan'],'private Lean changed')
        report['inputs_after'] = {str(p.relative_to(ROOT)):rust.sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'],'probe/policy drift')
        report['built_olean_count'] = len(list(work.rglob('*.olean')))
        report['status'] = 'isolated_stale_file_removal_main_kernel_and_boundary_match'
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
        out = Path(tempfile.mkdtemp(prefix='sail-stale-cleanup-',dir=ROOT/'artifacts/boundary-check'))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
