//! Minimal RV64I encoders for building injected corpus programs.
//!
//! These build *test inputs*, not semantics: nothing here decides what an
//! instruction means, and no comparison result depends on this module beyond
//! which bit pattern both engines were asked to execute. A wrong encoding
//! produces a different — but still identically injected — instruction on both
//! sides, so it can weaken coverage and never manufacture a PASS.

const OPCODE_OP: u32 = 0b011_0011;
const OPCODE_OP_IMM: u32 = 0b001_0011;
const OPCODE_BRANCH: u32 = 0b110_0011;

fn register(index: u8) -> u32 {
    assert!(index < 32, "x{index} is not an integer register");
    u32::from(index)
}

fn r_type(funct7: u32, rs2: u8, rs1: u8, funct3: u32, rd: u8, opcode: u32) -> u32 {
    (funct7 << 25)
        | (register(rs2) << 20)
        | (register(rs1) << 15)
        | (funct3 << 12)
        | (register(rd) << 7)
        | opcode
}

fn i_type(immediate: i32, rs1: u8, funct3: u32, rd: u8, opcode: u32) -> u32 {
    assert!(
        (-2048..=2047).contains(&immediate),
        "{immediate} does not fit in a signed 12-bit immediate"
    );
    ((immediate as u32 & 0xfff) << 20)
        | (register(rs1) << 15)
        | (funct3 << 12)
        | (register(rd) << 7)
        | opcode
}

/// `add rd, rs1, rs2`
pub fn add(rd: u8, rs1: u8, rs2: u8) -> u32 {
    r_type(0, rs2, rs1, 0b000, rd, OPCODE_OP)
}

/// `addi rd, rs1, immediate`
pub fn addi(rd: u8, rs1: u8, immediate: i32) -> u32 {
    i_type(immediate, rs1, 0b000, rd, OPCODE_OP_IMM)
}

/// `slli rd, rs1, shift` (RV64 shift amounts are six bits wide).
pub fn slli(rd: u8, rs1: u8, shift: u32) -> u32 {
    assert!(shift < 64, "{shift} is not an RV64 shift amount");
    (shift << 20) | (register(rs1) << 15) | (0b001 << 12) | (register(rd) << 7) | OPCODE_OP_IMM
}

/// `beq rs1, rs2, offset`, where the offset is relative to the branch itself.
pub fn beq(rs1: u8, rs2: u8, offset: i32) -> u32 {
    assert!(
        (-4096..=4094).contains(&offset) && offset % 2 == 0,
        "{offset} is not an encodable branch offset"
    );
    // funct3 is 0b000 for BEQ, so it contributes nothing to the word.
    let bits = offset as u32;
    (((bits >> 12) & 0x1) << 31)
        | (((bits >> 5) & 0x3f) << 25)
        | (register(rs2) << 20)
        | (register(rs1) << 15)
        | (((bits >> 1) & 0xf) << 8)
        | (((bits >> 11) & 0x1) << 7)
        | OPCODE_BRANCH
}

/// `nop`, the canonical `addi x0, x0, 0`.
pub fn nop() -> u32 {
    addi(0, 0, 0)
}

/// Build an exact 64-bit constant in `rd` using only OP-IMM instructions.
///
/// Direct instruction injection has no side channel for setting registers, so a
/// shared initial state has to be *executed* into existence on both sides. The
/// value is split into a 9-bit head and five 11-bit chunks; each chunk is
/// shifted in and added, which stays inside the signed 12-bit immediate range
/// and therefore needs no sign-extension correction.
pub fn materialize(rd: u8, value: u64) -> Vec<u32> {
    assert!(rd != 0, "x0 cannot hold a value");
    let chunks = [
        (value >> 55) & 0x1ff,
        (value >> 44) & 0x7ff,
        (value >> 33) & 0x7ff,
        (value >> 22) & 0x7ff,
        (value >> 11) & 0x7ff,
        value & 0x7ff,
    ];

    let first = chunks
        .iter()
        .position(|&chunk| chunk != 0)
        .unwrap_or(chunks.len() - 1);
    let mut program = vec![addi(rd, 0, chunks[first] as i32)];
    for &chunk in &chunks[first + 1..] {
        program.push(slli(rd, rd, 11));
        program.push(addi(rd, rd, chunk as i32));
    }
    program
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm_sail_ckb_runner::{run_injected_program, InjectionConfig};

    #[test]
    fn encodings_match_hand_assembled_words() {
        assert_eq!(add(3, 1, 2), 0x0020_81b3);
        assert_eq!(addi(1, 0, 5), 0x0050_0093);
        assert_eq!(addi(2, 0, 7), 0x0070_0113);
        assert_eq!(addi(1, 0, -2048), 0x8000_0093);
        assert_eq!(slli(1, 1, 11), 0x00b0_9093);
        assert_eq!(beq(0, 0, 8), 0x0000_0463);
        assert_eq!(beq(1, 2, -4), 0xfe20_8ee3);
        assert_eq!(nop(), 0x0000_0013);
    }

    /// The real interpreter is the oracle for the setup sequence: if
    /// `materialize` were wrong, every corpus case would silently test a
    /// different initial state than its name claims.
    #[test]
    fn materialize_builds_the_exact_value_on_the_real_interpreter() {
        for value in [
            0,
            1,
            0x7ff,
            0x800,
            u64::from(u32::MAX),
            0x7fff_ffff_ffff_ffff,
            0x8000_0000_0000_0000,
            u64::MAX,
            0x0123_4567_89ab_cdef,
        ] {
            let program = materialize(7, value);
            let outcome =
                run_injected_program(&program, InjectionConfig::default()).expect("run setup");
            assert_eq!(
                outcome.registers[7], value,
                "materialize({value:#x}) built {:#x}",
                outcome.registers[7]
            );
        }
    }

    #[test]
    fn materialize_stays_within_the_immediate_range() {
        for value in [u64::MAX, 0x8000_0000_0000_0000, 0xffff_ffff_ffff_f800] {
            // Encoding asserts would fire inside `materialize` itself.
            assert!(!materialize(1, value).is_empty());
        }
    }
}
