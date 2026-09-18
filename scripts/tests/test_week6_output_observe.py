#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SPEC = importlib.util.spec_from_file_location(
    'week6_output_observe', HERE.parent / 'week6_output_observe.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObservationTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / 'artifacts/boundary-check').mkdir(parents=True)
        refs = {}
        for name in ['formal', 'source', 'manifest']:
            path = root / (name + '.json')
            path.write_text('{}\n')
            refs[name] = {'path': path.name, 'sha256': MODULE.common.sha(path)}
        value = {'schema_version': 1, 'kind': 'week6-current-output-input-v1',
                 'candidate': 'a' * 40, 'formal_report': refs['formal'],
                 'current_source_review': refs['source'], 'current_manifest': refs['manifest']}
        inputs = root / 'inputs.json'
        inputs.write_text(json.dumps(value) + '\n')
        return temporary, root, inputs, value

    def test_input_references_are_hash_checked(self):
        temporary, root, inputs, _ = self.fixture()
        try:
            value, paths = MODULE.read_inputs(inputs, root=root)
            self.assertEqual(value['candidate'], 'a' * 40)
            self.assertEqual(set(paths), {'formal_report', 'current_source_review', 'current_manifest'})
        finally:
            temporary.cleanup()

    def test_changed_input_reference_rejected(self):
        temporary, root, inputs, value = self.fixture()
        try:
            value['formal_report']['sha256'] = '0' * 64
            inputs.write_text(json.dumps(value) + '\n')
            with self.assertRaises(RuntimeError):
                MODULE.read_inputs(inputs, root=root)
        finally:
            temporary.cleanup()

    def test_output_must_be_new_named_direct_child(self):
        temporary, root, _, _ = self.fixture()
        try:
            parent = root / 'artifacts/boundary-check'
            accepted = MODULE.new_output(parent / 'week6-output-observation-fixture', root=root)
            self.assertTrue(accepted.is_dir())
            for path in [parent / 'other', parent / 'week6-output-observation-',
                         root / 'week6-output-observation-outside', accepted]:
                with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, 'new Week6 output'):
                    MODULE.new_output(path, root=root)
        finally:
            temporary.cleanup()

    def test_scope_gate_accepts_ancestor_coverage_like_the_projection(self):
        formal = 'artifacts/boundary-check/week6-formal-clean-room'
        native = 'artifacts/boundary-check/week6-native-clean-room'
        historical = [formal + '/rocq', 'artifacts/rebuilt-main-runtime', 'proof/lean/generated', 'target']
        selected = [formal, native, 'artifacts/rebuilt-main-runtime', 'proof/lean/generated', 'target']
        self.assertTrue(MODULE.scope_covers(historical, selected, [formal, native]))
        self.assertFalse(MODULE.scope_covers(historical + ['artifacts/boundary-check/other'], selected, [formal, native]))
        self.assertFalse(MODULE.scope_covers(historical, [formal, 'artifacts/rebuilt-main-runtime',
                                                         'proof/lean/generated', 'target'], [formal, native]))
        # A prefix match must be on a path boundary, not a string prefix.
        self.assertFalse(MODULE.scope_covers([formal + '-other/x'], [formal, native], [formal, native]))

    def test_copy_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'source').write_text('source\n')
            (root / 'link').symlink_to(root / 'source')
            with self.assertRaisesRegex(RuntimeError, 'linked'):
                MODULE.copy_regular(root / 'link', root / 'target')


if __name__ == '__main__':
    unittest.main()
