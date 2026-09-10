import RustDispatch
import SailRetirement

/-! Normal 32-bit ADD, at the actual Rust production root and Sail try_step.
The correspondence is conditional on decoded inputs, wrapper delegation, and
explicit framed Sail prefix operations. It does not prove either raw decoder
correct or instantiate these contracts for a concrete running machine. -/
namespace AddStep
open Aeneas.Std AddBoundary AddRegister ckb_vm_sail_extract LeanRV64D Functions
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

/-- Entry/exit observations. Old next-PC need not correspond: staging overwrites it. -/
def state_rel_pc (view : Machine → Core) (m : Machine) (s : SailState) : Prop :=
  state_rel view m s ∧ s.regs.get? .PC = some (view m).pc.bv

theorem decoded_add_step (view : Machine → Core) (valid : Machine → Prop)
    (regs : RegisterDelegation view valid) (pcs : PcDelegation view valid)
    (m : Machine) (s : SailState) (hm : valid m) (hrel : state_rel_pc view m s)
    (inst : U64) (w : BitVec 32) (rd rs1 rs2 : Reg)
    (hd : DecodedAdd inst (rustReg rd) (rustReg rs1) (rustReg rs2))
    (entry : StepEntry s) (path : ActiveAddPath entry.prepared w rd rs1 rs2)
    (ready : RetireReady path.ready)
    (hactive : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (stepNo : Nat) (exitWait : Bool) :
    ∃ m' s',
      execute_production inst m = .ok (.Ok (), m') ∧
      try_step stepNo exitWait s = .ok false s' ∧
      valid m' ∧ state_rel_pc view m' s' ∧
      (view m').pc.bv = (view m).pc.bv + 4 ∧
      (view m').next_pc.bv = (view m).pc.bv + 4 ∧
      s'.regs.get? .nextPC = some ((view m).pc.bv + 4) ∧
      (∀ j : Reg, (gpr (view m') j).bv =
        if rd ≠ 0 ∧ j = rd then (gpr (view m) rs1).bv + (gpr (view m) rs2).bv
        else (gpr (view m) j).bv) ∧
      (view m').memory = (view m).memory ∧ s'.mem = s.mem := by
  obtain ⟨m', hr, hm', hv⟩ := rust_production_add view valid regs pcs m hm inst rd rs1 rs2 hd
  let a := (gpr (view m) rs1).bv
  let b := (gpr (view m) rs2).bv
  let p := (view m).pc.bv
  let s' := retiredState path.ready rd p (a + b) ready.increment ready.counter
  have hs : try_step stepNo exitWait s = .ok false s' :=
    sail_try_step_add s entry w rd rs1 rs2 path ready hactive p a b
      hrel.2 (hrel.1 rs1) (hrel.1 rs2) stepNo exitWait
  have hpc : (view m').pc.bv = p + 4 := by
    rw [hv, (addCore_pc _ _ _ _).1]
    rfl
  have hnext : (view m').next_pc.bv = p + 4 := by
    rw [hv, (addCore_pc _ _ _ _).2]
    rfl
  have hsp := retired_pc path.ready rd p (a + b) ready.increment ready.counter
  refine ⟨m', s', hr, hs, hm', ?_, hpc, hnext, hsp.2, ?_, ?_, ?_⟩
  · constructor
    · intro j
      rw [retired_gpr, hv, addCore_gpr]
      split
      · rfl
      · exact (path.frame.gprs j).trans (((prepared_frame s entry).gprs j).trans (hrel.1 j))
    · exact hsp.1.trans (congrArg some hpc.symm)
  · intro j
    rw [hv, addCore_gpr]
    split <;> rfl
  · rw [hv]
    exact addCore_memory _ _ _ _
  · exact (retired_memory _ _ _ _ _ _).trans
      (path.frame.memory.trans (prepared_frame s entry).memory)

end
end AddStep
