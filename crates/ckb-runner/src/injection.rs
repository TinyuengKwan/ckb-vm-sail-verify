//! CKB-VM mirror of RVFI direct instruction injection.
//!
//! The Sail emulator in RVFI-DII mode does not fetch from memory: the `k`-th
//! injected word is the instruction executed by the `k`-th step, whatever the
//! program counter happens to be. To drive the real CKB-VM interpreter with the
//! same stream, this module writes the injected word at the current program
//! counter immediately before each step and then runs the ordinary
//! `DefaultMachine::step`, so decode, execute and PC update all stay on the
//! production path.
//!
//! Both sides therefore start from the same architectural state — all integer
//! registers zero, PC at `INJECTION_ENTRY` — without an ELF loader or platform
//! stack in between.

use anyhow::{bail, Context, Result};
use ckb_vm::{
    decoder::{DefaultDecoder, InstDecoder},
    machine::VERSION2,
    CoreMachine, DefaultCoreMachine, Memory, RustDefaultMachineBuilder, SparseMemory,
    SupportMachine,
};
use ckb_vm_sail_core::{
    normalize_instruction_width, program::validate_program, CommitEvent, ExecutionTrace, TraceEnd,
    INJECTION_ENTRY,
};

use crate::{changed_registers, DEFAULT_ISA};

/// Size of the executable window reserved above [`INJECTION_ENTRY`].
///
/// A branch that leaves this window ends the trace with an error instead of
/// silently wrapping or aborting: the injected corpus is expected to stay near
/// the entry point.
pub const INJECTION_WINDOW: u64 = 64 * 1024;

#[derive(Debug, Clone, Copy)]
pub struct InjectionConfig {
    pub isa: u8,
    pub version: u32,
    pub max_cycles: u64,
}

impl Default for InjectionConfig {
    fn default() -> Self {
        Self {
            isa: DEFAULT_ISA,
            version: VERSION2,
            max_cycles: u64::MAX,
        }
    }
}

/// Result of an injected run, including the final architectural state.
///
/// The state is not part of the comparison protocol; it exists so tests can
/// assert what a setup sequence actually built.
#[derive(Debug, Clone)]
pub struct InjectionOutcome {
    pub trace: ExecutionTrace,
    pub registers: [u64; 32],
    pub pc: u64,
}

pub fn run_program(program: &[u32], config: InjectionConfig) -> Result<InjectionOutcome> {
    if program.is_empty() {
        bail!("an injected program must contain at least one instruction");
    }
    validate_program(program)?;

    let memory_size = usize::try_from(INJECTION_ENTRY + INJECTION_WINDOW)
        .context("injection window does not fit in the host address space")?;
    let core = DefaultCoreMachine::<u64, SparseMemory<u64>>::new_with_memory(
        config.isa,
        config.version,
        config.max_cycles,
        memory_size,
    );
    let mut machine = RustDefaultMachineBuilder::new(core).build();
    machine.update_pc(INJECTION_ENTRY);
    machine.commit_pc();
    machine.set_running(true);

    let mut decoder = <DefaultDecoder as InstDecoder>::new::<u64>(config.isa, config.version);
    let mut events = Vec::with_capacity(program.len());

    for (order, &bits) in program.iter().enumerate() {
        let pc_before = *machine.pc();
        // A branch can wrap the program counter, so this must not overflow.
        let fits = pc_before
            .checked_add(4)
            .is_some_and(|end| end <= INJECTION_ENTRY + INJECTION_WINDOW);
        if pc_before < INJECTION_ENTRY || !fits {
            return Ok(finish(
                &machine,
                events,
                TraceEnd::Error {
                    message: format!(
                        "program counter {pc_before:#x} left the injection window \
                         [{INJECTION_ENTRY:#x}, {:#x})",
                        INJECTION_ENTRY + INJECTION_WINDOW
                    ),
                },
            ));
        }

        // Inject: place the word to execute where the interpreter will fetch it.
        // The decoder caches by program counter, so a revisited address (a taken
        // backward branch) must not return the previously injected word.
        if let Err(error) = machine
            .memory_mut()
            .store_bytes(pc_before, &bits.to_le_bytes())
        {
            return Ok(finish(
                &machine,
                events,
                TraceEnd::Error {
                    message: format!("failed to inject instruction at {pc_before:#x}: {error}"),
                },
            ));
        }
        decoder
            .reset_instructions_cache()
            .context("failed to reset the CKB-VM instruction cache")?;

        let before = capture_registers(&machine);
        let result = machine.step(&mut decoder);
        let after = capture_registers(&machine);
        let trap = result.is_err();

        events.push(
            CommitEvent {
                order: order as u64,
                // The injected word is what both sides were asked to execute.
                // Instruction *fetch* is therefore not under test here; a
                // decoder defect still shows up in the effects below.
                instruction: normalize_instruction_width(bits),
                pc_before,
                pc_after: *machine.pc(),
                register_writes: changed_registers(&before, &after),
                // CKB-VM does not expose committed data-memory accesses at this
                // boundary. Programs that would need them are rejected by
                // `validate_program`, so an empty vector here is a fact rather
                // than a dropped field.
                memory: Vec::new(),
                trap,
                halt: !machine.running(),
            }
            .normalize(),
        );

        if let Err(error) = result {
            return Ok(finish(
                &machine,
                events,
                TraceEnd::Error {
                    message: error.to_string(),
                },
            ));
        }
        if !machine.running() {
            return Ok(finish(
                &machine,
                events,
                TraceEnd::Completed {
                    exit_code: Some(i32::from(machine.exit_code())),
                },
            ));
        }
    }

    Ok(finish(&machine, events, TraceEnd::InjectionComplete))
}

