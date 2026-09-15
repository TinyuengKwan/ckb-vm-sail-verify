"""Validate complete recorded output identity and a later exact rescan.

This composes a 24-root observation with three disjoint reviews of all nodes
outside the historical formal scope. A later full capture must be byte-for-byte
identical to that observation and must name the current source snapshot.
Neither classification records nor a non-atomic capture prove output semantics,
compiler correctness, clean-room execution, delivery approval or authorship.
"""
from collections import Counter
from pathlib import Path

import generated_output_inventory as inventory
import release_generation_review as base
import release_evidence as common
import release_worktree_source as source

OBSERVATION_FLAGS = {'release_claimed', 'week6_closed', 'worktree_audit_closed',
    'candidate_approval_claimed', 'fresh_kernel_run_claimed', 'regeneration_execution_proven',
    'clean_room_claimed', 'third_party_claimed', 'generated_outputs_audited',
    'whole_workspace_coverage_claimed', 'current_output_acceptance_closed',
    'atomic_filesystem_snapshot_claimed'}
REVIEW_FALSE_FLAGS = {'semantic_correctness_proven', 'record_authorship_authenticated',
    'generated_outputs_audited', 'worktree_audit_closed', 'candidate_approval_claimed',
    'release_claimed', 'week6_closed', 'whole_workspace_coverage_claimed'}
CONFIRMATION_FLAGS = {'release_claimed', 'week6_closed', 'worktree_audit_closed',
    'candidate_approval_claimed', 'fresh_execution_claimed', 'generated_outputs_audited',
    'whole_workspace_coverage_claimed', 'atomic_filesystem_snapshot_claimed'}
SCOPE_FIELDS = {'schema_version', 'kind', 'formal_report', 'formal_after', 'current_source_record',
    'current_manifest', 'historical_roots', 'observed_roots', 'actual_native_root',
    'new_evidence_children_since_formal', 'unobserved_preexisting_evidence_children',
    'artifacts_top_level_names_only', 'recording_directory_excluded_from_its_own_inventory',
    'additional_roots_have_no_invented_historical_baseline', 'whole_workspace_coverage_claimed',
    'final_delivery_scope_approved'}


def reference(refs, root, row, label):
    source.fields(row, {'path', 'sha256'}, label)
    return refs.link(root, row['path'], row['sha256'])


def record_files(refs, directory, report):
    common.require(type(report.get('record_files')) is dict and report['record_files'],
                   'missing sealed record file inventory')
    result = {}
    for name, digest in report['record_files'].items():
        result[name] = refs.link(directory, name, digest)
    return result


def false_flags(row, names, label):
    common.require(all(name in row and row[name] is False for name in names), label + ' assurance upgrade')


def review_rows(review, field, additional, label):
    rows = review[field]
    common.require(type(rows) is dict, 'invalid ' + label + ' row inventory')
    counts = Counter()
    for name, row in rows.items():
        inventory.safe(name)
        source.fields(row, {'node_sha256', 'category', 'evidence',
                            'semantic_correctness_proven', 'delivery_approved'}, label + ' row')
        common.require(name in additional and row['node_sha256'] == inventory.digest(additional[name]),
                       label + ' row points to another observed node')
        common.require(type(row['category']) is str and row['category'] and
                       row['semantic_correctness_proven'] is False and row['delivery_approved'] is False,
                       label + ' row assurance/category differs')
        counts[row['category']] += 1
    common.require(dict(counts) == review['category_counts'], label + ' category counters differ')
    return rows


