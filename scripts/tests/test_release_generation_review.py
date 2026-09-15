"""Synthetic records only: no generator, compiler, Git or live output scan."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_generation_review as gate


class GenerationReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='generation-review-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.review_dir = self.root / 'run', self.root / 'review'
        self.run.mkdir()
        self.review_dir.mkdir()
        self.producer_path, self.review_path = self.run / 'report.json', self.review_dir / 'report.json'
        self.digest = 'a' * 64
        self.staging = gate.recorder.PARENT + '/' + gate.recorder.PREFIX + 'fixture'
        before = {'schema_version': 1, 'kind': gate.inventory.KIND,
                  'roots': gate.inventory.roots(gate.recorder.EXTRAS),
                  'entries': dict.fromkeys(gate.inventory.roots(gate.recorder.EXTRAS)),
                  'symlinks_followed': False, 'whole_workspace_coverage_claimed': False}
        before['snapshot_sha256'] = gate.inventory.digest(before)
        expanded, _ = gate.recorder.expand_before(before, [], [self.staging.split('/')[-1]])
        after = copy.deepcopy(expanded)

        def add_file(name):
            owner = next(r for r in after['roots'] if name.startswith(r + '/'))
            parts = name.split('/')
            for length in range(len(owner.split('/')), len(parts)):
                after['entries']['/'.join(parts[:length])] = {'kind': 'directory', 'mode': 493}
            after['entries'][name] = {'kind': 'file', 'mode': 420, 'size': 1, 'sha256': self.digest}

        for name in [self.staging + '/report.json', 'target/CkbVmProduction.llbc',
                     'proof/lean/generated/rust/model.lean', 'proof/lean/generated/sail/model.lean']:
            add_file(name)
        after['snapshot_sha256'] = gate.inventory.digest({k: v for k, v in after.items() if k != 'snapshot_sha256'})
        delta = gate.inventory.compare(expanded, after)
        self.records = {'before/snapshot.json': before, 'before-expanded.json': expanded,
                        'after/snapshot.json': after, 'delta.json': delta,
                        'evidence-parent-before.json': [],
                        'evidence-parent-after.json': [self.staging.split('/')[-1]],
                        'formal-inputs-before.json': {}, 'sail-transactions.json': {}}
        source = {'schema_version': 1, 'identity_kind': 'HEAD-plus-byte-inventoried-working-tree-not-a-commit',
                  'ckb_source_baseline': {}, 'ignored_build_and_evidence_files_included': False,
                  'semantic_review_claimed': False,
                  'repositories': {r: {'files': {}} for r in gate.source_review.source.REPOS}}
        source['repositories']['.']['files']['proof/lean/audit/step-policy.json'] = {'sha256': self.digest}
        source['snapshot_sha256'] = gate.inventory.digest(source)
        self.records.update({'source-before.json': source, 'source-after.json': copy.deepcopy(source),
            'generated-identities.json': {'llbc_sha256': self.digest,
                'models': {k: {'model.lean': self.digest} for k in ['rust', 'sail']},
                'rust_provenance': {'llbc_sha256': self.digest,
                    'rebuilt_extraction': {'report': self.staging + '/report.json', 'report_sha256': self.digest}}}})
        stages = []
        for index, (name, argv) in enumerate([('inventory-before', None), *gate.COMMANDS, ('inventory-after', None)]):
            if argv is None:
                label = name.removeprefix('inventory-')
                argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                        '--out', str(self.run / label)]
                for extra in (gate.recorder.EXTRAS if label == 'before' else
                              [n for n in expanded['roots'] if n not in gate.inventory.CANONICAL_ROOTS]):
                    argv.extend(['--extra-root', extra])
            log = self.run / (name + '.log')
            log.write_text('fixture only\n')
            row = {'name': name, 'argv': argv, 'cwd': str(self.root),
                   'started_at': self.time(index * 2 + 1), 'timeout_seconds': 30,
                   'exit_code': None, 'status': 'starting', 'log': log.name}
            self.records[name + '-started.json'] = copy.deepcopy(row)
            row['pid'] = 1
            self.records[name + '-process.json'] = copy.deepcopy(row)
            row.update(exit_code=0, status='completed', finished_at=self.time(index * 2 + 2),
                       log_sha256=gate.common.sha(log))
            self.records[name + '-finished.json'] = row
            if name in dict(gate.COMMANDS):
                stages.append(copy.deepcopy(row))
        self.producer = {'schema_version': 1, 'kind': 'generation-execution-record-v1',
            'started_at': self.time(0), 'finished_at': self.time(13),
            'status': 'generation_sequence_recorded_pending_review', 'stages': stages,
            'generation_commands_completed': True, 'source_bookends_match': True,
            'policy_sha256': self.digest, 'environment_sha256': self.digest,
            'environment_values_published': False, 'new_staging_roots': [self.staging],
            'output_summary': gate.inventory.summary(after), 'changes': len(delta['changes']),
            'output_scope_is_whole_workspace': False, **dict.fromkeys(gate.recorder.FLAGS, False)}
        self.reviews = {name: {'change_sha256': gate.inventory.digest(change),
                       'category': 'directory' if change['after']['kind'] == 'directory' else 'extraction_record',
                       'rationale': 'fixture retention record only', 'evidence': None,
                       'candidate_delivery_approved': False} for name, change in delta['changes'].items()}
        self.review = {'started_at': self.time(14), 'finished_at': self.time(15),
            'status': 'all_recorded_deltas_explained_delivery_and_kernel_pending',
            'reviewed_changes': len(self.reviews),
            'categories': dict(gate.Counter(r['category'] for r in self.reviews.values())),
            **dict.fromkeys(gate.REVIEW_FLAGS, False)}
        (self.review_dir / 'review.py').write_text('raise RuntimeError("must never execute")\n')
        self.write(self.review_dir / 'facts.json', {})
        self.save()

    @staticmethod
    def time(second):
        return '2026-09-13T00:00:%02d+00:00' % second

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def save(self):
        for name, value in self.records.items():
            self.write(self.run / name, value)
        self.producer['references'] = {name: gate.common.sha(self.run / name) for name in gate.RECORD_FILES}
        self.write(self.producer_path, self.producer)
        self.write(self.review_dir / 'reviews.json', self.reviews)
        for name, key in [('reviews.json', 'reviews_sha256'), ('facts.json', 'facts_sha256'), ('review.py', 'driver_sha256')]:
            self.review[key] = gate.common.sha(self.review_dir / name)
        self.review.update(producer_report_sha256=gate.common.sha(self.producer_path),
                           delta_sha256=gate.common.sha(self.run / 'delta.json'))
        self.write(self.review_path, self.review)

    def check(self):
        return gate.check(self.producer_path, self.review_path, self.root)

    def rejects(self):
        self.save()
        with self.assertRaises((RuntimeError, KeyError, TypeError, ValueError)):
            self.check()

    def test_valid_records_are_only_historical_bindings(self):
        result = self.check()
        self.assertEqual(result['reviewed_changes'], len(self.reviews))
        for flag in [*gate.REVIEW_FLAGS, 'fresh_execution_claimed', 'review_semantics_revalidated']:
            self.assertIs(result[flag], False)

    def test_bare_pass_rejected(self):
        self.write(self.producer_path, {'status': 'PASS'})
        with self.assertRaises(RuntimeError): self.check()

    def test_missing_review_member(self):
        self.reviews.pop(next(iter(self.reviews)))
        self.rejects()

    def test_extra_review_member(self):
        self.reviews['target/extra'] = next(iter(self.reviews.values()))
        self.rejects()

    def test_wrong_change_hash(self):
        next(iter(self.reviews.values()))['change_sha256'] = 'b' * 64
        self.rejects()

    def test_review_delivery_approval(self):
        next(iter(self.reviews.values()))['candidate_delivery_approved'] = True
        self.rejects()

    def test_blank_rationale(self):
        next(iter(self.reviews.values()))['rationale'] = ' '
        self.rejects()

    def test_unknown_category(self):
        next(iter(self.reviews.values()))['category'] = 'approved'
        self.rejects()

    def test_unknown_entry_field(self):
        next(iter(self.reviews.values()))['execute'] = 'true'
        self.rejects()

    def test_wrong_category_count(self):
        self.review['categories']['directory'] += 1
        self.rejects()

    def test_boolean_count(self):
        self.review['reviewed_changes'] = True
        self.rejects()

    def test_review_assurance_upgrade(self):
        self.review['kernel_executed'] = True
        self.rejects()

    def test_producer_assurance_upgrade(self):
        self.producer['regeneration_execution_proven'] = True
        self.rejects()

    def test_missing_stage(self):
        self.producer['stages'].pop()
        self.rejects()

    def test_wrong_command(self):
        self.records['generate-rust-finished.json']['argv'] = ['true']
        self.rejects()

    def test_wrong_exit_code(self):
        self.records['generate-rust-finished.json']['exit_code'] = False
        self.rejects()

    def test_wrong_process_event(self):
        self.records['generate-rust-process.json']['pid'] = 22
        self.rejects()

    def test_out_of_order_stage(self):
        self.records['generate-rust-finished.json']['started_at'] = self.time(0)
        self.rejects()

    def test_review_before_generation(self):
        self.review['started_at'] = self.time(0)
        self.rejects()

    def test_omitted_delta(self):
        self.records['delta.json']['changes'].pop(next(iter(self.reviews)))
        self.rejects()

    def test_shrunk_scope(self):
        self.records['before/snapshot.json']['roots'].pop()
        self.rejects()

    def test_invented_initial_absence(self):
        self.records['evidence-parent-before.json'] = list(self.records['evidence-parent-after.json'])
        self.rejects()

    def test_source_bookend_mismatch(self):
        self.records['source-after.json']['snapshot_sha256'] = self.digest
        self.rejects()

    def test_wrong_policy(self):
        self.producer['policy_sha256'] = 'b' * 64
        self.rejects()

    def test_old_provenance(self):
        self.records['generated-identities.json']['rust_provenance']['rebuilt_extraction']['report'] = 'old/report.json'
        self.rejects()

    def test_wrong_llbc(self):
        self.records['generated-identities.json']['llbc_sha256'] = 'b' * 64
        self.rejects()

    def test_wrong_model(self):
        self.records['generated-identities.json']['models']['rust']['model.lean'] = 'b' * 64
        self.rejects()

    def test_stale_log(self):
        (self.run / 'generate-rust.log').write_text('changed')
        with self.assertRaises(RuntimeError): self.check()

    def test_symlink_reference(self):
        log = self.run / 'generate-rust.log'
        log.rename(self.root / 'saved-log')
        log.symlink_to(self.root / 'saved-log')
        with self.assertRaises(RuntimeError): self.check()

    def test_unsafe_reference(self):
        self.producer['references']['../outside'] = self.digest
        self.write(self.producer_path, self.producer)
        with self.assertRaises(RuntimeError): self.check()

    def test_review_wrong_producer(self):
        self.review['producer_report_sha256'] = self.digest
        self.write(self.review_path, self.review)
        with self.assertRaises(RuntimeError): self.check()

    def test_false_backup_mapping(self):
        row = next(iter(self.reviews.values()))
        row.update(category='relocated_original', evidence='target')
        self.rejects()

    def test_unsafe_support(self):
        row = next(r for r in self.reviews.values() if r['category'] != 'directory')
        row['evidence'] = '../outside'
        self.rejects()


if __name__ == '__main__':
    unittest.main()
