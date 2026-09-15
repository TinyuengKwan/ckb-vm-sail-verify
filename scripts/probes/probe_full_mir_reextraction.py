#!/usr/bin/env python3
"""Reextract public decoder and iterator using the independently rebuilt std.

Existing approved translators are reused. No input/policy migration, no kernel
or complete clean-room claim. Original LLBC and generated Lean stay untouched.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import check_proof as proof
import ckb_source_baseline as baseline
import decoder_harness as harness
import decoder_input_locations as locations
import decoder_model_identity as identity
import public_decoder_gate as gate
from source_snapshot import require, inventory, independent
from probes import probe_isolated_full_mir as mir
from probes.probe_release_runtime import now

MIR_REPORT = ROOT/'artifacts/boundary-check/isolated-full-mir-r3t1nq8t/report.json'
MIR_SHA = '13d82971a424442ea3fc4fbd4deda0672cb1725c0cda9e32817465830a618516'
CONFIG = ROOT/'proof/lean/decoder/toolchain/full-entry/extraction.json'


def environment(out,rust_home,config):
    env = mir.environment(out,rust_home,os.environ)
    for key in list(env):
        if key.startswith(('CHARON_','AENEAS_','RUST_LOG','GIT_')): env.pop(key)
    env.update(RUSTUP_TOOLCHAIN=config['rust_toolchain'],CARGO_TARGET_DIR=str(out/'cargo-target'),
               GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
    env.update(config['aeneas_env'])
    return env


def candidate_options(archived,fresh,verified_root):
    # Only location metadata is remapped for comparison, after the caller
    # verifies the candidate library bytes. This does NOT mark them approved.
    result = locations._compare_metadata(archived,fresh,verified_root)
    return {**result,'candidate_libraries_approved':False,'llbc_ast_equivalence_claimed':False}


def run_probe(out):
    sys.setrecursionlimit(100000)
    report = {'schema_version':1,'status':'running','started_at':now(),'stages':[],
              'clean_room_claimed':False,'third_party_claimed':False,'release_claimed':False,
              'kernel_executed':False,'full_toolchain_rebuilt':False,'policy_changed':False,
              'new_sysroot_approved':False,'existing_approved_translators_reused':True,
              'old_cargo_cache_or_target_copied':False,'os_sandboxed':False}
    env = None
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def stage(name,argv,cwd=out,timeout=900):
        row = {'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'started_at':now()}
        report['stages'].append(row)
        save()
        print('==> full-mir-reextraction: '+name,flush=True)
        log = out/(name+'.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'],cwd=cwd,env=env,stdout=stream,
                                        stderr=subprocess.STDOUT,timeout=timeout)
            row['exit_code'] = result.returncode
            require(result.returncode == 0,'reextraction stage failed: '+name)
        finally:
            row.update(finished_at=now(),log=log.name,log_sha256=mir.rust.sha(log))
            save()
        return log.read_text().strip()
    try:
        require(mir.rust.sha(MIR_REPORT) == MIR_SHA,'full-MIR build evidence changed')
        built = json.loads(MIR_REPORT.read_text())
        require(built['status'] == 'isolated_full_mir_identity_review_required','unexpected sysroot status')
        sysroot = Path(built['sysroot'])
        require(mir.libraries(sysroot/mir.LIB_SUFFIX) == built['libraries'],'new sysroot library drift')
        require(mir.rust.sha(mir.RUST_REPORT) == mir.RUST_SHA,'private Rust evidence drift')
        rust_install = json.loads(mir.RUST_REPORT.read_text())
        rust_home = Path(built['rustup_home'])
        require(mir.rust.inventory(rust_home) == rust_install['installed_closures']['rustup'],
                'private Rust installation drift')
        for name,digest in built['inputs_before'].items():
            require(mir.rust.sha(ROOT/name) == digest,'sysroot build input drift: '+name)
        require(mir.rust.sha(CONFIG) == 'aaed2661ab316b0cf959034fa8b3e9c836aa88ad52da7746b3b648c707771b1c',
                'extraction config drift')
        config = json.loads(CONFIG.read_text())
        public_policy = json.loads(gate.POLICY.read_text())
        require(gate.sources() == public_policy['sources'],'public source policy drift')
        input_dir = ROOT/public_policy['inputs']
        approved = locations.load(input_dir)
        payload = Path(approved['payload'])
        report['approved_input_package'] = approved
        report['candidate_sysroot'] = str(sysroot)
        report['candidate_libraries'] = built['libraries']
        charon,aeneas = payload/'bin/charon',payload/'bin/aeneas'
        report['reused_translators'] = {}
        for binary,key in [(charon,'charon_binary_sha256'),(charon.with_name('charon-driver'),'charon_driver_sha256'),
                           (aeneas,'aeneas_binary_sha256')]:
            require(mir.rust.sha(binary) == config[key],'translator drift')
            report['reused_translators'][str(binary)] = config[key]
        paths = [Path(__file__),MIR_REPORT,mir.RUST_REPORT,CONFIG,gate.POLICY,proof.POLICY,
                 ROOT/'scripts/decoder_model_identity.py',ROOT/'scripts/decoder_harness.py',
                 ROOT/'scripts/decoder_input_locations.py',ROOT/'scripts/decoder_input_bundle.py',
                 ROOT/'scripts/decoder_public_source.py',ROOT/'scripts/source_snapshot.py',
                 ROOT/'scripts/probes/probe_isolated_full_mir.py',ROOT/'scripts/probes/probe_isolated_rust_lean.py',
                 ROOT/'scripts/probes/probe_release_runtime.py']
        report['inputs_before'] = {str(p.relative_to(ROOT)):mir.rust.sha(p) for p in paths}
        source_before = baseline.check(ROOT)
        report['production_baseline'] = source_before
        env = environment(out,rust_home,config)
        require(not (out/'cargo').exists() and not (out/'cargo-target').exists(),'Cargo outputs must be absent')
        (out/'cargo').mkdir()
        report['cargo_home_initially_empty'] = True
        report['cargo_target_initially_absent'] = True
        head = proof.output(['git','rev-parse','HEAD'])
        checkout = out/'checkout'
        stage('clone-project',['git','clone','--no-hardlinks','--no-checkout',ROOT,checkout])
        stage('checkout-project',['git','checkout','--detach',head],cwd=checkout)
        stage('clone-ckb',['git','clone','--no-hardlinks','--no-checkout',ROOT/'deps/ckb-vm',checkout/'deps/ckb-vm'])
        stage('checkout-ckb',['git','checkout','--detach',source_before['upstream_commit']],cwd=checkout/'deps/ckb-vm')
        for path in [checkout,checkout/'deps/ckb-vm']: independent(path)
        require(baseline.check(checkout,apply=True) == source_before,'cloned CKB baseline drift')
        report['checkout'] = str(checkout)
        report['clone_sources_before'] = {name:inventory(checkout/name) for name in ['.','deps/ckb-vm']}
        outer = out/'outer'
        report['harness_before'] = harness.prepare(outer,checkout)
        rustc = Path(stage('rustc-path',['rustup','which','--toolchain',config['rust_toolchain'],'rustc']))
        require(rustc.resolve().is_relative_to(rust_home/'toolchains') and
                mir.rust.sha(rustc) == built['rustc_sha256'],'Rust compiler escaped private pinned installation')
        require('commit-hash: '+config['rust_commit'] in stage('rust-version',[rustc,'-vV']),'wrong Rust commit')
        report['rustc'] = {'path':str(rustc),'sha256':mir.rust.sha(rustc)}
        # Populate only this empty Cargo cache from the locked manifest;
        # preserve --offline in the actual approved extraction command.
        stage('fetch-locked',['cargo','fetch','--locked','--target',config['target']],cwd=outer)
        generated = out/'generated'
        report['extractions'] = {}
        cases = [('public','OuterClosedDepsV3.llbc'),('iterator','FnPtrFullMir.llbc')]
        iterator_source = checkout/identity.ITERATOR_RELATIVE
        require(mir.rust.sha(iterator_source) == public_policy['sources'][identity.ITERATOR_RELATIVE],
                'iterator source changed')
        for name,filename in cases:
            archive = json.loads((payload/'llbc'/filename).read_bytes())
            llbc = out/filename
            command = [charon,'cargo' if name == 'public' else 'rustc','--preset=aeneas',
                       '--sysroot',sysroot,'--dest-file',llbc]
            if name == 'public':
                for flag,key in [('start-from','outer_start_from'),('include','outer_include'),('opaque','outer_opaque')]:
                    for value in config[key]: command.extend(['--'+flag,value])
                command.extend(['--',*config['outer_cargo_args']])
                cwd = outer
                translate = [aeneas,*config['aeneas_args'],'-dest',generated,llbc]
            else:
                for value in archive['translated']['options']['include']: command.extend(['--include',value])
                command.extend(['--',iterator_source,'--crate-type=lib'])
                cwd = out
                translate = [aeneas,'-backend','lean','-abort-on-error','-no-progress-bar','-checks',
                             '-sequential','-dest',generated,llbc]
            stage('extract-'+name,command,cwd=cwd)
            fresh = json.loads(llbc.read_bytes())
            report['extractions'][name] = {'llbc_sha256':mir.rust.sha(llbc),
                'option_comparison':candidate_options(archive,fresh,sysroot)}
            stage('translate-'+name,translate,cwd=cwd)
            model = generated/(Path(filename).stem+'.lean')
            report['extractions'][name]['generated_model_sha256'] = mir.rust.sha(model)
            save()  # preserve raw generated identity even if the comparison fails
            report['extractions'][name]['model_identity'] = (identity.check(model,checkout) if name == 'public'
                else identity.check_iterator(model,checkout,out))
        report['harness_after'] = harness.verify(outer,checkout)
        require(report['harness_before'] == report['harness_after'],'harness drift')
        report['clone_sources_after'] = {name:inventory(checkout/name) for name in ['.','deps/ckb-vm']}
        require(report['clone_sources_before'] == report['clone_sources_after'],'clone source drift')
        require(baseline.check(ROOT) == source_before,'original CKB baseline drift')
        require(locations.load(input_dir) == approved,'approved input package drift')
        require(mir.libraries(sysroot/mir.LIB_SUFFIX) == built['libraries'],'candidate library drift')
        require(mir.rust.inventory(rust_home) == rust_install['installed_closures']['rustup'],'Rust installation drift')
        report['inputs_after'] = {str(p.relative_to(ROOT)):mir.rust.sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'],'probe/policy drift')
        report['status'] = 'new_sysroot_public_and_iterator_models_match_admission_pending'
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
        out = Path(tempfile.mkdtemp(prefix='full-mir-reextraction-',dir=ROOT/'artifacts/boundary-check'))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
