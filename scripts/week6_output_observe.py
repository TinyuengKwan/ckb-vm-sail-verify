"""Observe current outputs without mutating source, generation or acceptance.

Includes every original formal output root, the actual accepted native run,
the whole original formal run and all new evidence siblings since that run.
Preexisting historical experiments/tools remain explicitly unobserved; no
whole-workspace, delivery, semantic, clean-room or release approval is claimed.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = None
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_release as audit
import check_proof as proof
import generated_output_inventory as inventory
import record_generation as recorder
import release_evidence as common
import release_worktree_source as source_review
import source_snapshot as source
from week6_output_projection import project
FLAGS = ['release_claimed', 'week6_closed', 'worktree_audit_closed', 'candidate_approval_claimed',
         'fresh_kernel_run_claimed', 'regeneration_execution_proven', 'clean_room_claimed',
         'third_party_claimed', 'generated_outputs_audited', 'whole_workspace_coverage_claimed',
         'current_output_acceptance_closed', 'atomic_filesystem_snapshot_claimed']


def ref(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': common.sha(path)}


def parents():
    return sorted(os.listdir(OUT.parent))


def read_inputs(path, root=ROOT):
    value = common.read(path)
    common.require(type(value) is dict and set(value) == {
        'schema_version', 'kind', 'candidate', 'formal_report', 'current_source_review',
        'current_manifest'
    }, 'current-output input fields')
    common.require(common.same(value['schema_version'], 1) and
                   value['kind'] == 'week6-current-output-input-v1' and
                   isinstance(value['candidate'], str) and value['candidate'].strip(),
                   'current-output input identity')
    paths = {}
    for name in ['formal_report', 'current_source_review', 'current_manifest']:
        row = value[name]
        common.require(type(row) is dict and set(row) == {'path', 'sha256'},
                       'current-output input reference: ' + name)
        paths[name] = common.linked(root, row['path'], row['sha256'])
    return value, paths


def new_output(path, root=ROOT):
    path = Path(path).absolute()
    parent = Path(root).resolve() / 'artifacts/boundary-check'
    common.require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
                   path.name.startswith('week6-output-observation-') and
                   path.name != 'week6-output-observation-' and
                   not path.exists() and not path.is_symlink(),
                   'new Week6 output observation required')
    path.mkdir()
    return path


def copy_regular(source_path, destination):
    source_path = Path(source_path).absolute()
    common.require(source_path.is_file() and not source_path.is_symlink() and
                   all(not parent.is_symlink() for parent in source_path.parents),
                   'missing/linked observation support source')
    data = source_path.read_bytes()
    with Path(destination).open('xb') as stream:
        stream.write(data)
    common.require(common.sha(source_path) == common.sha(destination),
                   'observation support copy changed')


def main(output, inputs_path):
    global OUT
    OUT = new_output(output)
    copy_regular(ROOT / 'scripts/week6_output_projection.py', OUT / 'projection.py')
    copy_regular(ROOT / 'scripts/tests/test_week6_output_projection.py', OUT / 'test_projection.py')
    report = {'schema_version': 1, 'kind': 'current-expanded-output-observation-v1',
              'status': 'running', 'started_at': recorder.now(), 'stages': [], 'errors': [],
              **dict.fromkeys(FLAGS, False)}
    recorder.write(OUT / 'started.json', report)
    env = dict(os.environ)

    def stage(name, argv, timeout=1800):
        print(name, flush=True)
        row = recorder.command(OUT, name, argv, env, timeout, ROOT)
        report['stages'].append(row)
        common.require(row['status'] == 'completed' and common.same(row['exit_code'], 0), 'failed stage: ' + name)
        print({k: row[k] for k in ['name', 'status', 'exit_code', 'finished_at']}, flush=True)

    try:
        inputs, paths = read_inputs(inputs_path)
        FORMAL = paths['formal_report'].parent
        current_review = source_review.check(paths['current_source_review'], inputs['candidate'], root=ROOT)
        manifest = common.read(paths['current_manifest'])
        audit.validate_manifest(manifest)
        common.require(manifest['candidate'] == inputs['candidate'], 'current manifest candidate differs')
        frozen, checkers = source.capture(ROOT), audit.snapshot()
        common.require(frozen['snapshot_sha256'] == current_review['source_snapshot_sha256'],
                       'current source review differs from observation source')
        recorder.write(OUT / 'source-before.json', frozen)
        recorder.write(OUT / 'checker-before.json', checkers)
        producer = common.read(paths['formal_report'])
        common.require(producer.get('kind') == 'formal-execution-with-output-delta-v1' and
                       producer.get('status') == 'formal_execution_and_delta_recorded_pending_worktree_review' and
                       producer.get('errors') == [] and
                       producer.get('source_snapshot_sha256') == frozen['snapshot_sha256'],
                       'failed/stale formal observation anchor')
        for name, identity in producer['record_files'].items():
            common.linked(FORMAL, name, identity)
        policy = common.read(proof.POLICY)
        common.require(proof.local_sources() == policy['local_sources'], 'formal source policy differs')
        generated = proof.generated_evidence(policy)
        recorder.write(OUT / 'generated-identities-before.json', generated)
        for row in manifest['evidence'].values():
            if row is not None: common.linked(ROOT, row['path'], row['sha256'])
        runtime = ROOT / manifest['evidence']['runtime']['path']
        rust_tests = ROOT / manifest['evidence']['rust_tests']['path']
        native = runtime.parent.parent
        common.require(native == rust_tests.parent.parent and native.parent == OUT.parent,
                       'accepted native reports do not share a direct producer root')
        runtime_commands = common.read(runtime)['stages']
        common.require(any(row['argv'] and str(native / 'runtime/cargo-target') + '/' in row['argv'][0]
                           for row in runtime_commands), 'actual native executable scope missing')
        old = common.read(FORMAL / 'after/snapshot.json')
        inventory.validate(old)
        earlier, now = common.read(FORMAL / 'evidence-parent-after.json'), parents()
        common.require(set(earlier) <= set(now), 'historical evidence sibling disappeared')
        new_names = sorted(set(now) - set(earlier) - {OUT.name})
        old_extra = [r for r in old['roots'] if r not in inventory.CANONICAL_ROOTS]
        formal_name = FORMAL.relative_to(ROOT).as_posix()
        extras = [r for r in old_extra if not r.startswith(formal_name + '/')]
        extras += [formal_name, native.relative_to(ROOT).as_posix()]
        extras += [(OUT.parent / n).relative_to(ROOT).as_posix() for n in new_names]
        selected = inventory.roots(extras)
        scope = {'schema_version': 1, 'kind': 'current-output-scope-observation-not-delivery-approval',
            'formal_report': ref(FORMAL / 'report.json'), 'formal_after': ref(FORMAL / 'after/snapshot.json'),
            'current_source_record': ref(paths['current_source_review']),
            'current_manifest': ref(paths['current_manifest']),
            'historical_roots': old['roots'], 'observed_roots': selected,
            'actual_native_root': native.relative_to(ROOT).as_posix(),
            'new_evidence_children_since_formal': new_names,
            'unobserved_preexisting_evidence_children': [n for n in earlier
                if not any((OUT.parent / n).relative_to(ROOT).as_posix() == r for r in selected)],
            'artifacts_top_level_names_only': sorted(os.listdir(ROOT / 'artifacts')),
            'recording_directory_excluded_from_its_own_inventory': OUT.relative_to(ROOT).as_posix(),
            'additional_roots_have_no_invented_historical_baseline': True,
            'whole_workspace_coverage_claimed': False, 'final_delivery_scope_approved': False}
        common.require(set(old['roots']) <= set(selected) and formal_name in selected and
                       native.relative_to(ROOT).as_posix() in selected,
                       'observed scope changed; inspect before scanning')
        recorder.write(OUT / 'scope.json', scope)
        recorder.write(OUT / 'evidence-parent-before.json', now)
        for mode, options in [('ordinary', []), ('optimized', ['-O'])]:
            stage('inventory-tests-' + mode, ['/usr/bin/python3', '-B', *options, '-m', 'unittest',
                                              'scripts.tests.test_generated_output_inventory'])
            stage('projection-tests-' + mode, ['/usr/bin/python3', '-B', *options, str(OUT / 'test_projection.py')])
        argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                '--out', str(OUT / 'current')]
        for name in extras: argv.extend(['--extra-root', name])
        stage('inventory-current', argv, 7200)
        observed = common.read(OUT / 'current/snapshot.json')
        common.require(observed['roots'] == selected, 'captured output scope differs')
        projected = project(observed, old['roots'])
        recorder.write(OUT / 'current-formal-scope.json', projected)
        stage('compare-formal-to-current', ['/usr/bin/python3', '-B', '-O',
            'scripts/generated_output_inventory.py', 'compare', '--before', str(FORMAL / 'after/snapshot.json'),
            '--after', str(OUT / 'current-formal-scope.json'), '--out', str(OUT / 'formal-to-current')])
        delta = common.read(OUT / 'formal-to-current/delta.json')
        common.require(common.same(delta, inventory.compare(old, projected)) and delta['changes'] == {},
                       'historical formal outputs changed')
        remaining = {n: row for n, row in observed['entries'].items() if n not in projected['entries']}
        recorder.write(OUT / 'additional-observed-nodes.json', {
            'schema_version': 1, 'scope': 'current nodes outside historical formal-root comparison; not a historical delta',
            'observed_snapshot_sha256': observed['snapshot_sha256'], 'entries': remaining,
            'historical_absence_claimed': False, 'generated_outputs_audited': False})
        current = source.capture(ROOT)
        recorder.write(OUT / 'source-after.json', current)
        recorder.write(OUT / 'checker-after.json', audit.snapshot())
        recorder.write(OUT / 'evidence-parent-after.json', parents())
        recorder.write(OUT / 'generated-identities-after.json', proof.generated_evidence(policy))
        common.require(current == frozen and audit.snapshot() == checkers, 'source/checker drift during observation')
        common.require(parents() == now, 'evidence siblings changed during observation')
        common.require(proof.generated_evidence(policy) == generated, 'formal generated identities drift during observation')
        common.linked(ROOT, inputs['formal_report']['path'], inputs['formal_report']['sha256'])
        common.linked(ROOT, inputs['current_source_review']['path'], inputs['current_source_review']['sha256'])
        common.linked(ROOT, inputs['current_manifest']['path'], inputs['current_manifest']['sha256'])
        report.update(status='current_output_observation_and_complete_formal_delta_recorded_pending_review',
            source_snapshot_sha256=frozen['snapshot_sha256'], observed_summary=inventory.summary(observed),
            historical_scope_summary=inventory.summary(projected), scope=ref(OUT / 'scope.json'),
            current_inventory=ref(OUT / 'current/snapshot.json'), formal_delta=ref(OUT / 'formal-to-current/delta.json'),
            changed_historical_nodes=len(delta['changes']),
            change_operations=dict(Counter(row['operation'] for row in delta['changes'].values())),
            additional_observed_nodes=len(remaining), non_atomic_observation_only=True)
    except Exception as error:
        report['status'] = 'failed'
        report['errors'].append({'error_type': type(error).__name__, 'error': str(error)})
    report['finished_at'] = recorder.now()
    report['record_files'] = {p.relative_to(OUT).as_posix(): common.sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    recorder.write(OUT / 'report.json', report)
    print({'status': report['status'], 'errors': report['errors']}, flush=True)
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        sys.exit(main(args.out, args.inputs))
    except (Exception, KeyboardInterrupt) as error:
        print('week6 output observation rejected: ' + str(error), file=sys.stderr)
        sys.exit(1)
