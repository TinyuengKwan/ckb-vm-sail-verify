"""Synthetic complete snapshots; no tools, generators or kernels executed."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_source_increment_review as gate
import release_worktree_evidence as envelope


class SourceIncrementTests(unittest.TestCase):
    @staticmethod
    def node(text, mode='100644'):
        return {'mode': mode, 'size': len(text), 'sha256': gate.source.source.digest(text.encode())}

    @staticmethod
    def seal(snapshot):
        snapshot['snapshot_sha256'] = gate.source.source.digest(gate.source.source.canonical(
            {k: v for k, v in snapshot.items() if k != 'snapshot_sha256'}))

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data))

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='source-increment-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / 'review.json'
        self.before = {'schema_version': 1, 'identity_kind': 'HEAD-plus-byte-inventoried-working-tree-not-a-commit',
            'repositories': {r: {'head': 'a' * 40, 'gitlinks': {}, 'files': {}, 'changes_from_head': {}}
                             for r in gate.source.source.REPOS}, 'ckb_source_baseline': {'fixture': True},
            'ignored_build_and_evidence_files_included': False, 'semantic_review_claimed': False}
        self.before['repositories']['.']['gitlinks'] = dict.fromkeys(gate.source.source.REPOS[1:], 'a' * 40)
        self.before['repositories']['.']['files'] = {
            'same': self.node('same'), 'changed': self.node('old'), 'gone': self.node('gone'), 'mode': self.node('mode')}
        self.seal(self.before)
        self.after = copy.deepcopy(self.before)
        files = self.after['repositories']['.']['files']
        files['changed'] = self.node('new'); files['added'] = self.node('added'); del files['gone']
        files['mode']['mode'] = '100755'
        self.seal(self.after)
        self.before_id, self.after_id = self.before['snapshot_sha256'], self.after['snapshot_sha256']
        self.changes = gate.compare(self.before, self.after)
        support = self.root / 'notes.txt'; support.write_text('synthetic provenance note; no semantic approval')
        ref = {'path': support.name, 'sha256': gate.common.sha(support)}
        self.report = {'schema_version': 1, 'kind': 'worktree-source-increment-review-v1', 'candidate': 'fixture',
            'changes': self.changes, 'reviews': {repo: {name: {
                'change_sha256': gate.source.source.digest(gate.source.source.canonical(change)), 'category': 'build',
                'rationale': 'synthetic exact change review', 'reviewed_by': 'synthetic unauthenticated reviewer',
                'evidence': [copy.deepcopy(ref)]} for name, change in changes.items()}
                for repo, changes in self.changes.items()}, 'boundaries': dict.fromkeys(gate.FLAGS, False)}
        manager = patch.object(gate.source.source, 'capture', side_effect=lambda _: copy.deepcopy(self.after))
        self.capture = manager.start(); self.addCleanup(manager.stop)
        self.save()

    def save(self):
        for label, snapshot in [('before', self.before), ('after', self.after)]:
            path = self.root / (label + '.json'); self.write(path, snapshot)
            self.report[label] = {'path': path.name, 'sha256': gate.common.sha(path)}
        self.write(self.path, self.report)

    def check(self):
        return gate.check(self.path, 'fixture', self.before_id, self.after_id, root=self.root)

    def rejects(self):
        self.save()
        with self.assertRaises((RuntimeError, KeyError, TypeError, ValueError)): self.check()

    def test_complete_increment_is_bindings_only(self):
        result = self.check()
        self.assertEqual(result['reviewed_changes'], 4)
        self.assertEqual(result['operations'], {'added': 1, 'deleted': 1, 'modified': 2})
        self.assertEqual(result['before_snapshot_sha256'], self.before_id)
        for flag in [*gate.FLAGS, 'review_semantics_revalidated', 'record_authorship_authenticated']:
            self.assertIs(result[flag], False)

    def test_unchanged_snapshot_has_empty_complete_delta(self):
        self.assertEqual(gate.compare(self.before, self.before), {r: {} for r in gate.source.source.REPOS})

    def test_mode_only_change_is_not_omitted(self):
        self.assertEqual(self.changes['.']['mode']['operation'], 'modified')
        self.assertEqual(self.changes['.']['mode']['before']['sha256'], self.changes['.']['mode']['after']['sha256'])

    def test_reversal_is_included_without_current_head_delta(self):
        # compare uses complete file inventories, never current changes_from_head.
        reverse = gate.compare(self.after, self.before)
        self.assertEqual(reverse['.']['changed']['after'], self.before['repositories']['.']['files']['changed'])
        self.assertEqual(reverse['.']['added']['operation'], 'deleted')

    def test_wrong_candidate(self):
        self.report['candidate'] = 'other'; self.rejects()

    def test_unknown_schema(self):
        self.report['schema_version'] = 2; self.rejects()

    def test_boolean_schema(self):
        self.report['schema_version'] = True; self.rejects()

    def test_assurance_upgrade(self):
        self.report['boundaries']['semantic_correctness_proven'] = True; self.rejects()

    def test_false_flag_as_zero(self):
        self.report['boundaries']['current_outputs_verified'] = 0; self.rejects()

    def test_wrong_generation_endpoint(self):
        self.before_id = 'b' * 64
        with self.assertRaisesRegex(RuntimeError, 'endpoints'): self.check()

    def test_wrong_current_endpoint(self):
        self.after_id = 'b' * 64
        with self.assertRaisesRegex(RuntimeError, 'endpoints'): self.check()

    def test_declared_delta_omits_change(self):
        del self.changes['.']['mode']; self.rejects()

    def test_declared_delta_invents_change(self):
        self.changes['.']['invented'] = copy.deepcopy(self.changes['.']['added']); self.rejects()

    def test_wrong_operation(self):
        self.changes['.']['gone']['operation'] = 'modified'; self.rejects()

    def test_omitted_review(self):
        del self.report['reviews']['.']['changed']; self.rejects()

    def test_extra_review(self):
        self.report['reviews']['.']['extra'] = copy.deepcopy(self.report['reviews']['.']['changed']); self.rejects()

    def test_wrong_change_hash(self):
        self.report['reviews']['.']['changed']['change_sha256'] = 'b' * 64; self.rejects()

    def test_blank_rationale(self):
        self.report['reviews']['.']['changed']['rationale'] = ' '; self.rejects()

    def test_blank_reviewer(self):
        self.report['reviews']['.']['changed']['reviewed_by'] = ''; self.rejects()

    def test_unknown_category(self):
        self.report['reviews']['.']['changed']['category'] = 'approved'; self.rejects()

    def test_missing_support(self):
        self.report['reviews']['.']['changed']['evidence'] = []; self.rejects()

    def test_duplicate_support(self):
        row = self.report['reviews']['.']['changed']; row['evidence'] *= 2; self.rejects()

    def test_changed_support(self):
        (self.root / 'notes.txt').write_text('changed')
        with self.assertRaises(RuntimeError): self.check()

    def test_unsafe_reference(self):
        self.report['reviews']['.']['changed']['evidence'][0]['path'] = '../outside'; self.rejects()

    def test_symlink_reference(self):
        path = self.root / 'notes.txt'; path.rename(self.root / 'saved'); path.symlink_to(self.root / 'saved')
        with self.assertRaises(RuntimeError): self.check()

    def test_bad_snapshot_digest(self):
        self.before['snapshot_sha256'] = 'b' * 64; self.rejects()

    def test_changed_git_base(self):
        self.before['repositories']['.']['head'] = 'b' * 40; self.seal(self.before); self.rejects()

    def test_changed_adopted_ckb_baseline(self):
        self.after['ckb_source_baseline'] = {'other': True}; self.seal(self.after); self.rejects()

    def test_missing_repository(self):
        del self.before['repositories']['deps/sail-riscv']; self.seal(self.before); self.rejects()

    def test_unknown_snapshot_field(self):
        self.before['skip_source'] = True; self.seal(self.before); self.rejects()

    def test_boolean_file_size(self):
        self.before['repositories']['.']['files']['same']['size'] = True; self.seal(self.before); self.rejects()

    def test_unsafe_source_member(self):
        self.before['repositories']['.']['files']['../outside'] = self.node('x'); self.seal(self.before); self.rejects()

    def test_actual_current_source_differs(self):
        self.capture.side_effect = lambda _: self.before
        with self.assertRaisesRegex(RuntimeError, 'complete current source'): self.check()

    def test_current_source_changes_during_check(self):
        self.capture.side_effect = [copy.deepcopy(self.after), copy.deepcopy(self.before)]
        with self.assertRaisesRegex(RuntimeError, 'during increment'): self.check()

    def envelope_check(self, before_identity=None):
        # Only endpoint components are fixtures. The envelope calls the real
        # increment validator, including reference and complete-delta checks.
        item = {'path': self.path.name, 'sha256': gate.common.sha(self.path)}
        path = self.root / 'envelope.json'
        self.write(path, {'schema_version': 2, 'kind': 'worktree-record-review-v2',
            'candidate': 'fixture', 'source_review': item,
            'generation': {'producer': item, 'review': item}, 'source_increment': item,
            'boundaries': dict.fromkeys(envelope.FLAGS, False)})
        with patch.object(envelope.source, 'check', return_value={'source_snapshot_sha256': self.after_id}), \
             patch.object(envelope.generation, 'check', return_value={
                 'source_snapshot_sha256': self.before_id if before_identity is None else before_identity}):
            return envelope.check(path, 'fixture', root=self.root)

    def test_envelope_runs_real_increment_without_upgrading_source_identity(self):
        result = self.envelope_check()
        self.assertEqual(result['components']['source_increment']['reviewed_changes'], 4)
        self.assertNotIn('post_generation_source_delta_review', result['remaining'])
        self.assertEqual(set(result['remaining']), {'final_delivery_scope_and_semantic_approval',
            'final_generation_kernel_and_rocq_linkage', 'current_generated_output_identity'})
        self.assertIs(result['source_snapshots_match'], False)
        self.assertIs(result['worktree_audit_closed'], False)

    def test_envelope_rejects_real_increment_with_wrong_validated_endpoint(self):
        with self.assertRaisesRegex(RuntimeError, 'endpoints'):
            self.envelope_check('b' * 64)

    def test_envelope_rejects_real_increment_with_omitted_review(self):
        del self.report['reviews']['.']['mode']
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'review membership'):
            self.envelope_check()


if __name__ == '__main__':
    unittest.main()
