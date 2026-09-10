import OuterFetch

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

theorem fresh_initial : fresh_decoder = .ok (initial 2#u32) := by
  unfold fresh_decoder ckb_vm_definitions.ISA_IMC
    ckb_vm_definitions.ISA_B ckb_vm.machine.VERSION2
  exact initial_new 2#u32

/-- A concrete entry address but arbitrary register fields and memory states.
    The only memory contracts are size and the original 32-bit load. -/
theorem decode_raw_zero {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem mem' : M) (size : Usize) (hsize : mi.memory_size mem = .ok size)
    (hpos : 0#usize < size) (rd rs1 rs2 : BitVec 5)
    (hload : mi.execute_load32 mem 0#u64 =
      .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem')) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi (initial 2#u32) mem 0#u64 =
      .ok (.Ok (internal rd rs1 rs2),
        { initial 2#u32 with instructions_cache :=
          (initial 2#u32).instructions_cache.set 0#usize (0#u64, internal rd rs1 rs2) },
        mem') := by
  have hcast : UScalar.cast .Usize 0#u64 = 0#usize := by
    apply UScalar.eq_of_val_eq
    simp [UScalar.cast_val_eq]
  have hshr1 : (0#u64 >>> 1#i32 : Result U64) = .ok 0#u64 := rfl
  have hshr12 : (0#u64 >>> 12#i32 : Result U64) = .ok 0#u64 := rfl
  have hshl8 : (0#u64 <<< 8#i32 : Result U64) = .ok 0#u64 := rfl
  have hand : (0#u64 &&& 255#u64) = 0#u64 := rfl
  have hor : (0#u64 ||| 0#u64) = 0#u64 := rfl
  have hmod : (0#usize % 4096#usize : Result Usize) = .ok 0#usize := by
    simp [HMod.hMod, UScalar.rem]
    apply UScalar.eq_of_val_eq
    simp [UScalar.val, BitVec.toNat_umod]
    change (0 % 4096 : BitVec System.Platform.numBits).toNat = 0
    simp
  have hcache := initial_cache 2#u32 0#usize (by scalar_tac)
  have hfetch := fetch_add32 mi (initial 2#u32) mem mem' 0#u64 rd rs1 rs2
    (by decide) hload
  have hbound : (0#usize).val < (initial 2#u32).instructions_cache.val.length := by
    rw [Array.length_eq]
    scalar_tac
  have hloop := factory_loop_add (initial 2#u32).instructions_cache 0#u64 0#usize
    hbound rd rs1 rs2
  simp only [ckb_vm.decoder.DefaultDecoder.decode_raw, lift, bind_tc_ok,
    hcast, hsize, not_le_of_gt hpos, ↓reduceIte, hshr1, hand, hshr12,
    hshl8, hor, ckb_vm.decoder.INSTRUCTION_CACHE_SIZE, hmod, hcache]
  simp only [hfetch, core.result.Result.Insts.CoreOpsTry.branch,
    bind_tc_ok, iterator_entry]
  exact congrArg (fun (out : Result (core.result.Result U64 ckb_vm.error.Error × Cache)) => do
    let (r, a) ← out
    Result.ok (r, { initial 2#u32 with instructions_cache := a }, mem')) hloop

#print axioms fresh_initial
#print axioms decode_raw_zero
end
end OuterAdd
