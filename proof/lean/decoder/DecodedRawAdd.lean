import RustRawAdd

namespace RawAddDecode
open Aeneas.Std LeanRV64D AddRegister AddBoundary
open ckb_vm_sail_extract
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

def reg (v : BitVec 5) : Reg := ⟨v.toNat, v.isLt⟩

theorem reg_sail (v : BitVec 5) : sailReg (reg v) = .Regidx v := by
  simp [sailReg, reg]

theorem reg_rust (v : BitVec 5) : rustReg (reg v) = RawAddFields.index v := by
  apply UScalar.eq_of_val_eq
  rw [rustReg_val, RawAddFields.index_val]
  rfl

theorem byte_reg (v : BitVec 5) :
    UScalar.cast .Usize (⟨v.zeroExtend 8⟩ : U8) = rustReg (reg v) := by
  apply UScalar.eq_of_val_eq
  erw [U8.cast_Usize_val_eq]
  rw [rustReg_val]
  change (v.zeroExtend 8).toNat = v.toNat
  rw [BitVec.toNat_setWidth]
  exact Nat.mod_eq_of_lt (by have h := v.isLt; omega)

theorem internal_rd_bits (rd rs1 rs2 : BitVec 5) :
    ((internal rd rs1 rs2).bv >>> 8).setWidth 8 = rd.zeroExtend 8 := by
  unfold internal
  bitwise_ext
theorem internal_rs1_bits (rd rs1 rs2 : BitVec 5) :
    ((internal rd rs1 rs2).bv >>> 32).setWidth 8 = rs1.zeroExtend 8 := by
  unfold internal
  bitwise_ext
theorem internal_rs2_bits (rd rs1 rs2 : BitVec 5) :
    ((internal rd rs1 rs2).bv >>> 40).setWidth 8 = rs2.zeroExtend 8 := by
  unfold internal
  bitwise_ext
theorem internal_op_bits (rd rs1 rs2 : BitVec 5) :
    ((((internal rd rs1 rs2).bv >>> 8) &&& 65280) |||
      ((internal rd rs1 rs2).bv &&& 255)).setWidth 16 = 1 := by
  unfold internal
  bitwise_ext
theorem internal_length_bits (rd rs1 rs2 : BitVec 5) :
    ((((internal rd rs1 rs2).bv >>> 24) &&& 15) <<< 1).setWidth 8 = 4 := by
  unfold internal
  bitwise_ext

macro "normalize_shift" : tactic => `(tactic| (
  simp only [HShiftRight.hShiftRight, HShiftLeft.hShiftLeft,
    UScalar.shiftRight_IScalar, UScalar.shiftRight,
    UScalar.shiftLeft_IScalar, UScalar.shiftLeft]
  norm_num))

theorem internal_decoded (rd rs1 rs2 : BitVec 5) :
    DecodedAdd (internal rd rs1 rs2) (rustReg (reg rd))
      (rustReg (reg rs1)) (rustReg (reg rs2)) := by
  constructor
  · exact rustReg_bound _
  · exact rustReg_bound _
  · exact rustReg_bound _
  · unfold ckb_vm.instructions.extract_opcode
    normalize_shift
    exact congrArg (fun b : BitVec 16 => Result.ok (⟨b⟩ : U16))
      (internal_op_bits rd rs1 rs2)
  · unfold ckb_vm.instructions.instruction_length
    normalize_shift
    exact congrArg (fun b : BitVec 8 => Result.ok (⟨b⟩ : U8))
      (internal_length_bits rd rs1 rs2)
  · unfold ckb_vm.instructions.Rtype.rd
    normalize_shift
    exact (congrArg (fun b : BitVec 8 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U8)))
      (internal_rd_bits rd rs1 rs2)).trans (congrArg Result.ok (byte_reg rd))
  · unfold ckb_vm.instructions.Rtype.rs1
    normalize_shift
    exact (congrArg (fun b : BitVec 8 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U8)))
      (internal_rs1_bits rd rs1 rs2)).trans (congrArg Result.ok (byte_reg rs1))
  · unfold ckb_vm.instructions.Rtype.rs2
    normalize_shift
    exact (congrArg (fun b : BitVec 8 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U8)))
      (internal_rs2_bits rd rs1 rs2)).trans (congrArg Result.ok (byte_reg rs2))

#print axioms internal_decoded
end RawAddDecode
