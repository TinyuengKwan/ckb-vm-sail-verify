//! Normalized, backend-neutral architectural observations.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RegisterWrite {
    pub index: u8,
    pub value: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MemoryAccess {
    pub address: u64,
    pub read_mask: u32,
    pub write_mask: u32,
    pub read_data: u64,
    pub write_data: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CommitEvent {
    pub order: u64,
    pub instruction: u32,
    pub pc_before: u64,
    pub pc_after: u64,
    pub register_writes: Vec<RegisterWrite>,
    pub memory: Vec<MemoryAccess>,
    pub trap: bool,
    pub halt: bool,
}

impl CommitEvent {
    /// Normalize architectural no-ops such as writes to x0.
    pub fn normalize(mut self) -> Self {
        self.register_writes.retain(|write| write.index != 0);
        self.memory
            .retain(|access| access.read_mask != 0 || access.write_mask != 0);
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum TraceEnd {
    Completed {
        exit_code: Option<i32>,
    },
    StepLimit,
    /// Every instruction of a directly injected program was executed and the
    /// driver ended the trace. This is distinct from `StepLimit`: nothing was
    /// truncated, the finite injected instruction stream simply ran out.
    InjectionComplete,
    Trap {
        reason: String,
    },
    Error {
        message: String,
    },
}

impl TraceEnd {
    pub fn category(&self) -> &'static str {
        match self {
            Self::Completed { .. } => "completed",
            Self::StepLimit => "step_limit",
            Self::InjectionComplete => "injection_complete",
            Self::Trap { .. } => "trap",
            Self::Error { .. } => "error",
        }
    }
}

/// Architectural width normalization for a fetched instruction word.
///
/// A 16-bit compressed instruction is reported by RVFI in the low half of a
/// 32-bit field, while a raw 32-bit fetch from an implementation also contains
/// the bytes of the *following* instruction. Both sides must therefore drop the
/// upper half whenever the two low bits say the instruction is compressed.
pub fn normalize_instruction_width(bits: u32) -> u32 {
    if bits & 0b11 == 0b11 {
        bits
    } else {
        bits & 0xffff
    }
}

/// Mirror of the integer register file used to keep both observers at the same
/// resolution.
///
/// CKB-VM exposes register *state*, so an observer can only see a write that
/// changes it. Sail RVFI reports the destination register of every retired
/// instruction, including a write that stores the value the register already
/// held. Feeding the RVFI side through this shadow file reduces both sides to
/// the same observable — an architectural state change — instead of letting the
/// difference in observation power show up as a false mismatch.
///
/// This is sound only because RVFI reports *every* integer register write, so
/// the shadow file tracks the model exactly. The cost is stated in
/// `docs/semantic-gaps.md`: a write of an already-held value is invisible.
#[derive(Debug, Clone)]
pub struct RegisterShadow {
    registers: [u64; 32],
}

impl RegisterShadow {
    /// The architectural reset state used by direct instruction injection.
    pub fn zeroed() -> Self {
        Self { registers: [0; 32] }
    }

    pub fn registers(&self) -> &[u64; 32] {
        &self.registers
    }

    /// Record a reported write and return it only if it changes the state.
    pub fn observe(&mut self, index: u8, value: u64) -> Option<RegisterWrite> {
        if index == 0 || index >= 32 {
            return None;
        }
        let slot = &mut self.registers[usize::from(index)];
        if *slot == value {
            return None;
        }
        *slot = value;
        Some(RegisterWrite { index, value })
    }
}

impl Default for RegisterShadow {
    fn default() -> Self {
        Self::zeroed()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionTrace {
    pub events: Vec<CommitEvent>,
    pub end: TraceEnd,
}

impl ExecutionTrace {
    pub fn new(events: Vec<CommitEvent>, end: TraceEnd) -> Self {
        Self { events, end }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalization_discards_x0_and_empty_memory() {
        let event = CommitEvent {
            order: 0,
            instruction: 0x13,
            pc_before: 0,
            pc_after: 4,
            register_writes: vec![RegisterWrite { index: 0, value: 9 }],
            memory: vec![MemoryAccess {
                address: 0,
                read_mask: 0,
                write_mask: 0,
                read_data: 0,
                write_data: 0,
            }],
            trap: false,
            halt: false,
        }
        .normalize();

        assert!(event.register_writes.is_empty());
        assert!(event.memory.is_empty());
    }

    #[test]
    fn trace_json_round_trip_is_lossless() {
        let trace = ExecutionTrace::new(vec![], TraceEnd::Completed { exit_code: Some(0) });
        let json = serde_json::to_string(&trace).expect("serialize trace");
        let decoded: ExecutionTrace = serde_json::from_str(&json).expect("deserialize trace");
        assert_eq!(decoded, trace);
    }

    #[test]
    fn injection_complete_is_its_own_termination_category() {
        assert_eq!(TraceEnd::InjectionComplete.category(), "injection_complete");
        assert_ne!(
            TraceEnd::InjectionComplete.category(),
            TraceEnd::StepLimit.category()
        );
        let trace = ExecutionTrace::new(vec![], TraceEnd::InjectionComplete);
        let json = serde_json::to_string(&trace).expect("serialize trace");
        let decoded: ExecutionTrace = serde_json::from_str(&json).expect("deserialize trace");
        assert_eq!(decoded, trace);
    }

    #[test]
    fn compressed_instructions_lose_the_upper_half() {
        assert_eq!(normalize_instruction_width(0x0020_81b3), 0x0020_81b3);
        // A raw 32-bit fetch of `c.addi a0, 1` followed by other code.
        assert_eq!(normalize_instruction_width(0xdead_0505), 0x0505);
    }

    #[test]
    fn the_shadow_file_only_reports_state_changes() {
        let mut shadow = RegisterShadow::zeroed();
        assert_eq!(shadow.observe(0, 7), None, "x0 is never architectural");
        assert_eq!(shadow.observe(3, 0), None, "x3 already holds zero");
        assert_eq!(
            shadow.observe(3, 7),
            Some(RegisterWrite { index: 3, value: 7 })
        );
        assert_eq!(shadow.observe(3, 7), None, "rewriting the same value");
        assert_eq!(
            shadow.observe(3, 8),
            Some(RegisterWrite { index: 3, value: 8 })
        );
        assert_eq!(shadow.registers()[3], 8);
    }
}
