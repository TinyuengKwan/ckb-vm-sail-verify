#!/usr/bin/env python3
"""Fast isolated tests of import-gate failures; not a substitute for Lean builds."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ImportGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ckb-import-gate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env.pop("ELAN_TOOLCHAIN", None)
        self.env["AENEAS_HOME"] = str(self.root / "aeneas")
        self.env["PATH"] = str(self.root / "bin") + os.pathsep + self.env["PATH"]
        self.env["PROOF_BUILD_TIMEOUT"] = "10"
        for script in ("configure_lean_project.sh", "check_lean_imports.sh"):
            self.put("scripts/" + script, (ROOT / "scripts" / script).read_text(), executable=True)
        self.put("proof/lean/compat/sail-defs-computable.patch",
                 (ROOT / "proof/lean/compat/sail-defs-computable.patch").read_text())
        for location in ("proof/lean/theorems", "aeneas/backends/lean"):
            self.put(location + "/lean-toolchain", "leanprover/lean4:v4.31.0\n")
        (self.root / "aeneas/backends/lean/Aeneas").mkdir()
        self.put("proof/lean/generated/rust/CkbVmProduction.lean", "-- fixture\n")
        self.put("proof/lean/generated/rust/lakefile.toml", 'name = "CkbVmProduction"\n')
        self.put("proof/lean/generated/sail/LeanRV64D/Step.lean", "-- fixture\n")
        self.put("proof/lean/generated/sail/LeanRV64D/Defs.lean", "\n" * 8 +
                 "open Sail\nopen Sail.ConcurrencyInterfaceV1\n\n"
                 "noncomputable section\nnamespace LeanRV64D\n\n"
                 "/-- Type quantifiers: k_a : Type -/\n")
        self.put("proof/lean/generated/sail/lakefile.toml", 'name = "Lean_RV64D"\nrev = "main"\n')
        self.package = self.root / "proof/lean/theorems/.lake/packages/Sail"
        self.package.mkdir(parents=True)
        self.git("init", "-q")
        self.git("-c", "user.name=Import Test", "-c", "user.email=test@example.invalid",
                 "commit", "-q", "--allow-empty", "-m", "fixture")
        revision = self.git("rev-parse", "HEAD").stdout.strip()
        self.put("proof/lean/expected_build_status.txt", f"status=ok\nlean_sail_rev={revision}\n")
        self.manifest = self.root / "proof/lean/theorems/lake-manifest.json"
        self.manifest.write_text(json.dumps({"packagesDir": ".lake/packages", "packages": [
            {"name": "Aeneas", "type": "path", "dir": ".lake/aeneas"},
            {"name": "Sail", "type": "git", "rev": revision},
        ]}))
        self.put("bin/lake", '''#!/usr/bin/env bash
set -eu
if [ "$1" = env ]; then
    echo "Lean (version ${TEST_LEAN_VERSION:-4.31.0}, fixture)"
    exit 0
fi
[ "$1" = build ]
[ "$LEAN_ABORT_ON_PANIC" = 1 ]
[ "$ELAN_TOOLCHAIN" = leanprover/lean4:v4.31.0 ]
if [ "${TEST_REQUIRE_REGISTERS:-0}" = 1 ]; then
    case " $* " in *" AddRegisterAxioms RegisterRegression "*) ;; *) exit 9 ;; esac
fi
if [ "${TEST_REQUIRE_STEP:-0}" = 1 ]; then
    case " $* " in *" AddStepAxioms StepRegression ProductionAdd ProductionAddWitness "*) ;; *) exit 9 ;; esac
fi
case "${TEST_BUILD_MODE:-ok}" in
    panic) echo 'info: PANIC at compiler (replayed)'; exit 0 ;;
    failure) echo 'error: unknown identifier'; exit 1 ;;
    lock-change) echo ' ' >> lake-manifest.json ;;
esac
echo 'Build completed successfully.'
''', executable=True)

    def put(self, relative, content, executable=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if executable:
            path.chmod(0o755)
        return path

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.package), *args],
                              text=True, capture_output=True, check=True)

    def run_gate(self, expected=0, args=(), **env):
        result = subprocess.run([str(self.root / "scripts/check_lean_imports.sh"), *args],
                                env=self.env | env, text=True, capture_output=True)
        if expected == 0:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_success_and_configuration_idempotence(self):
        self.assertIn("No ADD theorem", self.run_gate())
        defs = self.root / "proof/lean/generated/sail/LeanRV64D/Defs.lean"
        adapted = defs.read_bytes()
        self.assertNotIn(b"noncomputable section", adapted)
        self.run_gate()
        self.assertEqual(defs.read_bytes(), adapted)
        for side in ("rust", "sail"):
            self.assertEqual((self.root / f"proof/lean/generated/{side}/lean-toolchain").read_text(),
                             "leanprover/lean4:v4.31.0\n")

    def test_missing_model(self):
        (self.root / "proof/lean/generated/rust/CkbVmProduction.lean").unlink()
        self.assertIn("missing generated", self.run_gate(expected=1))

    def test_register_proof_targets_and_boundary(self):
        output = self.run_gate(args=("--registers",), TEST_REQUIRE_REGISTERS="1")
        self.assertIn("conditional ADD register theorem", output)
        self.assertIn("Wrapper delegation remains a premise", output)
        self.assertTrue((self.root / "proof/lean/theorems/.lake/register-build.log").exists())

    def test_register_proof_failure(self):
        self.assertIn("shared import build failed", self.run_gate(
            expected=1, args=("--registers",), TEST_BUILD_MODE="failure"))

    def test_register_proof_cached_panic(self):
        self.assertIn("compiler panic", self.run_gate(
            expected=1, args=("--registers",), TEST_BUILD_MODE="panic"))

    def test_unknown_mode(self):
        self.assertIn("usage:", self.run_gate(expected=1, args=("--full-proof",)))

    def test_step_proof_targets_and_boundary(self):
        output = self.run_gate(args=("--step",), TEST_REQUIRE_STEP="1", TEST_REQUIRE_REGISTERS="1")
        self.assertIn("conditional decoded ADD step theorem", output)
        self.assertIn("Wrapper delegation and a concrete joint Sail witness are proved", output)
        self.assertIn("general theorem retains decoded-input/Sail premises", output)
        self.assertIn("does not prove Nonempty Machine or raw-decoder correspondence", output)
        self.assertTrue((self.root / "proof/lean/theorems/.lake/step-build.log").exists())

    def test_step_proof_failure(self):
        self.assertIn("shared import build failed", self.run_gate(
            expected=1, args=("--step",), TEST_BUILD_MODE="failure"))

    def test_step_proof_cached_panic(self):
        self.assertIn("compiler panic", self.run_gate(
            expected=1, args=("--step",), TEST_BUILD_MODE="panic"))

    def test_step_proof_lock_mutation(self):
        self.assertIn("Lake changed", self.run_gate(
            expected=1, args=("--step",), TEST_BUILD_MODE="lock-change"))

    def test_step_extra_argument(self):
        self.assertIn("usage:", self.run_gate(expected=1, args=("--step", "extra")))

    def test_extra_argument(self):
        self.assertIn("usage:", self.run_gate(expected=1, args=("--registers", "extra")))

    def test_aeneas_version_mismatch(self):
        self.put("aeneas/backends/lean/lean-toolchain", "leanprover/lean4:v4.29.0\n")
        self.assertIn("Aeneas support library", self.run_gate(expected=1))

    def test_actual_compiler_mismatch(self):
        self.assertIn("unexpected compiler", self.run_gate(expected=1, TEST_LEAN_VERSION="4.29.0"))

    def test_cached_panic_with_success_exit(self):
        self.assertIn("compiler panic", self.run_gate(expected=1, TEST_BUILD_MODE="panic"))

    def test_build_failure(self):
        self.assertIn("shared import build failed", self.run_gate(expected=1, TEST_BUILD_MODE="failure"))

    def test_lock_mutation(self):
        self.assertIn("Lake changed", self.run_gate(expected=1, TEST_BUILD_MODE="lock-change"))

    def test_dependency_drift(self):
        self.put("proof/lean/theorems/.lake/packages/Sail/untracked.txt", "drift\n")
        self.assertIn("checkout is dirty", self.run_gate(expected=1))

    def test_unrecognized_generated_scope(self):
        self.put("proof/lean/generated/sail/LeanRV64D/Defs.lean", "-- changed format\n")
        self.assertIn("scope adapter does not apply", self.run_gate(expected=1))


if __name__ == "__main__":
    unittest.main()
