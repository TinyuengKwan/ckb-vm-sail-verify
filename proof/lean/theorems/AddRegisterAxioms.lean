import AddRegisters
open Aeneas.Std ckb_vm_sail_extract

/-! Exact transitive footprint of the production-dictionary theorem.
These are existing generated declarations, NOT discharged assumptions.
Unused dictionary fields remain visible. No sorryAx or additional axiom is allowed.
The explicit RegisterDelegation/view/valid/state_rel parameters must also be audited.
-/

/-- info: 'AddRegister.add_registers' depends on axioms: [propext,
 Classical.choice,
 Quot.sound,
 bytes.bytes.Bytes,
 ckb_vm.decoder.DefaultDecoder,
 ckb_vm.machine.MachineRuntime,
 ckb_vm.machine.Pause,
 core.fmt.Formatter,
 I128.Insts.CoreConvertFromU64.from,
 I64.Insts.CoreOpsBitShlU64I64.shl,
 I64.Insts.CoreOpsBitShrU64I64.shr,
 Shared0U64.Insts.CoreOpsBitBitAndU64U64.bitand,
 Shared0U64.Insts.CoreOpsBitShlI32U64.shl,
 Shared0U64.Insts.CoreOpsBitShrI32U64.shr,
 U64.Insts.Ckb_vmInstructionsRegisterRegister.eq,
 U64.Insts.Ckb_vmInstructionsRegisterRegister.logical_not,
 U64.Insts.Ckb_vmInstructionsRegisterRegister.lt,
 U64.Insts.Ckb_vmInstructionsRegisterRegister.lt_s,
 U64.Insts.CoreOpsBitBitAndU64U64.bitand,
 U64.Insts.CoreOpsBitBitOrU64U64.bitor,
 U64.Insts.CoreOpsBitBitXorU64U64.bitxor,
 U64.Insts.CoreOpsBitNotU64.not,
 U64.Insts.CoreOpsBitShlU64U64.shl,
 U64.Insts.CoreOpsBitShrU64U64.shr,
 ckb_vm.memory.sparse.SparseMemory,
 core.num.I64.overflowing_rem,
 core.num.U64.count_ones,
 core.num.U64.overflowing_rem,
 core.num.U64.trailing_zeros,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.cycles,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.max_cycles,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.new_with_memory,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.reset,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.reset_signal,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.running,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.set_cycles,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.set_max_cycles,
 ckb_vm.machine.DefaultCoreMachine.Insts.Ckb_vmMachineSupportMachine.set_running,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.isa,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.memory,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.memory_mut,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineCoreMachine.version,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineMachine.ebreak,
 ckb_vm.machine.DefaultMachine.Insts.Ckb_vmMachineMachine.ecall,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.clear_flag,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.execute_load16,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.execute_load32,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.fetch_flag,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.init_pages,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.load16,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.load32,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.load64,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.load8,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.load_bytes,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.memory_size,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.new,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.set_flag,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store16,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store32,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store64,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store8,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store_byte,
 ckb_vm.memory.sparse.SparseMemory.Insts.Ckb_vmMemoryMemory.store_bytes] -/
#guard_msgs in
#print axioms AddRegister.add_registers

/-- info: 'AddRegister.sail_add' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms AddRegister.sail_add

/-- info: 'AddRegister.putGpr_pc' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms AddRegister.putGpr_pc

/-- info: 'AddRegister.putCore_frame' depends on axioms: [propext,
 Classical.choice,
 Quot.sound,
 ckb_vm.memory.sparse.SparseMemory] -/
#guard_msgs in
#print axioms AddRegister.putCore_frame
