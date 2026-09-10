#!/usr/bin/env python3
"""Real Git fixtures for fail-closed source identity and patch replay."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ckb_source_baseline as baseline
import check_proof


class SourceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ckb-baseline-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "deps/ckb-vm"
        self.repo.mkdir(parents=True)
        self.git("init", "-q")
        self.put("deps/ckb-vm/source.rs", "original\n")
        self.git("add", ".")
        self.git("-c", "user.name=Baseline Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "fixture")
        upstream_tree = baseline.tree(self.repo, [])
        self.put("deps/ckb-vm/source.rs", "reviewed\n")
        diff = self.git("diff", "HEAD", "--", "source.rs").decode()
        self.put("reviewed.patch", diff)
        self.put("extract.json", "{}\n")
        self.manifest = {"schema_version": 1, "baseline_id": "fixture-plus-patch",
                         "upstream_commit": self.git("rev-parse", "HEAD").decode().strip(),
                         "patch": "reviewed.patch", "patch_sha256": baseline.sha(diff.encode()),
                         "added_files": [], "upstream_tree_sha256": upstream_tree,
                         "source_tree_sha256": baseline.tree(self.repo, []),
                         "extraction_inputs": {"extract.json": baseline.sha(b"{}\n")}}
        self.put(str(baseline.MANIFEST), json.dumps(self.manifest))

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def git(self, *args):
        return baseline.git(self.repo, *args)

    def test_exact_baseline_and_idempotent_apply(self):
        evidence = baseline.check(self.root)
        self.assertEqual(evidence, baseline.check(self.root, apply=True))
        self.assertEqual(evidence["identity_kind"], "verified-source-checkout-not-binary-attestation")

    def test_clean_upstream_requires_explicit_apply(self):
        self.put("deps/ckb-vm/source.rs", "original\n")
        with self.assertRaisesRegex(RuntimeError, "source tree"):
            baseline.check(self.root)
        baseline.check(self.root, apply=True)
        self.assertEqual((self.repo / "source.rs").read_text(), "reviewed\n")

    def test_unreviewed_edit_and_partial_apply_are_rejected_without_repair(self):
        self.put("deps/ckb-vm/source.rs", "user change\n")
        for apply in (False, True):
            with self.assertRaises(RuntimeError):
                baseline.check(self.root, apply=apply)
        self.assertEqual((self.repo / "source.rs").read_text(), "user change\n")

    def test_extra_source_rejected(self):
        self.put("deps/ckb-vm/extra.rs", "extra\n")
        with self.assertRaisesRegex(RuntimeError, "additional source paths"):
            baseline.check(self.root)

    def test_missing_source_rejected(self):
        (self.repo / "source.rs").unlink()
        with self.assertRaisesRegex(RuntimeError, "missing"):
            baseline.check(self.root)

    def test_executable_mode_drift_rejected(self):
        (self.repo / "source.rs").chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "source tree"):
            baseline.check(self.root)

    def test_symlink_substitution_rejected(self):
        (self.repo / "source.rs").unlink()
        (self.repo / "source.rs").symlink_to(self.root / "extract.json")
        with self.assertRaisesRegex(RuntimeError, "non-regular"):
            baseline.check(self.root)

    def test_patch_drift_rejected(self):
        self.put("reviewed.patch", "changed\n")
        with self.assertRaisesRegex(RuntimeError, "patch hash"):
            baseline.check(self.root)

    def test_extraction_config_drift_rejected(self):
        self.put("extract.json", '{"opaque": "DefaultMachine"}\n')
        with self.assertRaisesRegex(RuntimeError, "extract.json"):
            baseline.check(self.root)

    def test_commit_drift_rejected(self):
        self.git("-c", "user.name=Baseline Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "another commit", "--allow-empty")
        with self.assertRaisesRegex(RuntimeError, "upstream commit"):
            baseline.check(self.root)

    def test_old_proof_policy_cannot_accept_new_source(self):
        with patch.object(check_proof, "ROOT", self.root):
            with self.assertRaisesRegex(RuntimeError, "theorem/policy migration pending"):
                check_proof.source_evidence({}, {}, self.root)

    def test_real_production_patch_replays_from_clean_upstream(self):
        root = self.root / "replay"
        repo = root / "deps/ckb-vm"
        repo.parent.mkdir(parents=True)
        manifest = json.loads((baseline.ROOT / baseline.MANIFEST).read_text())
        subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout",
                        str(baseline.ROOT / "deps/ckb-vm"), str(repo)], check=True)
        baseline.git(repo, "checkout", "--detach", manifest["upstream_commit"])
        for name in [str(baseline.MANIFEST), manifest["patch"], *manifest["extraction_inputs"]]:
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(baseline.ROOT / name, destination)
        with self.assertRaises(RuntimeError):
            baseline.check(root)
        evidence = baseline.check(root, apply=True)
        self.assertEqual(evidence, baseline.check(root, apply=True))
        self.assertEqual(evidence["source_tree_sha256"], manifest["source_tree_sha256"])


if __name__ == "__main__":
    unittest.main()
