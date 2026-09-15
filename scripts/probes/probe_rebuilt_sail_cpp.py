#!/usr/bin/env python3
"""Cold-build the complete simulator with the rebuilt Sail, without admission.

Fresh model clone, CMake build and generation; compare the generated C++ with
the retained candidate before compiling it. Host build tools are reused and
identified, not source-rebuilt. Configuration smoke is not runtime differential.
"""
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
import sail_cpp_correspondence as correspondence
from probes import probe_sail_model_identity as model
from source_snapshot import inventory, independent

require, sha = model.require, model.sha
CANDIDATE = correspondence.evidence.SAIL
CANDIDATE_SHA = correspondence.evidence.SAIL_SHA
CORRESPONDENCE = ROOT / 'artifacts/boundary-check/sail-cpp-correspondence-12524i33/report.json'
CORRESPONDENCE_SHA = 'f84f9104f8823640b7149ce8cb1083a66adcb201993213cccb6ffda48bbb341b'
MODEL_COMMIT = '8f91355eee63a85738723603e23d32eecdd763dc'
OVERRIDE = ROOT / 'sail-model/ckb_vm_config.json'
MERGE = ('.[0] as $default | .[1] as $override | '
         '($default | .extensions |= walk(if type == "object" and has("supported") '
         'then .supported = false else . end)) * $override')
GENERATED = ('sail_riscv_model.cpp', 'sail_riscv_model.h', 'sail_riscv_config_schema.json')


def environment(out, prefix):
    env = model.compiler_environment(out, prefix)
    # The base helper reads os.environ. Strip compiler/linker/cache overrides
    # that are outside its generation-only scope too.
    for key in list(env):
        if key.startswith(('CMAKE_', 'CCACHE', 'SCCACHE', 'GIT_', 'SAIL_', 'DUNE_', 'OCAML')) or key in (
                'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'AR', 'RANLIB',
                'LD', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH',
                'CPLUS_INCLUDE_PATH', 'COMPILER_PATH', 'GCC_EXEC_PREFIX', 'MAKEFLAGS', 'MFLAGS',
                'BASH_ENV', 'ENV', 'CONFIG_SITE'):
            env.pop(key)
    env.update(PATH='/usr/bin:/bin', SAIL_DIR=str(prefix / 'share/sail'),
               SAIL_PLUGIN_DIR=str(prefix / 'share/libsail/plugins'),
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', DUNE_CACHE='disabled')
    return env


def generated(build):
    result = {}
    for name in GENERATED:
        path = build / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1,
                'missing or linked generated file: ' + name)
        result[name] = sha(path)
    return result


def check_install(report):
    prefix = Path(report['prefix'])
    require(model.install.rocq.installed_inventory(prefix) == report['installed_closure'], 'Sail install drift')
    require(model.install.rocq.installed_inventory(Path(report['opam_root']) / report['switch']) ==
            report['opam_installed_closure'], 'Sail OPAM closure drift')
    require(model.install.check_source(Path(report['source'])) == report['source_after'], 'Sail compiler source drift')
    independent(Path(report['source']))
    return prefix


