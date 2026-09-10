import SailDispatch

namespace AddStep
open AddRegister LeanRV64D Functions
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

/-- Conditions on the actual pre-step counter decision, not on try_step's result. -/
structure StepEntry (start : SailState) where
  privilege : Privilege
  increment : Bool
  afterDecision : SailState
  readPrivilege : readReg .cur_privilege start = .ok privilege start
  decideIncrement : should_inc_minstret privilege start = .ok increment afterDecision
  frame : ArchFrame start afterDecision

def StepEntry.prepared {start : SailState} (entry : StepEntry start) : SailState :=
  putReg entry.afterDecision .minstret_increment entry.increment

/-- Keys read by the normal retirement branch, before the ADD body runs.
The counter itself is required only when its increment is enabled. -/
structure RetireReady (ready : SailState) where
  increment : Bool
  counter : BitVec 64
  hart : ready.regs.get? .hart_state = some (.HART_ACTIVE ())
  flag : ready.regs.get? .minstret_increment = some increment
  count : increment = true → ready.regs.get? .minstret = some counter

def retiredState (ready : SailState) (rd : Reg) (p v : BitVec 64)
    (increment : Bool) (counter : BitVec 64) : SailState :=
  let committed := putReg (putGpr (stageSail ready p) rd v) .PC (p + 4)
  if increment then putReg committed .minstret (counter + 1) else committed

theorem gpr_put_flag (s : SailState) (b : Bool) (i : Reg) :
    sailGpr (putReg s .minstret_increment b) i = sailGpr s i := by
  fin_cases i <;> simp [sailGpr, putReg, key, Std.ExtDHashMap.get?_insert]

theorem gpr_put_counter (s : SailState) (v : BitVec 64) (i : Reg) :
    sailGpr (putReg s .minstret v) i = sailGpr s i := by
  fin_cases i <;> simp [sailGpr, putReg, key, Std.ExtDHashMap.get?_insert]

theorem prepared_frame (s : SailState) (entry : StepEntry s) :
    ArchFrame s entry.prepared := by
  constructor
  · intro i
    exact (gpr_put_flag entry.afterDecision entry.increment i).trans (entry.frame.gprs i)
  · simpa [StepEntry.prepared, putReg, Std.ExtDHashMap.get?_insert] using entry.frame.pc
  · exact entry.frame.memory

-- No GPR destination aliases any of the three retirement keys.
theorem putGpr_retire_keys (s : SailState) (rd : Reg) (v : BitVec 64) :
    (putGpr s rd v).regs.get? .hart_state = s.regs.get? .hart_state ∧
    (putGpr s rd v).regs.get? .minstret_increment = s.regs.get? .minstret_increment ∧
    (putGpr s rd v).regs.get? .minstret = s.regs.get? .minstret := by
  fin_cases rd <;> simp [putGpr, key, Std.ExtDHashMap.get?_insert]

theorem sail_try_step_add (start : SailState) (entry : StepEntry start)
    (w : BitVec 32) (rd rs1 rs2 : Reg)
    (path : ActiveAddPath entry.prepared w rd rs1 rs2) (ready : RetireReady path.ready)
    (hactive : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (p a b : BitVec 64) (hp : start.regs.get? .PC = some p)
    (ha : sailGpr start rs1 = some a) (hb : sailGpr start rs2 = some b)
    (stepNo : Nat) (exitWait : Bool) :
    try_step stepNo exitWait start = .ok false
      (retiredState path.ready rd p (a + b) ready.increment ready.counter) := by
  have frame := prepared_frame start entry
  have hs := run_hart_add entry.prepared w rd rs1 rs2 path p a b
    (frame.pc.trans hp) ((frame.gprs rs1).trans ha) ((frame.gprs rs2).trans hb) stepNo
  let t := putGpr (stageSail path.ready p) rd (a + b)
  have hn : t.regs.get? .nextPC = some (p + 4) := by
    dsimp [t]
    rw [(putGpr_pc _ _ _).2]
    simp [stageSail, putReg]
  have ht := sail_tick_pc t (p + 4) hn
  have hh : t.regs.get? .hart_state = some (.HART_ACTIVE ()) := by
    dsimp [t]
    rw [(putGpr_retire_keys _ _ _).1]
    simpa [stageSail, putReg, Std.ExtDHashMap.get?_insert] using ready.hart
  have hf : (putReg t .PC (p + 4)).regs.get? .minstret_increment = some ready.increment := by
    simp only [putReg, Std.ExtDHashMap.get?_insert]
    simp only [t, (putGpr_retire_keys _ _ _).2.1]
    simpa [stageSail, putReg, Std.ExtDHashMap.get?_insert] using ready.flag
  have hc : ready.increment = true →
      (putReg t .PC (p + 4)).regs.get? .minstret = some ready.counter := by
    intro hi
    simp only [putReg, Std.ExtDHashMap.get?_insert]
    simp only [t, (putGpr_retire_keys _ _ _).2.2]
    simpa [stageSail, putReg, Std.ExtDHashMap.get?_insert] using ready.count hi
  change run_hart_active stepNo entry.prepared = .ok _ t at hs
  have he : putReg entry.afterDecision .minstret_increment entry.increment = entry.prepared := rfl
  cases hi : ready.increment <;>
    simp [try_step, bind_eq, pure_eq, entry.readPrivilege, entry.decideIncrement,
      write_eq, he, read_eq, hactive, hs, RETIRE_SUCCESS, hart_is_active,
      hh, ht, get_config_rvfi,
      assert, Sail.ConcurrencyInterfaceV1.PreSail.assert, retiredState, t, Sail.BitVec.addInt] <;>
    erw [hf] <;>
    simp [hi, bind_eq, map_eq, pure_eq, read_eq, write_eq]
  erw [hc hi]

theorem retired_gpr (s : SailState) (rd j : Reg) (p v : BitVec 64) (inc : Bool) (n : BitVec 64) :
    sailGpr (retiredState s rd p v inc n) j =
      if rd ≠ 0 ∧ j = rd then some v else sailGpr s j := by
  cases inc <;> simp only [retiredState, Bool.false_eq_true, ↓reduceIte,
    gpr_put_counter, gpr_put_PC, sailGpr_put, stageSail, gpr_put_nextPC]

theorem retired_pc (s : SailState) (rd : Reg) (p v : BitVec 64) (inc : Bool) (n : BitVec 64) :
    (retiredState s rd p v inc n).regs.get? .PC = some (p + 4) ∧
    (retiredState s rd p v inc n).regs.get? .nextPC = some (p + 4) := by
  cases inc <;>
    simp [retiredState, putReg, Std.ExtDHashMap.get?_insert, (putGpr_pc _ _ _).2,
      stageSail]

theorem retired_memory (s : SailState) (rd : Reg) (p v : BitVec 64) (inc : Bool) (n : BitVec 64) :
    (retiredState s rd p v inc n).mem = s.mem := by
  cases inc <;> exact (putGpr_frame (stageSail s p) rd v).1

end
end AddStep
