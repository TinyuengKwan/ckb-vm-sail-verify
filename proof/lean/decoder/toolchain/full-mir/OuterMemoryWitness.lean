import OuterGeneral

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- An explicit interface witness containing the word at addresses 0 and 4094.
    Unused operations fail. This is not an extraction of Rust SparseMemory and
    does not establish that implementation's semantics or all memory laws. -/
def wordMemory (w : BitVec 32) : ckb_vm.memory.Memory Unit U64 where
  instructionsregisterRegisterInst := regInst
  new := fun _ => .ok ()
  init_pages := fun _ _ _ _ _ _ => .fail .panic
  fetch_flag := fun _ _ => .fail .panic
  set_flag := fun _ _ _ => .fail .panic
  clear_flag := fun _ _ _ => .fail .panic
  memory_size := fun _ => .ok 8192#usize
  store_byte := fun _ _ _ _ => .fail .panic
  store_bytes := fun _ _ _ => .fail .panic
  load_bytes := fun _ _ _ => .fail .panic
  execute_load16 := fun _ pc =>
    if pc = 0#u64 ∨ pc = 4094#u64 then .ok (.Ok (lowHalf w), ())
    else if pc = 2#u64 ∨ pc = 4096#u64 then .ok (.Ok (highHalf w), ())
    else .fail .panic
  execute_load32 := fun _ pc =>
    if pc = 0#u64 ∨ pc = 4094#u64 then .ok (.Ok (⟨w⟩ : U32), ())
    else .fail .panic
  load8 := fun _ _ => .fail .panic
  load16 := fun _ _ => .fail .panic
  load32 := fun _ _ => .fail .panic
  load64 := fun _ _ => .fail .panic
  store8 := fun _ _ _ => .fail .panic
  store16 := fun _ _ _ => .fail .panic
  store32 := fun _ _ _ => .fail .panic
  store64 := fun _ _ _ => .fail .panic

theorem fast_word_witness (w : BitVec 32) : WordFetch (wordMemory w) () 0#u64 w () := by
  exact .fast (by decide) (by simp [wordMemory])

theorem edge_word_witness (w : BitVec 32) : WordFetch (wordMemory w) () 4094#u64 w () := by
  apply WordFetch.edge () (by decide) (by decide)
  · simp [wordMemory]
  · have h : nextHalfPc 4094#u64 = 4096#u64 := rfl
    simp [wordMemory, h]

theorem fast_decoder_witness (w : BitVec 32) (hraw : IsRawAdd w) :
    ckb_vm.decoder.DefaultDecoder.decode_raw (wordMemory w) (initial 2#u32) () 0#u64 =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey 0#u64)
          (0#u64, internal (rdOf w) (rs1Of w) (rs2Of w))), ()) := by
  exact decode_cold_word (wordMemory w) () () 0#u64 8192#usize rfl
    (by simp [UScalar.cast_val_eq]) w hraw (fast_word_witness w)

theorem edge_decoder_witness (w : BitVec 32) (hraw : IsRawAdd w) :
    ckb_vm.decoder.DefaultDecoder.decode_raw (wordMemory w) (initial 2#u32) () 4094#u64 =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey 4094#u64)
          (4094#u64, internal (rdOf w) (rs1Of w) (rs2Of w))), ()) := by
  exact decode_cold_word (wordMemory w) () () 4094#u64 8192#usize rfl
    (by
      simp [UScalar.cast_val_eq]
      exact lt_of_le_of_lt (Nat.mod_le _ _) (by decide)) w hraw (edge_word_witness w)

#print axioms fast_word_witness
#print axioms edge_word_witness
#print axioms fast_decoder_witness
#print axioms edge_decoder_witness
end
end OuterAdd
