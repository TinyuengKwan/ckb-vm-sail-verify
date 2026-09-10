"""Fresh Rust-to-Lean regression checks for the isolated borrow candidate.

Does not adopt tools or refresh the public decoder policy. Includes a semantic
mutation of the loop back edge and a checked concrete trace of that mutation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
STANDARD = {'propext', 'Classical.choice', 'Quot.sound'}
FIXTURES = ROOT / 'proof/lean/decoder/toolchain/branch-experimental'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def require(test, message):
    if not test:
        raise RuntimeError(message)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    args = parser.parse_args()
    inputs = args.inputs.resolve()
    out = Path(tempfile.mkdtemp(prefix='borrow-check-', dir=ROOT / 'artifacts/boundary-check'))
    models = out / 'models'
    report = {'status': 'running', 'directory': str(out), 'stages': [],
              'rust_reextracted': True, 'sysroot_rebuilt': False,
              'tool_adopted': False, 'clean_dependency_build': False}
    env = dict(os.environ, RUSTUP_TOOLCHAIN='nightly-2026-08-18',
               AENEAS_FACTOR_RETURN_GUARDS='1', AENEAS_EXTRACT_TRY_FROM_INT_ERROR='1')
    for key in ['RUSTFLAGS', 'CHARON_ARGS', 'CHARON_LOG', 'RUST_LOG',
                'AENEAS_BRANCH_DIAGNOSTIC', 'AENEAS_COLLAPSE_DIAGNOSTIC']:
        env.pop(key, None)
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(label, command, cwd=ROOT, run_env=env, reject=None):
        record = {'stage': label, 'command': list(map(str, command)), 'cwd': str(cwd)}
        report['stages'].append(record)
        save()
        start = time.monotonic()
        log = out / (label + '.log')
        with log.open('w') as stream:
            proc = subprocess.run(record['command'], cwd=cwd, env=run_env,
                stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        text = log.read_text()
        record.update(exit_code=proc.returncode, elapsed_seconds=time.monotonic()-start,
                      log_sha256=sha(log))
        save()
        if reject:
            require(proc.returncode == 1 and reject in text, label + ': wrong rejection')
            require(not re.search('unknownIdentifier|maximum.*(heartbeats|recursion)|out of memory', text, re.I),
                    label + ': infrastructure failure is not semantic rejection')
        else:
            require(proc.returncode == 0 and 'sorryAx' not in text, label + ': failed; see ' + str(log))
        print(label + (': expected rejection' if reject else ': PASS'), flush=True)
        return text
    try:
        aeneas = inputs / 'candidate-v2-bin/aeneas'
        charon = inputs.parent / 'charon-cfg-OYcaoK/candidate-bin/charon'
        require(sha(aeneas) == '1fe7040d9dc5dc2af5320722c23199eddb2d1d540a303f7fcbaa7cb0defacaae', 'Aeneas identity')
        require(sha(charon) == 'bb36ff589c4eec04b834504c26fd29308421e24013a3ab44b58ef54b9e9eb3de', 'Charon identity')
        require(sha(charon.with_name('charon-driver')) == 'b6ac4b189fd8b4afa43a02fd65ce3cb6e51b6cb408cd98b973d7345af416f49b', 'Charon driver identity')
        report['binaries'] = {str(p): sha(p) for p in [aeneas, charon, charon.with_name('charon-driver')]}
        report['proofs'] = {p.name: sha(p) for p in [FIXTURES / (name + '.lean') for name in
            ['BorrowProof', 'SharedEffectProof', 'ExportBorrowAudit']]}
        report['script_sha256'] = sha(Path(__file__))
        snapshot_path = FIXTURES / 'borrow-audit-snapshot.json'
        require(sha(snapshot_path) == '9806e98cba5033a180cd7a846860ddd767b99ffaee0c012fe802bde21d2eb7b7', 'borrow snapshot identity')
        snapshot = json.loads(snapshot_path.read_text())
        report['snapshot_sha256'] = sha(snapshot_path)
        report['rustc_version'] = subprocess.check_output(['rustc', '-vV'], env=env, text=True)
        require('commit-hash: 8fa1c96cfd489e4c27654c144ae871ce2c4db6c6' in report['rustc_version'], 'rustc identity')
        report['sources'] = {}
        report['llbc'] = {}
        for module, file, source_hash, model_hash in [
            ('JoinNested', 'join-duplicate.rs', '0829bcb76da6efe340d8dcc7cd0896250789f5edfb756de15e2da79299797308',
             '2c76e9a8b1431ecfca2097bf12106cc18c05d99fca15e96cd68b0575f6822f2a'),
            ('SharedLoop', 'loop_shared_loan_in_join.rs', '5adb5edcf264c932de1ccd51624c976dad24225d0e9eac6292a6353b42b31255',
             '47014aa8de3a12f3a302e1884f94cf87ce9f1bf0b96cd5446855cdfa241c47e9')]:
            relative = Path('aeneas-src/tests/src') / file
            require(sha(inputs / relative) == source_hash, 'Rust fixture identity')
            report['sources'][str(relative)] = source_hash
            llbc = out / (module + '.llbc')
            run('charon-' + module, [charon, 'rustc', '--sysroot',
                inputs.parent / 'decoder-sysroot-q8nI9W/sysroot', '--preset=aeneas',
                '--dest-file', llbc, '--', relative, '--crate-type=lib'], inputs)
            require(not json.loads(llbc.read_text())['has_errors'], 'frontend errors')
            report['llbc'][module] = sha(llbc)
            run('aeneas-' + module, [aeneas, '-backend', 'lean', '-abort-on-error',
                '-no-progress-bar', '-checks', '-sequential', '-dest', models, llbc], inputs)
            require(sha(models / (module + '.lean')) == model_hash, 'generated model changed: ' + module)
        project = ROOT / 'proof/lean/theorems'
        lean = subprocess.check_output(['lake', 'env', 'which', 'lean'], cwd=project, text=True).strip()
        base = subprocess.check_output(['lake', 'env', 'printenv', 'LEAN_PATH'], cwd=project, text=True).strip()
        lean_env = dict(env, LEAN_PATH=str(models) + os.pathsep + base)
        report['initial_new_oleans'] = len(list(models.glob('*.olean')))
        require(report['initial_new_oleans'] == 0, 'nonempty model cache')
        for module in ['JoinNested', 'SharedLoop', 'BorrowProof', 'SharedEffectProof']:
            folder = models if module in ['JoinNested', 'SharedLoop'] else FIXTURES
            run('kernel-' + module, [lean, '--root=' + str(folder), '-o', models / (module + '.olean'),
                folder / (module + '.lean')], project, lean_env)
        text = run('kernel-audit', [lean, FIXTURES / 'ExportBorrowAudit.lean'], project, lean_env)
        marker = 'BORROW_AUDIT_JSON='
        rows = [line[len(marker):] for line in text.splitlines() if line.startswith(marker)]
        require(len(rows) == 1, 'missing audit')
        audit = json.loads(rows[0])
        require(len(audit) == 9, 'incomplete theorem audit')
        require(all(set(row['axioms']) <= STANDARD for row in audit.values()), 'unexpected axiom')
        (out / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
        report['audit_sha256'] = sha(out / 'audit.json')
        report['theorems'] = {name: {'axioms': row['axioms'],
            'type_sha256': hashlib.sha256(row['type'].encode()).hexdigest()} for name, row in audit.items()}
        require(report['theorems'] == snapshot, 'borrow theorem type/dependency changed')
        weakened = out / 'weakened'
        weakened.mkdir()
        text = (FIXTURES / 'BorrowProof.lean').read_text()
        anchor = 'theorem nested_assert (b : Bool)'
        require(text.count(anchor) == 1, 'weakening anchor')
        (weakened / 'BorrowProof.lean').write_text(text.replace(anchor,
            'theorem nested_assert (unused : False) (b : Bool)', 1))
        weak_env = dict(lean_env, LEAN_PATH=str(weakened) + os.pathsep + lean_env['LEAN_PATH'])
        run('weakening-compiles', [lean, '--root=' + str(weakened), '-o',
            weakened / 'BorrowProof.olean', weakened / 'BorrowProof.lean'], project, weak_env)
        text = run('weakening-audit', [lean, FIXTURES / 'ExportBorrowAudit.lean'], project, weak_env)
        rows = [line[len(marker):] for line in text.splitlines() if line.startswith(marker)]
        require(len(rows) == 1, 'missing weak audit')
        weak = json.loads(rows[0])
        changed = [name for name in audit if weak[name]['type'] != audit[name]['type']]
        require(changed == ['BorrowRegression.nested_assert'], 'weakening not isolated to its theorem type')
        require(all(weak[name]['axioms'] == audit[name]['axioms'] for name in audit), 'weakening changed dependencies')
        report['false_premise_rejected_by_type_audit'] = True
        # Reproduce the original class of bug: only change the array sent along
        # the back edge, retaining the correctly updated array for this read.
        model = (models / 'SharedLoop.lean').read_text()
        anchor = 'ok (cont (iter1, a1, i5, s, lane_index2))'
        require(model.count(anchor) == 1, 'nonunique mutation anchor')
        mutant = model.replace(anchor, 'ok (cont (iter1, a, i5, s, lane_index2))').replace(
            'loop_shared_loan_in_join', 'MutantBorrow')
        (models / 'SharedMutant.lean').write_text(mutant)
        run('kernel-mutant-model', [lean, '--root=' + str(models), '-o', models / 'SharedMutant.olean',
            models / 'SharedMutant.lean'], project, lean_env)
        proof = (FIXTURES / 'SharedEffectProof.lean').read_text().replace('import SharedLoop',
            'import SharedMutant').replace('loop_shared_loan_in_join', 'MutantBorrow').replace(
            'namespace BorrowRegression', 'namespace MutantRegression').replace(
            'end BorrowRegression', 'end MutantRegression')
        bad = out / 'RejectOldBackEdge.lean'
        bad.write_text(proof)
        run('negative-old-back-edge', [lean, bad], project, lean_env, reject='unsolved goals')
        # A successful kernel proof of the mutant's actual wrong trace excludes
        # a timeout or missing-instance explanation for the preceding failure.
        require(proof.count('lanes 12#u64 22#u64 32#u64 42#u64, 1#u32') == 1, 'mutant final state anchor')
        actual = proof.replace('lanes 12#u64 22#u64 32#u64 42#u64, 1#u32',
            'lanes 10#u64 20#u64 30#u64 40#u64, 1#u32').replace(
            '.ok (finish, output 11#u64 12#u64)', '.ok (finish, output 11#u64 11#u64)')
        (out / 'MutantActualTrace.lean').write_text(actual)
        run('kernel-mutant-actual-trace', [lean, out / 'MutantActualTrace.lean'], project, lean_env)
        report['status'] = 'BORROW_REGRESSIONS_PASS_NOT_ADOPTED'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        raise
    finally:
        save()
        print('Report: ' + str(out / 'report.json'), flush=True)

if __name__ == '__main__':
    main()
