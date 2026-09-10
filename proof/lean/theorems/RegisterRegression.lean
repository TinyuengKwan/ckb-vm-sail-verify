import AddRegisterAxioms

/-! Kernel-checked edge cases. These specialize the general lemmas; they do not
replace the universally quantified theorem or instantiate wrapper delegation. -/
namespace AddRegister.Regression
open Aeneas.Std AddBoundary LeanRV64D Functions
noncomputable section

theorem wraparound : addValue 18446744073709551615#u64 1#u64 = 0#u64 := rfl

theorem discard_x0 (s : SailState) (v : BitVec 64) :
    wX_bits (sailReg 0) v s = .ok () s := by
  simpa [putGpr] using sail_write s 0 v

theorem rd_eq_rs1 (c : Core) :
    gpr (putCore c 1 (addValue (gpr c 1) (gpr c 2))) 1 =
      addValue (gpr c 1) (gpr c 2) := by simp [gpr_putCore]

theorem rd_eq_rs2 (c : Core) :
    gpr (putCore c 2 (addValue (gpr c 1) (gpr c 2))) 2 =
      addValue (gpr c 1) (gpr c 2) := by simp [gpr_putCore]

theorem all_alias (c : Core) :
    gpr (putCore c 31 (addValue (gpr c 31) (gpr c 31))) 31 =
      addValue (gpr c 31) (gpr c 31) := by simp [gpr_putCore]

theorem missing_key_rejected (view : Machine → Core) (m : Machine) (s : SailState)
    (h : s.regs.get? .x1 = none) : ¬ state_rel view m s := by
  intro hr
  have h1 := hr 1
  change (s.regs.get? .x1).map id = some _ at h1
  simp [h] at h1

theorem nonzero_x0_rejected (view : Machine → Core) (m : Machine) (s : SailState)
    (h : (gpr (view m) 0).bv ≠ 0) : ¬ state_rel view m s := by
  exact fun hr => h (state_rel_x0 view m s hr)

end
end AddRegister.Regression
