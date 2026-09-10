import OuterRawLinked
import RustRawAdd
import RawEncoding

namespace OuterAdd
noncomputable section
open Aeneas.Std RawAddDecode OuterDecodeCandidate
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000
set_option linter.unusedSimpArgs false

abbrev regInst := U64.Insts.Ckb_vmInstructionsRegisterRegister
abbrev addFactory := ckb_vm.instructions.i.factory regInst
abbrev compressedFactory := ckb_vm.instructions.rvc.factory regInst

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

theorem add_dispatch (rd rs1 rs2 : BitVec 5) :
    addFactory (⟨encode rd rs1 rs2⟩ : U32) 2#u32 = assembled rd rs1 rs2 := by
  simp [addFactory, regInst, ckb_vm.instructions.i.factory,
    U64.Insts.Ckb_vmInstructionsRegisterRegister,
    U64.Insts.Ckb_vmInstructionsRegisterRegister.BITS,
    ckb_vm.instructions.i.factory.closure.Insts.CoreOpsFunctionFnTupleOptionU64.call,
    factory_op, factory_f3, factory_f7, op_bits, f3_bits, f7_bits,
    core.option.Option.map,
    ckb_vm.instructions.i.factory.closure.closure_6.Insts.CoreOpsFunctionFnOnceTupleU16U64,
    ckb_vm.instructions.i.factory.closure.closure_6.Insts.CoreOpsFunctionFnOnceTupleU16U64.call_once,
    factory_rd, factory_rs1, factory_rs2, rd_bits, rs1_bits, rs2_bits,
    ckb_vm.instructions.set_instruction_length_4.Insts.CoreOpsFunctionFnOnceTupleU64U64,
    ckb_vm.instructions.set_instruction_length_4.Insts.CoreOpsFunctionFnOnceTupleU64U64.call_once,
    ckb_vm_definitions.instructions.OP_ADD, assembled]

theorem add_decode (rd rs1 rs2 : BitVec 5) :
    addFactory (⟨encode rd rs1 rs2⟩ : U32) 2#u32 =
      .ok (some (internal rd rs1 rs2)) := by
  rw [add_dispatch]
  exact RawAddDecode.assemble_value rd rs1 rs2

theorem compressed_mask (rd rs1 rs2 : BitVec 5) :
    ((⟨encode rd rs1 rs2⟩ : U32) &&& 57347#u32) =
      if rs1[0] then 32771#u32 else 3#u32 := by
  cases h : rs1[0] <;> simp only [h, Bool.false_eq_true, ↓reduceIte]
  all_goals
    apply UScalar.eq_of_val_eq
    apply congrArg BitVec.toNat
    change encode rd rs1 rs2 &&& 57347#32 = _
    apply BitVec.eq_of_getElem_eq
    intro i hi
    interval_cases i <;> simp [encode]
    all_goals repeat' (erw [BitVec.getElem_append]; simp [h])

theorem compressed_rejects_add (rd rs1 rs2 : BitVec 5) (v : U32) :
    compressedFactory (⟨encode rd rs1 rs2⟩ : U32) v = .ok none := by
  cases h : rs1[0] <;>
    simp [compressedFactory, regInst, ckb_vm.instructions.rvc.factory,
      U64.Insts.Ckb_vmInstructionsRegisterRegister,
      U64.Insts.Ckb_vmInstructionsRegisterRegister.BITS, compressed_mask, h,
      core.option.Option.map, lift]
  all_goals rfl

#print axioms add_decode
#print axioms compressed_rejects_add
end
end OuterAdd
