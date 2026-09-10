import RustAdd
import SailRegisters

/-! Conditional register-only refinement of the two generated ADD leaves.
The production wrapper's two method contracts remain explicit parameters.
No PC, decode, fetch, interrupt, or whole-step refinement is claimed here. -/
namespace AddRegister
open Aeneas.Std AddBoundary ckb_vm_sail_extract LeanRV64D Functions
noncomputable section

theorem state_rel_x0 (view : Machine → Core) (m : Machine) (s : SailState)
    (h : state_rel view m s) : (gpr (view m) 0).bv = 0 := by
  have h0 := h 0
  simpa [sailGpr] using (Option.some.inj h0).symm

theorem putCore_frame (c : Core) (i : Reg) (v : U64) :
    (putCore c i v).pc = c.pc ∧ (putCore c i v).next_pc = c.next_pc ∧
      (putCore c i v).memory = c.memory := by
  by_cases h : i = 0 <;> simp [putCore, h]

theorem putGpr_frame (s : SailState) (i : Reg) (v : BitVec 64) :
    (putGpr s i v).mem = s.mem ∧
      (putGpr s i v).choiceState = s.choiceState ∧
      (putGpr s i v).cycleCount = s.cycleCount ∧
      (putGpr s i v).sailOutput = s.sailOutput := by
  by_cases h : i = 0 <;> simp [putGpr, h]

theorem putGpr_pc (s : SailState) (i : Reg) (v : BitVec 64) :
    (putGpr s i v).regs.get? .PC = s.regs.get? .PC ∧
      (putGpr s i v).regs.get? .nextPC = s.regs.get? .nextPC := by
  fin_cases i <;> simp [putGpr, key, Std.ExtDHashMap.get?_insert]

theorem state_rel_put (view : Machine → Core) (m m' : Machine) (s : SailState)
    (i : Reg) (v : U64) (h : state_rel view m s)
    (hv : view m' = putCore (view m) i v) :
    state_rel view m' (putGpr s i v.bv) := by
  intro j
  rw [sailGpr_put, hv, gpr_putCore]
  split <;> simp_all [state_rel]

/-- Both generated leaves succeed, retain the relation and have exactly the
same GPR effect. Sources are read in the pre-state, including all alias cases. -/
theorem add_registers (view : Machine → Core) (valid : Machine → Prop)
    (delegates : RegisterDelegation view valid) (m : Machine) (s : SailState)
    (hm : valid m) (hrel : state_rel view m s) (rd rs1 rs2 : Reg) :
    ∃ m' s',
      ckb_vm.instructions.common.add machineOps m (rustReg rd) (rustReg rs1) (rustReg rs2) =
        .ok m' ∧
      execute_RTYPE (sailReg rs2) (sailReg rs1) (sailReg rd) .ADD s =
        .ok RETIRE_SUCCESS s' ∧
      valid m' ∧ state_rel view m' s' ∧
      view m' = putCore (view m) rd (addValue (gpr (view m) rs1) (gpr (view m) rs2)) ∧
      s' = putGpr s rd ((gpr (view m) rs1).bv + (gpr (view m) rs2).bv) ∧
      (∀ j : Reg, (gpr (view m') j).bv =
        if rd ≠ 0 ∧ j = rd then (gpr (view m) rs1).bv + (gpr (view m) rs2).bv
        else (gpr (view m) j).bv) := by
  obtain ⟨m', hr, hm', hv⟩ := rust_add view valid delegates m hm rd rs1 rs2
  let v := addValue (gpr (view m) rs1) (gpr (view m) rs2)
  refine ⟨m', putGpr s rd v.bv, hr, ?_, hm', ?_, hv, rfl, ?_⟩
  · exact sail_add s rd rs1 rs2 _ _ (hrel rs1) (hrel rs2)
  · exact state_rel_put view m m' s rd v hrel hv
  · intro j
    rw [hv, gpr_putCore]
    split <;> rfl

end
end AddRegister
