//! Provisional small, total architectural functions intended for extraction.
//!
//! Keep this module free of VM plumbing, I/O, allocation-heavy state and
//! callbacks. The runtime interpreter can eventually call these functions
//! directly; until then, equivalence to production remains a separate proof
//! obligation and this module is not proof evidence.

use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchitecturalState {
    pub registers: [u64; 32],
    pub pc: u64,
}

impl ArchitecturalState {
    pub fn new(pc: u64) -> Self {
        Self {
            registers: [0; 32],
            pc,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct StepInput {
    pub operation: Operation,
    pub instruction_length: u8,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Operation {
    Add { rd: u8, rs1: u8, rs2: u8 },
    Sub { rd: u8, rs1: u8, rs2: u8 },
    Addi { rd: u8, rs1: u8, immediate: i64 },
    Slli { rd: u8, rs1: u8, shift: u8 },
    Srli { rd: u8, rs1: u8, shift: u8 },
    Srai { rd: u8, rs1: u8, shift: u8 },
    Beq { rs1: u8, rs2: u8, offset: i64 },
    Jal { rd: u8, offset: i64 },
    Mul { rd: u8, rs1: u8, rs2: u8 },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SemanticsError {
    InvalidRegister(u8),
    InvalidInstructionLength(u8),
}

impl fmt::Display for SemanticsError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidRegister(index) => write!(formatter, "invalid register x{index}"),
            Self::InvalidInstructionLength(length) => {
                write!(formatter, "invalid instruction length {length}")
            }
        }
    }
}

impl std::error::Error for SemanticsError {}

/// Execute one already-decoded operation.
///
/// Arithmetic is deliberately wrapping: it denotes RV64 bit-vector behavior,
/// rather than Rust debug-overflow behavior.
pub fn execute(
    input: StepInput,
    state: &ArchitecturalState,
) -> Result<ArchitecturalState, SemanticsError> {
    if !matches!(input.instruction_length, 2 | 4) {
        return Err(SemanticsError::InvalidInstructionLength(
            input.instruction_length,
        ));
    }

    validate_operation(input.operation)?;
    let mut next = state.clone();
    next.registers[0] = 0;
    next.pc = state.pc.wrapping_add(u64::from(input.instruction_length));

    match input.operation {
        Operation::Add { rd, rs1, rs2 } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_add(state.registers[usize::from(rs2)]),
            );
        }
        Operation::Sub { rd, rs1, rs2 } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_sub(state.registers[usize::from(rs2)]),
            );
        }
        Operation::Addi { rd, rs1, immediate } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_add(immediate as u64),
            );
        }
        Operation::Slli { rd, rs1, shift } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_shl(u32::from(shift & 63)),
            );
        }
        Operation::Srli { rd, rs1, shift } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_shr(u32::from(shift & 63)),
            );
        }
        Operation::Srai { rd, rs1, shift } => {
            let result = (state.registers[usize::from(rs1)] as i64) >> (shift & 63);
            write_register(&mut next, rd, result as u64);
        }
        Operation::Beq { rs1, rs2, offset } => {
            if state.registers[usize::from(rs1)] == state.registers[usize::from(rs2)] {
                next.pc = state.pc.wrapping_add(offset as u64);
            }
        }
        Operation::Jal { rd, offset } => {
            write_register(
                &mut next,
                rd,
                state.pc.wrapping_add(u64::from(input.instruction_length)),
            );
            next.pc = state.pc.wrapping_add(offset as u64);
        }
        Operation::Mul { rd, rs1, rs2 } => {
            write_register(
                &mut next,
                rd,
                state.registers[usize::from(rs1)].wrapping_mul(state.registers[usize::from(rs2)]),
            );
        }
    }

    next.registers[0] = 0;
    Ok(next)
}

fn validate_operation(operation: Operation) -> Result<(), SemanticsError> {
    let registers: &[u8] = match &operation {
        Operation::Add { rd, rs1, rs2 }
        | Operation::Sub { rd, rs1, rs2 }
        | Operation::Mul { rd, rs1, rs2 } => &[*rd, *rs1, *rs2],
        Operation::Addi { rd, rs1, .. }
        | Operation::Slli { rd, rs1, .. }
        | Operation::Srli { rd, rs1, .. }
        | Operation::Srai { rd, rs1, .. } => &[*rd, *rs1],
        Operation::Beq { rs1, rs2, .. } => &[*rs1, *rs2],
        Operation::Jal { rd, .. } => &[*rd],
    };

    if let Some(index) = registers.iter().copied().find(|index| *index >= 32) {
        return Err(SemanticsError::InvalidRegister(index));
    }
    Ok(())
}

fn write_register(state: &mut ArchitecturalState, index: u8, value: u64) {
    if index != 0 {
        state.registers[usize::from(index)] = value;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn step(operation: Operation) -> StepInput {
        StepInput {
            operation,
            instruction_length: 4,
        }
    }

    #[test]
    fn add_wraps_at_xlen() {
        let mut state = ArchitecturalState::new(0x1000);
        state.registers[1] = u64::MAX;
        state.registers[2] = 2;
        let next = execute(
            step(Operation::Add {
                rd: 3,
                rs1: 1,
                rs2: 2,
            }),
            &state,
        )
        .expect("valid step");
        assert_eq!(next.registers[3], 1);
        assert_eq!(next.pc, 0x1004);
    }

    #[test]
    fn x0_cannot_be_changed() {
        let mut state = ArchitecturalState::new(0);
        state.registers[0] = 99;
        let next = execute(
            step(Operation::Addi {
                rd: 0,
                rs1: 0,
                immediate: 1,
            }),
            &state,
        )
        .expect("valid step");
        assert_eq!(next.registers[0], 0);
    }

    #[test]
    fn taken_branch_uses_pc_relative_offset() {
        let state = ArchitecturalState::new(0x1000);
        let next = execute(
            step(Operation::Beq {
                rs1: 0,
                rs2: 0,
                offset: -4,
            }),
            &state,
        )
        .expect("valid step");
        assert_eq!(next.pc, 0x0ffc);
    }

    #[test]
    fn not_taken_branch_advances_by_instruction_length() {
        let mut state = ArchitecturalState::new(0x1000);
        state.registers[1] = 1;
        state.registers[2] = 2;
        let next = execute(
            step(Operation::Beq {
                rs1: 1,
                rs2: 2,
                offset: -4,
            }),
            &state,
        )
        .expect("valid step");
        assert_eq!(next.pc, 0x1004);
    }

    #[test]
    fn jal_writes_return_address() {
        let state = ArchitecturalState::new(0x1000);
        let next = execute(step(Operation::Jal { rd: 1, offset: 16 }), &state).expect("valid step");
        assert_eq!(next.registers[1], 0x1004);
        assert_eq!(next.pc, 0x1010);
    }
}
