//! Sail RISC-V emulator driver for differential testing.
//!
//! Launches the Sail C++ emulator as a subprocess, captures its execution
//! trace output, and parses it into StepState structs for comparison.
//!
//! The Sail emulator is expected to be built from sail-riscv with trace
//! output enabled (--trace flag).

use crate::StepState;
use anyhow::{Context, Result};
use std::path::Path;
use std::process::Command;

/// Execute an ELF binary on the Sail RISC-V emulator and return execution trace.
///
/// The Sail emulator outputs trace lines in the format:
///   [<step>] pc=<hex> x1=<hex> x2=<hex> ...
///
/// We parse these into StepState structs.
pub fn execute_elf(elf_path: &Path, sail_bin: &Path, max_steps: u64) -> Result<Vec<StepState>> {
    // Check if Sail emulator exists
    if !sail_bin.exists() {
        // Try to find it in common locations
        let alt_paths = [
            Path::new("build/c_emulator/sail_riscv_sim"),
            dirs_home().join("workplace/sail-riscv/build/c_emulator/sail_riscv_sim"),
        ];

        let found = alt_paths.iter().find(|p| p.exists());
        if found.is_none() {
            return Err(anyhow::anyhow!(
                "Sail emulator not found at '{}'. Build it with:\n\
                 cd ~/workplace/sail-riscv && ./build_simulator.sh",
                sail_bin.display()
            ));
        }
    }

    let output = Command::new(sail_bin)
        .arg(elf_path)
        .arg("--trace")
        .arg("--inst-limit")
        .arg(max_steps.to_string())
        .output()
        .with_context(|| format!("Failed to execute Sail emulator: {}", sail_bin.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow::anyhow!(
            "Sail emulator exited with {}: {}",
            output.status,
            stderr
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_sail_trace(&stdout)
}

/// Parse Sail emulator trace output into StepState vector.
///
/// Expected format (may vary by Sail version, will need adaptation):
/// ```text
/// [0] [M]: 0x0000000080000000 (0x00000297) auipc t0, 0
/// ```
///
/// For the PoC, we focus on extracting PC values and may need to
/// customize the Sail emulator's trace output format.
fn parse_sail_trace(output: &str) -> Result<Vec<StepState>> {
    let mut trace = Vec::new();

    for line in output.lines() {
        let line = line.trim();

        // Skip empty lines and non-trace lines
        if line.is_empty() || !line.starts_with('[') {
            continue;
        }

        // Basic parsing -- extract PC from trace line
        // Format: [<step>] [<mode>]: 0x<pc> ...
        if let Some(pc_str) = extract_pc_from_trace_line(line) {
            let pc = u64::from_str_radix(pc_str.trim_start_matches("0x"), 16).unwrap_or(0);

            // For now, we only capture PC. Full register state extraction
            // requires either:
            // 1. Modifying Sail emulator to dump registers at each step
            // 2. Using RVFI-DII protocol for instruction-level comparison
            trace.push(StepState {
                pc,
                regs: [0u64; 32], // TODO: extract from RVFI trace
            });
        }
    }

    Ok(trace)
}

fn extract_pc_from_trace_line(line: &str) -> Option<&str> {
    // Find pattern: ]: 0x<hex>
    let after_bracket = line.find("]:")?;
    let rest = &line[after_bracket + 2..].trim_start();

    // Extract hex address
    if rest.starts_with("0x") || rest.starts_with("0X") {
        let end = rest
            .find(|c: char| !c.is_ascii_hexdigit() && c != 'x' && c != 'X')
            .unwrap_or(rest.len());
        Some(&rest[..end])
    } else {
        None
    }
}

fn dirs_home() -> std::path::PathBuf {
    std::env::var("HOME")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from("/home/Lunarwall"))
}
