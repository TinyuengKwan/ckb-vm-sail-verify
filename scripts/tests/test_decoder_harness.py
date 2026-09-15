"""Relocatable public Rust harness identity and no-overwrite tests."""
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_harness as harness


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="decoder-harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "checkout"
        (self.checkout / "deps/ckb-vm").mkdir(parents=True)
        self.destination = self.root / "build/outer"
        self.assets = self.root / "assets"
        for relative in [harness.SOURCE, harness.LOCK]:
            destination = self.assets / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(harness.ROOT / relative, destination)
        self.original_root = harness.ROOT
        root_patch = patch.object(harness, "ROOT", self.assets)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        baseline_patch = patch.object(harness.baseline, "check", return_value={"baseline_id": "fixture"})
        self.check_baseline = baseline_patch.start()
        self.addCleanup(baseline_patch.stop)

    def test_materialized_inputs_keep_reviewed_source_and_lock(self):
        result = harness.prepare(self.destination, self.checkout)
        self.assertEqual(result["files"]["lib.rs"], harness.SOURCE_SHA256)
        self.assertEqual(result["files"]["Cargo.lock"], harness.LOCK_SHA256)
        self.assertEqual(harness.verify(self.destination, self.checkout), result)
        self.check_baseline.assert_called_with(self.checkout)

    def test_manifest_points_only_to_the_requested_relative_checkout(self):
        manifest = tomllib.loads(harness.manifest(self.destination, self.checkout))
        dependency = manifest["dependencies"]["ckb-vm"]["path"]
        self.assertFalse(Path(dependency).is_absolute())
        self.assertEqual((self.destination / dependency).resolve(), self.checkout / "deps/ckb-vm")
        self.assertNotIn(str(self.original_root), harness.manifest(self.destination, self.checkout))
        self.assertEqual(manifest["package"]["name"], "outer-decoder-probe")

    def test_quoted_paths_are_valid_toml(self):
        checkout = self.root / 'checkout with "quotes" and space'
        value = tomllib.loads(harness.manifest(self.destination, checkout))
        self.assertEqual((self.destination / value["dependencies"]["ckb-vm"]["path"]).resolve(),
                         checkout / "deps/ckb-vm")

    def test_existing_output_is_not_overwritten(self):
        self.destination.mkdir(parents=True)
        (self.destination / "old.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            harness.prepare(self.destination, self.checkout)
        self.assertEqual((self.destination / "old.txt").read_text(), "keep")

    def test_unverified_baseline_fails_before_creating_output(self):
        self.check_baseline.side_effect = RuntimeError("source mismatch")
        with self.assertRaisesRegex(RuntimeError, "source mismatch"):
            harness.prepare(self.destination, self.checkout)
        self.assertFalse(self.destination.exists())

    def test_changed_source_or_lock_fails_before_creating_output(self):
        for relative in [harness.SOURCE, harness.LOCK]:
            with self.subTest(relative=relative):
                path = self.assets / relative
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaises(RuntimeError):
                    harness.prepare(self.destination, self.checkout)
                self.assertFalse(self.destination.exists())
                path.write_bytes(original)

    def test_changed_materialized_source_or_lock_is_rejected(self):
        harness.prepare(self.destination, self.checkout)
        for name in ["lib.rs", "Cargo.lock"]:
            with self.subTest(name=name):
                path = self.destination / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaises(RuntimeError):
                    harness.verify(self.destination, self.checkout)
                path.write_bytes(original)

    def test_redirected_manifest_is_rejected(self):
        harness.prepare(self.destination, self.checkout)
        (self.destination / "Cargo.toml").write_text(harness.manifest(self.destination, self.root / "other"))
        with self.assertRaisesRegex(RuntimeError, "Cargo manifest"):
            harness.verify(self.destination, self.checkout)

    def test_added_cargo_option_is_rejected(self):
        harness.prepare(self.destination, self.checkout)
        path = self.destination / "Cargo.toml"
        path.write_text(path.read_text() + '\n[profile.dev]\noverflow-checks = false\n')
        with self.assertRaisesRegex(RuntimeError, "Cargo manifest"):
            harness.verify(self.destination, self.checkout)

    def test_changed_production_source_after_preparation_is_rejected(self):
        harness.prepare(self.destination, self.checkout)
        self.check_baseline.side_effect = RuntimeError("source changed")
        with self.assertRaisesRegex(RuntimeError, "source changed"):
            harness.verify(self.destination, self.checkout)


if __name__ == "__main__":
    unittest.main()
