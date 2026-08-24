//! Mandatory mutation matrix: negative evidence that the differential works.
//!
//! A differential that only ever reports PASS is indistinguishable from one
//! that cannot fail. Every mutation here is applied to a *real* trace produced
//! by the real CKB-VM interpreter and compared against the *real* Sail trace
//! for the same injected program, so what is being tested is the shipped
//! comparison path rather than a synthetic pair of hand-written traces.
//!
//! Two properties make a mutation count as evidence:
//!
//! 1. the unmutated pair must pass first — a mutation "detected" on top of an
//!    already-failing baseline proves nothing;
//! 2. the reported first differing field must be the field that was mutated —
//!    detecting the difference somewhere else is not localization.
//!
//! A mutation that does not apply to a given case (mutating a register write
//! in a trace that commits none) is reported with its reason and never
//! silently dropped: the run only passes if every mandatory category was
//! applied and located somewhere in the corpus.

use ckb_vm_sail_core::{CompareResult, ExecutionTrace, TraceEnd};
use serde::{Deserialize, Serialize};

use crate::{corpus::TestProgram, run::run_pair, run::RunOptions};

/// The mutation categories `VERIFICATION.md` §4 makes mandatory.
///
/// The document lists five, with trace length and termination sharing an
/// entry. They are separate observations with separate comparator fields, so
/// they are separate mutations here.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MutationKind {
    PcAfter,
    RegisterIndex,
    RegisterValue,
    Trap,
    TraceLength,
    Termination,
}

pub const MANDATORY_MUTATIONS: [MutationKind; 6] = [
    MutationKind::PcAfter,
    MutationKind::RegisterIndex,
    MutationKind::RegisterValue,
    MutationKind::Trap,
    MutationKind::TraceLength,
    MutationKind::Termination,
];

impl MutationKind {
    pub fn id(self) -> &'static str {
        match self {
            Self::PcAfter => "pc_after",
            Self::RegisterIndex => "register_index",
            Self::RegisterValue => "register_value",
            Self::Trap => "trap",
            Self::TraceLength => "trace_length",
            Self::Termination => "termination",
        }
    }

    /// The comparator field that must report this mutation.
    ///
    /// Register index and value both surface through `register_writes`: the
    /// event protocol commits the whole write, so the comparison field is the
    /// same even though the injected defect differs.
    pub fn expected_field(self) -> &'static str {
        match self {
            Self::PcAfter => "pc_after",
            Self::RegisterIndex | Self::RegisterValue => "register_writes",
            Self::Trap => "trap",
            Self::TraceLength => "trace_length",
            Self::Termination => "termination",
        }
    }

    pub fn description(self) -> &'static str {
        match self {
            Self::PcAfter => "advance the committed next program counter by two",
            Self::RegisterIndex => "commit the write to a different register",
            Self::RegisterValue => "flip the low bit of the committed value",
            Self::Trap => "invert the committed trap flag",
            Self::TraceLength => "drop the last committed event",
            Self::Termination => "report a different termination category",
        }
    }

    /// Apply the mutation to a copy of `trace`.
    ///
    /// `focus_step` is the index of the instruction the case exists to
    /// exercise, so a mutation lands on the instruction under test whenever
    /// that instruction can carry it.
    pub fn apply(
        self,
        trace: &ExecutionTrace,
        focus_step: usize,
    ) -> Result<ExecutionTrace, String> {
        let mut mutated = trace.clone();
        match self {
            Self::PcAfter => {
                let index = event_index(&mutated, focus_step)?;
                let event = &mut mutated.events[index];
                event.pc_after = event.pc_after.wrapping_add(2);
            }
            Self::RegisterIndex => {
                let index = write_index(&mutated, focus_step)?;
                let write = &mut mutated.events[index].register_writes[0];
                // Stay inside x1..x31: a write to x0 is normalized away, which
                // would test the normalizer rather than the comparator.
                write.index = if write.index >= 31 {
                    1
                } else {
                    write.index + 1
                };
            }
            Self::RegisterValue => {
                let index = write_index(&mutated, focus_step)?;
                mutated.events[index].register_writes[0].value ^= 1;
            }
            Self::Trap => {
                let index = event_index(&mutated, focus_step)?;
                let event = &mut mutated.events[index];
                event.trap = !event.trap;
            }
            Self::TraceLength => {
                if mutated.events.is_empty() {
                    return Err("the trace commits no events to drop".to_owned());
                }
                mutated.events.pop();
            }
            Self::Termination => {
                // The replacement differs in category as well as in value, so
                // this is detected under `TerminalPolicy::CategoryOnly` too.
                mutated.end = match mutated.end {
                    TraceEnd::StepLimit => TraceEnd::InjectionComplete,
                    _ => TraceEnd::StepLimit,
                };
            }
        }
        Ok(mutated)
    }
}

