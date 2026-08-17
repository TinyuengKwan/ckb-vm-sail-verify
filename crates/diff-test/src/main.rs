use anyhow::{bail, Context, Result};
use ckb_vm_sail_ckb_runner::{run_elf, InjectionConfig, RunnerConfig};
use ckb_vm_sail_core::{CompareResult, TerminalPolicy};
use ckb_vm_sail_diff::{
    artifact::{Artifact, Environment},
    corpus::{week2_corpus, TestProgram, DEFAULT_SEED},
    run::{compare_traces, run_case, CaseReport, RunOptions},
};
use ckb_vm_sail_riscv_runner::{execute_elf as run_sail_elf, DiiConfig};
use clap::Parser;
use serde::Serialize;
use std::{
    path::{Path, PathBuf},
    time::Duration,
};

#[derive(Debug, Parser)]
#[command(about = "Strict architectural trace comparison for CKB-VM and Sail")]
struct Arguments {
    /// Run the built-in Week 2 corpus over RVFI-DII.
    #[arg(long, conflicts_with_all = ["elf", "test_dir", "replay"])]
    corpus: bool,

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

fn main() -> Result<()> {
    let arguments = Arguments::parse();
    let policy = if arguments.terminal_category_only {
        TerminalPolicy::CategoryOnly
    } else {
        TerminalPolicy::Exact
    };

    let reports = if arguments.corpus || arguments.replay.is_some() {
        run_injected(&arguments, policy)?
    } else {
        run_elfs(&arguments, policy)?
    };

    let failed = reports.iter().filter(|report| !report.passed()).count();
    if arguments.json {
        println!("{}", serde_json::to_string_pretty(&reports)?);
    } else {
        for report in &reports {
            print_report(report);
        }
        println!("{} test(s), {failed} failure(s)", reports.len());
    }

    if failed != 0 {
        std::process::exit(1);
    }
    Ok(())
}

fn run_injected(arguments: &Arguments, policy: TerminalPolicy) -> Result<Vec<Report>> {
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

    Ok(cases
        .iter()
        .map(|case| Report::Case(run_case(case, &options, &environment)))
        .collect())
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

fn run_elfs(arguments: &Arguments, policy: TerminalPolicy) -> Result<Vec<Report>> {
    let files = collect_elfs(arguments)?;
    Ok(files
        .iter()
        .map(|elf| Report::Elf(run_one_elf(elf, arguments, policy)))
        .collect())
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
