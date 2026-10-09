#!/usr/bin/env python3
"""Forbidden phrases, broken links and the coverage vocabulary over a fixture tree."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import public_claims as claims

ROOT = Path(__file__).resolve().parents[2]


class PublicClaimsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="public-claims-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "docs/release").mkdir(parents=True)
        (self.root / "docs/release/policy.json").write_text(json.dumps({
            "public_claims": {"documents": ["README.md", "docs/coverage.md"],
                              "coverage_status_values": ["runtime-only", "conditional", "unsupported"],
                              "forbidden": ["Week6 is closed."]},
            "clean_room": {"generated_roots": ["proof/lean/generated"]}}))
        (self.root / "README.md").write_text("# Fixture\n\nSee [coverage](docs/coverage.md) and [gen](proof/lean/generated/X.lean)"
                                             " and [evidence](artifacts/run/report.json).\n")
        (self.root / "docs/coverage.md").write_text(
            "| Instruction family | V | R | E | T | M | Current status |\n|---|---|---|---|---|---|---|\n"
            "| ADD | 2 | a | b | c | d | runtime-only |\n| MUL | 2 | a | b | c | d | unsupported |\n")

    def test_passes_and_counts_evidence_and_generated_links(self):
        result = claims.check(self.root)
        self.assertEqual(result["documents"]["README.md"], {"links_checked": 1, "evidence_links_not_shipped_with_source": 2})
        self.assertEqual(result["documents"]["docs/coverage.md"]["coverage_rows"], 2)

    def test_forbidden_phrase_broken_link_and_bad_status_fail(self):
        readme = self.root / "README.md"
        readme.write_text(readme.read_text() + "\nWeek6 is closed.\n")
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            claims.check(self.root)
        readme.write_text("[missing](docs/nope.md)\n")
        with self.assertRaisesRegex(RuntimeError, "broken link"):
            claims.check(self.root)
        readme.write_text("[escape](../../etc/passwd)\n")
        with self.assertRaisesRegex(RuntimeError, "escaping"):
            claims.check(self.root)
        readme.write_text("ok\n")
        coverage = self.root / "docs/coverage.md"
        coverage.write_text(coverage.read_text().replace("unsupported", "proved"))
        with self.assertRaisesRegex(RuntimeError, "vocabulary"):
            claims.check(self.root)

    def test_code_blocks_are_not_scanned_for_links(self):
        (self.root / "README.md").write_text("```\n[x](docs/nope.md)\n```\n")
        self.assertEqual(claims.check(self.root)["documents"]["README.md"]["links_checked"], 0)

    def test_repository_documents_pass(self):
        result = claims.check(ROOT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(set(result["documents"]), set(claims.load_policy(ROOT)["documents"]))


if __name__ == "__main__":
    unittest.main()
