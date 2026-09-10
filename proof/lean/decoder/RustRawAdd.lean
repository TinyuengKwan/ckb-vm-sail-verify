import FactoryScoped
import SailRawAdd

namespace RawAddDecode
open Aeneas.Std LeanRV64D AddRegister RawDecodeFactory
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000
set_option linter.unusedSimpArgs false

theorem factory_rd (w : U32) : ckb_vm.instructions.utils.rd w =
    .ok (RawAddFields.index (Sail.BitVec.extractLsb w.bv 11 7)) := RawAddFields.rd w
theorem factory_rs1 (w : U32) : ckb_vm.instructions.utils.rs1 w =
    .ok (RawAddFields.index (Sail.BitVec.extractLsb w.bv 19 15)) := RawAddFields.rs1 w
theorem factory_rs2 (w : U32) : ckb_vm.instructions.utils.rs2 w =
    .ok (RawAddFields.index (Sail.BitVec.extractLsb w.bv 24 20)) := RawAddFields.rs2 w
theorem factory_op (w : U32) : ckb_vm.instructions.utils.opcode w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 6 0).zeroExtend 32⟩ : U32) := RawAddFields.opcode w
theorem factory_f3 (w : U32) : ckb_vm.instructions.utils.funct3 w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 14 12).zeroExtend 32⟩ : U32) := RawAddFields.funct3 w
theorem factory_f7 (w : U32) : ckb_vm.instructions.utils.funct7 w =
    .ok (⟨(Sail.BitVec.extractLsb w.bv 31 25).zeroExtend 32⟩ : U32) := RawAddFields.funct7 w

def assembled (rd rs1 rs2 : BitVec 5) : Result (Option U64) := do
  let inst ← ckb_vm.instructions.Rtype.new 1#u16
    (RawAddFields.index rd) (RawAddFields.index rs1) (RawAddFields.index rs2)
  let inst ← ckb_vm.instructions.set_instruction_length_4 inst
  .ok (some inst)

theorem factory_dispatch (rd rs1 rs2 : BitVec 5) :
    decode (⟨encode rd rs1 rs2⟩ : U32) = assembled rd rs1 rs2 := by
  simp [decode, ckb_vm.instructions.i.factory,
    U64.Insts.Ckb_vmInstructionsRegisterRegister,
    U64.Insts.Ckb_vmInstructionsRegisterRegister.BITS,
    ckb_vm.instructions.i.factory.closure.Insts.CoreOpsFunctionFnTupleOptionU64.call,
    factory_op, factory_f3, factory_f7, op_bits, f3_bits, f7_bits,
    core.option.Option.map,
    ckb_vm.instructions.i.factory.closure.closure_6.Insts.CoreOpsFunctionFnOnceTupleU16U64,
    ckb_vm.instructions.i.factory.closure.closure_6.Insts.CoreOpsFunctionFnOnceTupleU16U64.call_once,
    factory_rd, factory_rs1, factory_rs2, rd_bits, rs1_bits, rs2_bits,
    P.Insts.CoreOpsFunctionFnOnceTupleU64U64,
    P.Insts.CoreOpsFunctionFnOnceTupleU64U64.call_once,
    ckb_vm_definitions.instructions.OP_ADD, assembled]

def internal (rd rs1 rs2 : BitVec 5) : U64 :=
  ⟨1 ||| (rd.zeroExtend 64 <<< 8) ||| (rs1.zeroExtend 64 <<< 32) |||
    (rs2.zeroExtend 64 <<< 40) ||| 33554432⟩

theorem index_u64 (v : BitVec 5) :
    Aeneas.Std.core.convert.num.FromU64U8.from (UScalar.cast .U8 (RawAddFields.index v)) =
      (⟨v.zeroExtend 64⟩ : U64) := by
  apply UScalar.eq_of_val_eq
  erw [Aeneas.Std.core.convert.num.FromU64U8.from_val_eq, UScalar.cast_val_eq,
    RawAddFields.index_val]
  change v.toNat % 256 = (v.zeroExtend 64).toNat
  rw [BitVec.toNat_setWidth]
  have h := v.isLt
  have h8 : v.toNat < 256 := by omega
  have h64 : v.toNat < 2^64 := by omega
  simp [Nat.mod_eq_of_lt h8, Nat.mod_eq_of_lt h64]
  exact (Nat.mod_eq_of_lt h64).symm

theorem assemble_value (rd rs1 rs2 : BitVec 5) :
    assembled rd rs1 rs2 = .ok (some (internal rd rs1 rs2)) := by
  unfold assembled ckb_vm.instructions.Rtype.new
  simp only [lift, bind_tc_ok, index_u64, HShiftRight.hShiftRight, HShiftLeft.hShiftLeft,
    UScalar.shiftRight_IScalar, UScalar.shiftRight,
    UScalar.shiftLeft_IScalar, UScalar.shiftLeft]
  norm_num
  rfl

theorem rust_decode (rd rs1 rs2 : BitVec 5) :
    decode (⟨encode rd rs1 rs2⟩ : U32) = .ok (some (internal rd rs1 rs2)) := by
  rw [factory_dispatch, assemble_value]

#print axioms rust_decode
end RawAddDecode
