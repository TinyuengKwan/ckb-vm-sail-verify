import OuterCache

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

def lowHalf (w : BitVec 32) : U16 := ⟨w.setWidth 16⟩
def highHalf (w : BitVec 32) : U16 := ⟨(w >>> 16).setWidth 16⟩
def nextHalfPc (pc : U64) : U64 := ⟨pc.bv + 2⟩

theorem half_low_mask (w : BitVec 32) :
    (core.convert.num.FromU32U16.from (lowHalf w) &&& 3#u32) =
      ((⟨w⟩ : U32) &&& 3#u32) := by
  apply UScalar.eq_of_val_eq
  apply congrArg BitVec.toNat
  change (w.setWidth 16).setWidth 32 &&& 3#32 = w &&& 3#32
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp

theorem halves_rejoin (w : BitVec 32) :
    (core.convert.num.FromU32U16.from (lowHalf w) |||
      (⟨(core.convert.num.FromU32U16.from (highHalf w)).bv <<< 16⟩ : U32)) =
      (⟨w⟩ : U32) := by
  apply UScalar.eq_of_val_eq
  apply congrArg BitVec.toNat
  change (w.setWidth 16).setWidth 32 |||
    (((w >>> 16).setWidth 16).setWidth 32 <<< 16) = w
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp

theorem pc_add_two (pc : U64) (h : pc.val + 2 < 2^64) :
    (pc + 2#u64 : Result U64) = .ok (nextHalfPc pc) := by
  have hb : pc.val + (2#u64).val ≤ U64.max := by
    norm_num [U64.max, U64.numBits]
    omega
  obtain ⟨v, hv, _, hbits⟩ := Aeneas.Std.WP.spec_imp_exists
    (U64.add_bv_spec (x := pc) (y := 2#u64) hb)
  have he : v = nextHalfPc pc := by
    apply UScalar.eq_of_val_eq
    exact congrArg BitVec.toNat hbits
  exact hv.trans (congrArg Result.ok he)

theorem fetch_add16 {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem middle mem' : M) (pc : U64)
    (rd rs1 rs2 : BitVec 5)
    (hedge : ¬ (pc &&& 4095#u64) < 4094#u64)
    (hnext : pc.val + 2 < 2^64)
    (hlo : mi.execute_load16 mem pc = .ok (.Ok (lowHalf (encode rd rs1 rs2)), middle))
    (hhi : mi.execute_load16 middle (nextHalfPc pc) =
      .ok (.Ok (highHalf (encode rd rs1 rs2)), mem')) :
    ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc =
      .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem') := by
  have hs : (4095#u64 - 1#u64 : Result U64) = .ok 4094#u64 := rfl
  have hlow := (half_low_mask (encode rd rs1 rs2)).trans (add_low_two rd rs1 rs2)
  have hshift : (core.convert.num.FromU32U16.from (highHalf (encode rd rs1 rs2)) <<<
      16#i32 : Result U32) =
      .ok ⟨(core.convert.num.FromU32U16.from (highHalf (encode rd rs1 rs2))).bv <<< 16⟩ := rfl
  simp only [ckb_vm.decoder.DefaultDecoder.decode_bits, page_mask, lift,
    bind_tc_ok, hs, hedge, ↓reduceIte, hlo, core.result.Result.Insts.CoreOpsTry.branch]
  refine (if_pos hlow).trans ?_
  simp only [pc_add_two pc hnext, hhi, bind_tc_ok, lift,
    core.result.Result.Insts.CoreOpsTry.branch, hshift]
  exact congrArg (fun (w : U32) =>
    (Result.ok (core.result.Result.Ok w, mem') :
      Result (core.result.Result U32 ckb_vm.error.Error × M)))
    (halves_rejoin (encode rd rs1 rs2))

#print axioms fetch_add16
#print axioms half_low_mask
#print axioms halves_rejoin
#print axioms pc_add_two
end
end OuterAdd
