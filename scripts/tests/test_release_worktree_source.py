"""Real temporary Git inventories; synthetic review records, never release evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_worktree_source as review
import audit_release as gate


class WorktreeSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='worktree-source-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for repo in review.source.REPOS:
            directory = self.root / repo
            directory.mkdir(parents=True, exist_ok=True)
            self.git(directory, 'init', '-q')
            for name in ('source.txt', 'removed.txt', 'mode.txt'):
                (directory / name).write_text('fixture original\n')
            (directory / '.gitignore').write_text('evidence/\n')
            self.commit(directory)
        self.commit(self.root)
        manager = patch.object(review.source.baseline, 'check', return_value={'synthetic_fixture': True})
        manager.start()
        self.addCleanup(manager.stop)
        (self.root / 'source.txt').write_text('fixture changed\n')
        (self.root / 'removed.txt').unlink()
        (self.root / 'mode.txt').chmod(0o755)
        (self.root / 'added.txt').write_text('fixture added\n')
        (self.root / 'deps/ckb-vm/source.txt').write_text('fixture CKB delta\n')
        self.out = self.root / 'evidence'
        self.out.mkdir()
        self.note = self.out / 'note.txt'
        self.note.write_text('Synthetic fixture rationale only; no actual candidate approval.\n')
        self.snapshot = review.source.capture(self.root)
        snap = self.out / 'snapshot.json'
        snap.write_text(json.dumps(self.snapshot))
        reviews = {}
        for repo, info in self.snapshot['repositories'].items():
            reviews[repo] = {name: {'change_sha256': review.source.digest(review.source.canonical(delta)),
                'category': 'test', 'rationale': 'Synthetic fixture change.', 'reviewed_by': 'fixture-only',
                'evidence': [self.ref(self.note)]} for name, delta in info['changes_from_head'].items()}
        self.report = {'schema_version': 1, 'kind': 'worktree-source-review-v1',
            'candidate': 'synthetic-candidate', 'snapshot': self.ref(snap), 'reviews': reviews,
            'boundaries': dict.fromkeys(review.BOUNDARIES, False)}
        self.path = self.out / 'report.json'

    def git(self, directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args], stderr=subprocess.PIPE)

    def commit(self, directory):
        self.git(directory, 'add', '--all')
        self.git(directory, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'synthetic fixture only')

    def ref(self, path):
        return {'path': path.relative_to(self.root).as_posix(), 'sha256': review.common.sha(path)}

    def check(self):
        self.path.write_text(json.dumps(self.report))
        return review.check(self.path, 'synthetic-candidate', root=self.root)

    def row(self):
        return self.report['reviews']['.']['source.txt']

    def test_complete_inventory_checks_add_delete_mode_and_submodule_delta(self):
        result = self.check()
        self.assertEqual(result['reviewed_head_changes'], 5)
        self.assertEqual(result['reference_files'], 2)
        self.assertEqual(result['source_snapshot_sha256'], self.snapshot['snapshot_sha256'])
        self.assertEqual(result['source_files'], sum(len(r['files']) for r in self.snapshot['repositories'].values()))
        self.assertFalse(result['worktree_audit_closed'])
        self.assertFalse(result['reviewer_identity_authenticated'])
        self.assertEqual(result['remaining'], review.REMAINING)
        for name in review.BOUNDARIES: self.assertIs(result[name], False)

    def test_wrong_candidate_rejected_before_capture(self):
        self.report['candidate'] = 'another-candidate'
        with patch.object(review.source, 'capture') as capture, self.assertRaisesRegex(RuntimeError, 'candidate'):
            self.check()
        capture.assert_not_called()

    def test_schema_boolean_and_unknown_fields_rejected(self):
        for key, value in [('schema_version', True), ('kind', 'PASS'), ('approve', True)]:
            original = copy.deepcopy(self.report)
            self.report[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.check()
            self.report = original

    def test_assurance_upgrades_and_integer_false_rejected(self):
        for name in review.BOUNDARIES:
            for value in (True, 0, None):
                self.report['boundaries'][name] = value
                with self.subTest(name=name, value=value), self.assertRaisesRegex(RuntimeError, 'approval'):
                    self.check()
            self.report['boundaries'][name] = False

    def test_missing_or_extra_repository_rejected(self):
        original = copy.deepcopy(self.report['reviews'])
        for name in ['deps/ckb-vm', 'extra']:
            self.report['reviews'] = copy.deepcopy(original)
            if name in original: del self.report['reviews'][name]
            else: self.report['reviews'][name] = {}
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'repository'): self.check()

    def test_omitted_deletion_review_rejected(self):
        del self.report['reviews']['.']['removed.txt']
        with self.assertRaisesRegex(RuntimeError, 'change review inventory'): self.check()

    def test_extra_review_rejected(self):
        self.report['reviews']['.']['not-a-change'] = copy.deepcopy(self.row())
        with self.assertRaisesRegex(RuntimeError, 'change review inventory'): self.check()

    def test_reused_review_for_other_bytes_rejected(self):
        self.row()['change_sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'different source change'): self.check()

    def test_missing_rationale_reviewer_or_evidence_rejected(self):
        for name, value in [('rationale', ' '), ('reviewed_by', ''), ('evidence', []), ('category', 'PASS')]:
            old = copy.deepcopy(self.row()[name])
            self.row()[name] = value
            with self.subTest(name=name), self.assertRaises(RuntimeError): self.check()
            self.row()[name] = old

    def test_duplicate_evidence_rejected(self):
        self.row()['evidence'] *= 2
        with self.assertRaisesRegex(RuntimeError, 'duplicate'): self.check()

    def test_wrong_evidence_hash_rejected(self):
        self.row()['evidence'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): self.check()

    def test_symlink_evidence_rejected(self):
        link = self.out / 'link.txt'
        link.symlink_to(self.note)
        self.row()['evidence'][0]['path'] = 'evidence/link.txt'
        with self.assertRaisesRegex(RuntimeError, 'symlink'): self.check()

    def test_path_escape_rejected(self):
        self.row()['evidence'][0]['path'] = '../note.txt'
        with self.assertRaisesRegex(RuntimeError, 'unsafe'): self.check()

    def test_snapshot_cannot_reduce_file_inventory_even_with_updated_digest(self):
        snap = copy.deepcopy(self.snapshot)
        del snap['repositories']['.']['files']['source.txt']
        snap['snapshot_sha256'] = review.source.digest(review.source.canonical(
            {key: value for key, value in snap.items() if key != 'snapshot_sha256'}))
        path = self.out / 'snapshot.json'
        path.write_text(json.dumps(snap))
        self.report['snapshot'] = self.ref(path)
        with self.assertRaisesRegex(RuntimeError, 'complete source inventory'): self.check()

    def test_source_bytes_drift_rejected(self):
        (self.root / 'source.txt').write_text('later change')
        with self.assertRaisesRegex(RuntimeError, 'complete source inventory'): self.check()

    def test_source_mode_drift_rejected(self):
        (self.root / 'mode.txt').chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'complete source inventory'): self.check()

    def test_new_untracked_source_rejected(self):
        (self.root / 'unreviewed.txt').write_text('new source')
        with self.assertRaisesRegex(RuntimeError, 'complete source inventory'): self.check()

    def test_submodule_head_drift_rejected(self):
        self.commit(self.root / 'deps/ckb-vm')
        with self.assertRaisesRegex(RuntimeError, 'revision drift'): self.check()

    def test_changed_source_during_validation_rejected(self):
        changed = copy.deepcopy(self.snapshot)
        changed['snapshot_sha256'] = '0' * 64
        with patch.object(review.source, 'capture', side_effect=[self.snapshot, changed]), \
             self.assertRaisesRegex(RuntimeError, 'source changed during'): self.check()

    def test_changed_nested_reference_rejected_at_bookend(self):
        original = review.common.linked
        visits = 0
        def mutate(root, name, digest):
            nonlocal visits
            path = original(root, name, digest)
            if name == 'evidence/note.txt':
                visits += 1
                # Last of five review references, before the final hash sweep.
                if visits == 5: self.note.write_text('changed after validation')
            return path
        with patch.object(review.common, 'linked', side_effect=mutate), \
             self.assertRaisesRegex(RuntimeError, 'hash differs'): self.check()

    def test_changed_top_level_report_rejected_at_bookend(self):
        original = review.source.capture
        def mutate(root):
            value = original(root)
            self.path.write_text('{}')
            return value
        with patch.object(review.source, 'capture', side_effect=mutate), \
             self.assertRaisesRegex(RuntimeError, 'report changed during'): self.check()

    def test_ignored_outputs_never_gain_source_audit_coverage(self):
        (self.out / 'unreviewed-generated-model').write_text('ignored output')
        result = self.check()
        self.assertIs(result['generated_outputs_audited'], False)
        self.assertIn('ignored_generated_output_inventory_and_regeneration_deltas', result['remaining'])

    def test_duplicate_json_keys_rejected(self):
        self.path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(RuntimeError, 'duplicate JSON'):
            review.check(self.path, 'synthetic-candidate', root=self.root)

    def test_real_source_checker_through_aggregate_remains_incomplete(self):
        self.path.write_text(json.dumps(self.report))
        manifest = {'schema_version': 1, 'candidate': 'synthetic-candidate',
            'pins': {'fixture_pin': review.common.sha(self.root / 'source.txt')},
            'evidence': dict.fromkeys(gate.SLOTS)}
        manifest['evidence']['worktree_audit'] = self.ref(self.path)
        with patch.object(gate, 'ROOT', self.root), \
             patch.object(gate, 'PINS', {'fixture_pin': 'source.txt'}):
            result, code = gate.aggregate(manifest)
        self.assertEqual(code, 2)
        self.assertEqual(result['checks']['worktree_audit']['status'], 'incomplete')
        self.assertEqual(result['checks']['worktree_audit']['details']['reviewed_head_changes'], 5)
        self.assertEqual(set(result['outstanding']), set(gate.SLOTS))
        self.assertIs(result['week6_closed'], False)

    def test_real_source_checker_rejects_candidate_mix_in_aggregate(self):
        self.path.write_text(json.dumps(self.report))
        manifest = {'schema_version': 1, 'candidate': 'wrong-candidate',
            'pins': {'fixture_pin': review.common.sha(self.root / 'source.txt')},
            'evidence': dict.fromkeys(gate.SLOTS)}
        manifest['evidence']['worktree_audit'] = self.ref(self.path)
        with patch.object(gate, 'ROOT', self.root), \
             patch.object(gate, 'PINS', {'fixture_pin': 'source.txt'}):
            result, code = gate.aggregate(manifest)
        self.assertEqual(code, 1)
        self.assertIn('different candidate', result['checks']['worktree_audit']['reason'])


if __name__ == '__main__':
    unittest.main()
