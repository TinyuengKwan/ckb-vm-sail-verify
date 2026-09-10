import OuterPage
import RawAddStep

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- Contracts on memory reads only, with both actual production fetch branches.
    No constructor of this proposition contains a decoder result. -/
inductive WordFetch {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem : M) (pc : U64) (w : BitVec 32) (mem' : M) : Prop
  | fast (hfast : (pc &&& 4095#u64) < 4094#u64)
      (hload : mi.execute_load32 mem pc = .ok (.Ok (⟨w⟩ : U32), mem'))
  | edge (middle : M) (hedge : ¬ (pc &&& 4095#u64) < 4094#u64)
      (hnext : pc.val + 2 < 2^64)
      (hlo : mi.execute_load16 mem pc = .ok (.Ok (lowHalf w), middle))
      (hhi : mi.execute_load16 middle (nextHalfPc pc) = .ok (.Ok (highHalf w), mem'))

theorem fetch_encoded {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem mem' : M) (pc : U64)
    (rd rs1 rs2 : BitVec 5) (path : WordFetch mi mem pc (encode rd rs1 rs2) mem') :
    ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc =
      .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem') := by
  cases path with
  | fast hfast hload => exact fetch_add32 mi d mem mem' pc rd rs1 rs2 hfast hload
  | edge middle hedge hnext hlo hhi =>
    exact fetch_add16 mi d mem middle mem' pc rd rs1 rs2 hedge hnext hlo hhi

theorem fetch_word {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem mem' : M) (pc : U64)
    (w : BitVec 32) (hraw : IsRawAdd w) (path : WordFetch mi mem pc w mem') :
    ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc = .ok (.Ok (⟨w⟩ : U32), mem') := by
  have he : encode (rdOf w) (rs1Of w) (rs2Of w) = w := reconstruct w hraw
  have hp : WordFetch mi mem pc (encode (rdOf w) (rs1Of w) (rs2Of w)) mem' := by
    simpa only [he] using path
  simpa only [he] using fetch_encoded mi d mem mem' pc (rdOf w) (rs1Of w) (rs2Of w) hp

/-- The complete decode_raw cold-cache path, at arbitrary PC and with either
    load width. The input is an arbitrary original word satisfying ADD's bit pattern. -/
theorem decode_cold_word {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem mem' : M) (pc : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (w : BitVec 32) (hraw : IsRawAdd w) (path : WordFetch mi mem pc w mem') :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi (initial 2#u32) mem pc =
      .ok (.Ok (internal (rdOf w) (rs1Of w) (rs2Of w)),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey pc)
          (pc, internal (rdOf w) (rs1Of w) (rs2Of w))), mem') := by
  have he : encode (rdOf w) (rs1Of w) (rs2Of w) = w := reconstruct w hraw
  have hf := fetch_word mi (withCache (initial 2#u32).instructions_cache)
    mem mem' pc w hraw path
  apply decode_cache_miss mi (initial 2#u32).instructions_cache mem mem' pc
    core.num.U64.MAX 0#u64 size hsize hbound
    (initial_cache 2#u32 (cacheKey pc) (cache_key_bound pc))
    (Ne.symm (pc_not_sentinel pc size hbound)) (rdOf w) (rs1Of w) (rs2Of w)
  simpa only [he] using hf

/-- A subsequent hit reads the value established by the proved miss, without
    assuming another successful instruction load or a decoder result. -/
theorem decode_written_hit {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (a : Cache) (mem : M) (pc inst : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi
      (withCache (a.set (cacheKey pc) (pc, inst))) mem pc =
        .ok (.Ok inst, withCache (a.set (cacheKey pc) (pc, inst)), mem) := by
  exact decode_cache_hit mi _ mem pc inst size hsize hbound
    (cache_write_visible a (cacheKey pc) (pc, inst) (key_in_cache pc a))

#print axioms fetch_word
#print axioms decode_cold_word
#print axioms decode_written_hit
end
end OuterAdd
