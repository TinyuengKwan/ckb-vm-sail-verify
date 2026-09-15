"""Partial worktree evidence envelope; no path here closes release acceptance."""
import copy
from pathlib import Path

import release_evidence as common
import release_generation_review as generation
import release_worktree_source as source
import release_source_increment_review as increment
import release_current_output_review as output

FLAGS = source.BOUNDARIES | {'kernel_executed', 'current_outputs_verified'}
FORMAL_SCOPE = 'historical_formal_execution_and_complete_delta_review_bindings_only'
EXECUTION_LINKAGE = 'final_generation_kernel_and_rocq_linkage'
APPROVAL_STATEMENT = ('Approve delivery profile A and the exact reviewed source/output differences for candidate '
                      'packaging; do not expand proof coverage, approve historical profile B archives, or claim '
                      'clean-room, CI, third-party, release, or Week6 completion.')
APPROVAL_BOUNDARIES = {'proof_scope_expanded', 'historical_profile_b_approved', 'clean_room_claimed',
                       'ci_claimed', 'third_party_claimed', 'release_claimed', 'week6_closed'}


def check_approval(path, candidate, snapshot_sha256, source_review, output_identity):
    path = Path(path)
    initial = common.sha(path)
    report = common.read(path)
    source.fields(report, {'schema_version', 'kind', 'candidate', 'source_snapshot_sha256', 'source_review',
                           'output_identity',
                           'delivery_profile', 'approved_by', 'approval_statement', 'approved_at', 'boundaries'},
                  'worktree delivery approval')
    common.require(common.same(report['schema_version'], 1) and
                   report['kind'] == 'worktree-delivery-approval-v1' and report['candidate'] == candidate and
                   report['source_snapshot_sha256'] == snapshot_sha256 and report['source_review'] == source_review and
                   report['output_identity'] == output_identity and
                   report['delivery_profile'] == 'A' and report['approval_statement'] == APPROVAL_STATEMENT,
                   'worktree delivery approval identity/scope differs')
    source.fields(report['approved_by'], {'name', 'role', 'channel'}, 'worktree approver')
    source.text(report['approved_by']['name'], 'worktree approver name')
    common.require(report['approved_by']['name'] != 'Codex' and
                   report['approved_by']['role'] in ['repository_owner', 'release_maintainer'] and
                   report['approved_by']['channel'] == 'explicit_user_instruction',
                   'worktree approval lacks independent user authority')
    source.text(report['approved_at'], 'worktree approval timestamp')
    source.fields(report['boundaries'], APPROVAL_BOUNDARIES, 'worktree approval boundary')
    common.require(all(value is False for value in report['boundaries'].values()),
                   'worktree approval broadened an excluded assurance')
    common.require(common.sha(path) == initial, 'worktree approval changed during validation')
    return {'scope': 'explicit_profile_A_delivery_and_reviewed_difference_approval',
            'delivery_profile': 'A', 'approved_by': report['approved_by'],
            'source_snapshot_sha256': snapshot_sha256,
            'approved_output_identity': copy.deepcopy(output_identity), 'proof_scope_expanded': False,
            'historical_profile_b_approved': False, 'release_claimed': False, 'week6_closed': False}


def connect_formal_execution(details, checks, root=None):
    """Join independently accepted aggregate reports to validated formal records.

    Called only with results produced by the in-process checkers, never a report
    supplied as a substitute for those checks. Missing/failed formal components
    leave linkage pending; unrelated accepted reports are an invalid join.
    This removes only execution linkage, not source/output/delivery obligations.
    """
    root = common.ROOT if root is None else Path(root)
    result = copy.deepcopy(details)
    component = result.get('components', {}).get('generation', {})
    if component.get('scope') != FORMAL_SCOPE:
        return result
    common.require(component.get('recorded_main_rocq_generated_identity_matches') is True,
                   'formal generation identity match not verified')
    reports = component['formal_reports']
    source.fields(reports, {'lean', 'rocq'}, 'formal report linkage inventory')
    remaining = result['remaining']
    common.require(type(remaining) is list and remaining.count(EXECUTION_LINKAGE) == 1,
                   'execution linkage obligation absent or duplicated before join')
    refs = generation.References()
    pending = []
    for name in ['lean', 'rocq']:
        expected = reports[name]
        source.fields(expected, {'path', 'sha256'}, 'formal report linkage reference')
        refs.link(root, expected['path'], expected['sha256'])
        checked = checks.get(name, {})
        if checked.get('status') != 'verified_existing_evidence':
            pending.append(name)
            continue
        source.fields(checked['reference'], {'path', 'sha256'}, 'accepted formal reference')
        common.require(common.same(checked['reference'], expected),
                       'worktree formal execution linked to a different accepted ' + name + ' report')
    refs.recheck()
    result['formal_execution_linkage'] = {
        'status': 'pending' if pending else 'verified_existing_evidence_linkage',
        'reports': reports, 'missing_verified_components': pending,
        'fresh_execution_claimed': False, 'current_outputs_verified': False,
        'candidate_approval_claimed': False}
    if not pending:
        result['remaining'] = [item for item in remaining if item != EXECUTION_LINKAGE]
    if result.get('delivery_approval_verified') is True and result['remaining'] == []:
        result.update(scope='complete_current_source_output_and_delivery_scope_review',
                      candidate_identity_approved=True, candidate_approval_claimed=True,
                      current_outputs_verified=True, generated_outputs_audited=True,
                      worktree_audit_closed=True)
    return result


