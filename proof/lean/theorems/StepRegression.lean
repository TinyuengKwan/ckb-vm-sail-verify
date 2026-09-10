import AddStepAxioms

namespace AddStep.Regression
open Aeneas.Std AddBoundary AddRegister LeanRV64D Functions
noncomputable section

theorem pc_wraparound : addValue 18446744073709551612#u64 4#u64 = 0#u64 := rfl

theorem x0_still_advances_pc (c : Core) (rs1 rs2 : Reg) :
    (addCore c 0 rs1 rs2).pc = addValue c.pc 4#u64 := (addCore_pc c 0 rs1 rs2).1

theorem x0_preserves_all_gprs (c : Core) (rs1 rs2 j : Reg) :
    gpr (addCore c 0 rs1 rs2) j = gpr c j := by simp [addCore_gpr]

theorem old_next_pc_irrelevant (view : Machine → Core) (m : Machine) (s : SailState)
    (q : BitVec 64) :
    state_rel_pc view m (putReg s .nextPC q) ↔ state_rel_pc view m s := by
  simp only [state_rel_pc, state_rel, gpr_put_nextPC]
  simp [putReg, Std.ExtDHashMap.get?_insert]

theorem tick_commits_zero (s : SailState) :
    tick_pc () (putReg s .nextPC 0) = .ok () (putReg (putReg s .nextPC 0) .PC 0) := by
  apply sail_tick_pc
  simp [putReg]

theorem retired_pc_wraparound (s : SailState) (rd : Reg) (v : BitVec 64) :
    (retiredState s rd 18446744073709551612 v false 0).regs.get? .PC = some 0 := by
  exact (retired_pc s rd 18446744073709551612 v false 0).1

theorem counter_wraparound (s : SailState) (rd : Reg) (p v : BitVec 64) :
    (retiredState s rd p v true 18446744073709551615).regs.get? .minstret = some 0 := by
  simp [retiredState, putReg]

theorem disabled_counter_needs_no_counter_key (s : SailState)
    (hh : s.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (hf : s.regs.get? .minstret_increment = some false) :
    Nonempty (RetireReady s) := by
  exact ⟨⟨false, 0, hh, hf, by intro h; cases h⟩⟩

theorem enabled_counter_needs_counter_key (s : SailState)
    (h : s.regs.get? .minstret = none) :
    ¬ ∃ ready : RetireReady s, ready.increment = true := by
  rintro ⟨ready, hi⟩
  have hc := ready.count hi
  simp [h] at hc

theorem missing_pc_rejected (view : Machine → Core) (m : Machine) (s : SailState)
    (h : s.regs.get? .PC = none) : ¬ state_rel_pc view m s := by
  intro hr
  have hp := hr.2
  simp [h] at hp

end
end AddStep.Regression
