import LocalFields
import SailContractWitness
import Mathlib.Tactic.IntervalCases

/-! Field-level correspondence only. The Rust factory is not imported here. -/
namespace RawAddFields
open Aeneas.Std RawDecodeExtract LeanRV64D AddRegister
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

def index (v : BitVec 5) : Usize := UScalar.cast .Usize (⟨v.zeroExtend 32⟩ : U32)

macro "bitwise_ext" : tactic => `(tactic| (
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp))

macro "normalize_x" : tactic => `(tactic| (
  simp only [instructions.utils.x, HShiftRight.hShiftRight, HShiftLeft.hShiftLeft,
    UScalar.shiftRight_UScalar, UScalar.shiftRight,
    UScalar.shiftLeft_UScalar, UScalar.shiftLeft]
  norm_num
  first
  | erw [show ((⟨(1 : BitVec 32) <<< 5⟩ : U32) - 1#u32 : Result U32) = .ok (⟨31⟩ : U32) by rfl]
  | erw [show ((⟨(1 : BitVec 32) <<< 7⟩ : U32) - 1#u32 : Result U32) = .ok (⟨127⟩ : U32) by rfl]
  | erw [show ((⟨(1 : BitVec 32) <<< 3⟩ : U32) - 1#u32 : Result U32) = .ok (⟨7⟩ : U32) by rfl]
  rfl))

theorem rd (w : U32) : instructions.utils.rd w =
    .ok (index (Sail.BitVec.extractLsb w.bv 11 7)) := by
  have hx : instructions.utils.x w 7#usize 5#usize 0#usize =
      .ok (⟨(w.bv >>> 7) &&& 31⟩ : U32) := by
    normalize_x
  rw [instructions.utils.rd, hx]
  have hb : ((w.bv >>> 7) &&& 31) =
      (Sail.BitVec.extractLsb w.bv 11 7).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U32))) hb

theorem rs1 (w : U32) : instructions.utils.rs1 w =
    .ok (index (Sail.BitVec.extractLsb w.bv 19 15)) := by
  have hx : instructions.utils.x w 15#usize 5#usize 0#usize =
      .ok (⟨(w.bv >>> 15) &&& 31⟩ : U32) := by normalize_x
  rw [instructions.utils.rs1, hx]
  have hb : ((w.bv >>> 15) &&& 31) =
      (Sail.BitVec.extractLsb w.bv 19 15).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U32))) hb

theorem rs2 (w : U32) : instructions.utils.rs2 w =
    .ok (index (Sail.BitVec.extractLsb w.bv 24 20)) := by
  have hx : instructions.utils.x w 20#usize 5#usize 0#usize =
      .ok (⟨(w.bv >>> 20) &&& 31⟩ : U32) := by normalize_x
  rw [instructions.utils.rs2, hx]
  have hb : ((w.bv >>> 20) &&& 31) =
      (Sail.BitVec.extractLsb w.bv 24 20).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (UScalar.cast .Usize (⟨b⟩ : U32))) hb

theorem opcode (w : U32) : instructions.utils.opcode w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 6 0).zeroExtend 32⟩ : U32) := by
  have hx : instructions.utils.x w 0#usize 7#usize 0#usize =
      .ok (⟨w.bv &&& 127⟩ : U32) := by normalize_x
  rw [instructions.utils.opcode, hx]
  have hb : (w.bv &&& 127) = (Sail.BitVec.extractLsb w.bv 6 0).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (⟨b⟩ : U32)) hb

theorem funct3 (w : U32) : instructions.utils.funct3 w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 14 12).zeroExtend 32⟩ : U32) := by
  have hx : instructions.utils.x w 12#usize 3#usize 0#usize =
      .ok (⟨(w.bv >>> 12) &&& 7⟩ : U32) := by normalize_x
  rw [instructions.utils.funct3, hx]
  have hb : ((w.bv >>> 12) &&& 7) = (Sail.BitVec.extractLsb w.bv 14 12).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (⟨b⟩ : U32)) hb

theorem funct7 (w : U32) : instructions.utils.funct7 w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 31 25).zeroExtend 32⟩ : U32) := by
  have hx : instructions.utils.x w 25#usize 7#usize 0#usize =
      .ok (⟨(w.bv >>> 25) &&& 127⟩ : U32) := by normalize_x
  rw [instructions.utils.funct7, hx]
  have hb : ((w.bv >>> 25) &&& 127) = (Sail.BitVec.extractLsb w.bv 31 25).zeroExtend 32 := by
    simp only [Sail.BitVec.extractLsb]
    bitwise_ext
  exact congrArg (fun b : BitVec 32 => Result.ok (⟨b⟩ : U32)) hb

theorem index_val (v : BitVec 5) : (index v).val = v.toNat := by
  have h := v.isLt
  unfold index
  erw [U32.cast_Usize_val_eq]
  change (v.zeroExtend 32).toNat = v.toNat
  rw [BitVec.toNat_setWidth]
  exact Nat.mod_eq_of_lt (by omega)

theorem sail_reg_decode (v : BitVec 5) (s : SailState) :
    Functions.encdec_reg_backwards v s = .ok (.Regidx v) s := by
  simp [Functions.encdec_reg_backwards, Functions.not, Functions.base_E_enabled,
    Functions.regidx_bit_width, Sail.BitVec.extractLsb, AddStep.pure_eq]
  exact BitVec.extractLsb'_eq_self

/-- Actual Rust operand readers and Sail register decoding use the same slices.
This does not assert that either top-level decoder chooses the ADD constructor. -/
theorem operands_correspond (w : U32) (s : SailState) :
    instructions.utils.rd w = .ok (index (Sail.BitVec.extractLsb w.bv 11 7)) ∧
    instructions.utils.rs1 w = .ok (index (Sail.BitVec.extractLsb w.bv 19 15)) ∧
    instructions.utils.rs2 w = .ok (index (Sail.BitVec.extractLsb w.bv 24 20)) ∧
    Functions.encdec_reg_backwards (Sail.BitVec.extractLsb w.bv 11 7) s =
      .ok (.Regidx (Sail.BitVec.extractLsb w.bv 11 7)) s ∧
    Functions.encdec_reg_backwards (Sail.BitVec.extractLsb w.bv 19 15) s =
      .ok (.Regidx (Sail.BitVec.extractLsb w.bv 19 15)) s ∧
    Functions.encdec_reg_backwards (Sail.BitVec.extractLsb w.bv 24 20) s =
      .ok (.Regidx (Sail.BitVec.extractLsb w.bv 24 20)) s :=
  ⟨rd w, rs1 w, rs2 w, sail_reg_decode _ s, sail_reg_decode _ s, sail_reg_decode _ s⟩

end RawAddFields
