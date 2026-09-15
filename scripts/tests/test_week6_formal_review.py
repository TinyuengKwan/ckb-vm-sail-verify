#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SPEC = importlib.util.spec_from_file_location(
    'week6_formal_review', HERE.parent / 'week6_formal_review.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DriverTests(unittest.TestCase):
    def test_output_must_be_new_named_direct_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / 'artifacts/boundary-check'
            parent.mkdir(parents=True)
            accepted = MODULE.new_output(parent / 'week6-formal-review-fixture', root=root)
            self.assertTrue(accepted.is_dir())
            for path in [parent / 'other', parent / 'week6-formal-review-',
                         root / 'week6-formal-review-outside', accepted]:
                with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, 'new Week6 formal review'):
                    MODULE.new_output(path, root=root)

    def test_copy_preserves_bytes_and_rejects_existing_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source', root / 'target'
            source.write_bytes(b'reviewer\n')
            MODULE.copy_regular(source, target)
            self.assertEqual(target.read_bytes(), b'reviewer\n')
            with self.assertRaises(FileExistsError):
                MODULE.copy_regular(source, target)

    def test_copy_rejects_symlink_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_bytes(b'reviewer\n')
            (root / 'link').symlink_to(root / 'source')
            with self.assertRaisesRegex(RuntimeError, 'linked'):
                MODULE.copy_regular(root / 'link', root / 'target')

    def test_prepare_rejects_hash_before_creating_output(self):
        formal = MODULE.ROOT / 'artifacts/boundary-check/formal-final-kfncD8ln/report.json'
        out = MODULE.ROOT / 'artifacts/boundary-check/week6-formal-review-unit-never-created'
        self.assertFalse(out.exists())
        with self.assertRaisesRegex(RuntimeError, 'input differs'):
            MODULE.prepare(formal, '0' * 64, out)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
