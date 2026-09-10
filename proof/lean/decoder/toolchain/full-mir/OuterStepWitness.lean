import OuterStep
import OuterMemoryWitness
import RawAddWitness

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
open LeanRV64D Functions AddRegister AddBoundary AddStep ProductionWrapper
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- Explicit read-interface witness at the established Sail witness's PC.
    As with wordMemory, this is not a proof of the opaque Rust memory implementation. -/
def pairedMemory : ckb_vm.memory.Memory Unit U64 :=
  { wordMemory 0x002081b3 with
    memory_size := fun _ => .ok 0x80001000#usize
    execute_load32 := fun _ pc =>
      if pc = 0x80000000#u64 then .ok (.Ok 0x002081b3#u32, ()) else .fail .panic }

theorem paired_fetch (seed : Machine) :
    WordFetch pairedMemory () (view (AddWitness.rustInitial seed)).pc 0x002081b3 () := by
  apply WordFetch.fast
  · change (0x80000000#u64 &&& 4095#u64) < 4094#u64
    decide
  · simp [pairedMemory, view, AddWitness.rustInitial]
    rfl

/-- Instantiates the new actual decode_raw + execution theorem, including the
    common Sail premises. Only the pre-existing opaque Machine seed is a parameter. -/
theorem cold_paired_step (seed : Machine) :
    ∃ inst decoder' m' s',
      ckb_vm.decoder.DefaultDecoder.decode_raw pairedMemory (initial 2#u32) ()
        (view (AddWitness.rustInitial seed)).pc = .ok (.Ok inst, decoder', ()) ∧
      ckb_vm_sail_extract.execute_production inst (AddWitness.rustInitial seed) = .ok (.Ok (), m') ∧
      try_step 0 false AddWitness.initial = .ok false s' ∧
      state_rel_pc view m' s' ∧
      (gpr (view m') 3).bv = 12 ∧ (view m').pc.bv = 0x80000004 ∧
      (view m').memory = (view (AddWitness.rustInitial seed)).memory ∧
      s'.mem = AddWitness.initial.mem := by
  have hb : UScalar.cast .Usize (view (AddWitness.rustInitial seed)).pc < 0x80001000#usize := by
    simp [view, AddWitness.rustInitial, UScalar.cast_val_eq]
    exact lt_of_le_of_lt (Nat.mod_le _ _) (by decide)
  obtain ⟨inst, decoder', m', s', hd, hr, hs, hrel, hp, _, _, hg, hm, hsm⟩ :=
    cold_raw_add_step pairedMemory () () 0x80001000#usize
      (AddWitness.rustInitial seed) AddWitness.initial (AddWitness.initial_related seed)
      rfl hb 0x002081b3 ⟨rfl, rfl, rfl⟩ (paired_fetch seed)
      AddWitness.entry rawPath AddWitness.ready AddWitness.active 0 false
  refine ⟨inst, decoder', m', s', hd, hr, hs, hrel, ?_, hp, hm, hsm⟩
  simpa [rdOf, rs1Of, rs2Of, reg, Sail.BitVec.extractLsb,
    view, AddWitness.rustInitial, AddWitness.rustRegs, gpr] using hg 3

#print axioms paired_fetch
#print axioms cold_paired_step
end
end OuterAdd
