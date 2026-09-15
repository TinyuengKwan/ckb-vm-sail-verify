"""Hermetic negative tests: missing/unvalidated evidence cannot certify release."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as gate
import release_evidence as evidence


class AggregationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='release-audit-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.patch(patch.object(gate, 'ROOT', self.root))
        for name in gate.PINS.values():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture only ' + name)
        self.manifest = {'schema_version': 1, 'candidate': 'synthetic-test-only',
            'pins': {k: evidence.sha(self.root / v) for k, v in gate.PINS.items()},
            'evidence': dict.fromkeys(gate.SLOTS)}
        self.file = self.root / 'evidence.json'
        self.file.write_text('{"status":"PASS"}')
        self.ref = {'path': self.file.name, 'sha256': evidence.sha(self.file)}

    def patch(self, manager):
        self.addCleanup(manager.stop)
        return manager.start()

    def link_inventory(self):
        path = self.root / 'inventory.json'
        path.write_text(json.dumps({'runtime': self.ref, 'rust_tests': self.ref,
                                   'semantic_negative_cases': {gate.mismatches.CASES[-1]: self.ref}}))
        self.manifest['evidence']['mismatches'] = {'path': path.name, 'sha256': evidence.sha(path)}
        if self.manifest['evidence']['maintainer_demo'] is not None:
            folder = self.root / 'demo'
            folder.mkdir(exist_ok=True)
            plan = folder / 'plan.json'
            plan.write_text(json.dumps({'runtime': self.ref, 'trap': self.ref}))
            report = folder / 'report.json'
            report.write_text(json.dumps({'plan_sha256': evidence.sha(plan)}))
            self.manifest['evidence']['maintainer_demo'] = {
                'path': 'demo/report.json', 'sha256': evidence.sha(report)}

    def test_empty_evidence_is_incomplete_not_success(self):
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(result['outstanding'], gate.SLOTS)
        self.assertFalse(result['release_claimed'])
        self.assertFalse(result['week6_closed'])

    def formal_linkage_fixture(self):
        reports = {}
        for name in ['lean', 'rocq']:
            path = self.root / (name + '.json')
            path.write_text(json.dumps({'fixture_only': name}))
            reports[name] = {'path': path.name, 'sha256': evidence.sha(path)}
            self.manifest['evidence'][name] = copy.deepcopy(reports[name])
        details = {'components': {'generation': {
            'scope': gate.worktree_evidence.FORMAL_SCOPE,
            'recorded_main_rocq_generated_identity_matches': True, 'formal_reports': reports}},
            'remaining': [gate.worktree_evidence.EXECUTION_LINKAGE, 'current_generated_output_identity',
                          'current_complete_source_review', 'final_delivery_scope_and_semantic_approval'],
            'worktree_audit_closed': False}
        self.manifest['evidence']['worktree_audit'] = self.ref
        self.patch(patch.dict(gate.PARTIAL_CHECKERS, {'worktree_audit': lambda *a, **k: copy.deepcopy(details)}))
        self.patch(patch.dict(gate.CHECKERS, {name: lambda _: {'fixture_only': True} for name in ['lean', 'rocq']}))
        return details

    def test_formal_join_removes_only_execution_obligation(self):
        self.formal_linkage_fixture()
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        worktree = result['checks']['worktree_audit']
        self.assertEqual(worktree['status'], 'incomplete')
        self.assertEqual(worktree['details']['formal_execution_linkage']['status'], 'verified_existing_evidence_linkage')
        self.assertNotIn(gate.worktree_evidence.EXECUTION_LINKAGE, worktree['details']['remaining'])
        self.assertIn('current_generated_output_identity', worktree['details']['remaining'])
        self.assertFalse(result['release_claimed'])
        self.assertFalse(result['week6_closed'])

    def test_explicitly_approved_v4_worktree_promotes_after_exact_formal_join(self):
        details = self.formal_linkage_fixture()
        details['remaining'] = [gate.worktree_evidence.EXECUTION_LINKAGE]
        details['delivery_approval_verified'] = True
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        worktree = result['checks']['worktree_audit']
        self.assertEqual(worktree['status'], 'verified_existing_evidence')
        self.assertNotIn('worktree_audit', result['outstanding'])
        self.assertEqual(worktree['details']['remaining'], [])
        self.assertTrue(worktree['details']['worktree_audit_closed'])
        self.assertFalse(result['release_claimed'])

    def test_unrelated_accepted_formal_report_is_invalid_join(self):
        self.formal_linkage_fixture()
        path = self.root / 'other-lean.json'; path.write_bytes((self.root / 'lean.json').read_bytes())
        self.manifest['evidence']['lean'] = {'path': path.name, 'sha256': evidence.sha(path)}
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(result['checks']['lean']['status'], 'verified_existing_evidence')
        self.assertEqual(result['checks']['worktree_audit']['status'], 'invalid')
        self.assertIn('different accepted lean', result['checks']['worktree_audit']['reason'])

    def test_missing_formal_component_keeps_execution_pending(self):
        self.formal_linkage_fixture()
        self.manifest['evidence']['rocq'] = None
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        details = result['checks']['worktree_audit']['details']
        self.assertIn(gate.worktree_evidence.EXECUTION_LINKAGE, details['remaining'])
        self.assertEqual(details['formal_execution_linkage']['missing_verified_components'], ['rocq'])

    def test_failed_formal_checker_cannot_discharge_execution(self):
        self.formal_linkage_fixture()
        def fail(_): raise RuntimeError('synthetic invalid Lean evidence')
        self.patch(patch.dict(gate.CHECKERS, {'lean': fail}))
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn(gate.worktree_evidence.EXECUTION_LINKAGE,
                      result['checks']['worktree_audit']['details']['remaining'])

    def test_join_does_not_depend_on_slot_iteration_order(self):
        self.formal_linkage_fixture()
        self.patch(patch.object(gate, 'SLOTS', list(reversed(gate.SLOTS))))
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(result['checks']['worktree_audit']['details']['formal_execution_linkage']['status'],
                         'verified_existing_evidence_linkage')

    def test_envelope_changed_after_partial_check_cannot_acquire_linkage(self):
        self.formal_linkage_fixture()
        self.patch(patch.object(gate, 'SLOTS', list(reversed(gate.SLOTS))))
        def mutate(_):
            self.file.write_text('changed envelope')
            return {'fixture_only': True}
        self.patch(patch.dict(gate.CHECKERS, {'lean': mutate}))
        result, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(result['checks']['worktree_audit']['status'], 'invalid')

    def test_verified_local_components_do_not_certify_release(self):
        self.patch(patch.dict(gate.CHECKERS, {k: lambda *_, **__: {'test_only': True}
                                              for k in gate.CHECKERS}))
        for name in gate.CHECKERS: self.manifest['evidence'][name] = self.ref
        self.link_inventory()
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(report['outstanding'], [name for name in gate.SLOTS if name not in gate.CHECKERS])
        self.assertEqual(report['checks']['runtime']['status'], 'verified_existing_evidence')

    def test_all_twelve_verified_components_are_the_only_success_path(self):
        source_snapshot = 'f' * 64
        local_results = {name: {'fixture_only': True} for name in gate.CHECKERS}
        local_results['public_claims'] = {'public_claims_slot_closed': True,
                                          'source_snapshot_sha256': source_snapshot}
        self.patch(patch.dict(gate.CHECKERS,
                              {name: (lambda *_, value=value, **__: copy.deepcopy(value))
                               for name, value in local_results.items()}))
        for name in gate.CHECKERS:
            self.manifest['evidence'][name] = self.ref
        self.link_inventory()
        clean_ref = self.ref
        package_ref = self.ref
        ci = self.root / 'ci-success.json'
        ci.write_text(json.dumps({'clean_room': clean_ref}))
        third = self.root / 'third-success.json'
        third.write_text(json.dumps({'release_package': package_ref}))
        self.manifest['evidence'].update(
            clean_room=clean_ref,
            ci_download={'path': ci.name, 'sha256': evidence.sha(ci)},
            release_package=package_ref,
            third_party={'path': third.name, 'sha256': evidence.sha(third)},
        )
        external_results = {
            'clean_room': {'clean_room_verified': True, 'fresh_execution_claimed': True,
                           'source_snapshot_sha256': source_snapshot},
            'ci_download': {'ci_download_verified': True, 'remote_state_queried': True,
                            'source_snapshot_sha256': source_snapshot},
            'release_package': {'release_package_built': True, 'publication_verified': True,
                                'download_verified': True, 'remote_state_queried': True,
                                'delivery_profile': 'A', 'source_snapshot_sha256': source_snapshot},
            'third_party': {'third_party_reproduced': True, 'independent_third_party': True,
                            'source_snapshot_sha256': source_snapshot},
        }
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS,
                              {name: (lambda *_, value=value, **__: copy.deepcopy(value))
                               for name, value in external_results.items()}))
        formal_reports = {name: copy.deepcopy(self.manifest['evidence'][name]) for name in ['lean', 'rocq']}
        worktree_details = {
            'components': {
                'source': {'source_snapshot_sha256': source_snapshot},
                'approval': {'delivery_profile': 'A'},
                'generation': {
                    'scope': gate.worktree_evidence.FORMAL_SCOPE,
                    'recorded_main_rocq_generated_identity_matches': True,
                    'formal_reports': formal_reports,
                },
            },
            'remaining': [gate.worktree_evidence.EXECUTION_LINKAGE],
            'delivery_approval_verified': True,
            'worktree_audit_closed': False,
            **dict.fromkeys(gate.worktree_evidence.FLAGS, False),
        }
        self.patch(patch.dict(gate.PARTIAL_CHECKERS,
                              {'worktree_audit': lambda *a, **k: copy.deepcopy(worktree_details)}))
        self.manifest['evidence']['worktree_audit'] = self.ref
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['outstanding'], [])
        self.assertTrue(report['release_claimed'])
        self.assertTrue(report['week6_closed'])
        self.assertTrue(report['fresh_execution_claimed'])
        external_results['third_party']['source_snapshot_sha256'] = 'e' * 64
        with self.assertRaisesRegex(RuntimeError, 'completion fact'):
            gate.aggregate(self.manifest)
        external_results['third_party']['source_snapshot_sha256'] = source_snapshot
        external_results['release_package']['delivery_profile'] = 'B'
        with self.assertRaisesRegex(RuntimeError, 'completion fact'):
            gate.aggregate(self.manifest)
        external_results['release_package']['delivery_profile'] = 'A'
        # An independent ephemeral VM clean-room closes only through its operator-attested record.
        external_results['clean_room']['provider'] = gate.external.VM_PROVIDER
        with patch.object(gate.external, 'check_vm_provenance',
                          side_effect=gate.external.VmProvenanceAbsent('record absent')):
            report, code = gate.aggregate(self.manifest)
        self.assertEqual((code, report['status'], report['outstanding']), (2, 'incomplete', ['clean_room']))
        with patch.object(gate.external, 'check_vm_provenance',
                          return_value={'operator_attested': True, 'platform_signed_identity': False}):
            report, code = gate.aggregate(self.manifest)
        self.assertEqual((code, report['status']), (0, 'passed'))
        with patch.object(gate.external, 'check_vm_provenance', return_value={'operator_attested': False}), \
                self.assertRaisesRegex(RuntimeError, 'completion fact'):
            gate.aggregate(self.manifest)

    def test_vm_clean_room_stays_incomplete_until_the_host_record_binds_it(self):
        self.manifest['evidence']['clean_room'] = self.ref
        checker = lambda *_, **__: {'clean_room_verified': True, 'fresh_execution_claimed': True,
                                    'provider': gate.external.VM_PROVIDER}
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS, {'clean_room': checker}))
        with patch.object(gate.external, 'check_vm_provenance',
                          side_effect=gate.external.VmProvenanceAbsent('record absent')) as absent:
            report, code = gate.aggregate(self.manifest)
        absent.assert_called_once_with(self.file)
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['clean_room']['status'], 'incomplete')
        self.assertIn('record absent', report['checks']['clean_room']['reason'])
        with patch.object(gate.external, 'check_vm_provenance', side_effect=RuntimeError('bound elsewhere')):
            report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(report['checks']['clean_room']['status'], 'invalid')
        with patch.object(gate.external, 'check_vm_provenance',
                          return_value={'operator_attested': True, 'platform_signed_identity': False}):
            report, code = gate.aggregate(self.manifest)
        self.assertEqual(report['checks']['clean_room']['status'], 'verified_existing_evidence')
        self.assertTrue(report['checks']['clean_room']['details']['host_provenance']['operator_attested'])
        self.assertEqual(code, 2)
        self.assertFalse(report['week6_closed'])

    def test_all_verified_labels_without_completion_facts_fail_closed(self):
        self.patch(patch.dict(gate.CHECKERS, {name: lambda *_, **__: {} for name in gate.CHECKERS}))
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS, {name: lambda *a, **k: {}
                                                       for name in gate.EXTERNAL_CHECKERS}))
        for name in [*gate.CHECKERS, *gate.EXTERNAL_CHECKERS]:
            self.manifest['evidence'][name] = self.ref
        self.link_inventory()
        ci = self.root / 'ci-empty.json'; ci.write_text(json.dumps({'clean_room': self.ref}))
        third = self.root / 'third-empty.json'; third.write_text(json.dumps({'release_package': self.ref}))
        self.manifest['evidence']['ci_download'] = {'path': ci.name, 'sha256': evidence.sha(ci)}
        self.manifest['evidence']['third_party'] = {'path': third.name, 'sha256': evidence.sha(third)}
        self.manifest['evidence']['worktree_audit'] = self.ref
        closed = {'remaining': [], 'delivery_approval_verified': True, 'worktree_audit_closed': True}
        self.patch(patch.dict(gate.PARTIAL_CHECKERS, {'worktree_audit': lambda *a, **k: closed}))
        with self.assertRaisesRegex(RuntimeError, 'completion fact'):
            gate.aggregate(self.manifest)

    def test_pass_documents_cannot_close_pending_obligations(self):
        self.patch(patch.dict(gate.CHECKERS, {k: lambda *_, **__: {} for k in gate.CHECKERS}))
        self.manifest['evidence'] = dict.fromkeys(gate.SLOTS, self.ref)
        self.link_inventory()
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        for name in gate.PENDING.keys() - gate.CHECKERS.keys():
            self.assertEqual(report['checks'][name]['status'],
                             'invalid' if name in gate.PARTIAL_CHECKERS or name in gate.EXTERNAL_CHECKERS
                             else 'unimplemented')
        self.assertFalse(report['release_claimed'])

    def test_external_checker_receives_candidate_and_root(self):
        from unittest.mock import Mock
        checker = Mock(return_value={'clean_room_verified': True})
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS, {'clean_room': checker}))
        self.manifest['evidence']['clean_room'] = self.ref
        report, code = gate.aggregate(self.manifest)
        checker.assert_called_once_with(self.file, self.manifest['candidate'], root=self.root)
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['clean_room']['status'], 'verified_existing_evidence')

    def test_external_slots_use_real_validators(self):
        self.assertIs(gate.EXTERNAL_CHECKERS['clean_room'], gate.external.check_clean_room)
        self.assertIs(gate.EXTERNAL_CHECKERS['ci_download'], gate.external.check_ci_download)
        self.assertIs(gate.EXTERNAL_CHECKERS['release_package'], gate.external.check_release_package)
        self.assertIs(gate.EXTERNAL_CHECKERS['third_party'], gate.external.check_third_party)
        self.assertEqual(set(gate.EXTERNAL_CHECKERS),
                         {'clean_room', 'ci_download', 'release_package', 'third_party'})

    def test_ci_must_bind_same_clean_room(self):
        other = self.root / 'other-clean.json'
        other.write_text('{}')
        ci = self.root / 'ci.json'
        ci.write_text(json.dumps({'clean_room': {'path': other.name, 'sha256': evidence.sha(other)}}))
        self.manifest['evidence']['clean_room'] = self.ref
        self.manifest['evidence']['ci_download'] = {'path': ci.name, 'sha256': evidence.sha(ci)}
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS, {'ci_download': lambda *a, **k: {}}))
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(report['checks']['ci_download']['status'], 'invalid')
        self.assertIn('different clean-room', report['checks']['ci_download']['reason'])

    def test_third_party_must_bind_same_release_package(self):
        other = self.root / 'other-package.json'
        other.write_text('{}')
        third = self.root / 'third.json'
        third.write_text(json.dumps({'release_package': {
            'path': other.name, 'sha256': evidence.sha(other)}}))
        self.manifest['evidence']['release_package'] = self.ref
        self.manifest['evidence']['third_party'] = {
            'path': third.name, 'sha256': evidence.sha(third)}
        self.patch(patch.dict(gate.EXTERNAL_CHECKERS, {'third_party': lambda *a, **k: {}}))
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(report['checks']['third_party']['status'], 'invalid')
        self.assertIn('different release package', report['checks']['third_party']['reason'])

    def test_source_review_component_cannot_close_whole_worktree_slot(self):
        self.patch(patch.dict(gate.PARTIAL_CHECKERS,
            {'worktree_audit': lambda path, candidate, root: {'fixture_only': True}}))
        self.manifest['evidence']['worktree_audit'] = self.ref
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['worktree_audit']['status'], 'incomplete')
        self.assertIn('worktree_audit', report['outstanding'])
        self.assertFalse(report['week6_closed'])

    def test_source_review_receives_candidate_and_root(self):
        from unittest.mock import Mock
        checker = Mock(return_value={'fixture_only': True})
        self.patch(patch.dict(gate.PARTIAL_CHECKERS, {'worktree_audit': checker}))
        self.manifest['evidence']['worktree_audit'] = self.ref
        gate.aggregate(self.manifest)
        checker.assert_called_once_with(self.file, self.manifest['candidate'], root=self.root)

    def test_partial_source_review_changed_report_rejected(self):
        def changed(path, candidate, root):
            path.write_text('{}')
            return {}
        self.patch(patch.dict(gate.PARTIAL_CHECKERS, {'worktree_audit': changed}))
        self.manifest['evidence']['worktree_audit'] = self.ref
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn('changed during', report['checks']['worktree_audit']['reason'])

    def test_missing_source_review_does_not_call_partial_checker(self):
        from unittest.mock import Mock
        checker = Mock(side_effect=RuntimeError('must not execute'))
        self.patch(patch.dict(gate.PARTIAL_CHECKERS, {'worktree_audit': checker}))
        report, code = gate.aggregate(self.manifest)
        checker.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['worktree_audit']['status'], 'missing')

    def test_partial_mismatch_inventory_stays_incomplete(self):
        def incomplete(_):
            raise gate.mismatches.IncompleteEvidence({'pending': ['paired-input']})
        self.patch(patch.dict(gate.CHECKERS, {k: (incomplete if k == 'mismatches' else lambda *_, **__: {})
                                             for k in gate.CHECKERS}))
        for name in gate.CHECKERS: self.manifest['evidence'][name] = self.ref
        self.link_inventory()
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['mismatches']['status'], 'incomplete')
        self.assertIn('mismatches', report['outstanding'])

    def test_mismatch_inventory_must_bind_same_runtime(self):
        for name in gate.CHECKERS: self.manifest['evidence'][name] = self.ref
        self.link_inventory()
        self.manifest['evidence']['runtime'] = None
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn('different runtime', report['checks']['mismatches']['reason'])

    def test_missing_slot_is_invalid_not_implicitly_optional(self):
        del self.manifest['evidence']['third_party']
        with self.assertRaisesRegex(RuntimeError, 'slots'): gate.aggregate(self.manifest)

    def test_demo_must_bind_same_runtime(self):
        self.manifest['evidence']['maintainer_demo'] = self.ref
        self.link_inventory()
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn('different runtime', report['checks']['maintainer_demo']['reason'])

    def test_demo_must_bind_inventory_trap(self):
        self.patch(patch.dict(gate.CHECKERS, {k: lambda *_, **__: {} for k in gate.CHECKERS}))
        self.manifest['evidence']['maintainer_demo'] = self.ref
        self.manifest['evidence']['runtime'] = self.ref
        self.link_inventory()
        path = self.root / 'inventory.json'
        inventory = evidence.read(path)
        inventory['semantic_negative_cases'][gate.mismatches.CASES[-1]] = None
        path.write_text(json.dumps(inventory))
        self.manifest['evidence']['mismatches']['sha256'] = evidence.sha(path)
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn('different trap', report['checks']['maintainer_demo']['reason'])

    def test_demo_acceptance_is_not_a_pass_document(self):
        self.assertIs(gate.CHECKERS['maintainer_demo'], gate.demo.check)
        self.assertNotIn('maintainer_demo', gate.PENDING)
        self.assertEqual(len(gate.PENDING), 6)

    def test_public_claims_has_real_validator_but_remains_mandatory_when_missing(self):
        self.assertIs(gate.CHECKERS['public_claims'], gate.public_claims.check)
        self.assertIn('public_claims', gate.PENDING)
        self.assertEqual(gate.SLOTS.count('public_claims'), 1)
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 2)
        self.assertEqual(report['checks']['public_claims']['status'], 'missing')

    def test_public_claims_checker_receives_release_candidate(self):
        seen = []
        self.patch(patch.dict(gate.CHECKERS, {
            'public_claims': lambda _, candidate=None: seen.append(candidate) or {}
        }))
        self.manifest['evidence']['public_claims'] = self.ref
        gate.aggregate(self.manifest)
        self.assertEqual(seen, [self.manifest['candidate']])

    def test_unknown_slot_is_not_a_validator_extension(self):
        self.manifest['evidence']['run_this_command'] = 'true'
        with self.assertRaises(RuntimeError): gate.aggregate(self.manifest)

    def test_schema_boolean_or_extra_override_rejected(self):
        for key, value in [('schema_version', True), ('skip_missing', True), ('candidate', '')]:
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): gate.aggregate(manifest)

    def test_stale_policy_or_plan_pin(self):
        for key in gate.PINS:
            manifest = copy.deepcopy(self.manifest)
            manifest['pins'][key] = '0' * 64
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'stale pin'):
                gate.aggregate(manifest)

    def test_missing_policy_pin(self):
        del self.manifest['pins']['main_policy']
        with self.assertRaises(RuntimeError): gate.aggregate(self.manifest)

    def test_active_public_policy_is_v2_and_admission_is_mandatory(self):
        self.assertEqual(gate.PINS['public_policy'], 'proof/lean/decoder/public-rebuilt-policy.json')
        for key in ('raw_policy', 'input_admission', 'input_catalogue'):
            manifest = copy.deepcopy(self.manifest)
            del manifest['pins'][key]
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'pin inventory'):
                gate.aggregate(manifest)

    def test_forged_hash_or_missing_file_invalid(self):
        for ref in [dict(self.ref, sha256='0' * 64), dict(self.ref, path='absent.json')]:
            self.manifest['evidence']['runtime'] = ref
            report, code = gate.aggregate(self.manifest)
            self.assertEqual(code, 1)
            self.assertEqual(report['checks']['runtime']['status'], 'invalid')

    def test_bare_pass_boolean_not_evidence(self):
        self.manifest['evidence']['runtime'] = True
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(report['checks']['runtime']['status'], 'invalid')

    def test_invalid_component_does_not_hide_other_missing_items(self):
        self.patch(patch.dict(gate.CHECKERS, {'runtime': lambda _: (_ for _ in ()).throw(RuntimeError('bad trace'))}))
        self.manifest['evidence']['runtime'] = self.ref
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertEqual(report['checks']['runtime']['reason'], 'bad trace')
        self.assertEqual(report['checks']['third_party']['status'], 'missing')

    def test_changed_report_during_validation(self):
        def changed(path):
            path.write_text('{}')
            return {}
        self.patch(patch.dict(gate.CHECKERS, {'runtime': changed}))
        self.manifest['evidence']['runtime'] = self.ref
        report, code = gate.aggregate(self.manifest)
        self.assertEqual(code, 1)
        self.assertIn('changed during', report['checks']['runtime']['reason'])

    def test_paths_reject_escape_absolute_and_symlink(self):
        for name in ['../evidence.json', str(self.file), './evidence.json', 'x//y', '']:
            with self.subTest(name=name), self.assertRaises(RuntimeError): evidence.member(self.root, name)
        (self.root / 'linked.json').symlink_to(self.file)
        with self.assertRaises(RuntimeError): evidence.member(self.root, 'linked.json')
        (self.root / 'dir').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(RuntimeError): evidence.member(self.root, 'dir/evidence.json')

    def test_malformed_sha_rejected(self):
        for digest in [True, 'x' * 64, 'A' * 64, 'a' * 63]:
            with self.subTest(digest=digest), self.assertRaises(RuntimeError):
                evidence.linked(self.root, self.file.name, digest)

    def test_cli_saves_incomplete_without_overwriting(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.manifest))
        out = self.root / 'out'
        with patch.object(sys, 'argv', ['audit_release.py', '--manifest', str(manifest), '--out', str(out)]), \
             patch.object(gate, 'snapshot', return_value={'fixture': 'unchanged'}), \
             patch.object(gate.subprocess, 'check_output', return_value='fixture'), patch('builtins.print'):
            self.assertEqual(gate.main(), 2)
            original = (out / 'report.json').read_bytes()
            with self.assertRaises(FileExistsError): gate.main()
            self.assertEqual((out / 'report.json').read_bytes(), original)
        self.assertFalse(evidence.read(out / 'report.json')['week6_closed'])

    def test_cli_invalid_manifest_still_preserves_failed_report(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text('{"schema_version":1,"schema_version":1}')
        out = self.root / 'invalid'
        with patch.object(sys, 'argv', ['audit_release.py', '--manifest', str(manifest), '--out', str(out)]), \
             patch.object(gate, 'snapshot', return_value={}), \
             patch.object(gate.subprocess, 'check_output', return_value='fixture'), patch('builtins.print'):
            self.assertEqual(gate.main(), 1)
        self.assertEqual(evidence.read(out / 'report.json')['status'], 'invalid')


class ComponentBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='release-component-test-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'report.json'

    def test_old_rocq_policy_rejected_before_model_loading(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'verdict': 'NO-GO',
            'extra_proof_coverage': False, 'clean_room_claimed': False, 'policy_sha256': 'old'}))
        with patch.object(evidence, 'sha', return_value='current'), \
             patch.object(evidence, 'current_formal') as current, \
             self.assertRaisesRegex(RuntimeError, 'stale Rocq'):
            evidence.check_rocq(self.path)
        current.assert_not_called()

    def test_rocq_no_go_cannot_claim_extra_proof(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'verdict': 'NO-GO',
            'extra_proof_coverage': True, 'clean_room_claimed': False}))
        with self.assertRaisesRegex(RuntimeError, 'coverage'): evidence.check_rocq(self.path)

    def test_rebuilt_rocq_cannot_reuse_ten_stage_retranslation_only_report(self):
        policy = {'main_toolchain': 'rebuilt-main-v1'}
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'verdict': 'NO-GO',
            'extra_proof_coverage': False, 'clean_room_claimed': False, 'policy_sha256': 'current',
            'directory': str(self.path.parent), 'source': {}, 'generated': {},
            'input_sha256': {}, 'input_sha256_after': {}, 'stages': [{'name': n} for n in evidence.ROCQ_STAGES]}))
        with patch.object(evidence, 'sha', return_value='current'), \
             patch.object(evidence, 'current_formal', return_value=(policy, {}, {})), \
             patch.object(evidence.rocq, 'inputs', return_value={}), \
             self.assertRaisesRegex(RuntimeError, 'Rocq stage inventory'):
            evidence.check_rocq(self.path)

    def test_rebuilt_rocq_unknown_profile_is_not_legacy(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'verdict': 'NO-GO',
            'extra_proof_coverage': False, 'clean_room_claimed': False, 'policy_sha256': 'current',
            'directory': str(self.path.parent), 'source': {}, 'generated': {}}))
        with patch.object(evidence, 'sha', return_value='current'), \
             patch.object(evidence, 'current_formal', return_value=({'main_toolchain': 'unknown'}, {}, {})), \
             self.assertRaisesRegex(RuntimeError, 'unknown Rocq main'):
            evidence.check_rocq(self.path)

    def test_lean_cannot_upgrade_conditional_to_unconditional(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'assurance': 'unconditional'}))
        with patch.object(evidence, 'current_formal', return_value=({}, {}, {})), \
             self.assertRaisesRegex(RuntimeError, 'assurance'): evidence.check_lean(self.path)

    def test_lean_missing_stages_rejected(self):
        policy = {'theorem': 'fixture', 'configuration': {}, 'outstanding_contracts': []}
        source = {'ckb_source_baseline': {}}
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'passed', 'assurance': 'conditional',
            'coverage': 'runtime-only', 'release_audit': False, 'policy_sha256': 'current',
            **policy, 'source': source, 'generated': {}, 'ckb_source_baseline': {}, 'stages': []}))
        with patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
             patch.object(evidence, 'sha', return_value='current'), \
             self.assertRaisesRegex(RuntimeError, 'stage inventory'): evidence.check_lean(self.path)

    def lean_fixture(self):
        policy = {'theorem': 'fixture', 'configuration': {}, 'outstanding_contracts': []}
        source = {'ckb_source_baseline': {}}
        report = {'schema_version': 1, 'status': 'passed', 'assurance': 'conditional',
            'coverage': 'runtime-only', 'release_audit': False, 'policy_sha256': 'current',
            **policy, 'source': source, 'generated': {}, 'ckb_source_baseline': {},
            'stages': [{'name': name, 'status': 'passed', 'exit_code': 0,
                        'log': name + '.log', 'sha256': '0' * 64}
                       for name in evidence.LEAN_STAGES]}
        for name in evidence.LEAN_STAGES:
            count = evidence.TEST_COUNTS.get(name)
            (self.path.parent / (name + '.log')).write_text(
                f'Ran {count} tests in 0.001s\n\nOK\n' if count else 'fixture\n')
        return policy, source, report

    def test_lean_install_regression_is_required(self):
        policy, source, report = self.lean_fixture()
        report['stages'] = [row for row in report['stages']
                            if row['name'] != 'test_sail_model_transaction']
        self.path.write_text(json.dumps(report))
        with patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
             patch.object(evidence, 'sha', return_value='current'), \
             self.assertRaisesRegex(RuntimeError, 'stage inventory'):
            evidence.check_lean(self.path)

    def test_lean_install_reduced_test_count_rejected(self):
        policy, source, report = self.lean_fixture()
        self.path.write_text(json.dumps(report))
        log = self.path.parent / 'test_sail_model_transaction.log'
        for content in ['Ran 20 tests in 0.001s\n\nOK\n',
                        'Ran 21 tests in 0.001s\n\nFAILED (failures=1)\n']:
            log.write_text(content)
            with self.subTest(content=content), \
                 patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
                 patch.object(evidence, 'sha', return_value='current'), \
                 patch.object(evidence, 'linked', side_effect=lambda root, name, _: root / name), \
                 self.assertRaisesRegex(RuntimeError, 'test completion: test_sail_model_transaction'):
                evidence.check_lean(self.path)

    def test_lean_required_stage_and_test_totals(self):
        self.assertEqual(len(evidence.LEAN_STAGES), 24)
        self.assertEqual(len(evidence.TEST_COUNTS), 17)
        self.assertEqual(sum(evidence.TEST_COUNTS.values()), 236)
        self.assertEqual(evidence.LEAN_STAGES[-3:], ['test_decoder_rebuilt_inputs', 'test_decoder_rebuilt_locations', 'public-decoder'])
        self.assertEqual(evidence.TEST_COUNTS['test_sail_model_transaction'], 21)

    def test_rebuilt_main_adds_all_four_groups_without_mutating_legacy(self):
        old_counts, old_stages = evidence.lean_inventory({})
        counts, stages = evidence.lean_inventory({'main_toolchain': 'rebuilt-main-v1'})
        self.assertEqual((len(stages), len(counts), sum(counts.values())), (28, 21, 287))
        self.assertEqual(stages, old_stages[:-1] + list(evidence.REBUILT_TEST_COUNTS) + ['public-decoder'])
        self.assertEqual({k: counts[k] for k in old_counts}, old_counts)
        self.assertEqual(evidence.lean_inventory({}), (old_counts, old_stages))

    def test_unknown_main_inventory_does_not_fall_back_to_legacy(self):
        for profile in (None, '', 'rebuilt-main-v2', 'legacy'):
            with self.subTest(profile=profile), self.assertRaisesRegex(RuntimeError, 'unknown main'):
                evidence.lean_inventory({'main_toolchain': profile})

    def test_rebuilt_main_cannot_reuse_a_complete_legacy_stage_list(self):
        policy, source, report = self.lean_fixture()
        policy['main_toolchain'] = 'rebuilt-main-v1'
        self.path.write_text(json.dumps(report))
        with patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
             patch.object(evidence, 'sha', return_value='current'), \
             self.assertRaisesRegex(RuntimeError, 'stage inventory'):
            evidence.check_lean(self.path)

    def test_each_rebuilt_group_requires_its_exact_completed_count(self):
        for name, count in evidence.REBUILT_TEST_COUNTS.items():
            for content in (f'Ran {count-1} tests in 0.001s\n\nOK\n',
                            f'Ran {count} tests in 0.001s\n\nFAILED (failures=1)\n'):
                policy, source, report = self.lean_fixture()
                policy['main_toolchain'] = 'rebuilt-main-v1'
                counts, stages = evidence.lean_inventory(policy)
                report['stages'] = [{'name': n, 'status': 'passed', 'exit_code': 0,
                    'log': n + '.log', 'sha256': '0' * 64} for n in stages]
                for group, total in counts.items():
                    (self.path.parent / (group + '.log')).write_text(f'Ran {total} tests in 0.001s\n\nOK\n')
                (self.path.parent / (name + '.log')).write_text(content)
                self.path.write_text(json.dumps(report))
                with self.subTest(name=name, content=content), \
                     patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
                     patch.object(evidence, 'sha', return_value='current'), \
                     patch.object(evidence, 'linked', side_effect=lambda root, name, _: root / name), \
                     self.assertRaisesRegex(RuntimeError, 'test completion: ' + name):
                    evidence.check_lean(self.path)

    def test_v1_stage_inventory_cannot_satisfy_v2(self):
        policy, source, report = self.lean_fixture()
        report['stages'] = [row for row in report['stages'] if row['name'] not in
                            ('test_decoder_rebuilt_inputs', 'test_decoder_rebuilt_locations')]
        self.path.write_text(json.dumps(report))
        with patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
             patch.object(evidence, 'sha', return_value='current'), \
             self.assertRaisesRegex(RuntimeError, 'stage inventory'):
            evidence.check_lean(self.path)

    def test_each_v2_test_group_requires_exact_success_count(self):
        for name, count in [('test_decoder_rebuilt_inputs', 15), ('test_decoder_rebuilt_locations', 13),
                            ('test_public_decoder_gate', 14)]:
            for output in [f'Ran {count-1} tests in 0.001s\n\nOK\n',
                           f'Ran {count} tests in 0.001s\n\nFAILED (failures=1)\n']:
                policy, source, report = self.lean_fixture()
                self.path.write_text(json.dumps(report))
                (self.path.parent / (name + '.log')).write_text(output)
                with self.subTest(name=name, output=output), \
                     patch.object(evidence, 'current_formal', return_value=(policy, source, {})), \
                     patch.object(evidence, 'sha', return_value='current'), \
                     patch.object(evidence, 'linked', side_effect=lambda root, name, _: root / name), \
                     self.assertRaisesRegex(RuntimeError, 'test completion: ' + name):
                    evidence.check_lean(self.path)

    def test_runtime_cannot_claim_local_copy_is_third_party(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'status': 'local_runtime_and_relocated_replay_passed',
            'release_claimed': False, 'clean_room_claimed': False, 'third_party_claimed': True}))
        with patch.object(evidence.producer, 'environment', return_value=({}, None)), \
             patch.object(evidence.producer, 'observed_environment', return_value={}), \
             self.assertRaisesRegex(RuntimeError, 'third_party'):
            evidence.check_runtime(self.path)


if __name__ == '__main__':
    unittest.main()
