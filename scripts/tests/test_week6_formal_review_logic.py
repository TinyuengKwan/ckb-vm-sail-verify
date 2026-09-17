"""Fail-closed checks of the review's representation and classification helpers."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
if (HERE / 'review.py').is_file():
    sys.path.insert(0, str(HERE))
    import review
else:
    sys.path.insert(0, str(HERE.parent))
    spec = importlib.util.spec_from_file_location('review', HERE.parent / 'week6_formal_review.py')
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    review.FORMAL = 'artifacts/boundary-check/week6-formal-fixture'
    review.RUST = 'artifacts/boundary-check/rebuilt-production-rust-fixture'
    review.PUBLIC = 'artifacts/boundary-check/public-check-fixture'
    review.ROCQ = review.FORMAL + '/rocq'
    review.CLEAN = review.PUBLIC + '/clean'


class ReviewTests(unittest.TestCase):
    def test_transaction_mapping_json_round_trip(self):
        mappings = [review.transaction_mapping('model', 'backup/previous')]
        self.assertEqual(json.loads(json.dumps(mappings)), mappings)

    def test_transaction_mapping_preserves_exact_paths(self):
        self.assertEqual(review.transaction_mapping('a/b', 'c/d'), ['a/b', 'c/d'])

    def documents(self):
        a = {'translated': {'options': {'dest_file': 'old', 'flag': False},
                             'short_names': [[1, 'a'], [2, 'b']], 'body': [7]}, 'has_errors': False}
        b = copy.deepcopy(a)
        b['translated']['options']['dest_file'] = 'new'
        b['translated']['short_names'].reverse()
        return a, b

    def compare(self, a, b):
        return review.llbc_difference(json.dumps(a).encode(), json.dumps(b).encode(), 'old', 'new')

    def test_exact_permutation(self):
        self.assertEqual(self.compare(*self.documents())['short_name_rows'], 2)

    def test_changed_row_rejected(self):
        a, b = self.documents(); b['translated']['short_names'][0][1] = 'different'
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def test_duplicate_rows_rejected(self):
        a, b = self.documents()
        a['translated']['short_names'] = [[1, 'a'], [1, 'a']]
        b['translated']['short_names'] = [[1, 'a'], [1, 'a']]
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def test_body_difference_rejected(self):
        a, b = self.documents(); b['translated']['body'] = [8]
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def test_option_difference_rejected(self):
        a, b = self.documents(); b['translated']['options']['flag'] = True
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def test_wrong_destination_rejected(self):
        a, b = self.documents(); b['translated']['options']['dest_file'] = 'other'
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def test_top_level_error_flag_rejected(self):
        a, b = self.documents(); b['has_errors'] = True
        with self.assertRaises(RuntimeError): self.compare(a, b)

    def node(self, name, *, kind='file', operation='added', bindings=None):
        return review.classify(name, {'operation': operation, 'after': {'kind': kind}}, bindings or {}, [])

    def test_known_cache(self):
        self.assertEqual(self.node(review.PUBLIC + '/cargo-target/debug/a.o')['category'], 'cargo_build_cache')

    def test_unknown_producer_root_file_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/unreviewed.lean')

    def test_unknown_registry_source_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/cargo/registry/src/new/lib.rs')

    def test_unknown_symlink_in_cache_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/cargo-target/link', kind='symlink')

    def test_unbound_modified_cache_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/cargo-target/a', operation='modified')

    def test_explicit_binding_precedes_cache(self):
        n = review.PUBLIC + '/cargo-target/a'
        self.assertEqual(self.node(n, bindings={n: {'category': 'specific'}})['category'], 'specific')

    def test_scope_prefix_escape_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '-other/cargo-target/a')

    def test_path_traversal_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/cargo-target/../a')

    def test_unknown_rocq_source_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.ROCQ + '/rust/unreviewed.v')

    def test_operation_inventory_allows_only_explained_modifications(self):
        def changes(modified, extra_added=('artifacts/boundary-check/x/report.json',), deleted=()):
            rows = {name: {'operation': 'modified', 'after': {'kind': 'file'}} for name in modified}
            rows.update({name: {'operation': 'added', 'after': {'kind': 'file'}} for name in extra_added})
            rows.update({name: {'operation': 'deleted', 'after': None} for name in deleted})
            return rows
        mandatory = set(review.MANDATORY_MODIFICATIONS)
        self.assertEqual(review.check_operations(changes(mandatory)), mandatory)
        # A cold Sail SMT memo cache may be rewritten in a fresh environment.
        self.assertEqual(review.check_operations(changes(mandatory | {review.SOLVER_MEMO_CACHE})),
                         mandatory | {review.SOLVER_MEMO_CACHE})
        with self.assertRaisesRegex(RuntimeError, 'unexplained formal modifications'):
            review.check_operations(changes(mandatory | {'proof/lean/theorems/Other.lean'}))
        with self.assertRaisesRegex(RuntimeError, 'expected formal modifications absent'):
            review.check_operations(changes(mandatory - {'target/CkbVmProduction.llbc'}))
        with self.assertRaisesRegex(RuntimeError, 'unexpected formal operation inventory'):
            review.check_operations(changes(mandatory, deleted=('proof/lean/generated/sail/x.lean',)))
        with self.assertRaisesRegex(RuntimeError, 'unexpected formal operation inventory'):
            review.check_operations({})

    def test_sail_backups_required_exactly_when_outputs_pre_existed(self):
        paths = {'source': 'proof/rocq/generated/sail', 'destination': 'proof/rocq/generated/installed',
                 'generation_backup': 'proof/rocq/generated/.sail-generation-x',
                 'installation_backup': 'proof/rocq/generated/.sail-install-y'}
        before_warm = {'proof/rocq/generated/sail/rv64d.v': {}, 'proof/rocq/generated/installed/rv64d.v': {}}
        mappings, first = review.sail_backup_expectations(
            paths, {'old_source_saved': True, 'old_destination_saved': True}, before_warm)
        self.assertEqual(mappings, [['proof/rocq/generated/sail', 'proof/rocq/generated/.sail-generation-x/previous'],
                                    ['proof/rocq/generated/installed', 'proof/rocq/generated/.sail-install-y/previous']])
        self.assertEqual(first, [])
        mappings, first = review.sail_backup_expectations(
            paths, {'old_source_saved': False, 'old_destination_saved': False}, {'target/x.llbc': {}})
        self.assertEqual(mappings, [])
        self.assertEqual([row['first_generation'] for row in first], [True, True])
        with self.assertRaisesRegex(RuntimeError, 'missing Sail backup for pre-existing source'):
            review.sail_backup_expectations(paths, {'old_source_saved': False, 'old_destination_saved': True}, before_warm)
        with self.assertRaisesRegex(RuntimeError, 'absent before the run'):
            review.sail_backup_expectations(paths, {'old_source_saved': True, 'old_destination_saved': True}, {})
        with self.assertRaisesRegex(RuntimeError, 'flag shape'):
            review.sail_backup_expectations(paths, {'old_source_saved': None, 'old_destination_saved': False}, {})

    def test_unbound_deletion_rejected(self):
        with self.assertRaises(RuntimeError):
            review.classify('x', {'operation': 'deleted', 'after': None}, {}, [])

    def test_cache_directory_tag_is_metadata(self):
        self.assertEqual(self.node(review.PUBLIC + '/cargo/registry/CACHEDIR.TAG')['category'], 'cargo_metadata')

    def test_unknown_registry_root_file_rejected(self):
        with self.assertRaises(RuntimeError): self.node(review.PUBLIC + '/cargo/registry/unreviewed.rs')

    def test_unbound_directory_modification_rejected(self):
        with self.assertRaises(RuntimeError): self.node('directory', kind='directory', operation='modified')

    def summary(self):
        facts = {'reviewed_changes': 1, 'category_counts': {'directory': 1},
                 'formal_report_sha256': 'f', 'delta_sha256': 'd'}
        report = {'schema_version': 1, 'status': 'all_recorded_formal_deltas_explained_final_scope_pending',
                  'reviewed_changes': 1, 'categories': {'directory': 1},
                  'formal_report_sha256': 'f', 'delta_sha256': 'd', **review.FLAGS}
        return report, facts, {'x': {'category': 'directory'}}

    def test_matching_summary(self):
        review.validate_summary(*self.summary())

    def test_summary_count_rejected(self):
        report, facts, rows = self.summary(); report['reviewed_changes'] = 2
        with self.assertRaises(RuntimeError): review.validate_summary(report, facts, rows)

    def test_summary_approval_rejected(self):
        report, facts, rows = self.summary(); report['candidate_approval_claimed'] = True
        with self.assertRaises(RuntimeError): review.validate_summary(report, facts, rows)

    def test_summary_other_delta_rejected(self):
        report, facts, rows = self.summary(); report['delta_sha256'] = 'other'
        with self.assertRaises(RuntimeError): review.validate_summary(report, facts, rows)


if __name__ == '__main__':
    unittest.main()
