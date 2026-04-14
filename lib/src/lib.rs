//! Shared library for CKB-VM Sail formal verification.
//!
//! Provides common abstractions used across the project:
//! - Machine state snapshots for trace comparison
//! - CKB-VM wrapper for step-by-step execution
//! - Instruction set mapping between CKB-VM and Sail RISC-V

pub mod runner;
pub mod state;

pub use state::StepState;
