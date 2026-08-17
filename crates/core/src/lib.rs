//! Backend-neutral architectural events and strict trace comparison.

pub mod compare;
pub mod event;
pub mod program;

pub use compare::{CompareResult, TerminalPolicy, TraceMismatch};
pub use event::{
    normalize_instruction_width, CommitEvent, ExecutionTrace, MemoryAccess, RegisterShadow,
    RegisterWrite, TraceEnd,
};
pub use program::{validate_program, UnsupportedInstruction, INJECTION_ENTRY};
