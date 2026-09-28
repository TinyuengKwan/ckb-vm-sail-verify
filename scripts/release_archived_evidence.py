"""Explicit post-CI acceptance of guest validation, never a local-check fallback.

The seven local results and preapproval worktree result must be bytes covered
by the current candidate's verified GitHub artifact attestation. VM execution
remains operator-attested, not platform-signed. No host toolchain or generated
output re-probe is claimed. Owner approval and release publication stay separate.
"""
import copy
from pathlib import Path

import release_evidence as common
import release_external_evidence as external
import release_worktree_evidence as worktree
import source_snapshot

BASIS = 'current_candidate_ci_attested_guest_validation'
OPEN = ['clean_room', 'ci_download', 'release_package', 'third_party', 'worktree_audit']
APPROVAL_PENDING = 'final_delivery_scope_and_semantic_approval'


def compose(root, guest_manifest, guest_report, ci_report, approval=None):
    """Compose a new manifest without rewriting the guest's evidence or approval."""
    root = Path(root).resolve()

    def ref(path):
        path = Path(path).absolute()
        common.require(path.is_relative_to(root), 'post-CI evidence outside checkout')
        name = path.relative_to(root).as_posix()
        checked = common.member(root, name)
        return {'path': name, 'sha256': common.sha(checked)}

    manifest_ref = ref(guest_manifest)
    value = common.read(root / manifest_ref['path'])
    common.require(common.same(value.get('schema_version'), 1), 'post-CI input must be guest manifest v1')
    value['schema_version'] = 2
    value['archived_guest'] = {'manifest': manifest_ref, 'report': ref(guest_report),
                               'approval': ref(approval) if approval is not None else None}
    value['evidence']['ci_download'] = ref(ci_report)
    return value


