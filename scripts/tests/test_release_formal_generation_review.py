"""Synthetic bound records, never executing producer/reviewer code or a kernel."""
from collections import Counter
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_formal_generation_review as gate
import release_worktree_evidence as envelope
import audit_release


class FormalReviewTests(unittest.TestCase):
    @staticmethod
    def time(second):
        return (datetime(2026, 9, 13, tzinfo=timezone.utc) + timedelta(seconds=second)).isoformat()

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def event(self, destination, name, argv, start, end, log):
        (destination / (name + '.log')).write_text(log)
        row = {'name': name, 'argv': argv, 'cwd': str(self.root), 'started_at': self.time(start),
               'timeout_seconds': 600, 'exit_code': None, 'status': 'starting', 'log': name + '.log'}
        self.write(destination / (name + '-started.json'), row)
        row['pid'] = 123
        self.write(destination / (name + '-process.json'), row)
        row.update(exit_code=0, status='completed', finished_at=self.time(end),
                   log_sha256=gate.common.sha(destination / row['log']))
        self.write(destination / (name + '-finished.json'), row)
        return row

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='formal-review-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.review_dir = self.root / 'run', self.root / 'review'
        self.run.mkdir(); self.review_dir.mkdir()
        self.producer_path, self.review_path = self.run / 'report.json', self.review_dir / 'report.json'
        self.digest = 'a' * 64
        self.added = ['artifacts/boundary-check/public-check-fixture',
                      'artifacts/boundary-check/rebuilt-production-rust-fixture']
        extras = ['artifacts/rebuilt-main-runtime', 'run/rocq']
        before = {'schema_version': 1, 'kind': gate.inventory.KIND, 'roots': gate.inventory.roots(extras),
                  'entries': dict.fromkeys(gate.inventory.roots(extras)), 'symlinks_followed': False,
                  'whole_workspace_coverage_claimed': False}
        before['snapshot_sha256'] = gate.inventory.digest(before)
        expanded, _ = gate.expand(before, [], sorted(Path(n).name for n in self.added))
        self.after = copy.deepcopy(expanded)
        self.generated = {'models': {k: {'model.lean': self.digest} for k in ['rust', 'sail']},
                          'llbc_sha256': self.digest, 'sail_config_sha256': self.digest,
                          'rust_provenance': {'llbc_sha256': self.digest, 'rebuilt_extraction': {
                              'report': self.added[1] + '/report.json', 'report_sha256': self.digest}}}
        self.main = {'status': 'passed', 'policy_sha256': self.digest, 'generated': copy.deepcopy(self.generated)}
        self.rocq = {**copy.deepcopy(self.main), 'verdict': 'NO-GO', 'extra_proof_coverage': False}
        self.write(self.run / 'rocq/report.json', self.rocq)

        def add_file(name, digest):
            owner = next(r for r in self.after['roots'] if name.startswith(r + '/'))
            parts = name.split('/')
            for length in range(len(owner.split('/')), len(parts)):
                self.after['entries']['/'.join(parts[:length])] = {'kind': 'directory', 'mode': 493}
            self.after['entries'][name] = {'kind': 'file', 'mode': 420, 'size': 1, 'sha256': digest}

        for name in [self.added[1] + '/report.json', 'target/CkbVmProduction.llbc',
                     'proof/lean/generated/rust/model.lean', 'proof/lean/generated/sail/model.lean']:
            add_file(name, self.digest)
        add_file('run/rocq/report.json', gate.common.sha(self.run / 'rocq/report.json'))
        self.after['snapshot_sha256'] = gate.inventory.digest({k: v for k, v in self.after.items() if k != 'snapshot_sha256'})
        self.delta = gate.inventory.compare(expanded, self.after)
        source = {'schema_version': 1, 'identity_kind': 'HEAD-plus-byte-inventoried-working-tree-not-a-commit',
                  'ckb_source_baseline': {}, 'ignored_build_and_evidence_files_included': False,
                  'semantic_review_claimed': False,
                  'repositories': {r: {'files': {}} for r in gate.base.source_review.source.REPOS}}
        source['repositories']['.']['files']['proof/lean/audit/step-policy.json'] = {'sha256': self.digest}
        source['snapshot_sha256'] = gate.inventory.digest(source)
        acceptance = {'lean': {'fresh_kernel_run_claimed': False}, 'rocq': {'extra_proof_coverage': False}}
        stages = []
        for index, name in enumerate(gate.STAGES):
            if name.startswith('inventory-'):
                label = name.removeprefix('inventory-')
                argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                        '--out', str(self.run / label)]
                for extra in (extras if label == 'before' else
                              [n for n in expanded['roots'] if n not in gate.inventory.CANONICAL_ROOTS]):
                    argv.extend(['--extra-root', extra])
            elif name == 'independent-acceptance':
                argv = ['/usr/bin/python3', '-B', '-O', '-c', gate.ACCEPTANCE_CODE,
                        str(self.run / 'main/report.json'), str(self.run / 'rocq/report.json')]
            else:
                argv = ['/usr/bin/make', name] + (['BACKEND=lean'] if name == 'proof-check' else [])
            stages.append(self.event(self.run, name, argv, 2 * index + 1, 2 * index + 2,
                          'FORMAL_FINAL_CHECK_JSON=' + json.dumps(acceptance) if name == 'independent-acceptance' else 'fixture'))
        self.records = {name: gate.common.read(self.run / name) for name in gate.RECORD_FILES if name.endswith('.json')
                        and (self.run / name).exists()}
        archive = {'files': {}, 'unscanned_historical_directories': [], 'nested_historical_builds_copied': False}
        self.records.update({'before/snapshot.json': before, 'before-expanded.json': expanded,
            'after/snapshot.json': self.after, 'delta.json': self.delta,
            'evidence-parent-before.json': [], 'evidence-parent-after.json': sorted(Path(n).name for n in self.added),
            'source-before.json': source, 'source-after.json': copy.deepcopy(source),
            'formal-inputs-before.json': {'local_sources': {}},
            'generated-after-main.json': self.generated, 'generated-after-rocq.json': copy.deepcopy(self.generated),
            'main/report.json': self.main, 'previous-main/report.json': {},
            'main-archive.json': copy.deepcopy(archive), 'previous-main-archive.json': copy.deepcopy(archive),
            'started.json': {'schema_version': 1, 'kind': 'formal-execution-with-output-delta-v1',
                'started_at': self.time(0), 'status': 'running', 'stages': [], 'errors': [],
                'kernel_and_rocq_records_validated': False, **dict.fromkeys(gate.PRODUCER_FLAGS, False)}})
        (self.run / 'run.py').write_text('raise RuntimeError("never execute")\n')
        self.producer = {'schema_version': 1, 'kind': 'formal-execution-with-output-delta-v1',
            'started_at': self.time(0), 'finished_at': self.time(11),
            'status': 'formal_execution_and_delta_recorded_pending_worktree_review', 'stages': stages, 'errors': [],
            'kernel_and_rocq_records_validated': True, 'policy_sha256': self.digest,
            'source_snapshot_sha256': source['snapshot_sha256'], 'environment_sha256': self.digest,
            'new_evidence_roots': self.added, 'output_summary': gate.inventory.summary(self.after),
            'output_changes': len(self.delta['changes']), 'main_records': self.records['main-archive.json'],
            'previous_main_records': self.records['previous-main-archive.json'], 'formal_acceptance': acceptance,
            **dict.fromkeys(gate.PRODUCER_FLAGS, False)}
        self.rows = {name: {'change_sha256': gate.inventory.digest(change),
                     'category': 'directory' if change['after']['kind'] == 'directory' else 'execution_or_audit_record',
                     'evidence': 'synthetic bound record only', 'candidate_delivery_approved': False}
                     for name, change in self.delta['changes'].items()}
        self.facts = {'formal_source_snapshot_sha256': source['snapshot_sha256'],
                      'category_counts': dict(Counter(r['category'] for r in self.rows.values())),
                      'reviewed_changes': len(self.rows),
                      'operation_counts': dict(Counter(c['operation'] for c in self.delta['changes'].values()))}
        (self.review_dir / 'review.py').write_text('raise RuntimeError("never execute")\n')
        (self.review_dir / 'test_review.py').write_text('raise RuntimeError("never execute")\n')
        for mode, options, start in [('ordinary', [], 12), ('optimized', ['-O'], 14)]:
            self.event(self.review_dir, 'test-review-' + mode,
                       ['/usr/bin/python3', '-B', *options, str(self.review_dir / 'test_review.py')],
                       start, start + 1, 'Ran 26 tests in 0.01s\n\nOK\n')
        names = ['test_review.py', *[f'test-review-{m}{s}' for m in ['ordinary', 'optimized']
                                   for s in ['-finished.json', '.log']]]
        self.review = {'schema_version': 1, 'started_at': self.time(17), 'finished_at': self.time(18),
            'status': 'all_recorded_formal_deltas_explained_final_scope_pending',
            'reviewed_changes': len(self.rows), 'categories': copy.deepcopy(self.facts['category_counts']),
            'tests': {'tests_per_mode': 26, 'modes': ['ordinary', 'optimized'],
                      'files': {n: gate.common.sha(self.review_dir / n) for n in names}},
            **dict.fromkeys(gate.REVIEW_FLAGS, False)}
        self.save()

    def save(self):
        for name, value in self.records.items(): self.write(self.run / name, value)
        for label, key in [('main', 'main_records'), ('previous-main', 'previous_main_records')]:
            self.producer[key]['files'] = {'report.json': gate.common.sha(self.run / label / 'report.json')}
            self.write(self.run / (label + '-archive.json'), self.producer[key])
        names = gate.RECORD_FILES | {'main/report.json', 'previous-main/report.json'}
        self.producer['record_files'] = {n: gate.common.sha(self.run / n) for n in names}
        self.write(self.producer_path, self.producer)
        self.facts.update(formal_report_sha256=gate.common.sha(self.producer_path),
                          delta_sha256=gate.common.sha(self.run / 'delta.json'))
        self.write(self.review_dir / 'facts.json', self.facts)
        self.write(self.review_dir / 'reviews.json', self.rows)
        self.review.update(formal_report_sha256=self.facts['formal_report_sha256'], delta_sha256=self.facts['delta_sha256'])
        for name, key in [('facts.json', 'facts_sha256'), ('reviews.json', 'reviews_sha256'), ('review.py', 'reviewer_sha256')]:
            self.review[key] = gate.common.sha(self.review_dir / name)
        self.write(self.review_path, self.review)
        for name, start, end, log in [('record-review', 16, 19, json.dumps(self.review)),
                                     ('check-review', 20, 21, json.dumps({
                                         'status': 'independently_recomputed_record_bindings_match',
                                         'changes': len(self.rows), **dict.fromkeys(gate.REVIEW_FLAGS, False)}))]:
            self.event(self.review_dir, name, ['/usr/bin/python3', '-B', '-O', str(self.review_dir / 'review.py')]
                       + (['--check'] if name == 'check-review' else []), start, end, log)

    def check(self):
        return gate.base.check(self.producer_path, self.review_path, self.root)

    def rejects(self):
        self.save()
        with self.assertRaises((RuntimeError, KeyError, TypeError, ValueError)): self.check()

    def test_valid_formal_records_are_only_partial_bindings(self):
        result = self.check()
        self.assertEqual(result['reviewed_changes'], len(self.rows))
        self.assertTrue(result['recorded_main_rocq_generated_identity_matches'])
        for flag in [*gate.REVIEW_FLAGS, 'review_semantics_revalidated', 'record_authorship_authenticated', 'fresh_execution_claimed']:
            self.assertIs(result[flag], False)
        self.assertEqual(result['formal_reports'], {
            'lean': {'path': 'run/main/report.json', 'sha256': gate.common.sha(self.run / 'main/report.json')},
            'rocq': {'path': 'run/rocq/report.json', 'sha256': gate.common.sha(self.run / 'rocq/report.json')}})

    def test_producer_failure(self):
        self.producer['errors'] = ['failed']; self.rejects()

    def test_boolean_schema(self):
        self.producer['schema_version'] = True; self.rejects()

    def test_producer_approval(self):
        self.producer['worktree_audit_closed'] = True; self.rejects()

    def test_incomplete_kernel_record(self):
        self.producer['kernel_and_rocq_records_validated'] = False; self.rejects()

    def test_missing_stage(self):
        self.producer['stages'].pop(); self.rejects()

    def test_wrong_command(self):
        self.records['proof-check-finished.json']['argv'] = ['true']; self.rejects()

    def test_boolean_exit(self):
        self.records['proof-check-finished.json']['exit_code'] = False; self.rejects()

    def test_bad_process(self):
        self.records['proof-check-process.json']['pid'] = 456; self.rejects()

    def test_acceptance_summary_differs(self):
        self.producer['formal_acceptance']['lean']['fresh_kernel_run_claimed'] = True; self.rejects()

    def test_stage_out_of_order(self):
        self.records['proof-spike-finished.json']['started_at'] = self.time(0); self.rejects()

    def test_missing_delta_member(self):
        self.delta['changes'].pop(next(iter(self.rows))); self.rejects()

    def test_shrunk_initial_scope(self):
        self.records['before/snapshot.json']['roots'].pop(); self.rejects()

    def test_invented_new_root(self):
        self.records['evidence-parent-before.json'] = self.records['evidence-parent-after.json']; self.rejects()

    def test_changed_source(self):
        self.records['source-after.json']['snapshot_sha256'] = self.digest; self.rejects()

    def test_wrong_policy(self):
        self.producer['policy_sha256'] = 'b' * 64; self.rejects()

    def test_wrong_main_identity(self):
        self.main['generated']['llbc_sha256'] = 'b' * 64; self.rejects()

    def test_wrong_model_output(self):
        self.generated['models']['rust']['model.lean'] = 'b' * 64; self.rejects()

    def test_wrong_extraction(self):
        self.generated['rust_provenance']['rebuilt_extraction']['report'] = 'old/report.json'; self.rejects()

    def test_missing_review_member(self):
        self.rows.pop(next(iter(self.rows))); self.rejects()

    def test_extra_review_member(self):
        self.rows['target/extra'] = next(iter(self.rows.values())); self.rejects()

    def test_wrong_change_hash(self):
        next(iter(self.rows.values()))['change_sha256'] = 'b' * 64; self.rejects()

    def test_unknown_category(self):
        next(iter(self.rows.values()))['category'] = 'approved'; self.rejects()

    def test_approved_review_row(self):
        next(iter(self.rows.values()))['candidate_delivery_approved'] = True; self.rejects()

    def test_empty_support(self):
        next(iter(self.rows.values()))['evidence'] = ''; self.rejects()

    def test_false_retained_original(self):
        next(iter(self.rows.values())).update(category='retained_original', evidence='target/missing'); self.rejects()

    def test_review_assurance_upgrade(self):
        self.review['clean_room_claimed'] = True; self.rejects()

    def test_review_count_boolean(self):
        self.review['reviewed_changes'] = True; self.rejects()

    def test_facts_count(self):
        self.facts['reviewed_changes'] += 1; self.rejects()

    def test_wrong_test_count(self):
        self.review['tests']['tests_per_mode'] += 1; self.rejects()

    def test_missing_test_mode(self):
        self.review['tests']['modes'].pop(); self.rejects()

    def test_review_before_execution(self):
        self.review['started_at'] = self.time(0); self.rejects()

    def test_changed_check_log(self):
        (self.review_dir / 'check-review.log').write_text('PASS')
        with self.assertRaises(RuntimeError): self.check()

    def test_failed_second_process(self):
        path = self.review_dir / 'check-review-finished.json'
        row = gate.common.read(path); row.update(exit_code=1, status='command_failed'); self.write(path, row)
        with self.assertRaises(RuntimeError): self.check()

    def test_symbolic_reference(self):
        path = self.run / 'run.py'; path.rename(self.root / 'saved.py'); path.symlink_to(self.root / 'saved.py')
        with self.assertRaises(RuntimeError): self.check()

    def test_missing_required_reference(self):
        del self.producer['record_files']['run.py']; self.write(self.producer_path, self.producer)
        with self.assertRaises(RuntimeError): self.check()

    def test_unknown_reference(self):
        self.producer['record_files']['../outside'] = self.digest; self.write(self.producer_path, self.producer)
        with self.assertRaises(RuntimeError): self.check()

    def test_wrong_startup_summary(self):
        self.records['started.json']['kernel_and_rocq_records_validated'] = True; self.rejects()

    def test_bad_environment_digest(self):
        self.producer['environment_sha256'] = 'not a digest'; self.rejects()

    def envelope(self):
        def ref(path):
            return {'path': path.relative_to(self.root).as_posix(), 'sha256': gate.common.sha(path)}
        path = self.root / 'envelope.json'
        self.write(path, {'schema_version': 1, 'kind': 'worktree-record-review-v1', 'candidate': 'fixture',
                         'source_review': None, 'generation': {'producer': ref(self.producer_path),
                         'review': ref(self.review_path)}, 'boundaries': dict.fromkeys(envelope.FLAGS, False)})
        return path

    def test_real_envelope_keeps_current_output_and_final_linkage_pending(self):
        result = envelope.check(self.envelope(), 'fixture', root=self.root)
        self.assertEqual(result['components']['generation']['reviewed_changes'], len(self.rows))
        self.assertIn('current_complete_source_review', result['remaining'])
        self.assertIn('post_generation_source_delta_review', result['remaining'])
        self.assertIn('final_generation_kernel_and_rocq_linkage', result['remaining'])
        self.assertIn('current_generated_output_identity', result['remaining'])
        self.assertFalse(result['worktree_audit_closed'])

    def test_real_aggregate_cannot_promote_formal_review_to_release_success(self):
        path = self.envelope()
        for name in audit_release.PINS.values():
            file = self.root / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('fixture')
        manifest = {'schema_version': 1, 'candidate': 'fixture',
                    'pins': {k: gate.common.sha(self.root / v) for k, v in audit_release.PINS.items()},
                    'evidence': dict.fromkeys(audit_release.SLOTS)}
        manifest['evidence']['worktree_audit'] = {'path': path.name, 'sha256': gate.common.sha(path)}
        with patch.object(audit_release, 'ROOT', self.root):
            result, code = audit_release.aggregate(manifest)
        self.assertEqual(code, 2)
        self.assertEqual(result['checks']['worktree_audit']['status'], 'incomplete')
        self.assertFalse(result['release_claimed'])
        self.assertFalse(result['week6_closed'])

    def test_real_formal_record_and_envelope_join_exact_checker_references(self):
        details = envelope.check(self.envelope(), 'fixture', root=self.root)
        reports = details['components']['generation']['formal_reports']
        checked = {name: {'status': 'verified_existing_evidence', 'reference': ref} for name, ref in reports.items()}
        result = envelope.connect_formal_execution(details, checked, root=self.root)
        self.assertNotIn(envelope.EXECUTION_LINKAGE, result['remaining'])
        self.assertIn('current_complete_source_review', result['remaining'])
        self.assertFalse(result['worktree_audit_closed'])

    def test_real_formal_record_rejects_another_accepted_execution(self):
        details = envelope.check(self.envelope(), 'fixture', root=self.root)
        reports = details['components']['generation']['formal_reports']
        checked = {name: {'status': 'verified_existing_evidence', 'reference': ref} for name, ref in reports.items()}
        checked['lean']['reference'] = {'path': 'run/previous-main/report.json',
                                     'sha256': gate.common.sha(self.run / 'previous-main/report.json')}
        with self.assertRaisesRegex(RuntimeError, 'different accepted lean'):
            envelope.connect_formal_execution(details, checked, root=self.root)


if __name__ == '__main__':
    unittest.main()