def check(path, candidate, root=None):
    root = common.ROOT if root is None else Path(root)
    path = Path(path)
    initial = common.sha(path)
    report = common.read(path)
    if type(report) is dict and report.get('kind') == 'worktree-source-review-v1':
        return source.check(path, candidate, root=root)
    versions = {'worktree-record-review-v1': 1, 'worktree-record-review-v2': 2,
                'worktree-record-review-v3': 3, 'worktree-record-review-v4': 4}
    version = versions.get(report.get('kind')) if type(report) is dict else None
    extra = ({'source_increment'} if version in [2, 3, 4] else set()) | \
            ({'output_identity'} if version in [3, 4] else set()) | ({'approval'} if version == 4 else set())
    source.fields(report, {'schema_version', 'kind', 'candidate', 'source_review', 'generation', 'boundaries'} |
                  extra, 'worktree record envelope')
    common.require(version is not None and common.same(report['schema_version'], version),
                   'unknown worktree envelope')
    source.text(candidate, 'candidate')
    common.require(report['candidate'] == candidate, 'different worktree candidate')
    source.fields(report['boundaries'], FLAGS, 'worktree boundary')
    common.require(all(v is False for v in report['boundaries'].values()), 'worktree assurance upgrade')
    refs = generation.References()

    def reference(row):
        source.fields(row, {'path', 'sha256'}, 'worktree reference')
        return refs.link(root, row['path'], row['sha256'])

    common.require(report['source_review'] is not None or report['generation'] is not None,
                   'empty worktree envelope')
    components, remaining = {}, ['final_delivery_scope_and_semantic_approval',
                                 EXECUTION_LINKAGE,
                                 'current_generated_output_identity']
    if report['source_review'] is not None:
        components['source'] = source.check(reference(report['source_review']), candidate, root=root)
    else:
        remaining.append('current_complete_source_review')
    if report['generation'] is not None:
        source.fields(report['generation'], {'producer', 'review'}, 'generation references')
        components['generation'] = generation.check(reference(report['generation']['producer']),
                                                     reference(report['generation']['review']), root=root)
    else:
        remaining.append('recorded_generation_and_delta_review')
    same_source = (len(components) == 2 and components['source']['source_snapshot_sha256'] ==
                   components['generation']['source_snapshot_sha256'])
    if not same_source:
        remaining.append('post_generation_source_delta_review')
    if version in [2, 3, 4] and report['source_increment'] is not None:
        common.require('source' in components and 'generation' in components,
                       'source increment requires both validated endpoint components')
        components['source_increment'] = increment.check(reference(report['source_increment']), candidate,
            components['generation']['source_snapshot_sha256'], components['source']['source_snapshot_sha256'], root=root)
        remaining = [item for item in remaining if item != 'post_generation_source_delta_review']
    if version in [3, 4] and report['output_identity'] is not None:
        common.require('source' in components, 'current output identity requires validated current source')
        components['output_identity'] = output.check(report['output_identity'],
            components['source']['source_snapshot_sha256'], root=root)
        remaining = [item for item in remaining if item != 'current_generated_output_identity']
    delivery_approval_verified = False
    if version == 4:
        common.require(report['approval'] is not None and 'source' in components and
                       'output_identity' in components and report['source_review'] is not None,
                       'v4 delivery approval requires current source and output identity')
        components['approval'] = check_approval(reference(report['approval']), candidate,
                                                components['source']['source_snapshot_sha256'],
                                                report['source_review'], report['output_identity'])
        remaining = [item for item in remaining if item != 'final_delivery_scope_and_semantic_approval']
        delivery_approval_verified = True
    refs.recheck()
    if 'source' in components:
        common.require(source.source.capture(root)['snapshot_sha256'] ==
                       components['source']['source_snapshot_sha256'], 'source changed during envelope validation')
    common.require(common.sha(path) == initial, 'worktree envelope changed during validation')
    return {'scope': 'partial_source_and_historical_generation_review_records_only',
            'candidate': candidate, 'components': components, 'remaining': remaining,
            'source_snapshots_match': same_source, 'candidate_identity_approved': False,
            'delivery_approval_verified': delivery_approval_verified,
            'record_authorship_authenticated': False, 'fresh_execution_claimed': False,
            'worktree_audit_closed': False, **dict.fromkeys(FLAGS, False)}
