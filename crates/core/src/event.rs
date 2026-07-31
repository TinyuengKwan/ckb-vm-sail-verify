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
    Completed { exit_code: Option<i32> },
    StepLimit,
    Trap { reason: String },
    Error { message: String },
}

impl TraceEnd {
    pub fn category(&self) -> &'static str {
        match self {
            Self::Completed { .. } => "completed",
            Self::StepLimit => "step_limit",
            Self::Trap { .. } => "trap",
            Self::Error { .. } => "error",
        }
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
}
