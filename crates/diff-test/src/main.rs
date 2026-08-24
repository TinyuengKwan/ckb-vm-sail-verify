//! Command line entry point.
//!
//! Every mode prints the same top-level JSON envelope under `--json` so a CI
//! job can read one shape regardless of what was run, and every mode exits
//! non-zero the moment anything fails to pass.

use anyhow::{bail, Context, Result};
use ckb_vm_sail_ckb_runner::{run_elf, InjectionConfig, RunnerConfig};
use ckb_vm_sail_core::{CompareResult, TerminalPolicy};
use ckb_vm_sail_diff::{
    artifact::{write_mutation_summary, Artifact, Environment},
    corpus::{week2_corpus, TestProgram, DEFAULT_SEED},
    mutation::{run_mutations, MutationSummary},
    run::{compare_traces, run_case, CaseReport, RunOptions},
};
use ckb_vm_sail_riscv_runner::{execute_elf as run_sail_elf, DiiConfig};
use clap::Parser;
use serde::Serialize;
use std::{
    path::{Path, PathBuf},
    time::Duration,
};

/// Bumped whenever the report envelope changes in a way a reader must notice.
///
/// 2 added the build toolchain to `environment`.
const REPORT_SCHEMA_VERSION: u32 = 2;

#[derive(Debug, Parser)]
#[command(about = "Strict architectural trace comparison for CKB-VM and Sail")]
struct Arguments {
    /// Run the built-in Week 2 corpus over RVFI-DII.
    #[arg(long, conflicts_with_all = ["elf", "test_dir", "replay"])]
    corpus: bool,

    /// Also run the mandatory mutation matrix over the corpus traces.
    ///
    /// Each mutation is applied to a real recorded trace and the comparator
    /// must both notice it and name the field that was damaged.
    #[arg(long, requires = "corpus")]
    mutate: bool,

    /// Restrict the corpus to these case identifiers.
    #[arg(long = "case", value_name = "ID", requires = "corpus")]
    cases: Vec<String>,

    /// Re-run the program recorded in an artifact, without the generator.
    #[arg(long, conflicts_with_all = ["elf", "test_dir"])]
    replay: Option<PathBuf>,

    /// Run one ELF file.
    #[arg(long, conflicts_with = "test_dir")]
    elf: Option<PathBuf>,

    /// Run every *.elf regular file in this directory.
    #[arg(long, conflicts_with = "elf")]
    test_dir: Option<PathBuf>,

    #[arg(
        long,
        default_value = "deps/sail-riscv/build/c_emulator/sail_riscv_sim"
    )]
    sail_bin: PathBuf,

    #[arg(long, default_value = "sail-model/build/ckb_vm_config.json")]
    sail_config: PathBuf,

    #[arg(long, default_value_t = 100_000)]
    max_steps: u64,

    /// Seed for the generated part of the corpus.
    #[arg(long, default_value_t = DEFAULT_SEED)]
    seed: u64,

    /// Write one replayable artifact per case into this directory.
    #[arg(long, value_name = "DIR")]
    artifact_dir: Option<PathBuf>,

    /// Seconds to wait for the Sail emulator and for each RVFI-DII packet.
    #[arg(long, default_value_t = 30)]
    sail_timeout: u64,

    /// Compare only terminal categories. Exact termination is the default.
    #[arg(long)]
    terminal_category_only: bool,

    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize)]