fn event_index(trace: &ExecutionTrace, focus_step: usize) -> Result<usize, String> {
    if trace.events.is_empty() {
        return Err("the trace commits no events".to_owned());
    }
    Ok(focus_step.min(trace.events.len() - 1))
}

/// The focus event if it commits a register write, else the first event that
/// does. `BEQ` and `rd = x0` cases commit none at all.
fn write_index(trace: &ExecutionTrace, focus_step: usize) -> Result<usize, String> {
    if trace
        .events
        .get(focus_step)
        .is_some_and(|event| !event.register_writes.is_empty())
    {
        return Ok(focus_step);
    }
    trace
        .events
        .iter()
        .position(|event| !event.register_writes.is_empty())
        .ok_or_else(|| "the trace commits no register write".to_owned())
}

/// Outcome of one mutation applied to one case.
#[derive(Debug, Clone, Serialize)]
pub struct MutationReport {
    pub case_id: String,
    pub mutation: String,
    pub description: String,
    pub applied: bool,
    /// Why the mutation does not apply to this case, when it does not.
    pub skipped_because: Option<String>,
    pub expected_field: String,
    pub located_field: Option<String>,
    pub located_step: Option<usize>,
    pub detected: bool,
    /// Detected *and* localized to the mutated field.
    pub passed: bool,
}

