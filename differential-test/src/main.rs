//! CKB-VM Differential Test Runner
//!
//! Executes RISC-V ELF binaries on both CKB-VM and the Sail RISC-V C++ emulator,
//! then compares the execution traces to detect semantic differences.

mod ckb_vm_runner;
mod sail_runner;

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "ckb-vm-diff-test")]
#[command(about = "Differential testing: CKB-VM vs Sail RISC-V specification")]
struct Args {
    /// Path to RISC-V ELF binary to test
    #[arg(short, long)]
    elf: Option<PathBuf>,

    /// Directory containing test ELF binaries
    #[arg(short, long)]
    test_dir: Option<PathBuf>,

    /// Path to Sail RISC-V emulator binary
    #[arg(short, long, default_value = "sail_riscv_sim")]
    sail_bin: PathBuf,

    /// Verbose output (print register state at each step)
    #[arg(short, long)]
    verbose: bool,

    /// Maximum number of instructions to execute
    #[arg(short, long, default_value = "1000000")]
    max_steps: u64,
}

/// Execution state snapshot at a single step
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct StepState {
    pub pc: u64,
    pub regs: [u64; 32],
}

impl std::fmt::Display for StepState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "pc={:#018x}", self.pc)?;
        for (i, r) in self.regs.iter().enumerate() {
            if *r != 0 {
                write!(f, " x{}={:#x}", i, r)?;
            }
        }
        Ok(())
    }
}

/// Result of comparing two execution traces
#[derive(Debug)]
pub struct CompareResult {
    pub total_steps: usize,
    pub first_mismatch: Option<(usize, StepState, StepState)>,
}

fn compare_traces(ckb_trace: &[StepState], sail_trace: &[StepState]) -> CompareResult {
    let total_steps = ckb_trace.len().min(sail_trace.len());

    for i in 0..total_steps {
        if ckb_trace[i] != sail_trace[i] {
            return CompareResult {
                total_steps: i,
                first_mismatch: Some((i, ckb_trace[i].clone(), sail_trace[i].clone())),
            };
        }
    }

    // Check if one trace is longer
    if ckb_trace.len() != sail_trace.len() {
        return CompareResult {
            total_steps,
            first_mismatch: None, // Traces match but different lengths
        };
    }

    CompareResult {
        total_steps,
        first_mismatch: None,
    }
}

fn run_single_test(elf_path: &std::path::Path, args: &Args) -> Result<bool> {
    println!("Testing: {}", elf_path.display());

    // Run on CKB-VM
    let ckb_trace = ckb_vm_runner::execute_elf(elf_path, args.max_steps)?;
    if args.verbose {
        println!("  CKB-VM: {} steps", ckb_trace.len());
    }

    // Run on Sail emulator
    let sail_trace = sail_runner::execute_elf(elf_path, &args.sail_bin, args.max_steps)?;
    if args.verbose {
        println!("  Sail:   {} steps", sail_trace.len());
    }

    // Compare
    let result = compare_traces(&ckb_trace, &sail_trace);

    match result.first_mismatch {
        None => {
            println!("  PASS ({} steps)", result.total_steps);
            Ok(true)
        }
        Some((step, ckb_state, sail_state)) => {
            println!("  FAIL at step {}:", step);
            println!("    CKB-VM: {}", ckb_state);
            println!("    Sail:   {}", sail_state);
            // Print diffs
            if ckb_state.pc != sail_state.pc {
                println!("    DIFF pc: {:#x} vs {:#x}", ckb_state.pc, sail_state.pc);
            }
            for i in 0..32 {
                if ckb_state.regs[i] != sail_state.regs[i] {
                    println!(
                        "    DIFF x{}: {:#x} vs {:#x}",
                        i, ckb_state.regs[i], sail_state.regs[i]
                    );
                }
            }
            Ok(false)
        }
    }
}

fn main() -> Result<()> {
    let args = Args::parse();

    println!("=== CKB-VM Differential Test ===");
    println!("Sail emulator: {}", args.sail_bin.display());
    println!();

    let mut total = 0;
    let mut passed = 0;
    let mut failed = 0;

    if let Some(ref elf_path) = args.elf {
        total += 1;
        if run_single_test(elf_path, &args)? {
            passed += 1;
        } else {
            failed += 1;
        }
    }

    if let Some(ref test_dir) = args.test_dir {
        let mut entries: Vec<_> = std::fs::read_dir(test_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| {
                let path = e.path();
                // Accept ELF files (no extension or common ELF extensions)
                path.is_file()
                    && !path
                        .extension()
                        .map(|ext| ext == "dump" || ext == "s" || ext == "S" || ext == "c")
                        .unwrap_or(false)
            })
            .collect();
        entries.sort_by_key(|e| e.file_name());

        for entry in entries {
            total += 1;
            match run_single_test(&entry.path(), &args) {
                Ok(true) => passed += 1,
                Ok(false) => failed += 1,
                Err(e) => {
                    println!("  ERROR: {}", e);
                    failed += 1;
                }
            }
        }
    }

    if total == 0 {
        println!("No test files specified. Use --elf or --test-dir.");
        println!("Example:");
        println!("  ckb-vm-diff-test --elf path/to/test.elf");
        println!("  ckb-vm-diff-test --test-dir path/to/tests/");
        return Ok(());
    }

    println!();
    println!("=== Results ===");
    println!("Total: {}  Passed: {}  Failed: {}", total, passed, failed);

    if failed > 0 {
        std::process::exit(1);
    }

    Ok(())
}