struct ElfReport {
    elf: PathBuf,
    passed: bool,
    comparison: Option<CompareResult>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum Report {
    Case(CaseReport),
    Elf(ElfReport),
}

impl Report {
    fn passed(&self) -> bool {
        match self {
            Self::Case(report) => report.passed,
            Self::Elf(report) => report.passed,
        }
    }
}

/// The stable top-level shape of `--json`.
#[derive(Debug, Serialize)]
struct RunReport {
    schema_version: u32,
    mode: &'static str,
    /// Present for corpus runs; a replay takes its program from the artifact.
    seed: Option<u64>,
    terminal_policy: &'static str,
    environment: Option<Environment>,
    results: Vec<Report>,
    mutations: Option<MutationSummary>,
    summary: Summary,
}

#[derive(Debug, Serialize)]
struct Summary {
    total: usize,
    failures: usize,
    /// `null` when the mutation matrix was not requested.
    mutations_passed: Option<bool>,
    passed: bool,
}

struct Outcome {
    mode: &'static str,
    results: Vec<Report>,
    environment: Option<Environment>,
    mutations: Option<MutationSummary>,
    mutation_artifact: Option<PathBuf>,
}

fn main() -> Result<()> {
    let arguments = Arguments::parse();
    let policy = if arguments.terminal_category_only {
        TerminalPolicy::CategoryOnly
    } else {
        TerminalPolicy::Exact
    };

    let outcome = if arguments.corpus || arguments.replay.is_some() {
        run_injected(&arguments, policy)?
    } else {
        run_elfs(&arguments, policy)?
    };

    let failures = outcome
        .results
        .iter()
        .filter(|report| !report.passed())
        .count();
    let mutations_passed = outcome.mutations.as_ref().map(|summary| summary.passed);
    let passed = failures == 0 && mutations_passed.unwrap_or(true);

    let report = RunReport {
        schema_version: REPORT_SCHEMA_VERSION,
        mode: outcome.mode,
        seed: arguments.corpus.then_some(arguments.seed),
        terminal_policy: match policy {
            TerminalPolicy::Exact => "exact",
            TerminalPolicy::CategoryOnly => "category_only",
        },
        environment: outcome.environment,
        summary: Summary {
            total: outcome.results.len(),
            failures,
            mutations_passed,
            passed,
        },
        results: outcome.results,
        mutations: outcome.mutations,
    };

    if arguments.json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        for result in &report.results {
            print_report(result);
        }
        println!("{} test(s), {failures} failure(s)", report.results.len());
        if let Some(mutations) = &report.mutations {
            print_mutations(mutations, outcome.mutation_artifact.as_deref());
        }
    }

    if !passed {
        std::process::exit(1);
    }
    Ok(())
}

fn run_injected(arguments: &Arguments, policy: TerminalPolicy) -> Result<Outcome> {
    let cases = select_cases(arguments)?;
    let options = RunOptions {
        dii: DiiConfig {
            sail_bin: arguments.sail_bin.clone(),
            sail_config: arguments.sail_config.clone(),
            timeout: Duration::from_secs(arguments.sail_timeout),
        },
        ckb: InjectionConfig::default(),
        terminal_policy: policy,
        artifact_dir: arguments.artifact_dir.clone(),
        seed: arguments.seed,
    };
    let environment = Environment::detect(
        &arguments.sail_bin,
        &arguments.sail_config,
        options.ckb.isa,
        options.ckb.version,
    );

    let results = cases
        .iter()
        .map(|case| Report::Case(run_case(case, &options, &environment)))
        .collect();

    let (mutations, mutation_artifact) = if arguments.mutate {
        let summary = run_mutations(&cases, &options);
        let artifact = match &arguments.artifact_dir {
            Some(directory) => Some(write_mutation_summary(
                directory,
                &environment,
                arguments.seed,
                &summary,
            )?),
            None => None,
        };
        (Some(summary), artifact)
    } else {
        (None, None)
    };

    Ok(Outcome {
        mode: if arguments.replay.is_some() {
            "replay"
        } else {
            "corpus"
        },
        results,
        environment: Some(environment),
        mutations,
        mutation_artifact,
    })
}

fn select_cases(arguments: &Arguments) -> Result<Vec<TestProgram>> {
    if let Some(path) = &arguments.replay {
        let artifact = Artifact::read(path)?;
        return Ok(vec![artifact.program()?]);
    }

    let corpus = week2_corpus(arguments.seed);
    if arguments.cases.is_empty() {
        return Ok(corpus);
    }
    let selected: Vec<_> = corpus
        .into_iter()
        .filter(|case| arguments.cases.contains(&case.id))
        .collect();
    for wanted in &arguments.cases {
        if !selected.iter().any(|case| &case.id == wanted) {
            bail!("no corpus case is called {wanted}");
        }
    }
    Ok(selected)
}

fn run_elfs(arguments: &Arguments, policy: TerminalPolicy) -> Result<Outcome> {
    let files = collect_elfs(arguments)?;
    Ok(Outcome {
        mode: "elf",
        results: files
            .iter()
            .map(|elf| Report::Elf(run_one_elf(elf, arguments, policy)))
            .collect(),
        environment: None,
        mutations: None,
        mutation_artifact: None,
    })
}

