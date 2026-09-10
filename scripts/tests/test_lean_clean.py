#!/usr/bin/env python3
"""Tests of clean source copying and import isolation, not a substitute for compilation."""
from pathlib import Path
import tempfile
import unittest

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_lean_clean as clean


class CleanBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ckb-clean-guard-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "fresh"
        self.compiler = self.root / "compiler"
        self.project.mkdir()

    def test_only_fresh_paths_and_compiler_standard_library_allowed(self):
        paths = str(self.project / "lib") + ":" + str(self.compiler / "lib/lean")
        self.assertEqual(len(clean.check_paths(paths, self.project, self.compiler)), 2)

    def test_external_cached_support_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "external compiled dependency"):
            clean.check_paths(str(self.root / "old/.lake/build/lib/lean"), self.project, self.compiler)

    def test_sibling_prefix_is_not_inside_clean_tree(self):
        with self.assertRaisesRegex(RuntimeError, "external compiled dependency"):
            clean.check_paths(str(self.root / "fresh-old/lib"), self.project, self.compiler)

    def test_symlink_escape_rejected(self):
        (self.project / "lib").symlink_to(self.root / "old")
        with self.assertRaisesRegex(RuntimeError, "external compiled dependency"):
            clean.check_paths(str(self.project / "lib"), self.project, self.compiler)

    def test_empty_path_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "empty"):
            clean.check_paths("", self.project, self.compiler)

    def test_source_copy_excludes_cached_modules_and_build_metadata(self):
        source = self.root / "source"
        (source / ".lake/build").mkdir(parents=True)
        (source / ".lake/build/Old.olean").write_text("old")
        (source / "Old.olean").write_text("old")
        (source / "Old.ilean").write_text("old")
        (source / "New.lean").write_text("theorem good : True := True.intro\n")
        destination = self.project / "copy"
        clean.source_copy(source, destination)
        self.assertEqual(sorted(p.name for p in destination.iterdir()), ["New.lean"])
        self.assertEqual((source / "New.lean").read_bytes(), (destination / "New.lean").read_bytes())


if __name__ == "__main__":
    unittest.main()
