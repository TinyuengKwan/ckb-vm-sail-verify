#!/usr/bin/env python3
"""Reextract original borrow fixtures with rebuilt tools and check original proofs.

Fresh fixture/model/proof directory; explicitly reused pinned support cache.
Does not adopt tools, rebuild the full dependency graph or claim clean-room.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_lower_original_negatives as n
from experiments import probe_decoder_borrows as original
import public_decoder_gate as public

k, lower, chain = n.kernel, n.lower, n.lower.chain
require, sha, read = n.require, n.sha, n.read
FIXTURES = original.FIXTURES
CASES = {
    'JoinNested': ('join-duplicate.rs', '0829bcb76da6efe340d8dcc7cd0896250789f5edfb756de15e2da79299797308',
                   '2c76e9a8b1431ecfca2097bf12106cc18c05d99fca15e96cd68b0575f6822f2a'),
    'SharedLoop': ('loop_shared_loan_in_join.rs', '5adb5edcf264c932de1ccd51624c976dad24225d0e9eac6292a6353b42b31255',
                   '47014aa8de3a12f3a302e1884f94cf87ce9f1bf0b96cd5446855cdfa241c47e9')}
PROOFS = ['BorrowProof', 'SharedEffectProof', 'ExportBorrowAudit']
MARKER = 'BORROW_AUDIT_JSON='
SNAPSHOT_SHA = '9806e98cba5033a180cd7a846860ddd767b99ffaee0c012fe802bde21d2eb7b7'


def parse(output):
    rows = [line[len(MARKER):] for line in output.splitlines() if line.startswith(MARKER)]
    require(len(rows) == 1, 'missing/duplicate borrow audit')
    return json.loads(rows[0])


def audit_summary(audit):
    require(len(audit) == 9 and all(set(row['axioms']) <= original.STANDARD for row in audit.values()),
            'incomplete borrow audit or unaccepted axioms')
    return {name: {'axioms': row['axioms'], 'type_sha256': lower.proof.digest(row['type'].encode())}
            for name, row in audit.items()}


def weakening(audit, weak):
    require(set(audit) == set(weak), 'weakened theorem set changed')
    changed = sorted(name for name in audit if weak[name]['type'] != audit[name]['type'])
    require(changed == ['BorrowRegression.nested_assert'], 'weakening changed unexpected theorem types')
    require(all(weak[name]['axioms'] == audit[name]['axioms'] for name in audit), 'weakening changed axioms')
    return changed


def old_backedge(model):
    mutant = n.mutate(model, 'ok (cont (iter1, a1, i5, s, lane_index2))',
                     'ok (cont (iter1, a, i5, s, lane_index2))')
    require('loop_shared_loan_in_join' in mutant, 'missing mutant namespace')
    return mutant.replace('loop_shared_loan_in_join', 'MutantBorrow')


def run(out):
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [], 'models': {},
              'rust_reextracted': False, 'kernel_executed': False, 'tool_adopted': False,
              'policy_changed': False, 'clean_room_claimed': False, 'release_claimed': False,
              'support_compiled_cache_reused': True, 'full_translator_qualification_claimed': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, args, cwd=out, run_env=None, reject=None):
        actual_env = run_env or env
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(cwd), 'started_at': chain.now(),
               'lean_path': actual_env.get('LEAN_PATH'), 'expected_rejection': reject}
        report['stages'].append(row); save()
        print('==> rebuilt-borrows: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                proc = subprocess.run(row['argv'], cwd=cwd, env=actual_env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = proc.returncode
            output = log.read_text(errors='replace')
            if reject:
                n.rejection(proc.returncode, output, reject)
            else:
                k.check_exit(proc.returncode, output)
        finally:
            row.update(finished_at=chain.now(), log=log.name, log_sha256=sha(log)); save()
        return output.strip()

    try:
        components = chain.verify_components()
        report['components'] = components
        pp = read(public.POLICY)
        require(sha(public.POLICY) == 'e2643499ef13d20ed1797dca4d2e6192851fdad0b0e6e53ffc41247ce85fd0b4' and
                public.sources() == pp['sources'], 'formal public policy/source drift')
        baseline_path = chain.PUBLIC / 'qualification/borrow.json'
        require(sha(baseline_path) == pp['qualification']['borrow']['sha256'], 'original borrow qualification drift')
        baseline = read(baseline_path)
        require(baseline['status'] == 'BORROW_REGRESSIONS_PASS_NOT_ADOPTED', 'original borrow evidence incomplete')
        snapshot_path = FIXTURES / 'borrow-audit-snapshot.json'
        require(sha(snapshot_path) == SNAPSHOT_SHA, 'borrow snapshot drift')
        snapshot = read(snapshot_path)
        require(sha(n.ORIGIN / 'report.json') == n.ORIGIN_SHA, 'cache origin drift')
        cache = read(n.ORIGIN / 'report.json')
        paths = [Path(path) for path in cache['compiled_dependencies_before']]
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache drift')
        installation = read(chain.MIR.RUST_REPORT)
        elan = Path(installation['private_homes']['ELAN_HOME'])
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'private Lean closure drift')
        lean = Path(cache['lean']['path'])
        require(sha(lean) == cache['lean']['sha256'], 'Lean identity drift')
        ar = read(Path(components['reports']['aeneas']['path']))
        source = Path(ar['sides']['public']['source'])
        input_paths = {Path(__file__), Path(original.__file__), baseline_path, snapshot_path, public.POLICY,
                       lower.proof.POLICY, lower.raw.POLICY, n.ORIGIN / 'report.json'}
        input_paths |= {FIXTURES / (stem + '.lean') for stem in PROOFS}
        input_paths |= {source / 'tests/src' / row[0] for row in CASES.values()}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(input_paths)}
        report['formal_generated_before'] = lower.proof.generated_evidence(read(lower.proof.POLICY))
        env = chain.environment(out, components)
        env.update(AENEAS_FACTOR_RETURN_GUARDS='1', AENEAS_EXTRACT_TRY_FROM_INT_ERROR='1', CARGO_NET_OFFLINE='true')
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env['LEAN_ABORT_ON_PANIC'] = '1'
        report['environment'] = {key: env[key] for key in ['RUSTUP_HOME', 'RUSTUP_TOOLCHAIN', 'CARGO_HOME',
            'CARGO_TARGET_DIR', 'OPAMROOT', 'OPAMSWITCH', 'AENEAS_FACTOR_RETURN_GUARDS', 'AENEAS_EXTRACT_TRY_FROM_INT_ERROR']}
        require(not (out / 'cargo').exists() and not (out / 'cargo-target').exists(), 'old Cargo state reused')
        report['cargo_cache_and_target_initially_absent'] = True
        models = out / 'models'; models.mkdir()
        fixture_dir = out / 'aeneas-src/tests/src'; fixture_dir.mkdir(parents=True)
        side = components['tools']['public']
        opam = [components['opam']['bootstrap']['path'], 'exec', '--switch=' + components['opam']['switch'], '--set-switch', '--']
        stage('charon-version', [side['charon']['path'], 'version'])
        require(stage('aeneas-version', [*opam, side['aeneas']['path'], '-version']) == side['aeneas_version'], 'Aeneas version drift')
        require(stage('rustc-path', ['rustup', 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], 'rustc']) == components['rustc'], 'Rust installation escape')
        for stem, (filename, source_sha, model_sha) in CASES.items():
            original_source = source / 'tests/src' / filename
            require(sha(original_source) == source_sha, 'fixture source drift')
            shutil.copyfile(original_source, fixture_dir / filename)
            relative = Path('aeneas-src/tests/src') / filename
            llbc = out / (stem + '.llbc')
            stage('charon-' + stem, [side['charon']['path'], 'rustc', '--sysroot', components['sysroot'],
                  '--preset=aeneas', '--dest-file', llbc, '--', relative, '--crate-type=lib'])
            require(read(llbc)['has_errors'] is False, 'frontend errors')
            old_llbc = Path(baseline['directory']) / (stem + '.llbc')
            require(sha(old_llbc) == baseline['llbc'][stem], 'original LLBC evidence drift')
            options = chain.previous.candidate_options(read(old_llbc), read(llbc), Path(components['sysroot']))
            stage('aeneas-' + stem, [*opam, side['aeneas']['path'], '-backend', 'lean', '-abort-on-error',
                  '-no-progress-bar', '-checks', '-sequential', '-dest', models, llbc])
            report['models'][stem] = {'source_sha256': source_sha, 'llbc_sha256': sha(llbc),
                                     'model_sha256': sha(models / (stem + '.lean')), 'options': options}
            require(sha(models / (stem + '.lean')) == model_sha, 'whole generated borrow model changed: ' + stem)
        report['rust_reextracted'] = True
        for stem in PROOFS:
            shutil.copyfile(FIXTURES / (stem + '.lean'), models / (stem + '.lean'))
        report['model_and_proof_sources_before'] = {p.name: sha(p) for p in models.glob('*.lean')}
        require(not list(models.glob('*.olean')), 'initial compiled models not empty')
        env['LEAN_PATH'] = os.pathsep.join(map(str, [models, *paths]))
        report['lean_path'] = env['LEAN_PATH']; report['lean'] = cache['lean']
        for stem in [*CASES, 'BorrowProof', 'SharedEffectProof']:
            stage('kernel-' + stem, [lean, '--root=' + str(models), models / (stem + '.lean'),
                  '-o', models / (stem + '.olean')])
        audit = parse(stage('kernel-audit', [lean, models / 'ExportBorrowAudit.lean']))
        require(audit_summary(audit) == snapshot, 'borrow theorem types/axioms changed')
        lower.proof.write_json(out / 'audit.json', audit)
        report['audit_sha256'] = sha(out / 'audit.json')
        weak = out / 'weakened'; weak.mkdir()
        (weak / 'BorrowProof.lean').write_text(n.mutate((models / 'BorrowProof.lean').read_text(),
            'theorem nested_assert (b : Bool)', 'theorem nested_assert (unused : False) (b : Bool)'))
        weak_env = dict(env, LEAN_PATH=str(weak) + os.pathsep + env['LEAN_PATH'])
        stage('weakening-compiles', [lean, '--root=' + str(weak), weak / 'BorrowProof.lean', '-o', weak / 'BorrowProof.olean'], run_env=weak_env)
        wa = parse(stage('weakening-audit', [lean, models / 'ExportBorrowAudit.lean'], run_env=weak_env))
        report['weakening_changed_types'] = weakening(audit, wa)
        lower.proof.write_json(out / 'weak-audit.json', wa)
        (models / 'SharedMutant.lean').write_text(old_backedge((models / 'SharedLoop.lean').read_text()))
        stage('kernel-mutant-model', [lean, '--root=' + str(models), models / 'SharedMutant.lean', '-o', models / 'SharedMutant.olean'])
        proof = (models / 'SharedEffectProof.lean').read_text().replace('import SharedLoop', 'import SharedMutant').replace(
            'loop_shared_loan_in_join', 'MutantBorrow').replace('namespace BorrowRegression', 'namespace MutantRegression').replace(
            'end BorrowRegression', 'end MutantRegression')
        (out / 'RejectOldBackEdge.lean').write_text(proof)
        stage('negative-old-back-edge', [lean, out / 'RejectOldBackEdge.lean'], reject='unsolved goals')
        actual = n.mutate(proof, 'lanes 12#u64 22#u64 32#u64 42#u64, 1#u32', 'lanes 10#u64 20#u64 30#u64 40#u64, 1#u32')
        actual = n.mutate(actual, '.ok (finish, output 11#u64 12#u64)', '.ok (finish, output 11#u64 11#u64)')
        (out / 'MutantActualTrace.lean').write_text(actual)
        stage('kernel-mutant-actual-trace', [lean, out / 'MutantActualTrace.lean'])
        report['negative_sources'] = {str(path.relative_to(out)): sha(path) for path in [weak / 'BorrowProof.lean',
            models / 'SharedMutant.lean', out / 'RejectOldBackEdge.lean', out / 'MutantActualTrace.lean', out / 'weak-audit.json']}
        for name, digest in report['model_and_proof_sources_before'].items():
            require(sha(models / name) == digest, 'model/proof source changed')
        for stem, (filename, source_sha, _) in CASES.items():
            require(sha(fixture_dir / filename) == source_sha and sha(out / (stem + '.llbc')) ==
                    report['models'][stem]['llbc_sha256'], 'fixture/LLBC changed')
        require(k.cached_modules(paths) == cache['compiled_dependencies_before'], 'support cache changed')
        require(chain.verify_components() == components, 'component closure changed')
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean closure changed')
        require(lower.proof.generated_evidence(read(lower.proof.POLICY)) == report['formal_generated_before'], 'formal models changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(input_paths)}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        report.update(status='rebuilt_borrow_regressions_checked_admission_pending', kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    report['finished_at'] = chain.now(); save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-borrows-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
