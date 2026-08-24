//! Corpus construction, case execution and replayable artifacts for the
//! CKB-VM versus Sail differential.
//!
//! The binary in `main.rs` is a thin command-line wrapper around these modules
//! so that the corpus and the artifact format can be exercised by tests.

pub mod artifact;
pub mod corpus;
pub mod encode;
pub mod mutation;
pub mod run;

pub use corpus::{week2_corpus, TestProgram, DEFAULT_SEED};
pub use mutation::{run_mutations, MutationKind, MutationSummary, MANDATORY_MUTATIONS};
pub use run::{run_case, CaseReport, RunOptions};
