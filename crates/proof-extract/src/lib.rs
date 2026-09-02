//! The production entry points the proof track extracts from.
//!
//! Charon extracts a call graph from a set of roots. Naming those roots in
//! checked-in Rust, rather than in a script's command line, is what makes
//! "the proven function is reachable from production" auditable: the roots are
//! ordinary Rust that has to compile against the pinned CKB-VM.
//!
//! Nothing here reimplements anything. Each function is a one-line call into
//! the production interpreter at [`InjectedMachine`] -- the same type
//! `ckb-runner` drives for the runtime differential, imported rather than
//! respelled, so the proof track and the differential cannot drift apart.
//!
//! `ckb_vm::instructions::execute` is where an instruction's PC advance and
//! its dispatch live, and `common::add` is reached from it. Extracting from
//! here therefore shows ADD *in* the production call graph instead of
//! asserting that it is there.

use ckb_vm::instructions::{execute, Instruction};
use ckb_vm::Error;

pub use ckb_vm_sail_ckb_runner::InjectedMachine;

/// One production instruction execution: advance the program counter by the
/// instruction's size, dispatch, then commit.
pub fn execute_production(inst: Instruction, machine: &mut InjectedMachine) -> Result<(), Error> {
    execute(inst, machine)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm::{
        CoreMachine, DefaultCoreMachine, Memory, RustDefaultMachineBuilder, SparseMemory,
        SupportMachine,
    };
    use ckb_vm_sail_core::INJECTION_ENTRY;

    fn machine() -> InjectedMachine {
        let core = DefaultCoreMachine::<u64, SparseMemory<u64>>::new_with_memory(
            ckb_vm_sail_ckb_runner::DEFAULT_ISA,
            ckb_vm::machine::VERSION2,
            u64::MAX,
            usize::try_from(INJECTION_ENTRY + 4096).expect("window fits"),
        );
        let mut machine: InjectedMachine = RustDefaultMachineBuilder::new(core).build();
        machine.update_pc(INJECTION_ENTRY);
        machine.commit_pc();
        machine
    }

    /// The extraction root has to be the real thing: executing a decoded ADD
    /// through it must move the architectural state exactly as the runtime
    /// differential expects.
    #[test]
    fn the_extraction_root_executes_a_real_add() {
        let mut machine = machine();
        machine.set_register(1, 5);
        machine.set_register(2, 7);
        // add x3, x1, x2
        let decoded = decode(&mut machine, 0x0020_81b3);
        execute_production(decoded, &mut machine).expect("execute");
        assert_eq!(machine.registers()[3], 12);
        assert_eq!(*machine.pc(), INJECTION_ENTRY + 4);
    }

    /// x0 stays zero and the program counter still advances: the two adapter
    /// behaviours the theorem does not cover live here.
    #[test]
    fn a_write_to_x0_is_dropped_and_the_pc_still_advances() {
        let mut machine = machine();
        machine.set_register(1, 5);
        machine.set_register(2, 7);
        // add x0, x1, x2
        let decoded = decode(&mut machine, 0x0020_8033);
        execute_production(decoded, &mut machine).expect("execute");
        assert_eq!(machine.registers()[0], 0);
        assert_eq!(*machine.pc(), INJECTION_ENTRY + 4);
    }

    /// A compressed instruction advances the program counter by two, which is
    /// computed inside the extracted `execute`, not by the caller.
    #[test]
    fn a_compressed_instruction_advances_the_pc_by_two() {
        let mut machine = machine();
        // c.addi a0, 1
        let decoded = decode(&mut machine, 0x0000_0505);
        execute_production(decoded, &mut machine).expect("execute");
        assert_eq!(*machine.pc(), INJECTION_ENTRY + 2);
        assert_eq!(machine.registers()[10], 1);
    }

    fn decode(machine: &mut InjectedMachine, bits: u32) -> Instruction {
        use ckb_vm::decoder::{DefaultDecoder, InstDecoder};
        let pc = *machine.pc();
        machine
            .memory_mut()
            .store_bytes(pc, &bits.to_le_bytes())
            .expect("store");
        let mut decoder = <DefaultDecoder as InstDecoder>::new::<u64>(
            ckb_vm_sail_ckb_runner::DEFAULT_ISA,
            ckb_vm::machine::VERSION2,
        );
        decoder.decode(machine.memory_mut(), pc).expect("decode")
    }
}
