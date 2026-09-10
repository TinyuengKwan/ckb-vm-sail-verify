import CkbVmProduction

/- Diagnostic queries only: no refinement theorem is asserted here.
   Run from proof/lean/generated/rust:
     lake env lean ../../audit/RustDependencies.lean
   Or from the shared proof/lean/theorems project after make proof-imports:
     lake env lean ../audit/RustDependencies.lean
   Generic functions take machine operations as parameters; their axiom list
   does not certify the operations supplied by the production instance. -/
open ckb_vm_sail_extract

#print axioms ckb_vm_definitions.RISCV_GENERAL_REGISTER_NUMBER
#print axioms ckb_vm_definitions.registers.RA
#print axioms U64.Insts.Ckb_vmInstructionsRegisterRegister.BITS
#print axioms U64.Insts.Ckb_vmInstructionsRegisterRegister.SHIFT_MASK
#print axioms Aeneas.Std.core.num.U64.MIN
#print axioms Aeneas.Std.core.num.U64.MAX
#print axioms ckb_vm.instructions.common.add
#print axioms ckb_vm.instructions.utils.update_register
#print axioms U64.Insts.Ckb_vmInstructionsRegisterRegister.overflowing_add
#print axioms ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineCoreMachine.registers
#print axioms ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineCoreMachine.set_register
#print axioms ckb_vm.instructions.execute.handle_add
#print axioms ckb_vm.instructions.instruction_length
#print axioms ckb_vm.instructions.extract_opcode
#print axioms ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.registers
#print axioms ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.set_register
#print axioms ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.pc
#print axioms ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.update_pc
#print axioms ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.commit_pc

-- This includes all dispatch branches and the full production dictionaries.
-- It is not the path-sensitive dependency set of a future ADD theorem.
#print axioms execute_production
