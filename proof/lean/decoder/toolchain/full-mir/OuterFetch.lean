import OuterLoop

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

theorem page_mask : ckb_vm.decoder.RISCV_PAGESIZE_MASK = .ok 4095#u64 := by
  have hv : (12#usize).val < UScalarTy.Usize.numBits := by
    have hb := System.Platform.le_numBits
    change (12#usize).val < System.Platform.numBits
    scalar_tac
  have hshift : (1#usize <<< 12#usize : Result Usize) = .ok 4096#usize := by
    simp only [HShiftLeft.hShiftLeft, UScalar.shiftLeft_UScalar,
      UScalar.shiftLeft, hv, ↓reduceIte]
    congr 1
    apply UScalar.eq_of_val_eq
    simp only [UScalar.val, BitVec.shiftLeft_eq, BitVec.toNat_shiftLeft]
    change (1#usize).val <<< (12#usize).val % 2 ^ UScalarTy.Usize.numBits =
      (4096#usize).val
    have h1 : (1#usize).val = 1 := by scalar_tac
    have h12 : (12#usize).val = 12 := by scalar_tac
    have h4096 : (4096#usize).val = 4096 := by scalar_tac
    rw [h1, h12, h4096]
    rcases System.Platform.numBits_eq with hb | hb <;>
      norm_num [UScalarTy.numBits, hb]
    all_goals decide
  have hcast : UScalar.cast .U64 4096#usize = 4096#u64 := by
    apply UScalar.eq_of_val_eq
    simp only [UScalar.cast_val_eq]
    scalar_tac
  simp only [ckb_vm.decoder.RISCV_PAGESIZE_MASK, ckb_vm_definitions.RISCV_PAGESIZE,
    ckb_vm_definitions.RISCV_PAGE_SHIFTS, hshift, lift, bind_tc_ok, hcast]
  rfl

theorem add_low_two (rd rs1 rs2 : BitVec 5) :
    ((⟨encode rd rs1 rs2⟩ : U32) &&& 3#u32) = 3#u32 := by
  apply UScalar.eq_of_val_eq
  apply congrArg BitVec.toNat
  change encode rd rs1 rs2 &&& 3#32 = 3#32
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp [encode]
  all_goals repeat' (erw [BitVec.getElem_append]; simp)

/-- The memory interface supplies the original word, never a decoded instruction.
    This lemma covers the production single-load branch; the page edge is separate. -/
theorem fetch_add32 {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (d : ckb_vm.decoder.DefaultDecoder) (mem mem' : M) (pc : U64)
    (rd rs1 rs2 : BitVec 5)
    (hfast : (pc &&& 4095#u64) < 4094#u64)
    (hload : mi.execute_load32 mem pc = .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem')) :
    ckb_vm.decoder.DefaultDecoder.decode_bits mi d mem pc =
      .ok (.Ok (⟨encode rd rs1 rs2⟩ : U32), mem') := by
  have hs : (4095#u64 - 1#u64 : Result U64) = .ok 4094#u64 := rfl
  simp only [ckb_vm.decoder.DefaultDecoder.decode_bits, page_mask, lift,
    bind_tc_ok, hs, hfast, ↓reduceIte, hload,
    core.result.Result.Insts.CoreOpsTry.branch]
  exact congrArg (fun (low : U32) =>
    if low != 3#u32 then
      Result.ok (core.result.Result.Ok ((⟨encode rd rs1 rs2⟩ : U32) &&& 65535#u32), mem')
    else Result.ok (core.result.Result.Ok (⟨encode rd rs1 rs2⟩ : U32), mem'))
    (add_low_two rd rs1 rs2)

#print axioms page_mask
#print axioms add_low_two
#print axioms fetch_add32
end
end OuterAdd
