import OuterStep

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- The actual public trait method, with a proved configuration restriction.
    Its MOP branch is extracted with a body, not replaced by an axiom. -/
theorem public_mop_off {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem : M) (pc : U64)
    (hoff : d.mop = false) :
    ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode mi d mem pc =
      ckb_vm.decoder.DefaultDecoder.decode_raw mi d mem pc := by
  simp only [ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode, hoff,
    Bool.false_eq_true, ↓reduceIte]

/-- Original ADD word through the public decoder, at arbitrary PC and with
    either actual instruction-fetch width. Cold state is the actual VERSION2,
    IMC+B initialization, so no decoder-result premise is introduced. -/
theorem decode_cold_public_word {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem mem' : M) (pc : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (w : BitVec 32) (hraw : IsRawAdd w) (path : WordFetch mi mem pc w mem') :
    ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode
        mi (initial 2#u32) mem pc =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey pc)
          (pc, internal (rdOf w) (rs1Of w) (rs2Of w))), mem') := by
  rw [public_mop_off mi _ mem pc rfl]
  exact decode_cold_word mi mem mem' pc size hsize hbound w hraw path

/-- The extracted Rust harness also reaches the public trait method. This
    specialization retains explicit SparseMemory size/read contracts; it is
    not a proof of the opaque SparseMemory implementation. -/
theorem sparse_public_mop_off
    (d : ckb_vm.decoder.DefaultDecoder)
    (mem : ckb_vm.memory.sparse.SparseMemory U64) (pc : U64)
    (hoff : d.mop = false) :
    OuterDecodeCandidate.decode d mem pc = OuterDecodeCandidate.decode_raw d mem pc := by
  unfold OuterDecodeCandidate.decode OuterDecodeCandidate.decode_raw
  exact public_mop_off _ d mem pc hoff

/-- Compose the actual constructor with the actual public decoder. -/
theorem fresh_public_word {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem mem' : M) (pc : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (w : BitVec 32) (hraw : IsRawAdd w) (path : WordFetch mi mem pc w mem') :
    (do let d ← fresh_decoder
        ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode mi d mem pc) =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey pc)
          (pc, internal (rdOf w) (rs1Of w) (rs2Of w))), mem') := by
  rw [fresh_initial]
  exact decode_cold_public_word mi mem mem' pc size hsize hbound w hraw path

#print axioms public_mop_off
#print axioms decode_cold_public_word
#print axioms sparse_public_mop_off
#print axioms fresh_public_word
end
end OuterAdd