fn collect_elfs(arguments: &Arguments) -> Result<Vec<PathBuf>> {
    if let Some(elf) = &arguments.elf {
        return Ok(vec![elf.clone()]);
    }
    let Some(directory) = &arguments.test_dir else {
        bail!("one of --corpus, --replay, --elf or --test-dir is required");
    };
    let mut files = std::fs::read_dir(directory)
        .with_context(|| format!("failed to read {}", directory.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.is_file() && path.extension().is_some_and(|ext| ext == "elf"))
        .collect::<Vec<_>>();
    files.sort();
    if files.is_empty() {
        bail!("{} contains no *.elf files", directory.display());
    }
    Ok(files)
}

fn run_one_elf(elf: &Path, arguments: &Arguments, policy: TerminalPolicy) -> ElfReport {
    let result = (|| -> Result<CompareResult> {
        let ckb = run_elf(
            elf,
            RunnerConfig {
                max_steps: arguments.max_steps,
                ..RunnerConfig::default()
            },
        )?;
        let sail = run_sail_elf(
            elf,
            &arguments.sail_bin,
            &arguments.sail_config,
            arguments.max_steps,
        )?;
        Ok(compare_traces(&ckb, &sail, policy))
    })();

    match result {
        Ok(comparison) => ElfReport {
            elf: elf.to_path_buf(),
            passed: comparison.passed(),
            comparison: Some(comparison),
            error: None,
        },
        Err(error) => ElfReport {
            elf: elf.to_path_buf(),
            passed: false,
            comparison: None,
            error: Some(format!("{error:#}")),
        },
    }
}

fn print_report(report: &Report) {
    match report {
        Report::Case(case) => match (&case.error, &case.comparison) {
            (Some(error), _) => println!("ERROR {} [{}]: {error}", case.id, case.classification),
            (None, Some(comparison)) if comparison.passed() => println!(
                "PASS  {} ({} committed steps, {} instructions)",
                case.id, comparison.compared_steps, case.instructions
            ),
            (None, Some(comparison)) => {
                let mismatch = comparison.mismatch.as_ref().expect("failed comparison");
                println!(
                    "FAIL  {} step={:?} field={} ckb={} sail={}",
                    case.id, mismatch.step, mismatch.field, mismatch.left, mismatch.right
                );
            }
            (None, None) => println!("ERROR {}: no comparison and no error", case.id),
        },
        Report::Elf(elf) => match (&elf.error, &elf.comparison) {
            (Some(error), _) => println!("ERROR {}: {error}", elf.elf.display()),
            (None, Some(comparison)) if comparison.passed() => println!(
                "PASS  {} ({} committed steps)",
                elf.elf.display(),
                comparison.compared_steps
            ),
            (None, Some(comparison)) => {
                let mismatch = comparison.mismatch.as_ref().expect("failed comparison");
                println!(
                    "FAIL  {} step={:?} field={} ckb={} sail={}",
                    elf.elf.display(),
                    mismatch.step,
                    mismatch.field,
                    mismatch.left,
                    mismatch.right
                );
            }
            (None, None) => println!("ERROR {}: no comparison and no error", elf.elf.display()),
        },
    }
}

fn print_mutations(summary: &MutationSummary, artifact: Option<&Path>) {
    println!();
    for entry in &summary.coverage {
        let verdict = if entry.located > 0 {
            "LOCATED"
        } else {
            "MISSING"
        };
        println!(
            "{verdict:<8} {:<16} field={:<16} applied={:<3} located={:<3} example={}",
            entry.mutation,
            entry.expected_field,
            entry.applied,
            entry.located,
            entry.example_case.as_deref().unwrap_or("-")
        );
    }
    // Skipped mutations are printed rather than hidden: a category that never
    // applied is a gap in the corpus, not a silent pass.
    if summary.skipped != 0 {
        println!(
            "{} mutation(s) did not apply to their case:",
            summary.skipped
        );
        for report in summary.reports.iter().filter(|report| !report.applied) {
            println!(
                "  SKIP  {}/{}: {}",
                report.case_id,
                report.mutation,
                report
                    .skipped_because
                    .as_deref()
                    .unwrap_or("no reason given")
            );
        }
    }
    for undetected in &summary.undetected {
        println!("UNDETECTED {undetected}");
    }
    for mislocated in &summary.mislocated {
        println!("MISLOCATED {mislocated}");
    }
    for baseline in &summary.baseline_failures {
        println!("BASELINE-FAILED {baseline}");
    }
    println!(
        "{} mutation(s) applied over {} case(s), {} category/categories located, {}",
        summary.applied,
        summary.cases,
        summary
            .coverage
            .iter()
            .filter(|entry| entry.located > 0)
            .count(),
        if summary.passed { "PASS" } else { "FAIL" }
    );
    if let Some(path) = artifact {
        println!("mutation report: {}", path.display());
    }
}
