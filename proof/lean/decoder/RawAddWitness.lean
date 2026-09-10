import RawAddStep
import ProductionAddWitness

namespace RawAddDecode
open Aeneas.Std LeanRV64D Functions AddRegister AddBoundary AddStep ProductionWrapper
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

theorem decode_context_machine (s : SailState) (cfg : BitVec 64)
    (hp : s.regs.get? .cur_privilege = some .Machine)
    (hc : s.regs.get? .mseccfg = some cfg) :
    currentlyEnabled .Ext_Zicfilp s = .ok false s := by
  simp [currentlyEnabled, hartSupports, get_xLPE, bind_eq, map_eq, pure_eq, read_eq, hp, hc]

def rawPath : RawFetchPath AddWitness.entry.prepared 0x002081b3 :=
  { privilege := .Machine
    afterInterrupt := AddWitness.initial
    afterFetch := AddWitness.initial
    ready := AddWitness.initial
    readPrivilege := by simpa only [AddWitness.prepared_eq] using AddWitness.privilege_read
    noInterrupt := by simpa only [AddWitness.prepared_eq] using AddWitness.no_interrupt
    fetchBase := AddWitness.fetch_add
    decodeContext := by
      apply decode_context_machine _ 0
      all_goals simp [AddWitness.initial_regs, AddWitness.initialRegs, Std.ExtDHashMap.get?_insert]
    noLandingPad := AddWitness.no_landing_pad
    frame := by rw [AddWitness.prepared_eq]; exact ⟨fun _ => rfl, rfl, rfl⟩ }

theorem raw_premises_inhabited :
    ∃ s : SailState, ∃ e : StepEntry s, ∃ w : BitVec 32,
      IsRawAdd w ∧ ∃ p : RawFetchPath e.prepared w,
        Nonempty (RetireReady p.ready) ∧
        e.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()) :=
  ⟨AddWitness.initial, AddWitness.entry, 0x002081b3,
    ⟨rfl, rfl, rfl⟩, rawPath, ⟨AddWitness.ready⟩, AddWitness.active⟩

/-- The new raw-input theorem is instantiated, not merely the old decoded theorem. -/
theorem raw_paired_step (seed : Machine) :
    ∃ inst m' s',
      RawDecodeFactory.decode 0x002081b3#u32 = .ok (some inst) ∧
      ckb_vm_sail_extract.execute_production inst (AddWitness.rustInitial seed) = .ok (.Ok (), m') ∧
      try_step 0 false AddWitness.initial = .ok false s' ∧
      state_rel_pc view m' s' ∧
      (gpr (view m') 3).bv = 12 ∧
      (view m').pc.bv = 0x80000004 ∧
      (view m').memory = (view (AddWitness.rustInitial seed)).memory ∧
      s'.mem = AddWitness.initial.mem := by
  obtain ⟨inst, m', s', hd, hr, hs, hrel, hp, hn, hsn, hg, hm, hsm⟩ :=
    raw_add_step (AddWitness.rustInitial seed) AddWitness.initial
      (AddWitness.initial_related seed) 0x002081b3 ⟨rfl, rfl, rfl⟩
      AddWitness.entry rawPath AddWitness.ready AddWitness.active 0 false
  refine ⟨inst, m', s', hd, hr, hs, hrel, ?_, hp, hm, hsm⟩
  simpa [rdOf, rs1Of, rs2Of, reg, Sail.BitVec.extractLsb,
    view, AddWitness.rustInitial, AddWitness.rustRegs, gpr] using hg 3

#print axioms raw_premises_inhabited
#print axioms raw_paired_step
end
end RawAddDecode
