#!/usr/bin/env python3
"""Real Lean negative tests. Run `make proof-step` first.

Only temporary copies are mutated; generated inputs and workspace proofs stay intact.
These checks test rejection. Concrete contract satisfiability is separately proved
in SailContractWitness; this test suite does not certify translator correctness.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_proof


PROJECT = Path(__file__).resolve().parents[2] / "proof/lean/theorems"


class StepKernelNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lake = shutil.which("lake") or str(Path.home() / ".elan/bin/lake")
        if not (PROJECT / ".lake/build/lib/lean/StepRegression.olean").is_file():
            raise RuntimeError("Run make proof-step before these real-kernel tests")
        prefix = subprocess.check_output(
            [lake, "env", "lean", "--print-prefix"], cwd=PROJECT, text=True).strip()
        cls.lean = str(Path(prefix) / "bin/lean")
        cls.env = os.environ.copy()
        cls.env["LEAN_PATH"] = subprocess.check_output(
            [lake, "env", "printenv", "LEAN_PATH"], cwd=PROJECT, text=True).strip()
        cls.env["LEAN_ABORT_ON_PANIC"] = "1"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ckb-step-negative-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def copy_mutated(self, name, before, after):
        original = (PROJECT / name).read_text()
        self.assertEqual(original.count(before), 1, "Mutation anchor must be unique")
        path = self.directory / name
        path.write_text(original.replace(before, after, 1))
        return path

    def compile(self, path, *, success=False, override=False):
        env = self.env.copy()
        if override:
            env["LEAN_PATH"] = str(self.directory) + os.pathsep + env["LEAN_PATH"]
        result = subprocess.run(
            [self.lean, "--root=" + str(self.directory), str(path),
             "-o", str(path.with_suffix(".olean"))],
            cwd=PROJECT, env=env, text=True, capture_output=True,
            timeout=300 if path.name == "SailContractWitness.lean" else 120)
        output = result.stdout + result.stderr
        self.assertNotIn("PANIC", output)
        self.assertNotIn("unknown module prefix", output)
        if success:
            self.assertEqual(result.returncode, 0, output)
        else:
            self.assertNotEqual(result.returncode, 0, "Invalid theorem unexpectedly compiled")
            self.assertIn("error:", output, output)
        return output

    def test_rust_wrong_instruction_size(self):
        path = self.copy_mutated("RustDispatch.lean",
            "def stageCore (c : Core) : Core := {c with next_pc := addValue c.pc 4#u64}",
            "def stageCore (c : Core) : Core := {c with next_pc := addValue c.pc 2#u64}")
        self.compile(path)

    def test_rust_missing_pc_commit(self):
        path = self.copy_mutated("RustDispatch.lean",
            "def commitCore (c : Core) : Core := {c with pc := c.next_pc}",
            "def commitCore (c : Core) : Core := {c with pc := c.pc}")
        self.compile(path)

    def test_sail_wrong_pc_staging(self):
        path = self.copy_mutated("SailDispatch.lean",
            "putReg s .nextPC (p + 4)", "putReg s .nextPC (p + 2)")
        self.compile(path)

    def test_sail_missing_pc_commit(self):
        path = self.copy_mutated("SailRetirement.lean",
            "let committed := putReg (putGpr (stageSail ready p) rd v) .PC (p + 4)",
            "let committed := putReg (putGpr (stageSail ready p) rd v) .PC p")
        self.compile(path)

    def test_main_theorem_axiom_pollution(self):
        original = (PROJECT / "AddStep.lean").read_text()
        anchor = " := by\n  obtain ⟨m', hr, hm', hv⟩"
        self.assertEqual(original.count(anchor), 1)
        signature = original.split(anchor, 1)[0]
        signature = signature.replace("noncomputable section",
            "noncomputable section\naxiom injected_pollution : (P : Prop) → P", 1)
        path = self.directory / "AddStep.lean"
        path.write_text(signature + " := by\n  exact injected_pollution _\n\nend\nend AddStep\n")
        # The polluted theorem can be accepted only because it assumes a new axiom.
        self.compile(path, success=True)
        audit = self.directory / "AddStepAxioms.lean"
        audit.write_text((PROJECT / "AddStepAxioms.lean").read_text())
        output = self.compile(audit, override=True)
        self.assertIn("injected_pollution", output)
        self.assertIn("#guard_msgs", output)

    def test_strengthened_premise_without_axiom_pollution(self):
        path = self.copy_mutated("ProductionAdd.lean",
            "(stepNo : Nat) (exitWait : Bool) :",
            "(unjustified : False) (stepNo : Nat) (exitWait : Bool) :")
        # An unused False premise weakens the result without adding any axiom.
        self.compile(path, success=True)
        guard = self.directory / "AddStepAxioms.lean"
        guard.write_text((PROJECT / "AddStepAxioms.lean").read_text())
        self.compile(guard, success=True, override=True)
        export = self.directory / "ExportStepAudit.lean"
        export.write_text((PROJECT.parent / "audit/ExportStepAudit.lean").read_text())
        audit = check_proof.parse_audit(self.compile(export, success=True, override=True))
        import json
        policy = json.loads(check_proof.POLICY.read_text())
        with self.assertRaisesRegex(RuntimeError, "signature / contract"):
            check_proof.check_audit(audit, policy)

    def test_wrapper_view_cannot_discard_pc(self):
        self.compile(self.copy_mutated("WrapperContracts.lean",
            "def view (m : Machine) : Core := m.inner",
            "def view (m : Machine) : Core := {m.inner with pc := 0#u64}"))

    def test_wrapper_empty_validity_rejected(self):
        self.compile(self.copy_mutated("WrapperContracts.lean",
            "def valid (_ : Machine) : Prop := True", "def valid (_ : Machine) : Prop := False"))

    def test_wrapper_missing_register_write_rejected(self):
        self.compile(self.copy_mutated("WrapperContracts.lean",
            "refine ⟨{m with inner := c}, ?_, valid_all _, ?_⟩",
            "refine ⟨m, ?_, valid_all _, ?_⟩"))

    def test_wrapper_missing_pc_staging_rejected(self):
        self.compile(self.copy_mutated("WrapperContracts.lean",
            "refine ⟨{m with inner := {view m with next_pc := p}}, ?_, valid_all _, ?_⟩",
            "refine ⟨m, ?_, valid_all _, ?_⟩"))

    def test_wrapper_missing_pc_commit_rejected(self):
        self.compile(self.copy_mutated("WrapperContracts.lean",
            "refine ⟨{m with inner := commitCore (view m)}, ?_, valid_all _, ?_⟩",
            "refine ⟨m, ?_, valid_all _, ?_⟩"))

    def test_production_final_axiom_pollution_rejected(self):
        original = (PROJECT / "ProductionAdd.lean").read_text()
        anchor = " := by\n  obtain ⟨m', s', hr, hs, _, hrel', hpc, hnext, hsnext, hgpr, hmem, hsmem⟩"
        self.assertEqual(original.count(anchor), 1)
        signature = original.split(anchor, 1)[0].replace("noncomputable section",
            "noncomputable section\naxiom injected_pollution : (P : Prop) → P", 1)
        path = self.directory / "ProductionAdd.lean"
        path.write_text(signature + " := by\n  exact injected_pollution _\nend\nend ProductionAdd\n")
        self.compile(path, success=True)
        export = self.directory / "ExportStepAudit.lean"
        export.write_text((PROJECT.parent / "audit/ExportStepAudit.lean").read_text())
        audit = check_proof.parse_audit(self.compile(export, success=True, override=True))
        import json
        with self.assertRaisesRegex(RuntimeError, "axiom set"):
            check_proof.check_audit(audit, json.loads(check_proof.POLICY.read_text()))

    def test_witness_wrong_fetched_byte_rejected(self):
        # Alter the fixture, not its independently stated memory observation lemma.
        original = (PROJECT / "SailContractWitness.lean").read_text()
        anchor = "|>.insert 0x80000002 0x20"
        self.assertEqual(original.count(anchor), 2)
        path = self.directory / "SailContractWitness.lean"
        # Mutate both definitions consistently: rejection must come from fetch,
        # not from a mismatch between the fixture and initial_mem's bookkeeping.
        path.write_text(original.replace(anchor, "|>.insert 0x80000002 0x21"))
        output = self.compile(path)
        import re
        first = original[:original.index("theorem fetch_add")].count("\n") + 1
        last = original[:original.index("theorem put_existing")].count("\n") + 1
        errors = re.findall(re.escape(path.name) + r":(\d+):\d+: error:", output)
        self.assertTrue(any(first <= int(line) < last for line in errors), output)

    def test_witness_missing_decode_csr_rejected(self):
        self.compile(self.copy_mutated("SailContractWitness.lean",
            "      |>.insert .mseccfg 0\n", ""))

    def test_witness_nonexecutable_memory_rejected(self):
        self.compile(self.copy_mutated("SailContractWitness.lean",
            "      executable := true", "      executable := false"))

    def test_witness_missing_retirement_counter_rejected(self):
        self.compile(self.copy_mutated("SailContractWitness.lean",
            "      |>.insert .minstret 0\n", ""))

    def test_witness_mismatched_rust_registers_rejected(self):
        self.compile(self.copy_mutated("ProductionAddWitness.lean",
            "[0#u64, 5#u64, 7#u64]", "[0#u64, 6#u64, 7#u64]"))

    def test_witness_false_premise_rejected_by_type_audit(self):
        path = self.copy_mutated("ProductionAddWitness.lean",
            "theorem paired_step (seed : Machine) :",
            "theorem paired_step (seed : Machine) (unjustified : False) :")
        self.compile(path, success=True)
        export = self.directory / "ExportStepAudit.lean"
        export.write_text((PROJECT.parent / "audit/ExportStepAudit.lean").read_text())
        audit = check_proof.parse_audit(self.compile(export, success=True, override=True))
        import json
        with self.assertRaisesRegex(RuntimeError, "signature / contract"):
            check_proof.check_audit(audit, json.loads(check_proof.POLICY.read_text()))


if __name__ == "__main__":
    unittest.main()
