"""Partial envelope composition cannot turn record checks into release success."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_worktree_evidence as gate
import audit_release


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='worktree-envelope-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'envelope.json'
        self.refs = {}
        for name in ['source', 'producer', 'review']:
            file = self.root / (name + '.json')
            file.write_text('{}')
            self.refs[name] = {'path': file.name, 'sha256': gate.common.sha(file)}
        self.report = {'schema_version': 1, 'kind': 'worktree-record-review-v1', 'candidate': 'fixture',
                       'source_review': self.refs['source'],
                       'generation': {k: self.refs[k] for k in ['producer', 'review']},
                       'boundaries': dict.fromkeys(gate.FLAGS, False)}
        for module in [gate.source, gate.generation]:
            manager = patch.object(module, 'check', return_value={'source_snapshot_sha256': 'a' * 64})
            self.addCleanup(manager.stop)
            checker = manager.start()
            if module is gate.source:
                self.source_checker = checker
            else:
                self.generation_checker = checker
        manager = patch.object(gate.output, 'check', return_value={
            'source_snapshot_sha256': 'a' * 64, 'current_generated_output_identity_recorded': True})
        self.addCleanup(manager.stop)
        self.output_checker = manager.start()
        manager = patch.object(gate.source.source, 'capture', side_effect=lambda root:
                               {'snapshot_sha256': self.source_checker.return_value['source_snapshot_sha256']})
        self.addCleanup(manager.stop)
        self.capture = manager.start()

    def save(self):
        self.path.write_text(json.dumps(self.report))

    def check(self, candidate='fixture'):
        self.save()
        return gate.check(self.path, candidate, self.root)

    def test_both_components_still_partial(self):
        result = self.check()
        self.assertTrue(result['source_snapshots_match'])
        self.assertFalse(result['worktree_audit_closed'])
        self.assertFalse(result['candidate_identity_approved'])
        self.assertIn('final_generation_kernel_and_rocq_linkage', result['remaining'])

    def v2(self):
        self.report.update(schema_version=2, kind='worktree-record-review-v2', source_increment=None)

    def v3(self, output_identity=None):
        self.report.update(schema_version=3, kind='worktree-record-review-v3', source_increment=None,
                           output_identity={'fixture': True} if output_identity is None else output_identity)

    def v4(self, mutate=None):
        self.v3()
        approval = {
            'schema_version': 1,
            'kind': 'worktree-delivery-approval-v1',
            'candidate': 'fixture',
            'source_snapshot_sha256': 'a' * 64,
            'source_review': self.refs['source'],
            'output_identity': copy.deepcopy(self.report['output_identity']),
            'delivery_profile': 'A',
            'approved_by': {'name': 'Fixture Owner', 'role': 'repository_owner',
                            'channel': 'explicit_user_instruction'},
            'approval_statement': gate.APPROVAL_STATEMENT,
            'approved_at': '2026-09-14T00:00:00Z',
            'boundaries': dict.fromkeys(gate.APPROVAL_BOUNDARIES, False),
        }
        if mutate is not None:
            mutate(approval)
        path = self.root / 'approval.json'
        path.write_text(json.dumps(approval))
        self.report.update(schema_version=4, kind='worktree-record-review-v4',
                           approval={'path': path.name, 'sha256': gate.common.sha(path)})

    def test_v2_null_increment_keeps_mismatched_source_pending(self):
        self.v2(); self.source_checker.return_value = {'source_snapshot_sha256': 'b' * 64}
        self.assertIn('post_generation_source_delta_review', self.check()['remaining'])

    def test_v2_increment_receives_validated_endpoint_identities(self):
        self.v2(); self.source_checker.return_value = {'source_snapshot_sha256': 'b' * 64}
        self.report['source_increment'] = self.refs['review']
        with patch.object(gate.increment, 'check', return_value={'fixture_only': True}) as check:
            result = self.check()
        check.assert_called_once_with(self.root / 'review.json', 'fixture', 'a' * 64, 'b' * 64, root=self.root)
        self.assertFalse(result['source_snapshots_match'])
        self.assertNotIn('post_generation_source_delta_review', result['remaining'])
        self.assertIn('current_generated_output_identity', result['remaining'])
        self.assertFalse(result['worktree_audit_closed'])

    def test_v2_increment_requires_source(self):
        self.v2(); self.report.update(source_review=None, source_increment=self.refs['review'])
        with self.assertRaisesRegex(RuntimeError, 'both validated'): self.check()

    def test_v2_increment_requires_generation(self):
        self.v2(); self.report.update(generation=None, source_increment=self.refs['review'])
        with self.assertRaisesRegex(RuntimeError, 'both validated'): self.check()

    def test_v2_increment_failure_propagates(self):
        self.v2(); self.report['source_increment'] = self.refs['review']
        with patch.object(gate.increment, 'check', side_effect=RuntimeError('omitted source change')):
            with self.assertRaisesRegex(RuntimeError, 'omitted source'): self.check()

    def test_v1_cannot_smuggle_increment_field(self):
        self.report['source_increment'] = self.refs['review']
        with self.assertRaises(RuntimeError): self.check()

    def test_v2_requires_exact_version(self):
        self.v2(); self.report['schema_version'] = 1
        with self.assertRaises(RuntimeError): self.check()

    def test_v2_requires_explicit_nullable_increment_field(self):
        self.v2(); del self.report['source_increment']
        with self.assertRaises(RuntimeError): self.check()

    def test_v3_output_receives_validated_current_source_and_closes_only_identity(self):
        self.v3()
        result = self.check()
        self.output_checker.assert_called_once_with({'fixture': True}, 'a' * 64, root=self.root)
        self.assertNotIn('current_generated_output_identity', result['remaining'])
        self.assertIn('final_delivery_scope_and_semantic_approval', result['remaining'])
        self.assertIn(gate.EXECUTION_LINKAGE, result['remaining'])
        self.assertFalse(result['current_outputs_verified'])
        self.assertFalse(result['worktree_audit_closed'])

    def test_v3_null_output_keeps_identity_pending(self):
        self.v3(output_identity=False); self.report['output_identity'] = None
        result = self.check()
        self.output_checker.assert_not_called()
        self.assertIn('current_generated_output_identity', result['remaining'])

    def test_v3_output_requires_source(self):
        self.v3(); self.report['source_review'] = None
        with self.assertRaisesRegex(RuntimeError, 'validated current source'): self.check()

    def test_v3_output_failure_propagates(self):
        self.v3(); self.output_checker.side_effect = RuntimeError('output partition missing')
        with self.assertRaisesRegex(RuntimeError, 'partition missing'): self.check()

    def test_v3_requires_exact_version(self):
        self.v3(); self.report['schema_version'] = 2
        with self.assertRaisesRegex(RuntimeError, 'unknown'): self.check()

    def test_v2_cannot_smuggle_output_identity(self):
        self.v2(); self.report['output_identity'] = {'fixture': True}
        with self.assertRaises(RuntimeError): self.check()

    def test_v3_requires_explicit_output_field(self):
        self.v3(); del self.report['output_identity']
        with self.assertRaises(RuntimeError): self.check()

    def test_v4_explicit_profile_a_approval_removes_only_delivery_obligation(self):
        self.v4()
        result = self.check()
        self.assertTrue(result['delivery_approval_verified'])
        self.assertNotIn('final_delivery_scope_and_semantic_approval', result['remaining'])
        self.assertEqual(result['remaining'], [gate.EXECUTION_LINKAGE])
        self.assertFalse(result['worktree_audit_closed'])

    def test_v4_rejects_wrong_scope_authority_snapshot_or_boundary(self):
        changes = [
            (lambda r: r.update(delivery_profile='B'), 'identity/scope'),
            (lambda r: r['approved_by'].update(name='Codex'), 'user authority'),
            (lambda r: r.update(source_snapshot_sha256='b' * 64), 'identity/scope'),
            (lambda r: r.update(output_identity={'different': True}), 'identity/scope'),
            (lambda r: r['boundaries'].update(proof_scope_expanded=True), 'broadened'),
        ]
        for mutate, pattern in changes:
            self.v4(mutate)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                self.check()

    def test_v4_requires_approval_and_current_output(self):
        self.v4(); self.report['approval'] = None
        with self.assertRaisesRegex(RuntimeError, 'requires current source'): self.check()
        self.v4(); self.report['output_identity'] = None
        with self.assertRaisesRegex(RuntimeError, 'requires current source'): self.check()

    def test_source_missing_explicit(self):
        self.report['source_review'] = None
        result = self.check()
        self.source_checker.assert_not_called()
        self.assertIn('current_complete_source_review', result['remaining'])
        self.assertIn('post_generation_source_delta_review', result['remaining'])

    def test_generation_missing_explicit(self):
        self.report['generation'] = None
        result = self.check()
        self.generation_checker.assert_not_called()
        self.assertIn('recorded_generation_and_delta_review', result['remaining'])

    def test_later_source_not_silently_attached(self):
        self.source_checker.return_value = {'source_snapshot_sha256': 'b' * 64}
        result = self.check()
        self.assertFalse(result['source_snapshots_match'])
        self.assertIn('post_generation_source_delta_review', result['remaining'])

    def test_legacy_source_report_supported(self):
        self.report = {'kind': 'worktree-source-review-v1'}
        self.check()
        self.source_checker.assert_called_once_with(self.path, 'fixture', root=self.root)
        self.generation_checker.assert_not_called()

    def test_empty_envelope(self):
        self.report.update(source_review=None, generation=None)
        with self.assertRaisesRegex(RuntimeError, 'empty'): self.check()

    def test_candidate_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, 'candidate'): self.check('different')

    def test_assurance_upgrade(self):
        self.report['boundaries']['current_outputs_verified'] = True
        with self.assertRaisesRegex(RuntimeError, 'assurance'): self.check()

    def test_unknown_field(self):
        self.report['skip_source'] = True
        with self.assertRaises(RuntimeError): self.check()

    def test_unsafe_link(self):
        self.report['generation']['producer']['path'] = '../outside'
        with self.assertRaises(RuntimeError): self.check()

    def test_wrong_hash(self):
        self.report['generation']['review']['sha256'] = 'b' * 64
        with self.assertRaises(RuntimeError): self.check()

    def test_source_failure_propagates(self):
        self.source_checker.side_effect = RuntimeError('wrong source candidate')
        with self.assertRaisesRegex(RuntimeError, 'source candidate'): self.check()

    def test_generation_failure_propagates(self):
        self.generation_checker.side_effect = RuntimeError('missing delta')
        with self.assertRaisesRegex(RuntimeError, 'missing delta'): self.check()

    def test_report_mutation_rejected(self):
        def change(*args, **kwargs):
            self.path.write_text('{}')
            return {'source_snapshot_sha256': 'a' * 64}
        self.generation_checker.side_effect = change
        with self.assertRaisesRegex(RuntimeError, 'changed during'): self.check()

    def test_source_changes_during_generation_validation(self):
        self.capture.side_effect = None
        self.capture.return_value = {'snapshot_sha256': 'b' * 64}
        with self.assertRaisesRegex(RuntimeError, 'source changed'): self.check()

    def test_real_aggregator_keeps_envelope_incomplete(self):
        self.save()
        for name in audit_release.PINS.values():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        manifest = {'schema_version': 1, 'candidate': 'fixture',
                    'pins': {k: gate.common.sha(self.root / v) for k, v in audit_release.PINS.items()},
                    'evidence': dict.fromkeys(audit_release.SLOTS)}
        manifest['evidence']['worktree_audit'] = {'path': self.path.name, 'sha256': gate.common.sha(self.path)}
        with patch.object(audit_release, 'ROOT', self.root):
            result, code = audit_release.aggregate(manifest)
        self.assertEqual(code, 2)
        self.assertEqual(result['checks']['worktree_audit']['status'], 'incomplete')
        self.assertFalse(result['release_claimed'])
        self.assertFalse(result['week6_closed'])


class FormalLinkageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='formal-linkage-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.reports = {}
        for name in ['lean', 'rocq']:
            path = self.root / (name + '.json')
            path.write_text('synthetic independent-checker input: ' + name)
            self.reports[name] = {'path': path.name, 'sha256': gate.common.sha(path)}
        self.details = {'components': {'generation': {
            'scope': gate.FORMAL_SCOPE, 'recorded_main_rocq_generated_identity_matches': True,
            'formal_reports': copy.deepcopy(self.reports)}},
            'remaining': ['current_complete_source_review', gate.EXECUTION_LINKAGE,
                          'current_generated_output_identity', 'final_delivery_scope_and_semantic_approval'],
            'worktree_audit_closed': False, **dict.fromkeys(gate.FLAGS, False)}
        self.checks = {name: {'status': 'verified_existing_evidence', 'reference': copy.deepcopy(ref)}
                       for name, ref in self.reports.items()}

    def check(self):
        return gate.connect_formal_execution(self.details, self.checks, root=self.root)

    def test_exact_join_removes_only_linkage_without_mutating_inputs(self):
        original = copy.deepcopy(self.details)
        result = self.check()
        self.assertEqual(self.details, original)
        self.assertEqual(result['remaining'], [v for v in original['remaining'] if v != gate.EXECUTION_LINKAGE])
        self.assertEqual(result['formal_execution_linkage']['status'], 'verified_existing_evidence_linkage')
        self.assertEqual(result['formal_execution_linkage']['missing_verified_components'], [])
        self.assertFalse(result['worktree_audit_closed'])
        for flag in gate.FLAGS: self.assertIs(result[flag], False)

    def test_missing_lean_stays_pending(self):
        del self.checks['lean']
        result = self.check()
        self.assertIn(gate.EXECUTION_LINKAGE, result['remaining'])
        self.assertEqual(result['formal_execution_linkage']['missing_verified_components'], ['lean'])

    def test_missing_rocq_stays_pending(self):
        del self.checks['rocq']
        self.assertEqual(self.check()['formal_execution_linkage']['missing_verified_components'], ['rocq'])

    def test_both_missing_stay_pending(self):
        self.checks.clear()
        self.assertEqual(self.check()['formal_execution_linkage']['missing_verified_components'], ['lean', 'rocq'])

    def test_failed_component_cannot_close_linkage(self):
        self.checks['lean']['status'] = 'invalid'
        self.assertIn(gate.EXECUTION_LINKAGE, self.check()['remaining'])

    def test_unvalidated_pass_word_cannot_close_linkage(self):
        self.checks['rocq']['status'] = 'PASS'
        self.assertIn(gate.EXECUTION_LINKAGE, self.check()['remaining'])

    def test_other_accepted_lean_rejected(self):
        self.checks['lean']['reference'] = self.reports['rocq']
        with self.assertRaisesRegex(RuntimeError, 'different accepted lean'): self.check()

    def test_other_accepted_rocq_rejected(self):
        self.checks['rocq']['reference'] = self.reports['lean']
        with self.assertRaisesRegex(RuntimeError, 'different accepted rocq'): self.check()

    def test_other_accepted_report_rejected_even_when_peer_missing(self):
        del self.checks['rocq']
        self.checks['lean']['reference'] = self.reports['rocq']
        with self.assertRaisesRegex(RuntimeError, 'different accepted lean'): self.check()

    def test_same_bytes_different_path_not_the_recorded_reference(self):
        (self.root / 'copy.json').write_bytes((self.root / 'lean.json').read_bytes())
        self.checks['lean']['reference']['path'] = 'copy.json'
        with self.assertRaisesRegex(RuntimeError, 'different accepted lean'): self.check()

    def test_wrong_accepted_hash_rejected(self):
        self.checks['lean']['reference']['sha256'] = 'b' * 64
        with self.assertRaisesRegex(RuntimeError, 'different accepted lean'): self.check()

    def test_changed_report_rejected(self):
        (self.root / 'lean.json').write_text('changed')
        with self.assertRaises(RuntimeError): self.check()

    def test_symlink_report_rejected(self):
        path = self.root / 'lean.json'; path.rename(self.root / 'saved.json'); path.symlink_to(self.root / 'saved.json')
        with self.assertRaises(RuntimeError): self.check()

    def test_extra_formal_report_rejected(self):
        self.details['components']['generation']['formal_reports']['other'] = self.reports['lean']
        with self.assertRaises(RuntimeError): self.check()

    def test_missing_formal_reference_rejected(self):
        del self.details['components']['generation']['formal_reports']['rocq']
        with self.assertRaises(RuntimeError): self.check()

    def test_truthy_identity_flag_rejected(self):
        self.details['components']['generation']['recorded_main_rocq_generated_identity_matches'] = 1
        with self.assertRaises(RuntimeError): self.check()

    def test_connected_approved_v4_promotes_only_worktree_scope(self):
        self.details['delivery_approval_verified'] = True
        self.details['remaining'] = [gate.EXECUTION_LINKAGE]
        result = self.check()
        self.assertEqual(result['remaining'], [])
        self.assertTrue(result['worktree_audit_closed'])
        self.assertTrue(result['candidate_identity_approved'])
        self.assertTrue(result['candidate_approval_claimed'])
        self.assertTrue(result['current_outputs_verified'])
        self.assertTrue(result['generated_outputs_audited'])
        self.assertFalse(result['release_claimed'])
        self.assertFalse(result['week6_closed'])
        self.assertFalse(result['semantic_correctness_proven'])

    def test_missing_linkage_obligation_rejected(self):
        self.details['remaining'].remove(gate.EXECUTION_LINKAGE)
        with self.assertRaises(RuntimeError): self.check()

    def test_duplicate_linkage_obligation_rejected(self):
        self.details['remaining'].append(gate.EXECUTION_LINKAGE)
        with self.assertRaises(RuntimeError): self.check()

    def test_source_only_does_not_gain_linkage(self):
        self.details['components'] = {'source': {'scope': 'source only'}}
        self.assertEqual(self.check(), self.details)

    def test_legacy_generation_keeps_linkage_pending(self):
        self.details['components']['generation']['scope'] = 'historical_generation_records_and_complete_delta_review_bindings_only'
        self.assertEqual(self.check(), self.details)


if __name__ == '__main__':
    unittest.main()