def check(manifest, root, current_inputs):
    # Runtime import avoids the audit/gate initialization cycle.
    import audit_release as audit
    import week6_release_ci_gate as ci_gate

    root = Path(root)
    require = common.require
    candidate = manifest['candidate']
    cfg = manifest['archived_guest']
    external.fields(cfg, {'manifest', 'report', 'approval'}, 'archived guest input')
    initial_source = source_snapshot.capture(root)
    require(initial_source['repositories']['.']['head'] == candidate and
            not initial_source['repositories']['.']['changes_from_head'],
            'archived acceptance requires an exact clean candidate')
    snapshot_sha = initial_source['snapshot_sha256']
    anchors = {}

    def reference(base, row):
        external.fields(row, {'path', 'sha256'}, 'archived evidence reference')
        path = common.linked(base, row['path'], row['sha256'])
        if path in anchors:
            require(anchors[path] == row['sha256'], 'conflicting archive reference')
        anchors[path] = row['sha256']
        return path

    def accepted(row, details, basis):
        return {'status': 'verified_existing_evidence', 'reference': copy.deepcopy(row),
                'details': copy.deepcopy(details), 'validation_basis': basis}

    rows = manifest['evidence']
    clean_path = reference(root, rows['clean_room'])
    ci_path = reference(root, rows['ci_download'])
    clean = external.check_clean_room(clean_path, candidate, root=root)
    require(clean['provider'] == external.VM_PROVIDER and clean['clean_room_verified'] is True,
            'archived acceptance requires independent VM clean-room evidence')
    provenance = external.check_vm_provenance(clean_path)
    require(provenance['operator_attested'] is True and provenance['platform_signed_identity'] is False,
            'archived VM provenance boundary differs')
    clean['host_provenance'] = provenance
    ci = external.check_ci_download(ci_path, candidate, root=root)
    require(ci['ci_download_verified'] is True and ci['remote_state_queried'] is True and
            clean['source_snapshot_sha256'] == ci['source_snapshot_sha256'] == snapshot_sha and
            ci['clean_room_report_sha256'] == common.sha(clean_path),
            'archived CI/VM/source identity differs')
    ci_record = common.read(ci_path)
    require(ci_record['provider']['head_sha'] == candidate, 'archived CI candidate differs')
    ci_clean = reference(ci_path.parent, ci_record['clean_room'])
    require(common.sha(ci_clean) == common.sha(clean_path), 'CI references another clean-room report')
    for name in ('upload_archive', 'download_archive', 'attestation'):
        reference(ci_path.parent, ci_record['artifact'][name])
    attested_manifest = reference(ci_path.parent, ci_record['artifact']['manifest'])
    attested = common.read(attested_manifest)
    require(attested['candidate'] == candidate and attested['source_snapshot_sha256'] == snapshot_sha,
            'attested artifact source differs')
    members = external.manifest_members(attested['members'], 'archived guest CI artifact')

    def attested_member(row):
        path = reference(root, row)
        require(members.get(row['path']) == {'sha256': row['sha256'], 'size': path.stat().st_size},
                'guest record absent/different in attested CI artifact: ' + row['path'])
        return path

    guest_manifest_path = attested_member(cfg['manifest'])
    guest_report_path = attested_member(cfg['report'])
    require(attested['clean_room_report'] == rows['clean_room']['path'], 'attested clean-room path differs')
    attested_member(rows['clean_room'])
    vm_row = {'path': (clean_path.parent / external.VM_RECORD).relative_to(root).as_posix(),
              'sha256': provenance['record_sha256']}
    attested_member(vm_row)
    guest_manifest = common.read(guest_manifest_path)
    require(common.same(guest_manifest.get('schema_version'), 1), 'guest cannot recursively accept archives')
    audit.validate_manifest(guest_manifest)
    require(guest_manifest['candidate'] == candidate and guest_manifest['pins'] == manifest['pins'],
            'guest manifest candidate/pins differ')
    require(guest_manifest['evidence']['clean_room'] == rows['clean_room'], 'guest clean-room reference differs')
    for name in ('ci_download', 'release_package', 'third_party'):
        require(guest_manifest['evidence'][name] is None, 'guest prepublication slot unexpectedly supplied')
    guest = common.read(guest_report_path)
    require(guest.get('candidate') == guest.get('project_head') == candidate and
            guest.get('inputs_before') == guest.get('inputs_after') == current_inputs,
            'guest checker/source identity differs')
    ci_gate.validate_archived_aggregate(root, guest_manifest_path, guest_report_path, OPEN, clean_path)

    checks = {}
    for name in [*audit.CHECKERS, 'worktree_audit']:
        require(rows[name] == guest_manifest['evidence'][name] == guest['checks'][name].get('reference'),
                'archived slot reference differs: ' + name)
        reference(root, rows[name])
        checks[name] = copy.deepcopy(guest['checks'][name])
        checks[name]['validation_basis'] = BASIS
    require(checks['public_claims']['details'].get('public_claims_slot_closed') is True and
            checks['public_claims']['details'].get('source_snapshot_sha256') == snapshot_sha,
            'guest public claims not bound to current source')

    # Guest v3 must have discharged every technical worktree obligation. Its
    # attested result is reused, not recomputed against absent guest installations.
    partial = checks['worktree_audit']
    details = partial['details']
    require(partial['status'] == 'incomplete' and details['remaining'] == [APPROVAL_PENDING] and
            details.get('source_snapshots_match') is True and
            details.get('delivery_approval_verified') is False and
            details.get('worktree_audit_closed') is False,
            'guest worktree has undischarged obligations or claims approval')
    components = details['components']
    require(set(components) == {'source', 'generation', 'output_identity'} and
            all(row.get('source_snapshot_sha256') == snapshot_sha for row in components.values()),
            'guest worktree source/output identity differs')
    formal = {name: rows[name] for name in ('lean', 'rocq')}
    linkage = details['formal_execution_linkage']
    require(linkage.get('status') == 'verified_existing_evidence_linkage' and
            linkage.get('reports') == formal and linkage.get('missing_verified_components') == [] and
            components['generation'].get('formal_reports') == formal and
            components['generation'].get('recorded_main_rocq_generated_identity_matches') is True and
            components['output_identity'].get('current_generated_output_identity_recorded') is True,
            'guest worktree formal/output linkage differs')
    envelope = common.read(reference(root, rows['worktree_audit']))
    external.fields(envelope, {'schema_version', 'kind', 'candidate', 'source_review', 'generation',
                              'source_increment', 'output_identity', 'boundaries'}, 'guest worktree envelope')
    require(common.same(envelope['schema_version'], 3) and envelope['kind'] == 'worktree-record-review-v3' and
            envelope['candidate'] == candidate and envelope['source_increment'] is None and
            set(envelope['boundaries']) == worktree.FLAGS and
            all(value is False for value in envelope['boundaries'].values()), 'guest worktree envelope differs')
    reference(root, envelope['source_review'])
    external.fields(envelope['generation'], {'producer', 'review'}, 'guest generation')
    for row in envelope['generation'].values():
        reference(root, row)
    external.fields(envelope['output_identity'],
                    {'observation', 'registry_review', 'build_review', 'record_review', 'confirmation'},
                    'guest output identity')
    for row in envelope['output_identity'].values():
        reference(root, row)

    if cfg['approval'] is not None:
        approval = worktree.check_approval(reference(root, cfg['approval']), candidate, snapshot_sha,
                                          envelope['source_review'], envelope['output_identity'])
        details['components']['approval'] = approval
        details.update(remaining=[], delivery_approval_verified=True, candidate_identity_approved=True,
                       candidate_approval_claimed=True, current_outputs_verified=True,
                       generated_outputs_audited=True, worktree_audit_closed=True,
                       scope='ci_attested_guest_review_with_explicit_current_delivery_approval')
        partial['status'] = 'verified_existing_evidence'
        partial.pop('reason', None)
        partial['approval_reference'] = copy.deepcopy(cfg['approval'])
    else:
        partial['reason'] = 'Guest technical review accepted; exact source/output delivery approval absent.'
    checks['clean_room'] = accepted(rows['clean_room'], clean, 'host_vm_provenance_revalidated')
    checks['ci_download'] = accepted(rows['ci_download'], ci, 'external_download_and_attestation_revalidated')
    for path, digest in anchors.items():
        checked = common.member(root, path.relative_to(root).as_posix())
        require(common.sha(checked) == digest,
                'archived evidence changed during validation')
    require(source_snapshot.capture(root) == initial_source, 'source changed during archived validation')
    return checks
