//! Sail RISC-V emulator driver.
//!
//! Launches the Sail C++ emulator as a subprocess and parses trace output.

use anyhow::{Context, Result};
use ckb_vm_sail_lib::StepState;
use std::path::Path;
use std::process::Command;

/// Execute an ELF binary on the Sail emulator, returning a trace.
pub fn execute_elf(elf_path: &Path, sail_bin: &Path, max_steps: u64) -> Result<Vec<StepState>> {
    if !sail_bin.exists() {
        anyhow::bail!(
            "Sail emulator not found: {}\nBuild with: ./scripts/build_sail_emulator.sh",
            sail_bin.display()
        );
    }

    let output = Command::new(sail_bin)
        .arg(elf_path)
        .arg("--trace")
        .arg("--inst-limit")
        .arg(max_steps.to_string())
        .output()
        .with_context(|| format!("Failed to run: {}", sail_bin.display()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("Sail exited {}: {}", output.status, stderr);
    }

    parse_trace(&String::from_utf8_lossy(&output.stdout))
}

fn parse_trace(output: &str) -> Result<Vec<StepState>> {
    let mut trace = Vec::new();
    for line in output.lines() {
        let line = line.trim();
        if line.is_empty() || !line.starts_with('[') {
            continue;
        }
        if let Some(pc) = extract_pc(line) {
            trace.push(StepState::new(pc, [0u64; 32]));
        }
    }
    Ok(trace)
}

fn extract_pc(line: &str) -> Option<u64> {
    let rest = line.find("]:").map(|i| &line[i + 2..])?.trim_start();
    if !rest.starts_with("0x") {
        return None;
    }
    let hex_end = rest[2..]
        .find(|c: char| !c.is_ascii_hexdigit())
        .map(|i| i + 2)
        .unwrap_or(rest.len());
    u64::from_str_radix(&rest[2..hex_end], 16).ok()
}
