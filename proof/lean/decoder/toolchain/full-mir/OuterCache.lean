import OuterEntry

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- Pure arithmetic description of the production key; the entry theorem below
    proves the extracted shifts, cast and checked remainder compute this value. -/
def foldedPc (pc : U64) : U64 :=
  ⟨((pc.bv >>> 1) &&& 255) ||| (((pc.bv >>> 1) >>> 12) <<< 8)⟩
def cacheKey (pc : U64) : Usize :=
  ⟨(UScalar.cast .Usize (foldedPc pc)).bv % (4096#usize).bv⟩

theorem cache_key_val (pc : U64) :
    (cacheKey pc).val = (UScalar.cast .Usize (foldedPc pc)).val % 4096 := by
  change ((UScalar.cast .Usize (foldedPc pc)).bv % (4096#usize).bv).toNat = _
  rw [BitVec.toNat_umod]
  change (UScalar.cast .Usize (foldedPc pc)).val % (4096#usize).val = _
  have h : (4096#usize).val = 4096 := by scalar_tac
  rw [h]

theorem cache_key_bound (pc : U64) : (cacheKey pc).val < 4096 := by
  rw [cache_key_val]
  exact Nat.mod_lt _ (by decide)

theorem key_in_cache (pc : U64) (a : Cache) : (cacheKey pc).val < a.val.length := by
  rw [Array.length_eq]
  have h := cache_key_bound pc
  scalar_tac

theorem key_remainder (pc : U64) :
    (UScalar.cast .Usize (foldedPc pc) % 4096#usize : Result Usize) =
      .ok (cacheKey pc) := by
  simp [HMod.hMod, UScalar.rem, cacheKey]

/-- Expose the actual prefix while retaining both hit and miss continuations. -/
theorem decode_raw_key {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem : M) (pc : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi d mem pc = (do
      let (tag, inst) ← Array.index_usize d.instructions_cache (cacheKey pc)
      if tag = pc then .ok (.Ok inst, d, mem)
      else
        let (r, mem') ← ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc
        let cf ← core.result.Result.Insts.CoreOpsTry.branch r
        match cf with
        | .Continue w =>
          let iter ← SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter
            Global d.factories
          let (r', a) ← ckb_vm.decoder.DefaultDecoder.decode_raw_loop iter d.version
            d.instructions_cache pc (cacheKey pc) w
          .ok (r', { d with instructions_cache := a }, mem')
        | .Break residual =>
          let r' ← core.result.Result.Insts.CoreOpsTryTraitFromResidualResultInfallible.from_residual
            U64 (core.convert.FromSame ckb_vm.error.Error) residual
          .ok (r', d, mem')) := by
  have hs1 : (pc >>> 1#i32 : Result U64) = .ok ⟨pc.bv >>> 1⟩ := rfl
  have hs12 : ((⟨pc.bv >>> 1⟩ : U64) >>> 12#i32 : Result U64) =
      .ok ⟨(pc.bv >>> 1) >>> 12⟩ := rfl
  have hs8 : ((⟨(pc.bv >>> 1) >>> 12⟩ : U64) <<< 8#i32 : Result U64) =
      .ok ⟨((pc.bv >>> 1) >>> 12) <<< 8⟩ := rfl
  simp only [ckb_vm.decoder.DefaultDecoder.decode_raw, lift, bind_tc_ok, hsize,
    not_le_of_gt hbound, ↓reduceIte, hs1, hs12, hs8,
    ckb_vm.decoder.INSTRUCTION_CACHE_SIZE]
  exact congrArg (fun (out : Result Usize) => do
    let k ← out
    let (tag, inst) ← Array.index_usize d.instructions_cache k
    if tag = pc then .ok (core.result.Result.Ok inst, d, mem)
    else
      let (r, mem') ← ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc
      let cf ← core.result.Result.Insts.CoreOpsTry.branch r
      match cf with
      | .Continue w =>
        let iter ← SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter
          Global d.factories
        let (r', a) ← ckb_vm.decoder.DefaultDecoder.decode_raw_loop iter d.version
          d.instructions_cache pc k w
        .ok (r', { d with instructions_cache := a }, mem')
      | .Break residual =>
        let r' ← core.result.Result.Insts.CoreOpsTryTraitFromResidualResultInfallible.from_residual
          U64 (core.convert.FromSame ckb_vm.error.Error) residual
        .ok (r', d, mem')) (key_remainder pc)

theorem decode_cache_hit {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem : M) (pc inst : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (hcache : Array.index_usize d.instructions_cache (cacheKey pc) = .ok (pc, inst)) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi d mem pc = .ok (.Ok inst, d, mem) := by
  refine (decode_raw_key mi d mem pc size hsize hbound).trans ?_
  simp only [hcache, bind_tc_ok]
  exact if_pos rfl

def withCache (a : Cache) : ckb_vm.decoder.DefaultDecoder :=
  { initial 2#u32 with instructions_cache := a }

/-- A cache miss supplies a raw word, not a decoded instruction. The factory
    loop proves selection and operands and updates the computed cache slot. -/
theorem decode_cache_miss {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (a : Cache) (mem mem' : M) (pc tag previous : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (hcache : Array.index_usize a (cacheKey pc) = .ok (tag, previous))
    (hmiss : tag ≠ pc) (rd rs1 rs2 : BitVec 5)
    (hfetch : ckb_vm.decoder.DefaultDecoder.decode_bits mi (withCache a) mem pc =
      .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem')) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi (withCache a) mem pc =
      .ok (.Ok (internal rd rs1 rs2),
        withCache (a.set (cacheKey pc) (pc, internal rd rs1 rs2)), mem') := by
  refine (decode_raw_key mi (withCache a) mem pc size hsize hbound).trans ?_
  have hc : Array.index_usize (withCache a).instructions_cache (cacheKey pc) =
      .ok (tag, previous) := hcache
  simp only [hc, bind_tc_ok]
  refine (if_neg hmiss).trans ?_
  have hi : SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter
      Global (withCache a).factories = .ok (factoryIter 0) := rfl
  simp only [hfetch, bind_tc_ok, core.result.Result.Insts.CoreOpsTry.branch, hi]
  exact congrArg (fun (out : Result (core.result.Result U64 ckb_vm.error.Error × Cache)) => do
    let (r, a') ← out
    Result.ok (r, withCache a', mem'))
    (factory_loop_add a pc (cacheKey pc) (key_in_cache pc a) rd rs1 rs2)

theorem pc_not_sentinel (pc : U64) (size : Usize)
    (hbound : UScalar.cast .Usize pc < size) : pc ≠ core.num.U64.MAX := by
  intro h
  subst pc
  change (UScalar.cast .Usize core.num.U64.MAX).val < size.val at hbound
  rw [UScalar.cast_val_eq] at hbound
  have hm := size.hmax
  rcases System.Platform.numBits_eq with hb | hb <;>
    norm_num [UScalarTy.numBits, hb, core.num.U64.MAX, U64.rMax, U64.numBits] at hbound hm <;> omega

theorem decode_cold_fast {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem mem' : M) (pc : U64) (size : Usize)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize pc < size)
    (rd rs1 rs2 : BitVec 5) (hfast : (pc &&& 4095#u64) < 4094#u64)
    (hload : mi.execute_load32 mem pc = .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem')) :
    ckb_vm.decoder.DefaultDecoder.decode_raw mi (initial 2#u32) mem pc =
      .ok (.Ok (internal rd rs1 rs2),
        withCache ((initial 2#u32).instructions_cache.set (cacheKey pc)
          (pc, internal rd rs1 rs2)), mem') := by
  exact decode_cache_miss mi (initial 2#u32).instructions_cache mem mem' pc
    core.num.U64.MAX 0#u64 size hsize hbound
    (initial_cache 2#u32 (cacheKey pc) (cache_key_bound pc))
    (Ne.symm (pc_not_sentinel pc size hbound)) rd rs1 rs2
    (fetch_add32 mi _ mem mem' pc rd rs1 rs2 hfast hload)

#print axioms pc_not_sentinel
#print axioms decode_cold_fast
#print axioms decode_cache_hit
#print axioms decode_cache_miss
#print axioms cache_key_val
#print axioms cache_key_bound
#print axioms key_in_cache
#print axioms key_remainder
#print axioms decode_raw_key
end
end OuterAdd