fn finish<M>(machine: &M, events: Vec<CommitEvent>, end: TraceEnd) -> InjectionOutcome
where
    M: CoreMachine<REG = u64>,
{
    InjectionOutcome {
        registers: capture_registers(machine),
        pc: *machine.pc(),
        trace: ExecutionTrace::new(events, end),
    }
}

fn capture_registers<M>(machine: &M) -> [u64; 32]
where
    M: CoreMachine<REG = u64>,
{
    let mut registers = [0; 32];
    registers.copy_from_slice(&machine.registers()[..32]);
    registers
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm_sail_core::RegisterWrite;

    // addi x1, x0, 5 / addi x2, x0, 7 / add x3, x1, x2
    const ADD_PROGRAM: [u32; 3] = [0x0050_0093, 0x0070_0113, 0x0020_81b3];

    #[test]
    fn an_injected_program_runs_on_the_production_interpreter() {
        let outcome = run_program(&ADD_PROGRAM, InjectionConfig::default()).expect("run");
        assert_eq!(outcome.trace.end, TraceEnd::InjectionComplete);
        assert_eq!(outcome.trace.events.len(), 3);
        assert_eq!(outcome.registers[3], 12);
        assert_eq!(outcome.pc, INJECTION_ENTRY + 12);

        let last = &outcome.trace.events[2];
        assert_eq!(last.order, 2);
        assert_eq!(last.instruction, 0x0020_81b3);
        assert_eq!(last.pc_before, INJECTION_ENTRY + 8);
        assert_eq!(last.pc_after, INJECTION_ENTRY + 12);
        assert_eq!(
            last.register_writes,
            vec![RegisterWrite {
                index: 3,
                value: 12
            }]
        );
        assert!(!last.trap && !last.halt);
    }

    #[test]
    fn a_taken_branch_moves_the_next_injected_instruction() {
        // beq x0, x0, +8 / addi x1, x0, 1
        let program = [0x0000_0463, 0x0010_0093];
        let outcome = run_program(&program, InjectionConfig::default()).expect("run");
        assert_eq!(outcome.trace.events[0].pc_after, INJECTION_ENTRY + 8);
        assert!(outcome.trace.events[0].register_writes.is_empty());
        assert_eq!(outcome.trace.events[1].pc_before, INJECTION_ENTRY + 8);
        assert_eq!(outcome.registers[1], 1);
    }

    #[test]
    fn a_backward_branch_re_injects_a_visited_address() {
        // addi x1, x0, 1 / beq x0, x0, -4 / addi x2, x0, 2
        let program = [0x0010_0093, 0xfe00_0ee3, 0x0020_0113];
        let outcome = run_program(&program, InjectionConfig::default()).expect("run");
        assert_eq!(outcome.trace.events[1].pc_after, INJECTION_ENTRY);
        // The third injected word executes at the revisited address, which only
        // holds if the decoder cache was invalidated.
        assert_eq!(outcome.trace.events[2].pc_before, INJECTION_ENTRY);
        assert_eq!(outcome.trace.events[2].instruction, 0x0020_0113);
        assert_eq!(outcome.registers[2], 2);
    }

    #[test]
    fn a_branch_out_of_the_window_ends_the_trace_with_an_error() {
        // beq x0, x0, -2048 leaves the window downwards; the following
        // instruction is never executed.
        let program = [0xf800_00e3, addi_x1_1()];
        let outcome = run_program(&program, InjectionConfig::default()).expect("run");
        assert_eq!(outcome.trace.events.len(), 1);
        match outcome.trace.end {
            TraceEnd::Error { ref message } => {
                assert!(message.contains("injection window"), "{message}");
            }
            ref other => panic!("expected a window error, got {other:?}"),
        }
        assert_eq!(outcome.registers[1], 0, "the second word never ran");
    }

    fn addi_x1_1() -> u32 {
        0x0010_0093
    }

    #[test]
    fn an_empty_or_unsupported_program_is_refused() {
        assert!(run_program(&[], InjectionConfig::default()).is_err());
        let error = run_program(&[0x0001_3083], InjectionConfig::default())
            .expect_err("a load must be refused");
        assert!(error.to_string().contains("unsupported instruction"));
    }

    #[test]
    fn writing_a_register_with_its_current_value_is_not_observable() {
        // add x3, x0, x0 leaves x3 at zero, so no architectural write happens.
        let outcome = run_program(&[0x0000_01b3], InjectionConfig::default()).expect("run");
        assert!(outcome.trace.events[0].register_writes.is_empty());
    }
}

#[cfg(test)]
mod isa_tests {
    use super::*;

    /// Macro-operation fusion makes the CKB-VM decoder read past the word that
    /// was injected, so a fused step would retire several instructions against
    /// a Sail side that retires one. The injected default must not enable it.
    #[test]
    fn the_injection_default_does_not_enable_macro_op_fusion() {
        assert_eq!(InjectionConfig::default().isa & ckb_vm::ISA_MOP, 0);
        assert_eq!(
            InjectionConfig::default().isa,
            ckb_vm::ISA_IMC | ckb_vm::ISA_B
        );
    }
}
