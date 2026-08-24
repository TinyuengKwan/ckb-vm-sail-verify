//! Running one case against both engines and reporting the result.
//!
//! Nothing in this module can turn a failure into a PASS: a runner error, an
//! unsupported instruction, an empty trace, a differing field, a differing
//! trace length and a differing termination all end up as `passed: false`.

use ckb_vm_sail_ckb_runner::{run_injected_program as run_ckb, InjectionConfig};
use ckb_vm_sail_core::{CompareResult, ExecutionTrace, TerminalPolicy};
use ckb_vm_sail_riscv_runner::{dii::V1_PACKET_BYTES, run_injected_program as run_sail, DiiConfig};
use serde::Serialize;
use std::path::PathBuf;

use crate::{
    artifact::{
        hex_bytes, hex_words, Artifact, Environment, InitialState, Replay, ARTIFACT_SCHEMA_VERSION,
    },
    corpus::TestProgram,
};

#[derive(Debug, Clone)]
pub struct RunOptions {
    pub dii: DiiConfig,
    pub ckb: InjectionConfig,
    pub terminal_policy: TerminalPolicy,
    pub artifact_dir: Option<PathBuf>,
    /// Seed the corpus was generated with, recorded for replay commands.
    pub seed: u64,
}

/// Machine-readable outcome of one case.
#[derive(Debug, Clone, Serialize)]
pub struct CaseReport {
    pub id: String,
    pub description: String,
    pub family: String,
    pub focus_step: usize,
    pub instructions: usize,
    pub passed: bool,
    pub classification: String,
    pub comparison: Option<CompareResult>,
    pub error: Option<String>,
    pub artifact: Option<PathBuf>,
}

pub const CLASSIFICATION_MATCH: &str = "match";
pub const CLASSIFICATION_MISMATCH: &str = "unclassified_mismatch";
pub const CLASSIFICATION_RUNNER_ERROR: &str = "runner_error";
pub const CLASSIFICATION_UNSUPPORTED: &str = "unsupported";

/// Both engines' traces for one case.
#[derive(Debug, Clone)]
pub struct EnginePair {
    pub ckb: ExecutionTrace,
    pub sail: ExecutionTrace,
    pub packets: Vec<[u8; V1_PACKET_BYTES]>,
}

/// Run one case on both engines, failing if either engine fails.
///
/// [`run_case`] keeps whichever side succeeded so a runner error can still be
/// reported with partial evidence; this is the stricter entry point used by
/// the mutation matrix, which has nothing to say about a case that did not
/// produce two traces.
pub fn run_pair(case: &TestProgram, options: &RunOptions) -> anyhow::Result<EnginePair> {
    let ckb = run_ckb(&case.instructions, options.ckb)
        .map_err(|error| anyhow::anyhow!("CKB-VM runner: {error:#}"))?;
    let sail = run_sail(&case.instructions, &options.dii)
        .map_err(|error| anyhow::anyhow!("Sail runner: {error:#}"))?;
    Ok(EnginePair {
        ckb: ckb.trace,
        sail: sail.trace,
        packets: sail.raw_packets,
    })
}

pub fn run_case(case: &TestProgram, options: &RunOptions, environment: &Environment) -> CaseReport {
    let ckb = run_ckb(&case.instructions, options.ckb).map(|outcome| outcome.trace);
    let sail = run_sail(&case.instructions, &options.dii);

    let (comparison, ckb_trace, sail_trace, packets, error) = match (ckb, sail) {
        (Ok(ckb), Ok(sail)) => {
            let comparison =
                CompareResult::compare_with_policy(&ckb, &sail.trace, options.terminal_policy);
            (
                Some(comparison),
                Some(ckb),
                Some(sail.trace),
                sail.raw_packets,
                None,
            )
        }
        (Err(error), sail) => (
            None,
            None,
            sail.as_ref().ok().map(|outcome| outcome.trace.clone()),
            sail.map(|outcome| outcome.raw_packets).unwrap_or_default(),
            Some(format!("CKB-VM runner: {error:#}")),
        ),
        (Ok(ckb), Err(error)) => (
            None,
            Some(ckb),
            None,
            Vec::new(),
            Some(format!("Sail runner: {error:#}")),
        ),
    };

    let passed = comparison.as_ref().is_some_and(CompareResult::passed);
    let classification = classify(&comparison, error.as_deref());
    let artifact = options.artifact_dir.as_ref().map(|directory| {
        let artifact = Artifact {
            schema_version: ARTIFACT_SCHEMA_VERSION,
            instructions_hex: hex_words(&case.instructions),
            case: case.clone(),
            environment: environment.clone(),
            initial_state: InitialState::default(),
            passed,
            classification: classification.clone(),
            comparison: comparison.clone(),
            error: error.clone(),
            ckb_trace: ckb_trace.clone(),
            sail_trace: sail_trace.clone(),
            sail_raw_packets: hex_bytes(&packets),
            replay: replay_commands(case, directory, options.seed),
        };
        artifact.write(directory)
    });

    let (artifact, artifact_error) = match artifact {
        Some(Ok(path)) => (Some(path), None),
        Some(Err(failure)) => (None, Some(format!("artifact: {failure:#}"))),
        None => (None, None),
    };

    CaseReport {
        id: case.id.clone(),
        description: case.description.clone(),
        family: case.family.clone(),
        focus_step: case.focus_step,
        instructions: case.instructions.len(),
        // A run whose evidence could not be stored is not a clean pass.
        passed: passed && artifact_error.is_none(),
        classification: if artifact_error.is_some() {
            CLASSIFICATION_RUNNER_ERROR.to_owned()
        } else {
            classification
        },
        comparison,
        error: match (error, artifact_error) {
            (Some(error), Some(artifact)) => Some(format!("{error}; {artifact}")),
            (Some(error), None) | (None, Some(error)) => Some(error),
            (None, None) => None,
        },
        artifact,
    }
}

