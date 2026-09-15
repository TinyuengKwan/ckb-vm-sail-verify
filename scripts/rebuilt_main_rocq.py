#!/usr/bin/env python3
"""Fresh Sail Rocq generation and explicit dual-OPAM spike for one candidate.

Reuses the frozen spike's rejection classifiers and independent evidence checks.
This driver is additional, hashed execution code, not the original spike entry.
No source editing, formal adoption, proof coverage or full clean-room claim.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import rebuilt_main_acceptance as anchors
import rebuilt_main_runtime as native

require, sha, read = anchors.require, anchors.sha, anchors.read
PROFILE = 'rebuilt-main-explicit-rocq-v1'
INSTALL = anchors.ROOT / 'artifacts/boundary-check/isolated-rocq-ac54t6f8/report.json'
INSTALL_SHA = '3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540'
CLOSURE_SHA = 'e03a37b1c376dfe9305c5a991c65ef6ff104ad14bfe96bda4aa7da6fe8a13e72'
PRIMITIVES_SHA = '45d1909de822a99f9f8685fc504d6622b86959e6e0bacaae3443b426ef977c16'
MARKER = 'REBUILT_ROCQ_CHECK_JSON='
STAGES = ['packages', 'version', 'rust-generate', 'rust-primitives', 'rust-model',
          'rust-repro', 'sail-support', 'sail-types', 'sail-model', 'sail-repro']
COPIES = {'rust/result_shadowing.v': 'proof/rocq/spike/result_shadowing.v',
          'sail/rv64d.v': 'proof/rocq/generated/sail/rv64d.v',
          'sail/rv64d_types.v': 'proof/rocq/generated/sail/rv64d_types.v',
          'sail/riscv_extras.v': 'deps/sail-riscv/handwritten_support/riscv_extras.v',
          'sail/missing_e_div.v': 'proof/rocq/spike/missing_e_div.v'}


def install_primitives(source, destination, expected):
    """Explicit upstream support, never a synthesized or silently replaced file.

    Aeneas locates this next to argv[0]; the admitted binary package intentionally
    stores its audited source elsewhere. Both placements must have the same bytes.
    """
    require(source.resolve() == source and source.is_file() and sha(source) == expected,
            'Rocq primitive source identity differs')
    require(destination.resolve() == destination and not destination.is_symlink(), 'linked Rocq primitives output')
    existed = destination.exists()
    if existed:
        require(destination.is_file() and sha(destination) == expected, 'unexpected translator primitives; not overwritten')
    else:
        shutil.copyfile(source, destination)
    require(sha(destination) == expected, 'Rocq primitive copy differs')
    return {'source': str(source), 'sha256': expected,
            'installation': 'translator_emitted_exact' if existed else 'copied_from_verified_source'}


def rocq_environment(env, installation):
    require(installation['switch'] == 'isolated-rocq', 'unreviewed Rocq switch')
    result = {k: v for k, v in env.items() if not k.startswith(('OPAM', 'OCAML', 'CAML', 'COQ', 'ROCQ'))}
    result.update(OPAMROOT=installation['opam_root'], OPAMSWITCH=installation['switch'],
                  PATH='/usr/bin:/bin', OPAMNOENVNOTICE='true', DUNE_CACHE='disabled')
    return result


def opam_exec(opam, root, switch):
    require(Path(opam).is_absolute() and Path(root).is_absolute() and switch and
            not switch.startswith('-') and '/' not in switch, 'non-explicit OPAM selection')
    return [str(opam), 'exec', '--root=' + str(root), '--switch=' + switch, '--set-switch', '--']


def commands(root, out, env, binaries, installation):
    opam = installation['opam_bootstrap']['path']
    rocq = opam_exec(opam, installation['opam_root'], installation['switch'])
    aeneas = opam_exec(opam, env['OPAMROOT'], env['OPAMSWITCH'])
    compiler = installation['binaries']['rocq']['path']
    result = {
        'packages': ([opam, 'list', '--root=' + installation['opam_root'],
                      '--switch=' + installation['switch'], '--installed', '--short', '--columns=name,version'], out),
        'version': (rocq + [compiler, '--version'], out),
        'rust-generate': (aeneas + [str(binaries['aeneas']), '-backend', 'rocq', '-dest', str(out / 'rust'),
                                    str(root / 'target/CkbVmProduction.llbc')], out),
    }
    for name, folder, file in [('rust-primitives', 'rust', 'Primitives.v'),
        ('rust-model', 'rust', 'CkbVmProduction.v'), ('rust-repro', 'rust', 'result_shadowing.v'),
        ('sail-support', 'sail', 'riscv_extras.v'), ('sail-types', 'sail', 'rv64d_types.v'),
        ('sail-model', 'sail', 'rv64d.v'), ('sail-repro', 'sail', 'missing_e_div.v')]:
        result[name] = (rocq + [compiler, 'compile', '-Q', '.', '', file], out / folder)
    require(list(result) == STAGES, 'explicit spike command inventory differs')
    return result


def check_commands(report, expected):
    require([r['name'] for r in report['stages']] == list(expected), 'spike stage inventory differs')
    for row in report['stages']:
        argv, cwd = expected[row['name']]
        require(row['command'] == argv and row['cwd'] == str(cwd), 'spike command/context differs: ' + row['name'])


def generation_evidence(report, out, root):
    require(report['candidate'] == str(root), 'wrong Rocq generation candidate')
    row = report['stages'][0]
    require(row['name'] == 'generate-sail-rocq' and row['argv'] ==
            ['bash', 'scripts/generate_proof_model.sh', 'rocq'] and
            type(row['exit_code']) is int and row['exit_code'] == 0 and
            row['log'] == 'generate-sail-rocq.log', 'fresh Sail Rocq command not completed')
    log = out / row['log']
    require(log.resolve() == log and sha(log) == row['log_sha256'], 'Sail Rocq generation log drift')
    rows = [json.loads(line[len('SAIL_INSTALL_JSON='):]) for line in log.read_text().splitlines()
            if line.startswith('SAIL_INSTALL_JSON=')]
    require(rows == [report['sail_generation']], 'Sail Rocq transaction record mismatch')
    record = rows[0]
    source = root / 'deps/sail-riscv/build/rocq'
    destination = root / 'proof/rocq/generated/sail'
    backup = Path(record['installation_backup'])
    require(record['source'] == str(source) and record['destination'] == str(destination) and
            record['status'] == 'installed' and record['published'] is True and record['policy_changed'] is False and
            backup.parent == destination.parent and backup.name.startswith('.sail-install-'),
            'wrong Sail Rocq transaction target/status')
    transaction = backup / 'transaction.json'
    require(transaction.resolve() == transaction and read(transaction) == record and
            report['sail_transaction'] == {'path': str(transaction), 'sha256': sha(transaction)},
            'Sail Rocq transaction identity drift')
    files = {}
    for path in sorted(destination.rglob('*')):
        require(path.resolve() == path, 'linked Sail Rocq output')
        if path.is_dir(): continue
        require(path.is_file() and path.stat().st_nlink == 1, 'nonregular/shared Sail Rocq output')
        files[str(path.relative_to(destination))] = sha(path)
    require(list(files) == record['installed_files'] and {'rv64d.v', 'rv64d_types.v'} <= files.keys(),
            'fresh Sail Rocq file inventory drift')
    return {'transaction_sha256': sha(transaction), 'installed_files_sha256': files}


def resolve():
    root = anchors.CANDIDATE
    require(sha(anchors.REVIEW) == anchors.REVIEW_SHA and
            sha(anchors.PREPARATION / 'candidate-source-snapshot.json') == anchors.SNAPSHOT_SHA and
            sha(root / 'proof/lean/audit/step-policy.json') == anchors.POLICY_SHA and
            sha(anchors.ROOT / 'proof/lean/audit/step-policy.json') == anchors.OLD_POLICY_SHA,
            'fixed candidate/review/formal policy drift')
    require(read(anchors.REVIEW)['status'] == 'rebuilt_main_candidate_ready_full_execution_pending',
            'candidate preparation not accepted')
    path = root / 'artifacts/proof-check/report.json'
    prefix = native.ready(read(path), path.parent)
    sys.path.insert(0, str(root / 'scripts'))
    import rebuilt_main_tools as tools
    import source_snapshot as snapshot
    import rocq_spike as spike
    require(tools.proof.ROOT == root and spike.ROOT == root, 'wrong candidate code root')
    frozen = read(anchors.PREPARATION / 'candidate-source-snapshot.json')
    require(snapshot.capture(root) == frozen, 'frozen candidate source drift')
    env, binaries, home, _ = tools.resolve(root, read(tools.proof.POLICY))
    require(sha(INSTALL) == INSTALL_SHA, 'Rocq installation report drift')
    installation = read(INSTALL)
    require(installation['status'] == 'isolated_rocq_rebuild_and_existing_input_nogo_passed' and
            installation['installed_closure']['sha256'] == CLOSURE_SHA, 'Rocq installation not accepted')
    require(tools.locations.installation_inventory(Path(installation['opam_root']) / installation['switch'],
            tools.INSTALL_FOLDERS) == installation['installed_closure'], 'Rocq installation closure drift')
    for row in [installation['opam_bootstrap'], *installation['binaries'].values()]:
        require(sha(Path(row['path'])) == row['sha256'], 'Rocq/bootstrap binary drift')
    return tools, snapshot, spike, frozen, prefix, env, binaries, home, installation


def execute_spike(out, context):
    tools, _, spike, _, _, env, binaries, home, installation = context
    root = anchors.CANDIDATE
    proof, policy = tools.proof, read(tools.proof.POLICY)
    rocq_env = rocq_environment(env, installation)
    before = spike.inputs(root)
    report = {'schema_version': 1, 'status': 'running', 'verdict': None, 'extra_proof_coverage': False,
              'clean_room_claimed': False, 'directory': str(out), 'stages': [], 'started_at': anchors.stamp(),
              'execution_profile': PROFILE, 'driver_sha256': sha(Path(__file__)),
              'opam_switch': installation['switch'], 'rocq_opam_root': installation['opam_root'],
              'aeneas_opam_root': env['OPAMROOT'], 'aeneas_opam_switch': env['OPAMSWITCH'],
              'input_regeneration': 'candidate production LLBC freshly extracted; Sail Rocq freshly generated in enclosing run',
              'input_sha256': before, 'policy_sha256': sha(proof.POLICY),
              'source': proof.source_evidence(policy, binaries, home), 'generated': proof.generated_evidence(policy)}
    expected = commands(root, out, env, binaries, installation)
    def run(name, rejection=None):
        argv, cwd = expected[name]
        return spike.stage(out, report, env if name == 'rust-generate' else rocq_env,
                           name, argv, cwd, rejection)
    try:
        report['packages'] = spike.check_packages(run('packages'))
        require(report['packages'] == installation['packages'], 'full Rocq package inventory drift')
        report['rocq_version'] = run('version').strip()
        require(report['rocq_version'] == 'The Rocq Prover, version 9.1.1\ncompiled with OCaml 5.2.1', 'Rocq version drift')
        (out / 'rust').mkdir()
        (out / 'sail').mkdir()
        run('rust-generate')
        report['rust_primitives'] = install_primitives(home / 'backends/coq/Primitives.v',
                                                       out / 'rust/Primitives.v', PRIMITIVES_SHA)
        for name in ('Primitives.v', 'CkbVmProduction.v'):
            require((out / 'rust' / name).is_file(), 'missing fresh Rust Rocq output')
        for target, source in COPIES.items(): shutil.copyfile(root / source, out / target)
        models = {str(p.relative_to(out)): sha(p) for folder in ('rust', 'sail') for p in (out / folder).glob('*.v')}
        run('rust-primitives')
        run('rust-model', 'rust')
        require('Expands to: Inductive Corelib.Init.Datatypes.result' in run('rust-repro'), 'Rust minimal reproduction absent')
        run('sail-support')
        run('sail-types')
        run('sail-model', 'sail')
        run('sail-repro', 'sail')
        require(spike.inputs(root) == before, 'spike input drift')
        require(all(sha(out / p) == h for p, h in models.items()), 'checked Rocq model drift')
        check_commands(report, expected)
        report.update(status='passed', verdict='NO-GO', model_sha256=models, input_sha256_after=spike.inputs(root))
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        raise
    finally:
        report['finished_at'] = anchors.stamp()
        spike.save(out, report)


def validate_spike(out):
    context = resolve()
    tools, _, _, _, _, env, binaries, home, installation = context
    import release_evidence as evidence
    require(out.resolve() == out and out.is_relative_to(anchors.ROOT / 'artifacts/boundary-check'), 'unsafe spike directory')
    enclosing = read(out.parent / 'report.json')
    require(out.name == 'spike' and out.parent.name.startswith('rebuilt-main-rocq-') and
            enclosing['spike_report_sha256'] == sha(out / 'report.json'), 'unbound Rocq child report')
    require(generation_evidence(enclosing, out.parent, anchors.CANDIDATE) == enclosing['sail_generation_identity'],
            'enclosing fresh Sail generation identity drift')
    report = read(out / 'report.json')
    require(report['execution_profile'] == PROFILE and report['driver_sha256'] == sha(Path(__file__)), 'Rocq driver identity drift')
    primitive_source = home / 'backends/coq/Primitives.v'
    require(report['rust_primitives']['source'] == str(primitive_source) and
            report['rust_primitives']['sha256'] == sha(primitive_source) == sha(out / 'rust/Primitives.v') == PRIMITIVES_SHA and
            report['rust_primitives']['installation'] in ('translator_emitted_exact', 'copied_from_verified_source'),
            'Rocq primitive source/copy provenance drift')
    require(report['rocq_opam_root'] == installation['opam_root'] and report['opam_switch'] == installation['switch'] and
            report['aeneas_opam_root'] == env['OPAMROOT'] and report['aeneas_opam_switch'] == env['OPAMSWITCH'],
            'recorded OPAM context drift')
    check_commands(report, commands(anchors.CANDIDATE, out, env, binaries, installation))
    result = evidence.check_rocq(out / 'report.json')
    require(report['packages'] == installation['packages'], 'full Rocq package inventory differs')
    return result


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--check-spike':
        print(MARKER + json.dumps(validate_spike(Path(sys.argv[2])), sort_keys=True), flush=True)
        return 0
    require(len(sys.argv) == 1, 'usage: rebuilt_main_rocq.py [--check-spike DIRECTORY]')
    root = anchors.CANDIDATE
    out = Path(tempfile.mkdtemp(prefix='rebuilt-main-rocq-', dir=anchors.ROOT / 'artifacts/boundary-check'))
    report = {'status': 'running', 'started_at': anchors.stamp(), 'candidate': str(root), 'stages': [],
              'extra_proof_coverage': False, 'formal_adoption_claimed': False, 'clean_room_claimed': False,
              'release_claimed': False, 'week6_closed': False}
    def save(): (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def stage(name, argv):
        row = {'name': name, 'argv': argv, 'started_at': anchors.stamp()}
        report['stages'].append(row)
        save()
        log = out / (name + '.log')
        print('==> rebuilt candidate Rocq: ' + name, flush=True)
        try:
            with log.open('xb') as stream:
                result = subprocess.run(argv, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'Rocq wrapper stage failed: ' + name)
        finally:
            row.update(finished_at=anchors.stamp(), log=log.name, log_sha256=sha(log))
            save()
        return log
    save()
    print(out, flush=True)
    try:
        paths = [Path(__file__), Path(native.__file__), Path(anchors.__file__), INSTALL,
                 anchors.ROOT / 'scripts/tests/test_rebuilt_main_rocq.py', anchors.REVIEW,
                 anchors.PREPARATION / 'candidate-source-snapshot.json',
                 anchors.ROOT / 'proof/lean/audit/step-policy.json']
        report['inputs_before'] = {str(p): sha(p) for p in paths}
        context = resolve()
        tools, snapshot, spike, frozen, prefix, env, binaries, home, installation = context
        policy = read(tools.proof.POLICY)
        report.update(completed_generation_prefix=prefix, source_snapshot_sha256=frozen['snapshot_sha256'],
                      generated_before=tools.proof.generated_evidence(policy), rocq_installation_report_sha256=INSTALL_SHA)
        log = stage('generate-sail-rocq', ['bash', 'scripts/generate_proof_model.sh', 'rocq'])
        rows = [json.loads(line[len('SAIL_INSTALL_JSON='):]) for line in log.read_text().splitlines()
                if line.startswith('SAIL_INSTALL_JSON=')]
        require(len(rows) == 1 and rows[0]['status'] == 'installed' and rows[0]['published'] is True and
                rows[0]['policy_changed'] is False, 'fresh Sail Rocq installation missing')
        report['sail_generation'] = rows[0]
        transaction = Path(rows[0]['installation_backup']) / 'transaction.json'
        require(read(transaction) == rows[0], 'Sail transaction/log mismatch')
        report['sail_transaction'] = {'path': str(transaction), 'sha256': sha(transaction)}
        report['sail_generation_identity'] = generation_evidence(report, out, root)
        spike_out = out / 'spike'
        spike_out.mkdir()
        execute_spike(spike_out, context)
        child = spike_out / 'report.json'
        report['spike_report_sha256'] = sha(child)
        log = stage('independent-check', ['/usr/bin/python3', '-O', str(Path(__file__).resolve()), '--check-spike', str(spike_out)])
        rows = [json.loads(line[len(MARKER):]) for line in log.read_text().splitlines() if line.startswith(MARKER)]
        require(len(rows) == 1 and rows[0]['stages'] == 10 and rows[0]['extra_proof_coverage'] is False,
                'independent Rocq acceptance absent')
        report['details'] = rows[0]
        require(sha(child) == report['spike_report_sha256'] and sha(transaction) == report['sail_transaction']['sha256'],
                'Rocq evidence drift')
        require(generation_evidence(report, out, root) == report['sail_generation_identity'], 'fresh Rocq input drift')
        report['generated_after'] = tools.proof.generated_evidence(policy)
        require(report['generated_before'] == report['generated_after'] and snapshot.capture(root) == frozen,
                'candidate Lean inputs/source changed during Rocq execution')
        main_path = root / 'artifacts/proof-check/report.json'
        require(native.ready(read(main_path), main_path.parent) == prefix, 'main generation prefix changed')
        report['inputs_after'] = {str(p): sha(p) for p in paths}
        require(report['inputs_before'] == report['inputs_after'], 'Rocq driver/anchor drift')
        report['status'] = 'candidate_fresh_rocq_inputs_and_specific_nogo_verified_adoption_pending'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = anchors.stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