def run(out):
    report = {'schema_version': 1, 'status': 'running', 'started_at': model.now(), 'stages': [],
              'cpp_compiled': False, 'emulator_config_executed': False,
              'runtime_differential_executed': False, 'kernel_executed': False,
              'tool_adopted': False, 'policy_changed': False, 'generated_sources_edited': False,
              'old_generated_or_build_cache_copied': False, 'host_build_tools_reused': True,
              'host_tool_closure_rebuilt': False, 'cpp_semantic_equivalence_proved': False,
              'clean_room_claimed': False, 'third_party_claimed': False, 'release_claimed': False,
              'os_sandboxed': False}
    env = None

    def save():
        model.proof.write_json(out / 'report.json', report)

    def stage(name, argv, cwd=out, timeout=900):
        row = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd), 'started_at': model.now()}
        report['stages'].append(row); save()
        print('==> rebuilt-sail-cpp: ' + name, flush=True)
        stdout, stderr = out / (name + '.stdout'), out / (name + '.stderr')
        try:
            with stdout.open('xb') as output, stderr.open('xb') as errors:
                result = subprocess.run(row['argv'], cwd=cwd, env=env, stdout=output, stderr=errors, timeout=timeout)
            row['exit_code'] = result.returncode
            require(type(result.returncode) is int and result.returncode == 0, 'stage failed: ' + name)
        finally:
            row.update(finished_at=model.now(), logs={p.name: sha(p) for p in (stdout, stderr) if p.exists()})
            save()
        return stdout

    try:
        require(sha(CORRESPONDENCE) == CORRESPONDENCE_SHA, 'correspondence report drift')
        checked = json.loads(CORRESPONDENCE.read_text())
        require(checked['status'] == 'scoped_token_correspondence_checked_semantics_pending' and
                checked['inputs_before'] == checked['inputs_after'], 'incomplete correspondence')
        for name, digest in checked['inputs_after'].items():
            require(sha(ROOT / name) == digest, 'correspondence input drift: ' + name)
        require(sha(CORRESPONDENCE.parent / 'correspondence.json') == checked['correspondence_sha256'],
                'recorded correspondence map drift')
        require(sha(CANDIDATE / 'report.json') == CANDIDATE_SHA, 'candidate report drift')
        old = json.loads((CANDIDATE / 'report.json').read_text())
        require(old['status'] == 'failed' and old['error'] == 'raw candidate model differs', 'original disposition changed')
        for row in old['stages']:
            require(type(row['exit_code']) is int and row['exit_code'] == 0 and
                    sha(CANDIDATE / row['log']) == row['log_sha256'], 'original generation evidence drift')
        require(generated(CANDIDATE / 'candidate-build') == old['candidate_outputs']['cpp'], 'retained model drift')
        require(sha(model.INSTALL_REPORT) == model.INSTALL_SHA, 'Sail installation report drift')
        install = json.loads(model.INSTALL_REPORT.read_text())
        prefix = check_install(install)
        env = environment(out, prefix)
        report['environment'] = {k: env[k] for k in ('PATH', 'SAIL_DIR', 'SAIL_PLUGIN_DIR',
                                                    'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL')}
        source_before = inventory(ROOT / 'deps/sail-riscv')
        require(source_before == old['model_source_before'] and source_before['head'] == MODEL_COMMIT and
                not source_before['changes_from_head'] and not source_before['gitlinks'], 'model source drift')
        report['model_source_before'] = source_before
        # Bind all actually imported project helpers, not merely the producer.
        require(sha(model.CONFIG) == old['inputs_before']['sail-model/build/ckb_vm_config.json'], 'reference config drift')
        paths = {Path(__file__), model.INSTALL_REPORT, CANDIDATE / 'report.json', CORRESPONDENCE, model.CONFIG, OVERRIDE,
                 *[ROOT / 'proof/lean' / name for name in ('audit/step-policy.json', 'decoder/public-policy.json',
                                                           'decoder/raw-policy.json', 'decoder/field-policy.json')]}
        paths.update(Path(m.__file__).resolve() for m in list(sys.modules.values())
                     if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
        report['inputs_before'] = {str(p): sha(p) for p in sorted(paths)}
        host = {name: Path(shutil.which(name, path=env['PATH']) or '').resolve(strict=True)
                for name in ('cmake', 'make', 'cc', 'c++', 'ld', 'ar', 'ranlib', 'as', 'z3', 'jq', 'git')}
        require(all(p.is_file() and os.access(p, os.X_OK) for p in host.values()), 'missing host build tool')
        report['host_tools'] = {n: {'path': str(p), 'sha256': sha(p)} for n, p in host.items()}
        source, build = out / 'sail-riscv', out / 'build'
        require(all(not p.exists() and not p.is_symlink() for p in (source, build)), 'nonempty build destinations')
        report.update(source=str(source), build=str(build), build_destinations_initially_absent=True,
                      sail_install_report_sha256=model.INSTALL_SHA, retained_candidate_sha256=CANDIDATE_SHA)
        stage('clone', [host['git'], 'clone', '--no-hardlinks', '--no-checkout', ROOT / 'deps/sail-riscv', source])
        stage('checkout', [host['git'], 'checkout', '--detach', MODEL_COMMIT], source)
        independent(source)
        require(inventory(source) == source_before, 'cloned model source differs')
        require(not list(source.rglob('z3_problems')), 'old SMT cache copied')
        require(stage('sail-version', [prefix / 'bin/sail', '--version']).read_text().strip() ==
                model.install.VERSION, 'Sail version drift')
        stage('configure', [host['cmake'], '-S', source, '-B', build, '-DCMAKE_BUILD_TYPE=RelWithDebInfo',
                           '-DDOWNLOAD_GMP=TRUE', '-DCMAKE_C_COMPILER=' + str(host['cc']),
                           '-DCMAKE_CXX_COMPILER=' + str(host['c++']), '-DSAIL_BIN:FILEPATH=' + str(prefix / 'bin/sail')])
        stage('generate', [host['cmake'], '--build', build, '--parallel', '1', '--target', 'generated_sail_riscv_model'], timeout=1800)
        report['generated_before_compile'] = generated(build)
        retained = CANDIDATE / 'candidate-build'
        result = correspondence.analyze(*[(directory / name).read_bytes().decode()
                                         for name in GENERATED[:2] for directory in (retained, build)])
        model.proof.write_json(out / 'correspondence.json', result)
        report['correspondence_sha256'] = sha(out / 'correspondence.json')
        require(report['generated_before_compile'][GENERATED[2]] == old['candidate_outputs']['cpp'][GENERATED[2]],
                'generated schema differs')
        report['raw_candidate_bytes_identical'] = report['generated_before_compile'] == old['candidate_outputs']['cpp']
        save()
        stage('compile', [host['cmake'], '--build', build, '--parallel', '4', '--target', 'sail_riscv_sim'], timeout=3600)
        binary = build / 'c_emulator/sail_riscv_sim'
        require(binary.is_file() and not binary.is_symlink() and binary.stat().st_nlink == 1 and
                os.access(binary, os.X_OK), 'no fresh simulator executable')
        require(generated(build) == report['generated_before_compile'], 'generation drift during compile')
        report.update(cpp_compiled=True, binary=str(binary), binary_sha256=sha(binary))
        metadata = [build / 'CMakeCache.txt', build / 'compile_commands.json',
                    build / 'c_emulator/CMakeFiles/riscv_model.dir/link.txt',
                    build / 'c_emulator/CMakeFiles/sail_riscv_sim.dir/link.txt']
        report['build_metadata'] = {str(p.relative_to(out)): sha(p) for p in metadata}
        report['emulator_version'] = stage('emulator-version', [binary, '--version']).read_text().strip()
        default = stage('default-config', [binary, '--print-default-config'])
        cleaned = out / 'default-config.json'
        cleaned.write_text(''.join(line for line in default.read_text().splitlines(keepends=True)
                                   if not re.match(r'^\s*//', line)))
        json.loads(cleaned.read_text())
        merged = stage('merge-config', [host['jq'], '-s', MERGE, cleaned, OVERRIDE])
        require(sha(merged) == sha(model.CONFIG), 'rebuilt merged configuration differs')
        config = out / 'ckb_vm_config.json'
        shutil.copyfile(merged, config)
        report['isa_string'] = stage('validate-config', [binary, '--config', config, '--print-isa-string']).read_text().strip()
        report.update(emulator_config_executed=True, config=str(config), config_sha256=sha(config))
        require(check_install(install) == prefix, 'installation prefix changed')
        require(inventory(source) == source_before == inventory(ROOT / 'deps/sail-riscv'), 'model source changed')
        independent(source)
        require(generated(retained) == old['candidate_outputs']['cpp'] and
                generated(build) == report['generated_before_compile'] and sha(binary) == report['binary_sha256'],
                'generated inputs or executable changed')
        report['inputs_after'] = {str(p): sha(p) for p in sorted(paths)}
        require(report['inputs_before'] == report['inputs_after'], 'probe/helper/policy/config drift')
        require(all(sha(host[n]) == row['sha256'] for n, row in report['host_tools'].items()), 'host build tool drift')
        report['status'] = 'rebuilt_sail_cpp_compiled_config_checked_admission_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = model.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-sail-cpp-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
