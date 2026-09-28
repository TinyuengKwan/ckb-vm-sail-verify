"""Synthetic fixtures only; real external trust validators have separate tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as audit
import release_archived_evidence as archive
import release_evidence as common


class ArchivedAcceptanceTests(unittest.TestCase):
    def patch(self, manager):
        self.addCleanup(manager.stop)
        return manager.start()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return {'path': name, 'sha256': common.sha(path)}

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='archive-acceptance-fixture-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate = 'a' * 40
        self.snapshot = 'b' * 64
        self.source = {'snapshot_sha256': self.snapshot,
                       'repositories': {'.': {'head': self.candidate, 'changes_from_head': {}}}}
        self.inputs = {'fixture_only_checker_identity': 'c' * 64}
        self.patch(patch.object(audit, 'ROOT', self.root))
        self.patch(patch.object(audit, 'snapshot', return_value=self.inputs))
        self.patch(patch.object(archive.source_snapshot, 'capture', return_value=self.source))
        for path in audit.PINS.values():
            self.write(path, {'fixture_only': path})
        pins = {key: common.sha(self.root / path) for key, path in audit.PINS.items()}
        rows = dict.fromkeys(audit.SLOTS)
        checks = {}
        for name in audit.CHECKERS:
            rows[name] = self.write('local/' + name + '.json', {'fixture_only': name})
            checks[name] = {'status': 'verified_existing_evidence', 'reference': rows[name],
                            'details': {'fixture_only': True}}
        checks['public_claims']['details'] = {'public_claims_slot_closed': True,
                                             'source_snapshot_sha256': self.snapshot}
        self.envelope = {'schema_version': 3, 'kind': 'worktree-record-review-v3',
            'candidate': self.candidate, 'source_increment': None,
            'source_review': self.write('worktree/source.json', {'fixture_only': 'source'}),
            'generation': {name: self.write('worktree/' + name + '.json', {'fixture_only': name})
                           for name in ('producer', 'review')},
            'output_identity': {name: self.write('output/' + name + '.json', {'fixture_only': name})
                                for name in ('observation', 'registry_review', 'build_review', 'record_review', 'confirmation')},
            'boundaries': dict.fromkeys(archive.worktree.FLAGS, False)}
        rows['worktree_audit'] = self.write('worktree/envelope.json', self.envelope)
        formal = {name: rows[name] for name in ('lean', 'rocq')}
        details = {'remaining': [archive.APPROVAL_PENDING], 'source_snapshots_match': True,
            'delivery_approval_verified': False, 'worktree_audit_closed': False,
            'components': {name: {'source_snapshot_sha256': self.snapshot}
                           for name in ('source', 'generation', 'output_identity')},
            'formal_execution_linkage': {'status': 'verified_existing_evidence_linkage',
                                        'reports': formal, 'missing_verified_components': []}}
        details['components']['generation'].update(formal_reports=formal,
            recorded_main_rocq_generated_identity_matches=True)
        details['components']['output_identity']['current_generated_output_identity_recorded'] = True
        checks['worktree_audit'] = {'status': 'incomplete', 'reference': rows['worktree_audit'],
                                  'details': details}
        rows['clean_room'] = self.write('clean/report.json', {'fixture_only': 'clean'})
        self.vm_ref = self.write('clean/vm-provenance.json', {'fixture_only': 'vm'})
        self.provenance = {'record_sha256': self.vm_ref['sha256'], 'operator_attested': True,
                           'platform_signed_identity': False}
        self.vm_check = self.patch(patch.object(archive.external, 'check_vm_provenance', return_value=self.provenance))
        self.clean_result = {'provider': archive.external.VM_PROVIDER, 'clean_room_verified': True,
                             'fresh_execution_claimed': True, 'source_snapshot_sha256': self.snapshot}
        self.clean_check = self.patch(patch.object(archive.external, 'check_clean_room', return_value=self.clean_result))
        checks.update(clean_room={'status': 'incomplete', 'reference': rows['clean_room'],
                                   'reason': 'independent ephemeral VM host provenance record absent'},
                      ci_download={'status': 'missing'}, release_package={'status': 'missing'},
                      third_party=audit.delivery.third_party_deferred())
        self.guest_manifest = {'schema_version': 1, 'candidate': self.candidate, 'pins': pins, 'evidence': rows}
        self.guest = {'status': 'incomplete', 'candidate': self.candidate, 'project_head': self.candidate,
            'inputs_before': self.inputs, 'inputs_after': self.inputs,
            'release_claimed': False, 'week6_closed': False, 'fresh_execution_claimed': False,
            'outstanding': archive.OPEN, 'checks': checks, **audit.delivery.boundary(checks)}
        self.ci_record = {'provider': {'head_sha': self.candidate}, 'clean_room': rows['clean_room'],
            'artifact': {name: self.write('ci-' + name + '.json', {'fixture_only': name})
                         for name in ('upload_archive', 'download_archive', 'attestation')}}
        self.ci_result = {'ci_download_verified': True, 'remote_state_queried': True,
            'source_snapshot_sha256': self.snapshot, 'clean_room_report_sha256': rows['clean_room']['sha256']}
        self.ci_check = self.patch(patch.object(archive.external, 'check_ci_download', return_value=self.ci_result))
        self.manifest = copy.deepcopy(self.guest_manifest)
        self.manifest.update(schema_version=2, archived_guest={'approval': None})
        self.refresh()

    def refresh(self):
        """Synthetic re-signing for tests of semantically invalid attested data."""
        manifest_ref = self.write('clean/audit/manifest.json', self.guest_manifest)
        self.guest['manifest_sha256'] = manifest_ref['sha256']
        report_ref = self.write('clean/audit/result/report.json', self.guest)
        self.manifest['archived_guest'].update(manifest=manifest_ref, report=report_ref)
        refs = [manifest_ref, report_ref, self.guest_manifest['evidence']['clean_room'], self.vm_ref]
        self.attested = {'candidate': self.candidate, 'source_snapshot_sha256': self.snapshot,
            'clean_room_report': 'clean/report.json',
            'members': [{**row, 'size': (self.root / row['path']).stat().st_size} for row in refs]}
        self.refresh_ci()

    def refresh_ci(self):
        self.ci_record['artifact']['manifest'] = self.write('ci-manifest.json', self.attested)
        self.manifest['evidence']['ci_download'] = self.write('ci-report.json', self.ci_record)

    def aggregate(self):
        return audit.aggregate(self.manifest)

    def test_valid_archive_does_not_probe_host_and_keeps_approval_and_package_open(self):
        with patch.dict(audit.CHECKERS, {name: lambda *a, **kw: self.fail('host reprobe') for name in audit.CHECKERS}):
            result, code = self.aggregate()
        self.assertEqual(code, 2)
        self.assertEqual(result['delivery_outstanding'], ['release_package', 'worktree_audit'])
        self.assertEqual(result['post_delivery'], ['third_party'])
        self.assertFalse(result['week6_closed'])
        self.assertEqual(result['checks']['lean']['validation_basis'], archive.BASIS)
        self.ci_check.assert_called_once()

    def approval(self):
        value = {'schema_version': 1, 'kind': 'worktree-delivery-approval-v1',
            'candidate': self.candidate, 'source_snapshot_sha256': self.snapshot,
            'source_review': self.envelope['source_review'], 'output_identity': self.envelope['output_identity'],
            'delivery_profile': 'A', 'approved_by': {'name': 'fixture-owner-not-real-approval',
                'role': 'repository_owner', 'channel': 'explicit_user_instruction'},
            'approval_statement': archive.worktree.APPROVAL_STATEMENT, 'approved_at': 'fixture-only',
            'boundaries': dict.fromkeys(archive.worktree.APPROVAL_BOUNDARIES, False)}
        return value

    def test_explicit_approval_closes_only_worktree_not_release(self):
        self.manifest['archived_guest']['approval'] = self.write('approval.json', self.approval())
        result, code = self.aggregate()
        self.assertEqual(code, 2)
        self.assertEqual(result['delivery_outstanding'], ['release_package'])
        self.assertTrue(result['checks']['worktree_audit']['details']['worktree_audit_closed'])
        self.assertFalse(result['release_claimed'])

    def test_invalid_approval_cases(self):
        for change in ('candidate', 'source_snapshot_sha256', 'source_review', 'output_identity', 'delivery_profile', 'approved_by'):
            with self.subTest(change=change):
                value = self.approval()
                value[change] = 'wrong'
                self.manifest['archived_guest']['approval'] = self.write('approval.json', value)
                with self.assertRaises((RuntimeError, TypeError)):
                    self.aggregate()

    def test_rejects_failed_attestation_without_local_fallback(self):
        self.ci_check.side_effect = RuntimeError('CI provenance attestation verification failed')
        with self.assertRaisesRegex(RuntimeError, 'attestation'):
            self.aggregate()

    def test_rejects_missing_host_provenance(self):
        self.vm_check.side_effect = archive.external.VmProvenanceAbsent('absent')
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_failed_clean_room(self):
        self.clean_check.side_effect = RuntimeError('clean-room failed')
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_wrong_source_or_ci_bindings(self):
        for key in ('source_snapshot_sha256', 'clean_room_report_sha256', 'ci_download_verified', 'remote_state_queried'):
            with self.subTest(key=key):
                previous = self.ci_result[key]
                self.ci_result[key] = 'wrong'
                with self.assertRaises(RuntimeError): self.aggregate()
                self.ci_result[key] = previous

    def test_rejects_uncommitted_candidate(self):
        self.source['repositories']['.']['changes_from_head'] = {'changed': {}}
        with self.assertRaisesRegex(RuntimeError, 'clean candidate'): self.aggregate()

    def test_rejects_current_head_drift(self):
        self.source['repositories']['.']['head'] = 'c' * 40
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_guest_candidate_or_checker_drift(self):
        for key in ('candidate', 'project_head', 'inputs_before', 'inputs_after'):
            with self.subTest(key=key):
                old = self.guest[key]
                self.guest[key] = 'wrong'
                self.refresh()
                with self.assertRaisesRegex(RuntimeError, 'checker/source'): self.aggregate()
                self.guest[key] = old

    def test_rejects_recursive_guest_manifest(self):
        self.guest_manifest['schema_version'] = 2
        self.refresh()
        with self.assertRaisesRegex(RuntimeError, 'recursively'): self.aggregate()

    def test_rejects_absent_or_changed_attested_members(self):
        original = copy.deepcopy(self.attested)
        for name in ('clean/audit/manifest.json', 'clean/audit/result/report.json', 'clean/report.json', 'clean/vm-provenance.json'):
            for operation in ('missing', 'hash', 'size'):
                with self.subTest(name=name, operation=operation):
                    self.attested = copy.deepcopy(original)
                    if operation == 'missing':
                        self.attested['members'] = [row for row in self.attested['members'] if row['path'] != name]
                    else:
                        row = next(row for row in self.attested['members'] if row['path'] == name)
                        row['sha256' if operation == 'hash' else 'size'] = 'f' * 64 if operation == 'hash' else 1
                    self.refresh_ci()
                    with self.assertRaisesRegex(RuntimeError, 'attested CI artifact'): self.aggregate()

    def test_rejects_local_slot_replacement(self):
        for name in [*audit.CHECKERS, 'worktree_audit']:
            with self.subTest(name=name):
                old = self.manifest['evidence'][name]
                self.manifest['evidence'][name] = self.write('replacement.json', {})
                with self.assertRaisesRegex(RuntimeError, 'slot reference'): self.aggregate()
                self.manifest['evidence'][name] = old

    def test_rejects_missing_or_tampered_local_report(self):
        path = self.root / self.manifest['evidence']['lean']['path']
        path.write_text('tampered')
        with self.assertRaises(RuntimeError): self.aggregate()
        path.unlink()
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_guest_failed_slot_even_when_attested(self):
        self.guest['checks']['lean']['status'] = 'invalid'
        self.refresh()
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_guest_worktree_remaining_obligation(self):
        self.guest['checks']['worktree_audit']['details']['remaining'].append('current_generated_output_identity')
        self.refresh()
        with self.assertRaisesRegex(RuntimeError, 'undischarged'): self.aggregate()

    def test_rejects_guest_worktree_approval_laundering(self):
        self.guest['checks']['worktree_audit']['details']['delivery_approval_verified'] = True
        self.refresh()
        with self.assertRaisesRegex(RuntimeError, 'claims approval'): self.aggregate()

    def test_rejects_guest_formal_or_output_linkage_drift(self):
        details = self.guest['checks']['worktree_audit']['details']
        details['formal_execution_linkage']['reports']['lean'] = {'path': 'other', 'sha256': 'a' * 64}
        self.refresh()
        with self.assertRaisesRegex(RuntimeError, 'linkage'): self.aggregate()

    def test_rejects_output_record_tampering(self):
        (self.root / self.envelope['output_identity']['confirmation']['path']).write_text('tampered')
        with self.assertRaises(RuntimeError): self.aggregate()

    def test_rejects_symlink_and_traversal(self):
        row = self.manifest['archived_guest']['report']
        path = self.root / row['path']
        target = self.root / 'target.json'
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'symlink'): self.aggregate()
        row['path'] = '../target.json'
        with self.assertRaisesRegex(RuntimeError, 'unsafe'): self.aggregate()

    def test_rejects_late_evidence_mutation(self):
        import week6_release_ci_gate as ci_gate
        original = ci_gate.validate_archived_aggregate
        def mutate(*args):
            result = original(*args)
            (self.root / 'ci-report.json').write_text('tampered after attestation validation')
            return result
        self.patch(patch.object(ci_gate, 'validate_archived_aggregate', side_effect=mutate))
        with self.assertRaisesRegex(RuntimeError, 'changed during'): self.aggregate()

    def test_rejects_late_source_mutation(self):
        changed = copy.deepcopy(self.source)
        changed['snapshot_sha256'] = 'c' * 64
        self.patch(patch.object(archive.source_snapshot, 'capture', side_effect=[self.source, self.source, changed]))
        with self.assertRaisesRegex(RuntimeError, 'source changed'): self.aggregate()

    def test_rejects_source_change_after_archive_check(self):
        changed = copy.deepcopy(self.source)
        changed['snapshot_sha256'] = 'c' * 64
        self.patch(patch.object(archive.source_snapshot, 'capture', side_effect=[self.source] * 3 + [changed]))
        with self.assertRaisesRegex(RuntimeError, 'source changed'): self.aggregate()

    def test_complete_delivery_still_requires_real_package_checker(self):
        self.manifest['archived_guest']['approval'] = self.write('approval.json', self.approval())
        self.manifest['evidence']['release_package'] = self.write('package.json', {'fixture_only': True})
        self.patch(patch.dict(audit.EXTERNAL_CHECKERS, {'release_package': lambda *a, **kw: {
            'release_package_built': True, 'publication_verified': True, 'download_verified': True,
            'external_assets_verified': True, 'remote_state_queried': True, 'delivery_profile': 'A',
            'source_snapshot_sha256': self.snapshot}}))
        result, code = self.aggregate()
        self.assertEqual(code, 0)
        self.assertTrue(result['week6_closed'])
        self.assertEqual(result['outstanding'], ['third_party'])
        self.assertFalse(result['third_party_reproduced'])

    def test_bad_package_is_not_hidden_by_valid_archive(self):
        self.manifest['evidence']['release_package'] = self.write('package.json', {'fixture_only': True})
        result, code = self.aggregate()
        self.assertEqual(code, 1)
        self.assertEqual(result['checks']['release_package']['status'], 'invalid')

    def test_supplied_bad_third_party_still_blocks(self):
        self.manifest['evidence']['third_party'] = self.write('third.json', {'fixture_only': True})
        result, code = self.aggregate()
        self.assertEqual(code, 1)
        self.assertEqual(result['checks']['third_party']['status'], 'invalid')

    def test_compose_preserves_guest_and_only_connects_current_ci(self):
        cfg = self.manifest['archived_guest']
        old_bytes = (self.root / cfg['manifest']['path']).read_bytes()
        composed = archive.compose(self.root, self.root / cfg['manifest']['path'],
            self.root / cfg['report']['path'], self.root / self.manifest['evidence']['ci_download']['path'])
        self.assertEqual(composed, self.manifest)
        self.assertEqual((self.root / cfg['manifest']['path']).read_bytes(), old_bytes)

    def test_cli_composes_and_records_incomplete_without_installations(self):
        cfg = self.manifest['archived_guest']
        out = self.root / 'cli-result'
        args = ['audit_release.py', '--manifest', str(self.root / cfg['manifest']['path']),
            '--guest-report', str(self.root / cfg['report']['path']),
            '--ci-report', str(self.root / self.manifest['evidence']['ci_download']['path']), '--out', str(out)]
        with patch.object(sys, 'argv', args), patch.object(audit.subprocess, 'check_output', return_value=self.candidate):
            self.assertEqual(audit.main(), 2)
        result = common.read(out / 'report.json')
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['delivery_outstanding'], ['release_package', 'worktree_audit'])
        self.assertEqual(result['manifest_sha256'], common.sha(out / 'manifest.json'))

    def test_manifest_v1_cannot_sneak_archive_input(self):
        self.manifest['schema_version'] = 1
        with self.assertRaisesRegex(RuntimeError, 'fields'): self.aggregate()

    def test_archive_input_cannot_omit_or_add_fields(self):
        self.manifest['archived_guest']['skip_checks'] = True
        with self.assertRaises(RuntimeError): self.aggregate()


if __name__ == '__main__':
    unittest.main()