fn classify(comparison: &Option<CompareResult>, error: Option<&str>) -> String {
    match (comparison, error) {
        (Some(comparison), _) if comparison.passed() => CLASSIFICATION_MATCH.to_owned(),
        (Some(_), _) => CLASSIFICATION_MISMATCH.to_owned(),
        (None, Some(error)) if error.contains("unsupported instruction") => {
            CLASSIFICATION_UNSUPPORTED.to_owned()
        }
        (None, _) => CLASSIFICATION_RUNNER_ERROR.to_owned(),
    }
}

fn replay_commands(case: &TestProgram, directory: &std::path::Path, seed: u64) -> Replay {
    let artifact_path = directory.join(format!("{}.json", case.id));
    Replay {
        from_artifact: format!(
            "cargo run -p ckb-vm-sail-diff -- --replay {}",
            artifact_path.display()
        ),
        from_corpus: Some(format!(
            "cargo run -p ckb-vm-sail-diff -- --corpus --case {} --seed {seed}",
            case.id
        )),
    }
}

/// Compare two already-produced traces. Used by the ELF path.
pub fn compare_traces(
    ckb: &ExecutionTrace,
    sail: &ExecutionTrace,
    policy: TerminalPolicy,
) -> CompareResult {
    CompareResult::compare_with_policy(ckb, sail, policy)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm_sail_core::{CommitEvent, TraceEnd, TraceMismatch};

    fn passing() -> CompareResult {
        CompareResult {
            compared_steps: 1,
            mismatch: None,
        }
    }

    fn failing() -> CompareResult {
        CompareResult {
            compared_steps: 0,
            mismatch: Some(TraceMismatch {
                step: Some(0),
                field: "pc_after".into(),
                left: "1".into(),
                right: "2".into(),
            }),
        }
    }

    #[test]
    fn classification_follows_the_evidence() {
        assert_eq!(classify(&Some(passing()), None), CLASSIFICATION_MATCH);
        assert_eq!(classify(&Some(failing()), None), CLASSIFICATION_MISMATCH);
        assert_eq!(
            classify(&None, Some("CKB-VM runner: unsupported instruction 0x3")),
            CLASSIFICATION_UNSUPPORTED
        );
        assert_eq!(
            classify(&None, Some("Sail runner: connection refused")),
            CLASSIFICATION_RUNNER_ERROR
        );
        assert_eq!(classify(&None, None), CLASSIFICATION_RUNNER_ERROR);
    }

    #[test]
    fn an_empty_pair_of_traces_never_passes() {
        let empty = ExecutionTrace::new(vec![], TraceEnd::InjectionComplete);
        let result = compare_traces(&empty, &empty, TerminalPolicy::Exact);
        assert!(!result.passed());
        assert_eq!(result.mismatch.expect("mismatch").field, "empty_trace");
    }

    #[test]
    fn a_differing_termination_never_passes() {
        let event = CommitEvent {
            order: 0,
            instruction: 0x0020_81b3,
            pc_before: 0x8000_0000,
            pc_after: 0x8000_0004,
            register_writes: vec![],
            memory: vec![],
            trap: false,
            halt: false,
        };
        let left = ExecutionTrace::new(vec![event.clone()], TraceEnd::InjectionComplete);
        let right = ExecutionTrace::new(vec![event], TraceEnd::StepLimit);
        assert!(!compare_traces(&left, &right, TerminalPolicy::Exact).passed());
        assert!(!compare_traces(&left, &right, TerminalPolicy::CategoryOnly).passed());
    }
}
