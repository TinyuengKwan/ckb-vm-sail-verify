//! CKB-VM execution driver.
//!
//! Wraps CKB-VM to provide step-by-step execution with state capture.

use crate::StepState;
use anyhow::{Context, Result};
use std::path::Path;

use ckb_vm::{
    CoreMachine, DefaultCoreMachine, DefaultMachine, SparseMemory, SupportMachine, ISA_B, ISA_IMC,
    ISA_MOP,
};

/// Exit syscall handler (syscall number 93).
struct ExitSyscall;

impl<Mac: ckb_vm::SupportMachine> ckb_vm::Syscalls<Mac> for ExitSyscall {
    fn initialize(&mut self, _machine: &mut Mac) -> Result<(), ckb_vm::Error> {
        Ok(())
    }

    fn ecall(&mut self, machine: &mut Mac) -> Result<bool, ckb_vm::Error> {
        let syscall_num = machine.registers()[ckb_vm::registers::A7].to_u64();
        if syscall_num == 93 {
            let exit_code = machine.registers()[ckb_vm::registers::A0].to_u64();
            machine.set_register(ckb_vm::registers::A0, Mac::REG::from_u64(exit_code));
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

/// Execute an ELF binary on CKB-VM, returning a per-step trace.
pub fn execute_elf(elf_path: &Path, max_steps: u64) -> Result<Vec<StepState>> {
    let elf_data = std::fs::read(elf_path)
        .with_context(|| format!("Failed to read ELF: {}", elf_path.display()))?;

    let isa = ISA_IMC | ISA_B | ISA_MOP;
    let core = DefaultCoreMachine::<u64, SparseMemory<u64>>::new(isa, 2, 1024, 4 * 1024 * 1024);
    let mut machine = DefaultMachine::new(core);
    machine.add_syscall(Box::new(ExitSyscall));

    machine
        .load_program(&elf_data, &[])
        .context("Failed to load ELF into CKB-VM")?;

    let mut trace = Vec::new();
    trace.push(capture_state(&machine));

    for _ in 0..max_steps {
        match machine.step() {
            Ok(_) => {}
            Err(_) => break,
        }
        if !machine.running() {
            break;
        }
        trace.push(capture_state(&machine));
    }

    Ok(trace)
}

fn capture_state<M: CoreMachine<REG = u64>>(machine: &M) -> StepState {
    let mut regs = [0u64; 32];
    for i in 0..32 {
        regs[i] = machine.registers()[i].to_u64();
    }
    StepState::new(machine.pc().to_u64(), regs)
}
