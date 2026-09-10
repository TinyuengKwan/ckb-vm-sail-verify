import OuterPublicStep
import OuterStepWitness

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
open LeanRV64D Functions AddRegister AddBoundary AddStep ProductionWrapper
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- Both fetch-width witnesses also pass through the real public method. -/
theorem fast_public_witness (w : BitVec 32) (hraw : IsRawAdd w) :
    ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode
        (wordMemory w) (initial 2#u32) () 0#u64 =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey 0#u64)
          (0#u64, internal (rdOf w) (rs1Of w) (rs2Of w))), ()) := by
  rw [public_mop_off _ _ _ _ rfl]
  exact fast_decoder_witness w hraw

theorem edge_public_witness (w : BitVec 32) (hraw : IsRawAdd w) :
    ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode
        (wordMemory w) (initial 2#u32) () 4094#u64 =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey 4094#u64)
          (4094#u64, internal (rdOf w) (rs1Of w) (rs2Of w))), ()) := by
  rw [public_mop_off _ _ _ _ rfl]
  exact edge_decoder_witness w hraw

/-- The public-step theorem instantiated with the existing joint witness.
    The opaque execution Machine seed remains a parameter. -/
theorem cold_public_paired_step (seed : Machine) :
    ∃ inst decoder' m' s',
      ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode pairedMemory (initial 2#u32) ()
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
    cold_public_add_step pairedMemory () () 0x80001000#usize
      (AddWitness.rustInitial seed) AddWitness.initial (AddWitness.initial_related seed)
      rfl hb 0x002081b3 ⟨rfl, rfl, rfl⟩ (paired_fetch seed)
      AddWitness.entry rawPath AddWitness.ready AddWitness.active 0 false
  refine ⟨inst, decoder', m', s', hd, hr, hs, hrel, ?_, hp, hm, hsm⟩
  simpa [rdOf, rs1Of, rs2Of, reg, Sail.BitVec.extractLsb,
    view, AddWitness.rustInitial, AddWitness.rustRegs, gpr] using hg 3

#print axioms cold_public_paired_step
#print axioms fast_public_witness
#print axioms edge_public_witness
end
end OuterAdd
