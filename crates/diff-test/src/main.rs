//! CKB-VM Differential Test Runner
//!
//! Executes RISC-V ELF binaries on CKB-VM and a reference implementation,
//! comparing execution traces to detect semantic differences.

mod sail_runner;

use anyhow::Result;
use ckb_vm_sail_lib::{state::CompareResult, StepState};
use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "ckb-vm-diff-test")]
#[command(about = "Differential testing: CKB-VM vs Sail RISC-V")]
struct Args {
    /// Path to a single RISC-V ELF binary
    #[arg(short, long)]
    elf: Option<PathBuf>,

    /// Directory containing test ELF binaries
    #[arg(short, long)]
    test_dir: Option<PathBuf>,

    /// Path to Sail RISC-V emulator binary
    #[arg(short, long, default_value = "sail_riscv_sim")]
    sail_bin: PathBuf,

    /// Verbose output
    #[arg(short, long)]
    verbose: bool,

    /// Maximum instructions per test
    #[arg(short, long, default_value = "1000000")]
    max_steps: u64,
}

fn run_single_test(elf_path: &std::path::Path, args: &Args) -> Result<bool> {
    println!("Testing: {}", elf_path.display());

    let ckb_trace = ckb_vm_sail_lib::runner::execute_elf(elf_path, args.max_steps)?;
    if args.verbose {
        println!("  CKB-VM: {} steps", ckb_trace.len());
    }

    let sail_trace = sail_runner::execute_elf(elf_path, &args.sail_bin, args.max_steps)?;
    if args.verbose {
        println!("  Sail:   {} steps", sail_trace.len());
    }

    let result = CompareResult::compare(&ckb_trace, &sail_trace);
    if result.passed() {
        println!("  PASS ({} steps)", result.total_steps);
        Ok(true)
    } else if let Some(ref m) = result.first_mismatch {
        println!("  FAIL at step {}:", m.step);
        println!("    CKB-VM: {}", m.ckb_state);
        println!("    Sail:   {}", m.ref_state);
        Ok(false)
    } else {
        Ok(true)
    }
}

fn main() -> Result<()> {
    let args = Args::parse();
    println!("=== CKB-VM Differential Test ===\n");

    let mut total = 0u32;
    let mut passed = 0u32;

    if let Some(ref elf) = args.elf {
        total += 1;
        if run_single_test(elf, &args)? {
            passed += 1;
        }
    }

    if let Some(ref dir) = args.test_dir {
        let mut entries: Vec<_> = std::fs::read_dir(dir)?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_file())
            .collect();
        entries.sort_by_key(|e| e.file_name());
        for entry in entries {
            total += 1;
            match run_single_test(&entry.path(), &args) {
                Ok(true) => passed += 1,
                Ok(false) => {}
                Err(e) => println!("  ERROR: {e}"),
            }
        }
    }

    if total == 0 {
        println!("No tests. Use --elf <path> or --test-dir <dir>.");
    } else {
        println!(
            "\nTotal: {total}  Passed: {passed}  Failed: {}",
            total - passed
        );
        if passed < total {
            std::process::exit(1);
        }
    }
    Ok(())
}
