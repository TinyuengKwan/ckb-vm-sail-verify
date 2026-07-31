//! Strict trace comparison. A common prefix is never sufficient for PASS.

use crate::{CommitEvent, ExecutionTrace, TraceEnd};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TerminalPolicy {
    Exact,
    CategoryOnly,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TraceMismatch {
    pub step: Option<usize>,
    pub field: String,
    pub left: String,
    pub right: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompareResult {
    pub compared_steps: usize,
    pub mismatch: Option<TraceMismatch>,
}

impl CompareResult {
    pub fn compare(left: &ExecutionTrace, right: &ExecutionTrace) -> Self {
        Self::compare_with_policy(left, right, TerminalPolicy::Exact)
    }

    pub fn compare_with_policy(
        left: &ExecutionTrace,
        right: &ExecutionTrace,
        terminal_policy: TerminalPolicy,
    ) -> Self {
        for (step, (left_event, right_event)) in left.events.iter().zip(&right.events).enumerate() {
            if let Some(mismatch) = compare_event(step, left_event, right_event) {
                return Self {
                    compared_steps: step,
                    mismatch: Some(mismatch),
                };
            }
        }

        let common = left.events.len().min(right.events.len());
        if left.events.len() != right.events.len() {
            return Self {
                compared_steps: common,
                mismatch: Some(TraceMismatch {
                    step: Some(common),
                    field: "trace_length".into(),
                    left: left.events.len().to_string(),
                    right: right.events.len().to_string(),
                }),
            };
        }

        if !terminal_matches(&left.end, &right.end, terminal_policy) {
            return Self {
                compared_steps: common,
                mismatch: Some(TraceMismatch {
                    step: None,
                    field: "termination".into(),
                    left: format!("{:?}", left.end),
                    right: format!("{:?}", right.end),
                }),
            };
        }

        if common == 0 {
            return Self {
                compared_steps: 0,
                mismatch: Some(TraceMismatch {
                    step: None,
                    field: "empty_trace".into(),
                    left: "0 committed events".into(),
                    right: "0 committed events".into(),
                }),
            };
        }

        Self {
            compared_steps: common,
            mismatch: None,
        }
    }

    pub fn passed(&self) -> bool {
        self.mismatch.is_none()
    }
}

fn terminal_matches(left: &TraceEnd, right: &TraceEnd, policy: TerminalPolicy) -> bool {
    match policy {
        TerminalPolicy::Exact => left == right,
        TerminalPolicy::CategoryOnly => left.category() == right.category(),
    }
}

fn compare_event(step: usize, left: &CommitEvent, right: &CommitEvent) -> Option<TraceMismatch> {
    macro_rules! compare_field {
        ($name:literal, $field:ident) => {
            if left.$field != right.$field {
                return Some(TraceMismatch {
                    step: Some(step),
                    field: $name.into(),
                    left: format!("{:?}", left.$field),
                    right: format!("{:?}", right.$field),
                });
            }
        };
    }

    compare_field!("order", order);
    compare_field!("instruction", instruction);
    compare_field!("pc_before", pc_before);
    compare_field!("pc_after", pc_after);
    compare_field!("register_writes", register_writes);
    compare_field!("memory", memory);
    compare_field!("trap", trap);
    compare_field!("halt", halt);
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event() -> CommitEvent {
        CommitEvent {
            order: 0,
            instruction: 0x0020_81b3,
            pc_before: 0x1000,
            pc_after: 0x1004,
            register_writes: vec![],
            memory: vec![],
            trap: false,
            halt: false,
        }
    }

    #[test]
    fn a_missing_tail_event_is_a_failure() {
        let left = ExecutionTrace::new(vec![event()], TraceEnd::StepLimit);
        let right = ExecutionTrace::new(vec![], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "trace_length");
    }

    #[test]
    fn an_execution_error_is_not_completion() {
        let left = ExecutionTrace::new(vec![], TraceEnd::Completed { exit_code: None });
        let right = ExecutionTrace::new(
            vec![],
            TraceEnd::Error {
                message: "decode failed".into(),
            },
        );
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "termination");
    }

    #[test]
    fn register_mutation_is_located() {
        let left = ExecutionTrace::new(vec![event()], TraceEnd::StepLimit);
        let mut changed = event();
        changed
            .register_writes
            .push(crate::RegisterWrite { index: 3, value: 1 });
        let right = ExecutionTrace::new(vec![changed], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "register_writes");
    }

    #[test]
    fn pc_after_mutation_is_located() {
        let left = ExecutionTrace::new(vec![event()], TraceEnd::StepLimit);
        let mut changed = event();
        changed.pc_after = 0x1008;
        let right = ExecutionTrace::new(vec![changed], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "pc_after");
    }

    #[test]
    fn register_index_mutation_is_located() {
        let mut left_event = event();
        left_event
            .register_writes
            .push(crate::RegisterWrite { index: 3, value: 7 });
        let mut right_event = left_event.clone();
        right_event.register_writes[0].index = 4;
        let left = ExecutionTrace::new(vec![left_event], TraceEnd::StepLimit);
        let right = ExecutionTrace::new(vec![right_event], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "register_writes");
    }

    #[test]
    fn register_value_mutation_is_located() {
        let mut left_event = event();
        left_event
            .register_writes
            .push(crate::RegisterWrite { index: 3, value: 7 });
        let mut right_event = left_event.clone();
        right_event.register_writes[0].value = 8;
        let left = ExecutionTrace::new(vec![left_event], TraceEnd::StepLimit);
        let right = ExecutionTrace::new(vec![right_event], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "register_writes");
    }

    #[test]
    fn trap_mutation_is_located() {
        let left = ExecutionTrace::new(vec![event()], TraceEnd::StepLimit);
        let mut changed = event();
        changed.trap = true;
        let right = ExecutionTrace::new(vec![changed], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "trap");
    }

    #[test]
    fn memory_mask_mutation_is_located() {
        let mut left_event = event();
        left_event.memory.push(crate::MemoryAccess {
            address: 0x2000,
            read_mask: 0xff,
            write_mask: 0,
            read_data: 7,
            write_data: 0,
        });
        let mut right_event = left_event.clone();
        right_event.memory[0].read_mask = 0x0f;
        let left = ExecutionTrace::new(vec![left_event], TraceEnd::StepLimit);
        let right = ExecutionTrace::new(vec![right_event], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "memory");
    }

    #[test]
    fn completion_is_not_a_step_limit() {
        let left = ExecutionTrace::new(vec![], TraceEnd::Completed { exit_code: Some(0) });
        let right = ExecutionTrace::new(vec![], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "termination");
    }

    #[test]
    fn two_empty_traces_are_not_a_pass() {
        let left = ExecutionTrace::new(vec![], TraceEnd::StepLimit);
        let right = ExecutionTrace::new(vec![], TraceEnd::StepLimit);
        let result = CompareResult::compare(&left, &right);
        assert_eq!(result.mismatch.unwrap().field, "empty_trace");
    }

    #[test]
    fn category_policy_is_explicit() {
        let left = ExecutionTrace::new(vec![event()], TraceEnd::Completed { exit_code: Some(0) });
        let right = ExecutionTrace::new(vec![event()], TraceEnd::Completed { exit_code: None });
        assert!(!CompareResult::compare(&left, &right).passed());
        assert!(
            CompareResult::compare_with_policy(&left, &right, TerminalPolicy::CategoryOnly)
                .passed()
        );
    }
}