def check(component, expected_source_snapshot, root=None):
    root = (common.ROOT if root is None else Path(root)).absolute()
    source.fields(component, {'observation', 'registry_review', 'build_review',
                              'record_review', 'confirmation'}, 'current output component')
    refs = base.References()
    paths = {name: reference(refs, root, row, 'current output ' + name + ' reference')
             for name, row in component.items()}

    observation_sha = common.sha(paths['observation'])
    observation = common.read(paths['observation'])
    source.fields(observation, {'schema_version', 'kind', 'status', 'started_at', 'stages', 'errors',
        'source_snapshot_sha256', 'observed_summary', 'historical_scope_summary', 'scope',
        'current_inventory', 'formal_delta', 'changed_historical_nodes', 'change_operations',
        'additional_observed_nodes', 'non_atomic_observation_only', 'finished_at', 'record_files',
        *OBSERVATION_FLAGS}, 'output observation report')
    common.require(common.same(observation['schema_version'], 1) and
                   observation['kind'] == 'current-expanded-output-observation-v1' and
                   observation['status'] == 'current_output_observation_and_complete_formal_delta_recorded_pending_review' and
                   observation['errors'] == [] and observation['non_atomic_observation_only'] is True,
                   'output observation incomplete/unknown')
    false_flags(observation, OBSERVATION_FLAGS, 'output observation')
    observation_files = record_files(refs, paths['observation'].parent, observation)
    scope_path = reference(refs, root, observation['scope'], 'output scope reference')
    current_path = reference(refs, root, observation['current_inventory'], 'current inventory reference')
    delta_path = reference(refs, root, observation['formal_delta'], 'formal delta reference')
    common.require(scope_path == observation_files['scope.json'] and
                   current_path == observation_files['current/snapshot.json'] and
                   delta_path == observation_files['formal-to-current/delta.json'],
                   'observation top-level/member reference differs')
    scope = common.read(scope_path)
    source.fields(scope, SCOPE_FIELDS, 'output observation scope')
    common.require(common.same(scope['schema_version'], 1) and
                   scope['kind'] == 'current-output-scope-observation-not-delivery-approval' and
                   scope['additional_roots_have_no_invented_historical_baseline'] is True and
                   scope['whole_workspace_coverage_claimed'] is False and
                   scope['final_delivery_scope_approved'] is False,
                   'output observation scope assurance/schema differs')
    current = common.read(current_path)
    projected = common.read(observation_files['current-formal-scope.json'])
    formal_after = common.read(reference(refs, root, scope['formal_after'], 'formal after reference'))
    for value in [current, projected, formal_after]: inventory.validate(value)
    common.require(scope['observed_roots'] == current['roots'] and scope['historical_roots'] == formal_after['roots'] == projected['roots'],
                   'observed/historical root scope differs')
    delta = common.read(delta_path)
    common.require(common.same(inventory.compare(formal_after, projected), delta) and delta['changes'] == {} and
                   observation['changed_historical_nodes'] == 0 and observation['change_operations'] == {},
                   'historical output identity changed')
    common.require(observation['observed_summary'] == inventory.summary(current) and
                   observation['historical_scope_summary'] == inventory.summary(projected),
                   'observation summary differs')
    additional_path = observation_files['additional-observed-nodes.json']
    additional_record = common.read(additional_path)
    source.fields(additional_record, {'schema_version', 'scope', 'observed_snapshot_sha256', 'entries',
                                      'historical_absence_claimed', 'generated_outputs_audited'},
                  'additional observed nodes')
    additional = additional_record['entries']
    common.require(common.same(additional_record['schema_version'], 1) and
                   additional_record['observed_snapshot_sha256'] == current['snapshot_sha256'] and
                   additional_record['historical_absence_claimed'] is False and
                   additional_record['generated_outputs_audited'] is False and
                   set(additional) == set(current['entries']) - set(projected['entries']) and
                   all(common.same(node, current['entries'][name]) for name,node in additional.items()) and
                   observation['additional_observed_nodes'] == len(additional),
                   'additional-node projection differs')

    reviews = {}
    specs = [('registry_review', 'partial_additional_registry_review_checked_other_nodes_pending',
              'partial-additional-cargo-registry-review-v1', 'reviewed_nodes'),
             ('build_review', 'additional_build_and_directory_records_checked_other_files_pending',
              'partial-additional-build-and-directory-review-v1', 'new_reviewed_nodes'),
             ('record_review', 'all_additional_observed_nodes_record_reviewed_with_non_semantic_boundaries',
              'additional-record-and-cache-review-v1', 'new_reviewed_nodes')]
    for name, report_status, review_kind, field in specs:
        report = common.read(paths[name])
        common.require(report.get('status') == report_status and report.get('errors') == [] and
                       report.get('source_snapshot_sha256') == observation['source_snapshot_sha256'],
                       name + ' report incomplete or bound to another source')
        false_flags(report, REVIEW_FALSE_FLAGS, name + ' report')
        members = record_files(refs, paths[name].parent, report)
        review_path = reference(refs, root, report['review'], name + ' review reference')
        common.require(review_path == members['review.json'], name + ' report/member review differs')
        review = common.read(review_path)
        common.require(review.get('kind') == review_kind and
                       review.get('source_snapshot_sha256') == observation['source_snapshot_sha256'],
                       name + ' review kind/source differs')
        false_flags(review, REVIEW_FALSE_FLAGS, name + ' review')
        reviews[name] = (review, review_rows(review, field, additional, name))
    registry, registry_rows = reviews['registry_review']
    build, build_rows = reviews['build_review']
    records, record_rows = reviews['record_review']
    sets = [set(registry_rows), set(build_rows), set(record_rows)]
    common.require(not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2]) and
                   set().union(*sets) == set(additional) and
                   set(registry['remaining_unreviewed_nodes']) == sets[1] | sets[2] and
                   set(build['remaining_unreviewed_nodes']) == sets[2] and
                   records['remaining_unreviewed_nodes'] == {} and
                   build['prior_reviewed_nodes'] == len(sets[0]) and
                   records['prior_reviewed_nodes'] == len(sets[0]) + len(sets[1]),
                   'additional review partition/chain differs')

    confirmation = common.read(paths['confirmation'])
    source.fields(confirmation, {'schema_version', 'kind', 'status', 'started_at', 'finished_at',
        'stages', 'errors', 'source_snapshot_sha256', 'observation_report_sha256',
        'observed_snapshot_sha256', 'snapshot', 'record_files', *CONFIRMATION_FLAGS},
        'current output confirmation')
    common.require(common.same(confirmation['schema_version'], 1) and
                   confirmation['kind'] == 'current-output-exact-rescan-confirmation-v1' and
                   confirmation['status'] == 'current_24_root_snapshot_exactly_matches_reviewed_observation' and
                   confirmation['errors'] == [] and confirmation['source_snapshot_sha256'] == expected_source_snapshot and
                   confirmation['observation_report_sha256'] == observation_sha and
                   confirmation['observed_snapshot_sha256'] == current['snapshot_sha256'],
                   'current output confirmation incomplete/wrong source or observation')
    false_flags(confirmation, CONFIRMATION_FLAGS, 'current output confirmation')
    confirmation_files = record_files(refs, paths['confirmation'].parent, confirmation)
    snapshot_path = reference(refs, root, confirmation['snapshot'], 'confirmed snapshot reference')
    common.require(snapshot_path == confirmation_files['current/snapshot.json'] and
                   common.sha(snapshot_path) == common.sha(current_path),
                   'current rescan bytes differ from reviewed observation')
    rescanned = common.read(snapshot_path)
    inventory.validate(rescanned)
    common.require(common.same(rescanned, current), 'current rescan content differs from reviewed observation')
    common.require(type(confirmation['stages']) is list and len(confirmation['stages']) == 1,
                   'current rescan stage inventory differs')
    extras = [name for name in current['roots'] if name not in inventory.CANONICAL_ROOTS]
    argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
            '--out', str(paths['confirmation'].parent / 'current')]
    for name in extras: argv.extend(['--extra-root', name])
    read = lambda name: common.read(confirmation_files[name])
    stage = base.command_record(read, refs, paths['confirmation'].parent, 'capture-current', argv, str(root))
    common.require(confirmation['stages'] == [stage] and
                   base.moment(confirmation['started_at']) <= base.moment(stage['started_at']) <=
                   base.moment(stage['finished_at']) <= base.moment(confirmation['finished_at']),
                   'current rescan stage/report chronology differs')
    refs.recheck()
    return {'scope': 'complete_observed_output_identity_partition_with_exact_later_rescan',
            'source_snapshot_sha256': expected_source_snapshot,
            'current_snapshot_sha256': current['snapshot_sha256'],
            'observed_nodes': len(current['entries']), 'historical_nodes': len(projected['entries']),
            'additional_nodes': len(additional), 'reviewed_additional_nodes': sum(map(len, sets)),
            'changed_historical_nodes': 0, 'current_generated_output_identity_recorded': True,
            'non_atomic_observation_only': True, 'semantic_correctness_proven': False,
            'record_authorship_authenticated': False, 'generated_outputs_audited': False,
            'worktree_audit_closed': False, 'candidate_approval_claimed': False,
            'release_claimed': False, 'week6_closed': False, 'whole_workspace_coverage_claimed': False,
            'fresh_execution_claimed': False, 'dependency_closure_proven': False}
