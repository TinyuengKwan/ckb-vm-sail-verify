#!/usr/bin/env python3
"""Run original field/raw negatives and production-factory runtime on new models.

Reuses the audited candidate model/proof and support oleans. Fresh mutation
directories and fresh Cargo home/target. No policy/tool adoption or clean-room.
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
from probes import probe_lower_map_kernel as kernel

lower = kernel.lower
require, sha, read = kernel.require, kernel.sha, kernel.read
ORIGIN = ROOT / 'artifacts/boundary-check/lower-map-kernel-0v7r0ook'
ORIGIN_SHA = '57cb243c8742513062547a8983b6cafeca689907250146e78f46cbea3d8101cd'
LOCK = lower.FIELD_DIR / 'runtime/Cargo.lock'
LOCK_SHA = 'e2f3dce87c7e8af36f84037310360f2734cf07feb8dce91ef0d4dc7692cb7d19'
MUTATIONS = {
    'wrong-slice': ('RawFields',
        'theorem rd (w : U32) : instructions.utils.rd w =\n'
        '    .ok (index (Sail.BitVec.extractLsb w.bv 11 7))',
        'theorem rd (w : U32) : instructions.utils.rd w =\n'
        '    .ok (index (Sail.BitVec.extractLsb w.bv 12 8))', 'type mismatch'),
    'wrong-rust-shift': ('LocalFields', 'x instruction_bits 7#usize 5#usize',
                         'x instruction_bits 8#usize 5#usize', 'Did not find an occurrence'),
    'wrong-selector': ('SailRawAdd', 'rd) 0x33#7', 'rd) 0x13#7', 'unsolved goals'),
    'wrong-register-field': ('DecodedRawAdd',
        '((internal rd rs1 rs2).bv >>> 40).setWidth 8 = rs2.zeroExtend 8',
        '((internal rd rs1 rs2).bv >>> 40).setWidth 8 = rs1.zeroExtend 8', 'unsolved goals'),
}


def mutate(text, before, after):
    require(text.count(before) == 1 and before != after, 'mutation anchor not unique or unchanged')
    return text.replace(before, after)


def check_weakening(actual, baseline, theorem):
    require(actual['axioms'] == baseline['axioms'], 'weakening changed axioms')
    require(actual['definitions'] == baseline['definitions'], 'weakening changed definitions')
    require(set(actual['types']) == set(baseline['types']), 'weakening changed theorem set')
    changes = {name for name in baseline['types'] if actual['types'][name] != baseline['types'][name]}
    require(changes == {theorem}, 'False premise did not change exactly the intended theorem type')
    return sorted(changes)


def rejection(code, output, expected):
    require(not re.search(r'unknown identifier|unknown namespace|object file .* does not exist|'
                          r'failed to import|deterministic timeout|timed out', output, re.I),
            'infrastructure failure is not a semantic rejection')
    kernel.check_exit(code, output, expected)


def runtime_result(output, expected):
    lines = [line for line in output.splitlines() if line.startswith('{"status":')]
    require(len(lines) == 1, 'missing or duplicate runtime result')
    result = json.loads(lines[0])
    require(result == expected and result['status'] == 'passed' and
            type(result['legal_add_encodings']) is int and result['legal_add_encodings'] == 32768 and
            type(result['non_add_neighbor_checks']) is int and result['non_add_neighbor_checks'] == 196608 and
            type(result['detected_rd_mutations']) is int and result['detected_rd_mutations'] == 32768,
            'runtime counts/scope/status changed')
    return result


def run(out):
    report = {'status': 'running', 'started_at': lower.chain.now(), 'stages': [], 'mutations': {},
              'reused_candidate_model_and_proof_cache': True, 'reused_main_and_support_cache': True,
              'clean_room_claimed': False, 'policy_changed': False, 'tool_adopted': False,
              'release_claimed': False, 'rust_reextracted': False, 'new_proof_coverage_claimed': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, args, cwd=out, run_env=None, reject=None):
        actual_env = run_env or env
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(cwd), 'expected_rejection': reject,
               'started_at': lower.chain.now(), 'lean_path': actual_env.get('LEAN_PATH')}
        report['stages'].append(row)
        save()
        print('==> lower-original-negatives: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                process = subprocess.run(row['argv'], cwd=cwd, env=actual_env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = process.returncode
            output = log.read_text(errors='replace')
            if reject == 'strict-join':
                require(process.returncode == 2, 'wrong strict-join exit')
                lower.check_result(process.returncode, output, strict=True)
            elif reject:
                rejection(process.returncode, output, reject)
            else:
                require(process.returncode == 0, 'original-negative stage failed')
        finally:
            row.update(finished_at=lower.chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return output.strip()

    try:
        require(sha(ORIGIN / 'report.json') == ORIGIN_SHA, 'kernel candidate report drift')
        origin = read(ORIGIN / 'report.json')
        require(origin['status'] == 'lower_map_equivalence_and_raw_kernel_checked_admission_pending' and
                len(origin['stages']) == 23 and origin['inputs_before'] == origin['inputs_after'], 'incomplete candidate')
        for name, digest in origin['inputs_before'].items():
            require(sha(ROOT / name) == digest, 'candidate source drift: ' + name)
        for row in origin['stages']:
            lower.chain.evidence.linked(ORIGIN, row['log'], row['log_sha256'])
            kernel.check_exit(row['exit_code'], (ORIGIN / row['log']).read_text(), row['expected_rejection'])
        components = lower.chain.verify_components()
        extraction = read(kernel.ORIGIN / 'report.json')
        require(components == extraction['components'], 'candidate tool component drift')
        checkout = Path(extraction['checkout'])
        _, state = lower.candidate()
        require(lower.snapshot.capture(checkout) == state, 'runtime source candidate drift')
        report.update(kernel_report_sha256=ORIGIN_SHA,
                      extraction_report_sha256=kernel.ORIGIN_SHA,
                      runtime_source_snapshot_sha256=state['snapshot_sha256'], runtime_checkout=str(checkout))
        require(sha(lower.FIELD_DIR / 'report.json') == lower.PINS[lower.FIELD_DIR / 'report.json'], 'old runtime evidence drift')
        old_field = read(lower.FIELD_DIR / 'report.json')
        require(sha(LOCK) == LOCK_SHA == old_field['runtime_cargo_lock_sha256'], 'runtime lock drift')
        fp, rp = read(lower.fields.POLICY), read(lower.raw.POLICY)
        require(lower.fields.source_hashes() == fp['sources'] and lower.raw.source_hashes() == rp['sources'], 'proof source drift')
        models = ORIGIN / 'models'
        for name, digest in origin['model_and_proof_sources_before'].items():
            require(sha(models / name) == digest, 'candidate model/proof source drift')
        inputs = {Path(__file__), ORIGIN / 'report.json', LOCK, lower.FIELD_DIR / 'report.json',
                  lower.fields.POLICY, lower.raw.POLICY, lower.proof.POLICY,
                  ROOT / 'scripts/check_raw_add_fields.py', ROOT / 'scripts/check_raw_add.py'}
        inputs |= {ROOT / name for name in origin['inputs_before']}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        paths = [Path(path) for path in origin['compiled_dependencies_before']]
        print('==> lower-original-negatives: verify-cached-inputs', flush=True)
        require(kernel.cached_modules(paths) == origin['compiled_dependencies_before'], 'compiled support drift')
        report['candidate_compiled_before'] = kernel.cached_modules([models])
        lean = Path(origin['lean']['path'])
        require(sha(lean) == origin['lean']['sha256'], 'Lean executable drift')
        installation = read(lower.chain.MIR.RUST_REPORT)
        require(lower.chain.MIR.rust.inventory(Path(installation['private_homes']['ELAN_HOME'])) ==
                installation['installed_closures']['elan'], 'Lean installation drift')
        env = lower.chain.environment(out, components)
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env.update(LEAN_PATH=origin['lean_path'], LEAN_ABORT_ON_PANIC='1')
        report['lean'] = origin['lean']
        report['environment'] = {key: env[key] for key in ('RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME',
            'CARGO_TARGET_DIR', 'OPAMROOT', 'OPAMSWITCH', 'LEAN_PATH')}
        base = {}
        for label, module, marker in [('map', 'ExportLowerMapAudit', 'LOWER_MAP_AUDIT_JSON='),
                                      ('field', 'ExportFieldAudit', lower.fields.MARKER),
                                      ('raw', 'ExportRawAudit', lower.raw.MARKER)]:
            output = stage('baseline-' + label, [lean, '--root=' + str(models), models / (module + '.lean')])
            lines = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
            require(len(lines) == 1, 'missing baseline audit')
            base[label] = json.loads(lines[0])
            require(base[label] == read(ORIGIN / (label + '-audit.json')) and
                    sha(ORIGIN / (label + '-audit.json')) == origin[label + '_audit_sha256'], 'candidate audit differs')
        lower.fields.check_audit(base['field'], fp)
        kernel.changed_definitions(lower.fields.audit_summary(base['raw']), rp['audit'])
        try:
            lower.raw.check_audit(base['raw'], rp)
        except RuntimeError:
            report['unchanged_raw_policy_rejects_candidate'] = True
        else:
            raise RuntimeError('original raw policy accepted candidate')
        for label, (module, before, after, expected) in MUTATIONS.items():
            directory = out / label
            directory.mkdir()
            source = models / (module + '.lean')
            mutant = directory / source.name
            mutant.write_text(mutate(source.read_text(), before, after))
            row = report['mutations'][label] = {'source': str(source), 'source_sha256': sha(source),
                'mutant': str(mutant), 'mutant_sha256': sha(mutant), 'before': before, 'after': after}
            if label == 'wrong-rust-shift':
                bad_env = dict(env, LEAN_PATH=str(directory) + os.pathsep + env['LEAN_PATH'])
                stage('wrong-rust-model-compiles', [lean, '--root=' + str(directory), mutant,
                      '-o', directory / 'LocalFields.olean'], run_env=bad_env)
                stage('negative-' + label, [lean, '--root=' + str(models), models / 'RawFields.lean'],
                      run_env=bad_env, reject=expected)
            else:
                stage('negative-' + label, [lean, '--root=' + str(directory), mutant], reject=expected)
            row['rejected'] = True
        for label, module, before, after, theorem, exporter, parser in [
            ('field', 'RawFields', 'theorem operands_correspond (w : U32)',
             'theorem operands_correspond (unjustified : False) (w : U32)',
             'RawAddFields.operands_correspond', 'ExportFieldAudit', lower.fields.audit_from),
            ('raw', 'RawEncoding', 'theorem raw_add_iff (w : BitVec 32)',
             'theorem raw_add_iff (unjustified : False) (w : BitVec 32)',
             'RawAddDecode.raw_add_iff', 'ExportRawAudit', lower.raw.audit_from),
        ]:
            directory = out / (label + '-false-premise')
            directory.mkdir()
            source = models / (module + '.lean')
            mutant = directory / source.name
            mutant.write_text(mutate(source.read_text(), before, after))
            bad_env = dict(env, LEAN_PATH=str(directory) + os.pathsep + env['LEAN_PATH'])
            stage(label + '-false-compiles', [lean, '--root=' + str(directory), mutant,
                  '-o', directory / (module + '.olean')], run_env=bad_env)
            audit = parser(stage(label + '-false-audit', [lean, '--root=' + str(models),
                           models / (exporter + '.lean')], run_env=bad_env))
            changes = check_weakening(lower.fields.audit_summary(audit), lower.fields.audit_summary(base[label]), theorem)
            lower.proof.write_json(out / (label + '-false-audit.json'), audit)
            report['mutations'][label + '-false-premise'] = {'source': str(source), 'source_sha256': sha(source),
                'mutant': str(mutant), 'mutant_sha256': sha(mutant), 'before': before, 'after': after,
                'changed_types': changes, 'rejected_by_exact_type_comparison': True,
                'audit_sha256': sha(out / (label + '-false-audit.json'))}
        translator = Path(extraction['join_binary']['path'])
        lower.chain.executable(translator, extraction['join_binary']['sha256'])
        llbc = kernel.ORIGIN / 'MiniComplete.llbc'
        require(sha(llbc) == extraction['models']['MiniComplete']['llbc_sha256'], 'strict input drift')
        opam = [components['opam']['bootstrap']['path'], 'exec',
                '--switch=' + components['opam']['switch'], '--set-switch', '--']
        stage('strict-join-negative', [*opam, translator, *read(lower.raw.CONFIG)['aeneas_args'],
              '-strict-joins', '-dest', out / 'strict-negative', llbc], reject='strict-join')
        report['strict_join_rejected'] = True
        runtime = out / 'runtime'
        runtime.mkdir()
        source = checkout / 'proof/lean/decoder/RuntimeCheck.rs'
        require(sha(source) == fp['sources']['proof/lean/decoder/RuntimeCheck.rs'], 'runtime checker drift')
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'runtime Cargo cache reused')
        report['cargo_home_initially_absent'] = report['cargo_target_initially_absent'] = True
        (runtime / 'Cargo.toml').write_text('[package]\nname = "raw-add-runtime-check"\nversion = "0.0.0"\n'
            'edition = "2024"\n[workspace]\n[dependencies]\nckb-vm = { path = ' + json.dumps(str(checkout / 'deps/ckb-vm')) +
            ' }\n[[bin]]\nname = "runtime-check"\npath = ' + json.dumps(str(source)) + '\n')
        shutil.copy2(LOCK, runtime / 'Cargo.lock')
        report['runtime_harness_before'] = {name: sha(runtime / name) for name in ('Cargo.toml', 'Cargo.lock')}
        require(stage('runtime-rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) ==
                components['rustc'], 'runtime compiler escaped installation')
        stage('runtime-fetch-locked', ['cargo', 'fetch', '--locked', '--target', 'x86_64-unknown-linux-gnu'], runtime)
        env['CARGO_NET_OFFLINE'] = 'true'
        stage('runtime-build', ['cargo', 'build', '--locked', '--offline', '--target', 'x86_64-unknown-linux-gnu',
              '--bin', 'runtime-check'], runtime)
        binary = out / 'cargo-target/x86_64-unknown-linux-gnu/debug/runtime-check'
        report['runtime_binary'] = {'path': str(binary), 'sha256': sha(binary)}
        report['runtime'] = runtime_result(stage('runtime-check', [binary], runtime), old_field['runtime'])
        require(sha(binary) == report['runtime_binary']['sha256'], 'runtime binary changed during execution')
        require(lower.snapshot.capture(checkout) == state, 'runtime candidate source changed')
        require({name: sha(runtime / name) for name in report['runtime_harness_before']} ==
                report['runtime_harness_before'], 'runtime harness changed')
        require(kernel.cached_modules([models]) == report['candidate_compiled_before'], 'candidate cache changed')
        require(kernel.cached_modules(paths) == origin['compiled_dependencies_before'], 'support cache changed')
        require(lower.chain.verify_components() == components, 'component closure changed')
        require(lower.proof.generated_evidence(read(lower.proof.POLICY)) == origin['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_before'] == report['inputs_after'], 'inputs changed')
        report.update(status='original_lower_negatives_and_runtime_completed_admission_pending')
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = lower.chain.now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='lower-original-negatives-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
