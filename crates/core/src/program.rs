//! Directly injected instruction programs and their supported subset.
//!
//! Both backends are driven by the same finite list of raw instruction words
//! rather than by an ELF file, which is what removes the ELF loader and
//! platform stack from the initial-state comparison.

use std::fmt;

/// Reset program counter of an injected program.
///
/// Fixed by the upstream RVFI-DII handler (`rvfi_handler::get_entry` in
/// `deps/sail-riscv/c_emulator/rvfi_dii.cpp`). The CKB side must place its
/// program at the same address or the architectural PCs cannot be compared.
pub const INJECTION_ENTRY: u64 = 0x8000_0000;

/// An instruction the current observation protocol cannot compare honestly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnsupportedInstruction {
    pub index: usize,
    pub bits: u32,
    pub reason: &'static str,
}

impl fmt::Display for UnsupportedInstruction {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "unsupported instruction {:#010x} at index {}: {}",
            self.bits, self.index, self.reason
        )
    }
}

impl std::error::Error for UnsupportedInstruction {}

const MEMORY_REASON: &str =
    "data-memory accesses are unsupported: CKB-VM does not expose committed read/write \
     events at this boundary, so the memory field of a commit event would be missing \
     rather than equal";
const SYSTEM_REASON: &str =
    "SYSTEM instructions are unsupported: CKB-VM syscalls and the Sail HTIF/CSR \
     platform contracts differ and are excluded from the current MVP";

/// Classify one raw instruction word against the supported subset.
///
/// This rejects instruction classes whose observation is *missing* on one side.
/// Refusing them keeps `docs/semantic-gaps.md` honest: a gap is reported as
/// unsupported instead of silently comparing an absent event against an
/// observed one.
pub fn unsupported_instruction(bits: u32) -> Option<&'static str> {
    if bits & 0b11 == 0b11 {
        return match bits & 0x7f {
            0b000_0011 | 0b000_0111 => Some(MEMORY_REASON), // LOAD, LOAD-FP
            0b010_0011 | 0b010_0111 => Some(MEMORY_REASON), // STORE, STORE-FP
            0b010_1111 => Some(MEMORY_REASON),              // AMO
            0b111_0011 => Some(SYSTEM_REASON),              // SYSTEM
            _ => None,
        };
    }

    let quadrant = bits & 0b11;
    let funct3 = (bits >> 13) & 0b111;
    match (quadrant, funct3) {
        // Quadrant 0 is entirely loads and stores apart from C.ADDI4SPN. The
        // all-zero illegal encoding also lands here and is deliberately left
        // to the trap comparison rather than reported as a memory gap.
        (0b00, 0b000) => None,
        (0b00, _) => Some(MEMORY_REASON),
        // Stack-pointer relative loads and stores.
        (0b10, 0b010 | 0b011 | 0b110 | 0b111) => Some(MEMORY_REASON),
        (0b10, 0b100) if bits & 0xffff == 0x9002 => Some(SYSTEM_REASON), // C.EBREAK
        _ => None,
    }
}

/// Reject a program that leaves the honestly comparable subset.
pub fn validate_program(program: &[u32]) -> Result<(), UnsupportedInstruction> {
    for (index, &bits) in program.iter().enumerate() {
        if let Some(reason) = unsupported_instruction(bits) {
            return Err(UnsupportedInstruction {
                index,
                bits,
                reason,
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arithmetic_and_branches_are_supported() {
        // add x3, x1, x2 / addi x1, x0, 5 / beq x1, x2, 8 / c.addi a0, 1
        for bits in [0x0020_81b3, 0x0050_0093, 0x0020_8463, 0x0505] {
            assert_eq!(unsupported_instruction(bits), None, "{bits:#010x}");
        }
        assert_eq!(validate_program(&[0x0020_81b3, 0x0050_0093]), Ok(()));
    }

    #[test]
    fn memory_and_system_instructions_are_rejected_not_compared() {
        // ld x1, 0(x2) / sd x1, 0(x2) / ecall / c.ldsp a0, 0 / c.sdsp a0, 0
        for bits in [0x0001_3083, 0x0011_3023, 0x0000_0073, 0x6502, 0xe02a] {
            assert!(
                unsupported_instruction(bits).is_some(),
                "{bits:#010x} must be rejected"
            );
        }
    }

    #[test]
    fn validation_locates_the_offending_index() {
        let error = validate_program(&[0x0050_0093, 0x0001_3083]).expect_err("load is rejected");
        assert_eq!(error.index, 1);
        assert_eq!(error.bits, 0x0001_3083);
        assert!(error.to_string().contains("index 1"));
    }
}