/// Per-category tally across the corpus.
#[derive(Debug, Clone, Serialize)]
pub struct MutationCoverage {
    pub mutation: String,
    pub expected_field: String,
    pub applied: usize,
    pub located: usize,
    pub example_case: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MutationSummary {
    pub cases: usize,
    pub applied: usize,
    pub skipped: usize,
    /// Cases whose unmutated comparison did not pass, making their mutation
    /// results meaningless.
    pub baseline_failures: Vec<String>,
    /// Mutations the comparator did not notice at all.
    pub undetected: Vec<String>,
    /// Mutations noticed but reported against a different field.
    pub mislocated: Vec<String>,
    pub coverage: Vec<MutationCoverage>,
    pub reports: Vec<MutationReport>,
    pub passed: bool,
}

/// Run every mandatory mutation over every case.
///
/// Both engines run once per case; the mutations are then applied to the
/// recorded CKB-VM trace, so the emulator is not re-spawned per mutation.
pub fn run_mutations(cases: &[TestProgram], options: &RunOptions) -> MutationSummary {
    let mut reports = Vec::new();
    let mut baseline_failures = Vec::new();

    for case in cases {
        match run_pair(case, options) {
            Ok(pair) => {
                let baseline = CompareResult::compare_with_policy(
                    &pair.ckb,
                    &pair.sail,
                    options.terminal_policy,
                );
                if !baseline.passed() {
                    baseline_failures.push(case.id.clone());
                    continue;
                }
                for kind in MANDATORY_MUTATIONS {
                    reports.push(evaluate(case, kind, &pair.ckb, &pair.sail, options));
                }
            }
            Err(error) => baseline_failures.push(format!("{}: {error:#}", case.id)),
        }
    }

    summarize(cases.len(), baseline_failures, reports)
}

fn evaluate(
    case: &TestProgram,
    kind: MutationKind,
    ckb: &ExecutionTrace,
    sail: &ExecutionTrace,
    options: &RunOptions,
) -> MutationReport {
    let base = MutationReport {
        case_id: case.id.clone(),
        mutation: kind.id().to_owned(),
        description: kind.description().to_owned(),
        applied: false,
        skipped_because: None,
        expected_field: kind.expected_field().to_owned(),
        located_field: None,
        located_step: None,
        detected: false,
        passed: false,
    };

    let mutated = match kind.apply(ckb, case.focus_step) {
        Ok(mutated) => mutated,
        Err(reason) => {
            return MutationReport {
                skipped_because: Some(reason),
                ..base
            }
        }
    };

    let result = CompareResult::compare_with_policy(&mutated, sail, options.terminal_policy);
    let mismatch = result.mismatch;
    let located_field = mismatch.as_ref().map(|mismatch| mismatch.field.clone());
    let detected = located_field.is_some();
    let passed = located_field.as_deref() == Some(kind.expected_field());

    MutationReport {
        applied: true,
        located_step: mismatch.as_ref().and_then(|mismatch| mismatch.step),
        located_field,
        detected,
        passed,
        ..base
    }
}

fn summarize(
    cases: usize,
    baseline_failures: Vec<String>,
    reports: Vec<MutationReport>,
) -> MutationSummary {
    let applied = reports.iter().filter(|report| report.applied).count();
    let skipped = reports.len() - applied;

    let undetected = reports
        .iter()
        .filter(|report| report.applied && !report.detected)
        .map(|report| format!("{}/{}", report.case_id, report.mutation))
        .collect::<Vec<_>>();
    let mislocated = reports
        .iter()
        .filter(|report| report.detected && !report.passed)
        .map(|report| {
            format!(
                "{}/{}: expected {}, got {}",
                report.case_id,
                report.mutation,
                report.expected_field,
                report.located_field.as_deref().unwrap_or("none")
            )
        })
        .collect::<Vec<_>>();

    let coverage = MANDATORY_MUTATIONS
        .iter()
        .map(|kind| {
            let matching = reports
                .iter()
                .filter(|report| report.mutation == kind.id())
                .collect::<Vec<_>>();
            MutationCoverage {
                mutation: kind.id().to_owned(),
                expected_field: kind.expected_field().to_owned(),
                applied: matching.iter().filter(|report| report.applied).count(),
                located: matching.iter().filter(|report| report.passed).count(),
                example_case: matching
                    .iter()
                    .find(|report| report.passed)
                    .map(|report| report.case_id.clone()),
            }
        })
        .collect::<Vec<_>>();

    // Every mandatory category must have been located at least once. A
    // category that never applied anywhere is a gap in the corpus, not a pass.
    let every_category_located = coverage.iter().all(|entry| entry.located > 0);
    let passed = every_category_located
        && baseline_failures.is_empty()
        && undetected.is_empty()
        && mislocated.is_empty()
        && !reports.is_empty();

    MutationSummary {
        cases,
        applied,
        skipped,
        baseline_failures,
        undetected,
        mislocated,
        coverage,
        reports,
        passed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm_sail_core::{CommitEvent, RegisterWrite, TerminalPolicy};

    fn event(order: u64, write: Option<RegisterWrite>) -> CommitEvent {
        CommitEvent {
            order,
            instruction: 0x0020_81b3,
            pc_before: 0x8000_0000 + order * 4,
            pc_after: 0x8000_0004 + order * 4,
            register_writes: write.into_iter().collect(),
            memory: Vec::new(),
            trap: false,
            halt: false,
        }
    }

    fn trace_with_write() -> ExecutionTrace {
        ExecutionTrace::new(
            vec![
                event(0, Some(RegisterWrite { index: 1, value: 5 })),
                event(
                    1,
                    Some(RegisterWrite {
                        index: 3,
                        value: 12,
                    }),
                ),
            ],
            TraceEnd::InjectionComplete,
        )
    }

    fn trace_without_write() -> ExecutionTrace {
        ExecutionTrace::new(
            vec![event(0, None), event(1, None)],
            TraceEnd::InjectionComplete,
        )
    }

    /// Each mutation must be caught, and caught in the field it mutated.
    #[test]
    fn every_mandatory_mutation_is_detected_and_located() {
        let original = trace_with_write();
        for kind in MANDATORY_MUTATIONS {
            let mutated = kind.apply(&original, 1).expect("applies");
            assert_ne!(mutated, original, "{} changed nothing", kind.id());
            let result =
                CompareResult::compare_with_policy(&mutated, &original, TerminalPolicy::Exact);
            let mismatch = result
                .mismatch
                .unwrap_or_else(|| panic!("{} went undetected", kind.id()));
            assert_eq!(mismatch.field, kind.expected_field(), "{}", kind.id());
        }
    }

    #[test]
    fn a_mutation_lands_on_the_instruction_under_test() {
        let original = trace_with_write();
        let mutated = MutationKind::PcAfter.apply(&original, 1).expect("applies");
        assert_eq!(mutated.events[0], original.events[0]);
        assert_ne!(mutated.events[1].pc_after, original.events[1].pc_after);
    }

    /// A trace that commits no register write cannot carry a register
    /// mutation, and that must be reported rather than counted as a pass.
    #[test]
    fn an_inapplicable_mutation_reports_a_reason() {
        let trace = trace_without_write();
        for kind in [MutationKind::RegisterIndex, MutationKind::RegisterValue] {
            let error = kind.apply(&trace, 0).expect_err("no register write");
            assert!(error.contains("register write"), "{error}");
        }
        // The remaining categories still apply to the same trace.
        for kind in [
            MutationKind::PcAfter,
            MutationKind::Trap,
            MutationKind::TraceLength,
            MutationKind::Termination,
        ] {
            assert!(kind.apply(&trace, 0).is_ok(), "{}", kind.id());
        }
    }

    #[test]
    fn a_register_index_mutation_never_targets_x0() {
        let mut trace = trace_with_write();
        trace.events[1].register_writes[0].index = 31;
        let mutated = MutationKind::RegisterIndex
            .apply(&trace, 1)
            .expect("applies");
        assert_eq!(mutated.events[1].register_writes[0].index, 1);
    }

    /// The termination mutation must survive the loosest terminal policy.
    #[test]
    fn a_termination_mutation_is_detected_under_the_category_policy() {
        let original = trace_with_write();
        let mutated = MutationKind::Termination
            .apply(&original, 0)
            .expect("applies");
        let result =
            CompareResult::compare_with_policy(&mutated, &original, TerminalPolicy::CategoryOnly);
        assert_eq!(result.mismatch.expect("detected").field, "termination");
    }

    #[test]
    fn a_summary_without_full_coverage_does_not_pass() {
        let complete = |kind: MutationKind| MutationReport {
            case_id: "case".into(),
            mutation: kind.id().into(),
            description: kind.description().into(),
            applied: true,
            skipped_because: None,
            expected_field: kind.expected_field().into(),
            located_field: Some(kind.expected_field().into()),
            located_step: Some(0),
            detected: true,
            passed: true,
        };

        let all = MANDATORY_MUTATIONS.iter().copied().map(complete).collect();
        assert!(summarize(1, Vec::new(), all).passed);

        // One category missing everywhere.
        let missing = MANDATORY_MUTATIONS
            .iter()
            .copied()
            .filter(|kind| *kind != MutationKind::Trap)
            .map(complete)
            .collect();
        let summary = summarize(1, Vec::new(), missing);
        assert!(!summary.passed);
        assert_eq!(
            summary
                .coverage
                .iter()
                .find(|entry| entry.mutation == "trap")
                .expect("trap row")
                .located,
            0
        );
    }

    #[test]
    fn an_undetected_or_mislocated_mutation_fails_the_run() {
        let mut undetected = complete_reports();
        undetected[0].detected = false;
        undetected[0].located_field = None;
        undetected[0].passed = false;
        let summary = summarize(1, Vec::new(), undetected);
        assert!(!summary.passed);
        assert_eq!(summary.undetected.len(), 1);

        let mut mislocated = complete_reports();
        mislocated[0].located_field = Some("halt".into());
        mislocated[0].passed = false;
        let summary = summarize(1, Vec::new(), mislocated);
        assert!(!summary.passed);
        assert_eq!(summary.mislocated.len(), 1);
    }

    #[test]
    fn a_failing_baseline_invalidates_the_run() {
        let summary = summarize(1, vec!["case".into()], complete_reports());
        assert!(!summary.passed);
    }

    #[test]
    fn an_empty_run_is_not_a_pass() {
        let summary = summarize(0, Vec::new(), Vec::new());
        assert!(!summary.passed);
    }

    fn complete_reports() -> Vec<MutationReport> {
        MANDATORY_MUTATIONS
            .iter()
            .map(|kind| MutationReport {
                case_id: "case".into(),
                mutation: kind.id().into(),
                description: kind.description().into(),
                applied: true,
                skipped_because: None,
                expected_field: kind.expected_field().into(),
                located_field: Some(kind.expected_field().into()),
                located_step: Some(0),
                detected: true,
                passed: true,
            })
            .collect()
    }
}
