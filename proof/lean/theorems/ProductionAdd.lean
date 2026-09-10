import AddStep
import WrapperContracts

/-! The reviewed patched production root connected to Sail try_step.
Wrapper projection, validity and delegation are now fixed/proved, not arguments.
Decoded-input correspondence and actual Sail prefix/initialization remain premises.
-/
namespace ProductionAdd
open Aeneas.Std AddBoundary AddRegister AddStep ckb_vm_sail_extract LeanRV64D Functions
open ProductionWrapper
noncomputable section

theorem decoded_add_step
    (m : Machine) (s : SailState) (hrel : state_rel_pc view m s)
    (inst : U64) (w : BitVec 32) (rd rs1 rs2 : Reg)
    (hd : DecodedAdd inst (rustReg rd) (rustReg rs1) (rustReg rs2))
    (entry : StepEntry s) (path : ActiveAddPath entry.prepared w rd rs1 rs2)
    (ready : RetireReady path.ready)
    (hactive : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (stepNo : Nat) (exitWait : Bool) :
    ∃ m' s',
      execute_production inst m = .ok (.Ok (), m') ∧
      try_step stepNo exitWait s = .ok false s' ∧
      state_rel_pc view m' s' ∧
      (view m').pc.bv = (view m).pc.bv + 4 ∧
      (view m').next_pc.bv = (view m).pc.bv + 4 ∧
      s'.regs.get? .nextPC = some ((view m).pc.bv + 4) ∧
      (∀ j : Reg, (gpr (view m') j).bv =
        if rd ≠ 0 ∧ j = rd then (gpr (view m) rs1).bv + (gpr (view m) rs2).bv
        else (gpr (view m) j).bv) ∧
      (view m').memory = (view m).memory ∧ s'.mem = s.mem := by
  obtain ⟨m', s', hr, hs, _, hrel', hpc, hnext, hsnext, hgpr, hmem, hsmem⟩ :=
    AddStep.decoded_add_step view valid registerDelegation pcDelegation m s
      (valid_all m) hrel inst w rd rs1 rs2 hd entry path ready hactive stepNo exitWait
  exact ⟨m', s', hr, hs, hrel', hpc, hnext, hsnext, hgpr, hmem, hsmem⟩

end
end ProductionAdd
