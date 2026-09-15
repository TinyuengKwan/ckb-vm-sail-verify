"""Synthetic inventory projections, not a filesystem or generator execution."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
if (HERE / 'projection.py').is_file():
    sys.path.insert(0, str(HERE))
    from projection import inventory, project
else:
    sys.path.insert(0, str(HERE.parent))
    from week6_output_projection import inventory, project


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.selected = inventory.roots(['artifacts/formal/rocq'])
        self.observed = {'schema_version': 1, 'kind': inventory.KIND,
            'roots': inventory.roots(['artifacts/formal', 'artifacts/new']),
            'entries': {r: None for r in inventory.CANONICAL_ROOTS},
            'symlinks_followed': False, 'whole_workspace_coverage_claimed': False}
        self.observed['entries'].update({r: {'kind': 'directory', 'mode': 0o755}
            for r in ['artifacts/formal', 'artifacts/formal/rocq', 'artifacts/formal/rocq-other', 'artifacts/new']})
        self.observed['entries']['artifacts/formal/rocq/file'] = {
            'kind': 'file', 'mode': 0o644, 'size': 1, 'sha256': 'a' * 64}
        self.seal()

    def seal(self):
        self.observed['snapshot_sha256'] = inventory.digest({k: v for k, v in self.observed.items() if k != 'snapshot_sha256'})

    def test_exact_scope_and_entries(self):
        result = project(self.observed, self.selected)
        self.assertEqual(result['roots'], self.selected)
        self.assertEqual(set(result['entries']), set(inventory.CANONICAL_ROOTS) |
                         {'artifacts/formal/rocq', 'artifacts/formal/rocq/file'})

    def test_current_missing_child_is_absent(self):
        for name in ['artifacts/formal/rocq', 'artifacts/formal/rocq/file']: del self.observed['entries'][name]
        self.seal()
        self.assertIsNone(project(self.observed, self.selected)['entries']['artifacts/formal/rocq'])

    def test_outside_observation_cannot_be_invented_absent(self):
        with self.assertRaisesRegex(RuntimeError, 'not covered'):
            project(self.observed, inventory.roots(['artifacts/unobserved']))

    def test_sibling_prefix_not_coverage(self):
        with self.assertRaisesRegex(RuntimeError, 'not covered'):
            project(self.observed, inventory.roots(['artifacts/formal-other']))

    def test_parent_scope_cannot_be_invented(self):
        with self.assertRaisesRegex(RuntimeError, 'not covered'):
            project(self.observed, inventory.roots(['artifacts']))

    def test_mandatory_root_cannot_be_omitted(self):
        with self.assertRaises(RuntimeError): project(self.observed, [r for r in self.selected if r != 'build'])

    def test_symlink_ancestor_is_not_invented_absence(self):
        self.observed['entries']['artifacts/formal/link'] = {
            'kind': 'symlink', 'mode': 0o777, 'target': '/unobserved'}
        self.seal()
        with self.assertRaisesRegex(RuntimeError, 'ancestor'):
            project(self.observed, inventory.roots(['artifacts/formal/link/child']))

    def test_file_ancestor_is_not_invented_absence(self):
        self.observed['entries']['artifacts/formal/leaf'] = {
            'kind': 'file', 'mode': 0o644, 'size': 0, 'sha256': 'a' * 64}
        self.seal()
        with self.assertRaisesRegex(RuntimeError, 'ancestor'):
            project(self.observed, inventory.roots(['artifacts/formal/leaf/child']))

    def test_bad_input_digest(self):
        self.observed['snapshot_sha256'] = 'b' * 64
        with self.assertRaises(RuntimeError): project(self.observed, self.selected)

    def test_input_not_mutated(self):
        old = copy.deepcopy(self.observed)
        project(self.observed, self.selected)
        self.assertEqual(old, self.observed)

    def test_no_whole_workspace_upgrade(self):
        self.assertIs(project(self.observed, self.selected)['whole_workspace_coverage_claimed'], False)

    def test_identical_projection_has_no_delta(self):
        result = project(self.observed, self.selected)
        self.assertEqual(inventory.compare(result, copy.deepcopy(result))['changes'], {})


if __name__ == '__main__': unittest.main()
