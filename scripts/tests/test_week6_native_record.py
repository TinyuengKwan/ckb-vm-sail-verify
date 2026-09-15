#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
SPEC = importlib.util.spec_from_file_location(
    "week6_native_record", HERE.parent / "week6_native_record.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeRecordTests(unittest.TestCase):
    def installation(self, root):
        files = {}
        for name in ("cargo", "rustc", "rustdoc"):
            path = root / "toolchains" / MODULE.STABLE / "bin" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
            path.chmod(0o755)
            files[path.relative_to(root).as_posix()] = {"sha256": MODULE.evidence.sha(path)}
        return {"private_homes": {"RUSTUP_HOME": str(root)},
                "installed_closures": {"rustup": {"files": files}}}

    def test_native_environment_is_explicit_and_nonmutating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = self.installation(root)
            original = {"RUSTUP_HOME": str(root), "RUSTUP_TOOLCHAIN": "nightly",
                        "PATH": "/usr/bin", "CARGO_TARGET_DIR": "shared"}
            env, binaries = MODULE.native_environment(original, installation, root / "out")
            self.assertEqual(original["RUSTUP_TOOLCHAIN"], "nightly")
            self.assertEqual(env["RUSTUP_TOOLCHAIN"], MODULE.STABLE)
            self.assertNotIn("CARGO_TARGET_DIR", env)
            self.assertEqual(set(binaries), {"rustc", "cargo", "rustdoc"})

    def test_native_binary_drift_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = self.installation(root)
            path = root / "toolchains" / MODULE.STABLE / "bin/rustc"
            path.write_text("drift")
            with self.assertRaisesRegex(RuntimeError, "binary differs"):
                MODULE.native_environment({"RUSTUP_HOME": str(root), "PATH": "/usr/bin"},
                                          installation, root / "out")

    def test_summary_contract(self):
        value = {"runtime": {"cases": 33, "replays": 33,
                             "mutations": {"applied": 194, "skipped": 4}},
                 "rust_tests": {"test_binaries": 7, "tests_passed": 78, "engine_tests": 10,
                                "doctest_targets": 5, "doctests_passed": 0,
                                "ignored": 0, "filtered_out": 0}}
        self.assertEqual(MODULE.parse_check(MODULE.MARKER + json.dumps(value)), value)
        for text in ["{}", MODULE.MARKER + "{}", MODULE.MARKER + json.dumps(value) + "\n" +
                     MODULE.MARKER + json.dumps(value)]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                MODULE.parse_check(text)
        changed = copy.deepcopy(value)
        changed["runtime"]["cases"] = 32
        with self.assertRaisesRegex(RuntimeError, "corpus inventory"):
            MODULE.parse_check(MODULE.MARKER + json.dumps(changed))

    def test_output_must_be_new_named_direct_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "artifacts/boundary-check"
            parent.mkdir(parents=True)
            accepted = MODULE.new_output(parent / "week6-native-fixture", root)
            self.assertTrue(accepted.is_dir())
            for path in [parent / "other", parent / "week6-native-",
                         root / "week6-native-outside", accepted]:
                with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "new Week6 native"):
                    MODULE.new_output(path, root)


if __name__ == "__main__":
    unittest.main()
