//! CKB-VM adapter producing the normalized commit-event protocol.

use anyhow::{Context, Result};
use ckb_vm::{
    decoder::{DefaultDecoder, InstDecoder},
    machine::VERSION2,
    Bytes, CoreMachine, DefaultCoreMachine, Memory, RustDefaultMachineBuilder, SparseMemory,
    SupportMachine, ISA_B, ISA_IMC, ISA_MOP,
};
use ckb_vm_sail_core::{CommitEvent, ExecutionTrace, RegisterWrite, TraceEnd};
use std::path::Path;

pub mod semantics;

pub use semantics::{
    execute as execute_pure, ArchitecturalState, Operation, SemanticsError, StepInput,
};

pub const DEFAULT_ISA: u8 = ISA_IMC | ISA_B | ISA_MOP;
pub const DEFAULT_MEMORY_SIZE: usize = 4 * 1024 * 1024;

#[derive(Debug, Clone, Copy)]
pub struct RunnerConfig {
    pub isa: u8,
    pub version: u32,
    pub max_cycles: u64,
    pub memory_size: usize,
    pub max_steps: u64,
}

impl Default for RunnerConfig {
    fn default() -> Self {
        Self {
            isa: DEFAULT_ISA,
            version: VERSION2,
            max_cycles: u64::MAX,
            memory_size: DEFAULT_MEMORY_SIZE,
            max_steps: 100_000,
        }
    }
}

pub fn run_elf(path: impl AsRef<Path>, config: RunnerConfig) -> Result<ExecutionTrace> {
    let path = path.as_ref();
    let bytes =
        std::fs::read(path).with_context(|| format!("failed to read ELF {}", path.display()))?;
    run_bytes(Bytes::from(bytes), config)
}

pub fn run_bytes(program: Bytes, config: RunnerConfig) -> Result<ExecutionTrace> {
    let core = DefaultCoreMachine::<u64, SparseMemory<u64>>::new_with_memory(
        config.isa,
        config.version,
        config.max_cycles,
        config.memory_size,
    );
    let mut machine = RustDefaultMachineBuilder::new(core).build();
    machine
        .load_program(&program, std::iter::empty::<Result<Bytes, ckb_vm::Error>>())
        .context("failed to load ELF in CKB-VM")?;
    machine.set_running(true);

    let mut decoder = <DefaultDecoder as InstDecoder>::new::<u64>(config.isa, config.version);
    let mut events = Vec::new();

    while machine.running() && events.len() < config.max_steps as usize {
        let order = events.len() as u64;
        let pc_before = *machine.pc();
        let before = capture_registers(&machine);
        let instruction = match machine.memory_mut().execute_load32(pc_before) {
            Ok(bits) => bits,
            Err(error) => {
                return Ok(ExecutionTrace::new(
                    events,
                    TraceEnd::Error {
                        message: format!("instruction fetch at {pc_before:#x}: {error}"),
                    },
                ));
            }
        };

        let result = machine.step(&mut decoder);
        let after = capture_registers(&machine);
        let trap = result.is_err();
        let halt = !machine.running();
        events.push(
            CommitEvent {
                order,
                instruction,
                pc_before,
                pc_after: *machine.pc(),
                register_writes: changed_registers(&before, &after),
                // CKB-VM does not expose committed data-memory accesses at this
                // boundary yet. Empty is an explicit missing-observation marker:
                // a Sail memory event will therefore mismatch instead of passing.
                memory: Vec::new(),
                trap,
                halt,
            }
            .normalize(),
        );

        if let Err(error) = result {
            return Ok(ExecutionTrace::new(
                events,
                TraceEnd::Error {
                    message: error.to_string(),
                },
            ));
        }
    }

    let end = if machine.running() {
        TraceEnd::StepLimit
    } else {
        TraceEnd::Completed {
            exit_code: Some(i32::from(machine.exit_code())),
        }
    };
    Ok(ExecutionTrace::new(events, end))
}

fn capture_registers<M>(machine: &M) -> [u64; 32]
where
    M: CoreMachine<REG = u64>,
{
    let mut registers = [0; 32];
    registers.copy_from_slice(&machine.registers()[..32]);
    registers
}

fn changed_registers(before: &[u64; 32], after: &[u64; 32]) -> Vec<RegisterWrite> {
    before
        .iter()
        .zip(after)
        .enumerate()
        .filter_map(|(index, (old, new))| {
            (index != 0 && old != new).then_some(RegisterWrite {
                index: index as u8,
                value: *new,
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_delta_ignores_unchanged_values_and_x0() {
        let mut before = [0; 32];
        let mut after = [0; 32];
        before[0] = 1;
        after[0] = 2;
        after[3] = 7;
        assert_eq!(
            changed_registers(&before, &after),
            vec![RegisterWrite { index: 3, value: 7 }]
        );
    }
}
