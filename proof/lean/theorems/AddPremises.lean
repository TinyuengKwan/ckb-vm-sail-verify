import CkbVmProduction

/-! Explicit, unproved delegation contracts for the actual production instance.
No instance of these contracts, projection, or invariant is postulated here.
They are explicit parameters of conditional theorems, not new global axioms.
This file does not define an alternative ADD implementation or a Sail state relation.
-/
namespace AddBoundary
open Aeneas.Std ckb_vm_sail_extract

noncomputable section

abbrev Memory := ckb_vm.memory.sparse.SparseMemory U64
abbrev Core := ckb_vm.machine.DefaultCoreMachine U64 Memory
abbrev Machine := ckb_vm.machine.DefaultMachine Core ckb_vm.decoder.DefaultDecoder

def registerOps := U64.Insts.Ckb_vmInstructionsRegisterRegister
def memoryOps := ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory registerOps
def coreOps := ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineCoreMachine
  registerOps memoryOps
def supportOps := ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine
  registerOps memoryOps
def machineOps := ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineMachine
  ckb_vm.decoder.DefaultDecoder supportOps

-- This equation checks that the dictionary below really is the one at the root.
theorem production_dictionary (inst : U64) (m : Machine) :
    execute_production inst m = ckb_vm.instructions.execute.execute machineOps inst m := rfl

/-- Two method premises for the register-only ADD leaf. `view` must represent
the real inner core; `valid` must include all intended starting states and remain
closed under writes. Merely choosing an empty invariant proves nothing useful. -/
structure RegisterDelegation (view : Machine → Core) (valid : Machine → Prop) : Prop where
  registers : ∀ m, valid m →
    machineOps.CoreMachineInst.registers m = coreOps.registers (view m)
  -- update_register suppresses index zero before invoking this method.
  set_register : ∀ m, valid m → ∀ (i : Usize) (v : U64),
    i ≠ 0#usize → i < 32#usize →
    ∃ m', machineOps.CoreMachineInst.set_register m i v = .ok m' ∧
      valid m' ∧ coreOps.set_register (view m) i v = .ok (view m')

/-- Three additional method premises for the production PC staging/commit path.
The generated core methods specify the complete projected update, including
preservation of registers, memory and unrelated core fields. -/
structure PcDelegation (view : Machine → Core) (valid : Machine → Prop) : Prop where
  pc : ∀ m, valid m → machineOps.CoreMachineInst.pc m = coreOps.pc (view m)
  update_pc : ∀ m, valid m → ∀ p, ∃ m',
    machineOps.CoreMachineInst.update_pc m p = .ok m' ∧ valid m' ∧
      coreOps.update_pc (view m) p = .ok (view m')
  commit_pc : ∀ m, valid m → ∃ m',
    machineOps.CoreMachineInst.commit_pc m = .ok m' ∧ valid m' ∧
      coreOps.commit_pc (view m) = .ok (view m')

/-- Input correspondence for a normal 32-bit ADD in CKB's internal encoding.
This records what a future decoder connection must prove, not that the decoder
already satisfies it. The Sail operands must separately correspond to rd/rs1/rs2. -/
structure DecodedAdd (inst : U64) (rd rs1 rs2 : Usize) : Prop where
  rd_bound : rd < 32#usize
  rs1_bound : rs1 < 32#usize
  rs2_bound : rs2 < 32#usize
  opcode : ckb_vm.instructions.extract_opcode inst = .ok 1#u16
  length : ckb_vm.instructions.instruction_length inst = .ok 4#u8
  rd_field : ckb_vm.instructions.Rtype.rd inst = .ok rd
  rs1_field : ckb_vm.instructions.Rtype.rs1 inst = .ok rs1
  rs2_field : ckb_vm.instructions.Rtype.rs2 inst = .ok rs2

-- Intentionally no axiom/instance supplies view, valid, or these contracts.
-- GPR/Sail correspondence, valid initial states, decoded ADD fields and the
-- Sail fetch/interrupt/postlude boundary remain separate obligations.
end
end AddBoundary
