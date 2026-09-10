import RustDispatch

/-! Contract witnesses for the reviewed upstream-plus-patch production model.
No wrapper operations or their laws are assumed. The invariant is True for
every supplied Machine; constructing opaque runtime/initial Sail states is separate.
-/
namespace ProductionWrapper
open Aeneas.Std AddBoundary AddRegister AddStep ckb_vm_sail_extract
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

def view (m : Machine) : Core := m.inner
def valid (_ : Machine) : Prop := True
theorem valid_all (m : Machine) : valid m := True.intro

/-- An arbitrary supplied machine is admitted, rather than filtered by an empty invariant. -/
theorem valid_iff (m : Machine) : valid m ↔ True := Iff.rfl

theorem registers_delegate (m : Machine) :
    machineOps.CoreMachineInst.registers m = coreOps.registers (view m) := rfl

theorem pc_delegate (m : Machine) :
    machineOps.CoreMachineInst.pc m = coreOps.pc (view m) := rfl

theorem set_delegate (m : Machine) (i : Usize) (v : U64) :
    machineOps.CoreMachineInst.set_register m i v =
      (do let c ← coreOps.set_register (view m) i v
          pure {m with inner := c}) := rfl

theorem update_delegate (m : Machine) (p : U64) :
    machineOps.CoreMachineInst.update_pc m p =
      (do let c ← coreOps.update_pc (view m) p
          pure {m with inner := c}) := rfl

theorem commit_delegate (m : Machine) :
    machineOps.CoreMachineInst.commit_pc m =
      (do let c ← coreOps.commit_pc (view m)
          pure {m with inner := c}) := rfl

/-- Extend the existing Fin-32 core update lemma to the exact Usize contract domain. -/
theorem core_set_bounded (c : Core) (i : Usize) (v : U64) (hi : i < 32#usize) :
    coreOps.set_register c i v = .ok {c with registers := c.registers.set i v} := by
  have hb : i.val < 32 := by exact hi
  let r : Reg := ⟨i.val, hb⟩
  have hr : rustReg r = i := by
    apply UScalar.eq_of_val_eq
    simp [r]
  simpa only [hr] using core_set c r v

theorem registerDelegation : RegisterDelegation view valid := by
  constructor
  · intro m _
    exact registers_delegate m
  · intro m _ i v _ hi
    let c := {view m with registers := (view m).registers.set i v}
    refine ⟨{m with inner := c}, ?_, valid_all _, ?_⟩
    · rw [set_delegate, core_set_bounded _ _ _ hi]
      rfl
    · exact core_set_bounded _ _ _ hi

theorem pcDelegation : PcDelegation view valid := by
  constructor
  · intro m _
    exact pc_delegate m
  · intro m _ p
    refine ⟨{m with inner := {view m with next_pc := p}}, ?_, valid_all _, ?_⟩
    · rw [update_delegate, core_update_pc]
      rfl
    · exact core_update_pc _ _
  · intro m _
    refine ⟨{m with inner := commitCore (view m)}, ?_, valid_all _, ?_⟩
    · rw [commit_delegate, core_commit_pc]
      rfl
    · exact core_commit_pc _

end
end ProductionWrapper
