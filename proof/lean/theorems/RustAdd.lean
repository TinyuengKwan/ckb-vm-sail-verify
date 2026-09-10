import StateRel
import ExtractedConstants

namespace AddRegister
open Aeneas.Std AddBoundary ckb_vm_sail_extract
noncomputable section
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000

@[simp] theorem rustReg_val (i : Reg) : (rustReg i).val = i.val := by
  simp [rustReg, Usize.ofNat, UScalar.ofNat]

theorem rustReg_bound (i : Reg) : rustReg i < 32#usize := by
  change (rustReg i).val < (32#usize).val
  simp

theorem gpr_bound (c : Core) (i : Reg) : i.val < c.registers.val.length := by
  have := c.registers.property
  have := i.isLt
  scalar_tac

def putCore (c : Core) (i : Reg) (v : U64) : Core :=
  if i = 0 then c else {c with registers := c.registers.set (rustReg i) v}

def addValue (a b : U64) : U64 := ⟨a.bv + b.bv⟩

theorem core_registers (c : Core) :
    coreOps.registers c = .ok (Array.to_slice c.registers) := rfl

theorem rust_read (c : Core) (i : Reg) :
    Slice.index_usize (Array.to_slice c.registers) (rustReg i) = .ok (gpr c i) := by
  have hb := gpr_bound c i
  simp [Slice.index_usize, Array.to_slice, gpr]

theorem core_set (c : Core) (i : Reg) (v : U64) :
    coreOps.set_register c (rustReg i) v =
      .ok {c with registers := c.registers.set (rustReg i) v} := by
  have hb := gpr_bound c i
  have hb' := rustReg_bound i
  change (do
    massert (rustReg i < 32#usize)
    let (t, back) ← Array.index_mut_usize c.registers (rustReg i)
    let a ← Array.update (back t) (rustReg i) v
    .ok {c with registers := a}) = _
  simp [Array.index_mut_usize, Array.index_usize, Array.update, hb']
  apply Subtype.ext
  simp

theorem rust_overflowing_add (a b : U64) :
    machineOps.CoreMachineInst.instructionsregisterRegisterInst.overflowing_add a b =
      .ok (addValue a b) := rfl

theorem rustReg_mod (i : Reg) :
    (rustReg i % ckb_vm_definitions.RISCV_GENERAL_REGISTER_NUMBER : Result Usize) =
      Result.ok (rustReg i) := by
  rw [ExtractedConstants.register_count_eq]
  obtain ⟨r, hr, hv⟩ := Aeneas.Std.WP.spec_imp_exists
    (UScalar.rem_spec (rustReg i) (y := 32#usize) (by simp))
  have he : r = rustReg i := by
    apply UScalar.eq_of_val_eq
    simpa [Nat.mod_eq_of_lt i.isLt] using hv
  simpa [he] using hr

theorem gpr_putCore (c : Core) (i j : Reg) (v : U64) :
    gpr (putCore c i v) j = if i ≠ 0 ∧ j = i then v else gpr c j := by
  by_cases hi : i = 0
  · simp [putCore, hi]
  by_cases hj : j = i
  · subst j
    have hb := gpr_bound c i
    simp [putCore, hi, gpr]
  · have hn : i.val ≠ j.val := by
      intro h
      exact hj (Fin.ext h).symm
    simp [putCore, hi, hj, gpr, hn]

/-- The actual production dictionary, conditional only on method delegation. -/
theorem rust_update (view : Machine → Core) (valid : Machine → Prop)
    (delegates : RegisterDelegation view valid) (m : Machine) (hm : valid m)
    (i : Reg) (v : U64) :
    ∃ m', ckb_vm.instructions.utils.update_register machineOps m (rustReg i) v = .ok m' ∧
      valid m' ∧ view m' = putCore (view m) i v := by
  by_cases hi : i = 0
  · refine ⟨m, ?_, hm, ?_⟩
    · simp only [ckb_vm.instructions.utils.update_register, rustReg_mod]
      simp [hi, rustReg]
    · simp [putCore, hi]
  · have hn : rustReg i ≠ 0#usize := by
      intro h
      apply hi
      apply Fin.ext
      simpa using congrArg UScalar.val h
    have hp : rustReg i > 0#usize := by
      change (0#usize).val < (rustReg i).val
      have : i.val ≠ 0 := by exact fun h => hi (Fin.ext h)
      simp
      omega
    obtain ⟨m', hw, hm', hc⟩ := delegates.set_register m hm (rustReg i) v hn (rustReg_bound i)
    refine ⟨m', ?_, hm', ?_⟩
    · simp only [ckb_vm.instructions.utils.update_register, rustReg_mod]
      simp only [Aeneas.Std.bind_tc_ok, hp, ↓reduceIte, hw]
      rfl
    · rw [core_set] at hc
      have he := Aeneas.Std.Result.ok.inj hc
      simpa [putCore, hi] using he.symm

theorem rust_add (view : Machine → Core) (valid : Machine → Prop)
    (delegates : RegisterDelegation view valid) (m : Machine) (hm : valid m)
    (rd rs1 rs2 : Reg) :
    ∃ m', ckb_vm.instructions.common.add machineOps m (rustReg rd) (rustReg rs1) (rustReg rs2) =
        .ok m' ∧ valid m' ∧
      view m' = putCore (view m) rd (addValue (gpr (view m) rs1) (gpr (view m) rs2)) := by
  obtain ⟨m', h, hm', hv⟩ := rust_update view valid delegates m hm rd
    (addValue (gpr (view m) rs1) (gpr (view m) rs2))
  refine ⟨m', ?_, hm', hv⟩
  simp [ckb_vm.instructions.common.add, delegates.registers m hm, core_registers,
    rust_read, rust_overflowing_add, h]

end
end AddRegister
