use anyhow::{bail, Context, Result};
use ckb_vm_sail_ckb_runner::{run_elf, RunnerConfig};
use ckb_vm_sail_core::{CompareResult, TerminalPolicy};
use ckb_vm_sail_riscv_runner::execute_elf as run_sail_elf;
use clap::Parser;
use serde::Serialize;
use std::path::{Path, PathBuf};

#[derive(Debug, Parser)]
#[command(about = "Strict architectural trace comparison for CKB-VM and Sail")]
struct Arguments {
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

    /// Compare only terminal categories. Exact termination is the default.
    #[arg(long)]
    terminal_category_only: bool,

    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize)]
struct TestReport {
    elf: PathBuf,
    passed: bool,
    comparison: Option<CompareResult>,
    error: Option<String>,
}

fn main() -> Result<()> {
    let arguments = Arguments::parse();
    let files = collect_elfs(&arguments)?;
    let policy = if arguments.terminal_category_only {
        TerminalPolicy::CategoryOnly
    } else {
        TerminalPolicy::Exact
    };

    let reports: Vec<_> = files
        .iter()
        .map(|elf| run_one(elf, &arguments, policy))
        .collect();
    let failed = reports.iter().filter(|report| !report.passed).count();

    if arguments.json {
        println!("{}", serde_json::to_string_pretty(&reports)?);
    } else {
        for report in &reports {
            if let Some(error) = &report.error {
                println!("ERROR {}: {error}", report.elf.display());
            } else if let Some(comparison) = &report.comparison {
                if comparison.passed() {
                    println!(
                        "PASS  {} ({} committed steps)",
                        report.elf.display(),
                        comparison.compared_steps
                    );
                } else {
                    let mismatch = comparison.mismatch.as_ref().expect("failed comparison");
                    println!(
                        "FAIL  {} step={:?} field={} ckb={} sail={}",
                        report.elf.display(),
                        mismatch.step,
                        mismatch.field,
                        mismatch.left,
                        mismatch.right
                    );
                }
            }
        }
        println!("{} test(s), {failed} failure(s)", reports.len());
    }

    if failed != 0 {
        std::process::exit(1);
    }
    Ok(())
}

fn collect_elfs(arguments: &Arguments) -> Result<Vec<PathBuf>> {
    if let Some(elf) = &arguments.elf {
        return Ok(vec![elf.clone()]);
    }
    let Some(directory) = &arguments.test_dir else {
        bail!("one of --elf or --test-dir is required");
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

fn run_one(elf: &Path, arguments: &Arguments, policy: TerminalPolicy) -> TestReport {
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
        Ok(CompareResult::compare_with_policy(&ckb, &sail, policy))
    })();

    match result {
        Ok(comparison) => TestReport {
            elf: elf.to_path_buf(),
            passed: comparison.passed(),
            comparison: Some(comparison),
            error: None,
        },
        Err(error) => TestReport {
            elf: elf.to_path_buf(),
            passed: false,
            comparison: None,
            error: Some(format!("{error:#}")),
        },
    }
}
