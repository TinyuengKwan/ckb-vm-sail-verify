#!/usr/bin/env python3
"""Rebuild full-MIR std with independently installed Rust and empty Cargo cache.

Reuses host tools and the prior private Rust installation, not old std build
artifacts. Does not install into rustup or approve changed extraction inputs.
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
sys.path.insert(0,str(ROOT/'scripts'))
from probes import probe_isolated_rust_lean as rust
from probes.probe_sail_model_identity import difference
from probes.probe_release_runtime import now
from source_snapshot import require
from experiments import build_decoder_sysroot as builder

RUST_REPORT = ROOT/'artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/report.json'
RUST_SHA = '80058acabeef59e0eb424aa2028a28a7018e4acad0da8531da83db9b4bc9cbad'
LIB_SUFFIX = Path('lib/rustlib/x86_64-unknown-linux-gnu/lib')
PUBLIC = ROOT/'artifacts/decoder-inputs/public-v1/payload'


def environment(out, rust_home, original):
    env = {k:v for k,v in original.items() if not k.startswith(('CARGO','RUST','OPAM','OCAML'))
           and k not in ['LD_LIBRARY_PATH','MAKEFLAGS']}
    env.update(RUSTUP_HOME=str(rust_home),CARGO_HOME=str(out/'cargo'),PATH='/usr/bin:/bin',
               RUSTUP_NO_UPDATE_CHECK='1',CARGO_TERM_COLOR='never')
    return env


def libraries(directory, resolved_root=None):
    require(directory.is_dir() and not directory.is_symlink(),'missing library directory')
    result = {}
    for path in sorted(directory.iterdir()):
        require(path.suffix in ['.rlib','.rmeta'] and path.is_file(),'unexpected sysroot file')
        if resolved_root:
            require(path.resolve(strict=True).is_relative_to(resolved_root.resolve()),'library escaped new build')
        else:
            require(not path.is_symlink() and path.stat().st_nlink == 1,'library is linked/shared')
        result[path.name] = rust.sha(path)
    require(len(result) == 46 and any(k.startswith('libstd-') and k.endswith('.rlib') for k in result),
            'full-MIR library inventory incomplete')
    return result


def child_report(output):
    paths = re.findall(r'^Report: (.+)$',output,re.M)
    require(len(paths) == 1,'ambiguous sysroot build report')
    path = Path(paths[0]).resolve(strict=True)
    require(path.parent.parent == ROOT/'artifacts/boundary-check' and
            path.parent.name.startswith('decoder-sysroot-build-') and path.name == 'report.json',
            'unexpected child report location')
    return path


def run_probe(out):
    report = {'schema_version':1,'status':'running','started_at':now(),
              'clean_room_claimed':False,'third_party_claimed':False,'release_claimed':False,
              'proof_chain_executed':False,'old_build_or_cargo_cache_copied':False,
              'policy_changed':False,'new_extraction_inputs_approved':False,'os_sandboxed':False}
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        require(rust.sha(RUST_REPORT) == RUST_SHA,'Rust installation evidence changed')
        old = json.loads(RUST_REPORT.read_text())
        rust_home = Path(old['private_homes']['RUSTUP_HOME'])
        require(rust.inventory(rust_home) == old['installed_closures']['rustup'],'private Rust installation drift')
        inputs = [Path(__file__),RUST_REPORT,ROOT/'scripts/experiments/build_decoder_sysroot.py',
                  ROOT/'scripts/probes/probe_isolated_rust_lean.py',ROOT/'scripts/probes/probe_sail_model_identity.py',
                  ROOT/'scripts/probes/probe_release_runtime.py',ROOT/'scripts/source_snapshot.py',
                  ROOT/'proof/lean/audit/step-policy.json',ROOT/'proof/lean/decoder/public-policy.json',
                  PUBLIC/'package.json',*[builder.ASSETS/name for name in ['Cargo.toml','Cargo.lock','lib.rs']]]
        report['inputs_before'] = {str(p.relative_to(ROOT)):rust.sha(p) for p in inputs}
        manifest = json.loads((PUBLIC/'package.json').read_text())
        baseline = libraries(PUBLIC/'sysroot'/LIB_SUFFIX)
        for name,digest in baseline.items():
            require(manifest['files']['sysroot/'+(LIB_SUFFIX/name).as_posix()]['sha256'] == digest,
                    'installed baseline full-MIR library drift')
        report['baseline_libraries'] = baseline
        cargo_home = out/'cargo'
        require(not cargo_home.exists() and not cargo_home.is_symlink(),'Cargo home must be absent')
        cargo_home.mkdir()
        report.update(cargo_home=str(cargo_home),cargo_home_initially_empty=True,rustup_home=str(rust_home))
        env = environment(out,rust_home,os.environ)
        bootstrap = Path(old['bootstrap']['rustup']['path'])
        require(rust.sha(bootstrap) == old['bootstrap']['rustup']['sha256'],'rustup bootstrap drift')
        report['bootstrap'] = old['bootstrap']['rustup']
        rustc = Path(subprocess.check_output([bootstrap,'which','--toolchain',builder.NIGHTLY,'rustc'],env=env,text=True).strip())
        require(rustc.resolve().is_relative_to(rust_home/'toolchains'),'compiler escaped private installation')
        report['rustc_path'] = str(rustc)
        report['rustc_sha256'] = rust.sha(rustc)
        command = ['python3',str(ROOT/'scripts/experiments/build_decoder_sysroot.py')]
        report['build_stage'] = {'argv':command,'cwd':str(ROOT),'started_at':now()}
        save()
        print('==> isolated-full-mir: build from empty Cargo cache',flush=True)
        log = out/'builder.log'
        with log.open('xb') as stream:
            result = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
        report['build_stage'].update(exit_code=result.returncode,finished_at=now(),log=log.name,log_sha256=rust.sha(log))
        require(result.returncode == 0,'full-MIR build failed')
        child = child_report(log.read_text())
        generated = json.loads(child.read_text())
        require(generated['status'] == 'PASS' and generated['exit_code'] == 0 and
                generated['rustc_sha256'] == report['rustc_sha256'] and generated['rustflags'] == builder.FLAGS,
                'child build identity/status differs')
        rebuilt = libraries(Path(generated['sysroot'])/LIB_SUFFIX,child.parent)
        require(rebuilt == generated['libraries'],'rebuilt library digest drift')
        destination = out/'sysroot'/LIB_SUFFIX
        destination.mkdir(parents=True)
        for name in rebuilt:
            shutil.copyfile(Path(generated['sysroot'])/LIB_SUFFIX/name,destination/name)
        require(libraries(destination) == rebuilt,'materialized sysroot differs')
        report.update(child_report=str(child),child_report_sha256=rust.sha(child),
                      child_build_log_sha256=rust.sha(child.parent/'build.log'),libraries=rebuilt,
                      sysroot=str(out/'sysroot'),library_comparison=difference(baseline,rebuilt))
        require(rust.inventory(rust_home) == old['installed_closures']['rustup'],'installed Rust changed during build')
        require(libraries(PUBLIC/'sysroot'/LIB_SUFFIX) == baseline,'baseline sysroot changed')
        report['rustup_installation_unchanged'] = True
        report['inputs_after'] = {str(p.relative_to(ROOT)):rust.sha(p) for p in inputs}
        require(report['inputs_before'] == report['inputs_after'],'input/policy drift')
        matches = report['library_comparison']['identical']
        report['status'] = 'isolated_full_mir_bytes_match' if matches else 'isolated_full_mir_identity_review_required'
        code = 0 if matches else 2
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
        out = Path(tempfile.mkdtemp(prefix='isolated-full-mir-',dir=ROOT/'artifacts/boundary-check'))
    print(out,flush=True)
    return run_probe(out)


if __name__ == '__main__':
    sys.exit(main())
