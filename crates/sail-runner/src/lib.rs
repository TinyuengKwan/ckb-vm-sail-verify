//! Sail adapter for textual RVFI records.
//!
//! Upstream sail-riscv currently emits RVFI only while an RVFI-DII socket is
//! active. Consequently `execute_elf` rejects an empty RVFI stream instead of
//! silently treating it as a passing trace. The parser is also usable with a
//! dedicated trace exporter while the binary DII client is being integrated.

use anyhow::{bail, Context, Result};
use ckb_vm_sail_core::{CommitEvent, ExecutionTrace, MemoryAccess, RegisterWrite, TraceEnd};
use std::{path::Path, process::Command};

pub fn execute_elf(
    elf_path: &Path,
    sail_bin: &Path,
    config_path: &Path,
    max_steps: u64,
) -> Result<ExecutionTrace> {
    if !sail_bin.is_file() {
        bail!("Sail emulator not found: {}", sail_bin.display());
    }
    if !config_path.is_file() {
        bail!(
            "Materialized Sail config not found: {}",
            config_path.display()
        );
    }

    let output = Command::new(sail_bin)
        .arg(elf_path)
        .arg("--config")
        .arg(config_path)
        .arg("--trace-rvfi")
        .arg("--trace-step")
        .arg("--inst-limit")
        .arg(max_steps.to_string())
        .output()
        .with_context(|| format!("failed to run Sail emulator {}", sail_bin.display()))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let combined = format!("{stdout}\n{stderr}");
    if !output.status.success() {
        bail!("Sail exited {}: {}", output.status, stderr.trim());
    }

    let events = parse_rvfi_text(&combined)?;
    if events.is_empty() {
        bail!(
            "Sail produced no RVFI records. In this sail-riscv revision, \
             --trace-rvfi only prints packets in RVFI-DII mode; use the \
             planned DII client/exporter rather than accepting an empty trace"
        );
    }

    let end = terminal_from_output(&combined, &events, max_steps);
    Ok(ExecutionTrace::new(events, end))
}

#[derive(Default)]
struct EventBuilder {
    order: Option<u64>,
    instruction: Option<u32>,
    pc_before: Option<u64>,
    pc_after: Option<u64>,
    rd_address: Option<u8>,
    rd_value: Option<u64>,
    memory_address: Option<u64>,
    memory_read_mask: Option<u32>,
    memory_write_mask: Option<u32>,
    memory_read_data: Option<u64>,
    memory_write_data: Option<u64>,
    trap: bool,
    halt: bool,
}

impl EventBuilder {
    fn finish(&mut self) -> Result<CommitEvent> {
        let order = self.order.context("RVFI record is missing rvfi_order")?;
        let instruction = self
            .instruction
            .context("RVFI record is missing rvfi_insn")?;
        let pc_before = self
            .pc_before
            .context("RVFI record is missing rvfi_pc_rdata")?;
        let pc_after = self
            .pc_after
            .context("RVFI record is missing rvfi_pc_wdata")?;

        let register_writes = match (self.rd_address.unwrap_or(0), self.rd_value) {
            (0, _) | (_, None) => Vec::new(),
            (index, Some(value)) => vec![RegisterWrite { index, value }],
        };
        let read_mask = self.memory_read_mask.unwrap_or(0);
        let write_mask = self.memory_write_mask.unwrap_or(0);
        let memory = if read_mask == 0 && write_mask == 0 {
            Vec::new()
        } else {
            vec![MemoryAccess {
                address: self
                    .memory_address
                    .context("RVFI memory event is missing rvfi_mem_addr")?,
                read_mask,
                write_mask,
                read_data: self.memory_read_data.unwrap_or(0),
                write_data: self.memory_write_data.unwrap_or(0),
            }]
        };

        let event = CommitEvent {
            order,
            instruction,
            pc_before,
            pc_after,
            register_writes,
            memory,
            trap: self.trap,
            halt: self.halt,
        }
        .normalize();
        *self = Self::default();
        Ok(event)
    }
}

pub fn parse_rvfi_text(output: &str) -> Result<Vec<CommitEvent>> {
    let mut events = Vec::new();
    let mut builder = EventBuilder::default();

    for line in output.lines() {
        let Some((raw_name, raw_value)) = line.trim().split_once(':') else {
            continue;
        };
        let name = raw_name.trim();
        if !name.starts_with("rvfi_") {
            continue;
        }
        let value = parse_number(raw_value)
            .with_context(|| format!("invalid {name} value: {}", raw_value.trim()))?;
        match name {
            "rvfi_halt" => builder.halt = value != 0,
            "rvfi_trap" => builder.trap = value != 0,
            "rvfi_rd_addr" => builder.rd_address = Some(narrow(value, name)?),
            "rvfi_mem_wmask" => builder.memory_write_mask = Some(narrow(value, name)?),
            "rvfi_mem_rmask" => builder.memory_read_mask = Some(narrow(value, name)?),
            "rvfi_mem_wdata" => builder.memory_write_data = Some(value),
            "rvfi_mem_rdata" => builder.memory_read_data = Some(value),
            "rvfi_mem_addr" => builder.memory_address = Some(value),
            "rvfi_rd_wdata" => builder.rd_value = Some(value),
            "rvfi_insn" => builder.instruction = Some(narrow(value, name)?),
            "rvfi_pc_wdata" => builder.pc_after = Some(value),
            "rvfi_pc_rdata" => builder.pc_before = Some(value),
            "rvfi_order" => {
                builder.order = Some(value);
                events.push(builder.finish()?);
            }
            _ => {}
        }
    }
    Ok(events)
}

fn parse_number(raw: &str) -> Result<u64> {
    let token = raw
        .split_whitespace()
        .next()
        .context("empty number")?
        .replace('_', "");
    if let Some(hex) = token
        .strip_prefix("0x")
        .or_else(|| token.strip_prefix("0X"))
    {
        // RVFI memory data can be 256 bits. The current event protocol is
        // RV64, so retain its least-significant 64 bits.
        let low = &hex[hex.len().saturating_sub(16)..];
        Ok(u64::from_str_radix(low, 16)?)
    } else if let Some(binary) = token
        .strip_prefix("0b")
        .or_else(|| token.strip_prefix("0B"))
    {
        let low = &binary[binary.len().saturating_sub(64)..];
        Ok(u64::from_str_radix(low, 2)?)
    } else {
        Ok(token.parse()?)
    }
}

fn narrow<T>(value: u64, field: &str) -> Result<T>
where
    T: TryFrom<u64>,
{
    T::try_from(value).map_err(|_| anyhow::anyhow!("{field} value {value:#x} is out of range"))
}

fn terminal_from_output(output: &str, events: &[CommitEvent], max_steps: u64) -> TraceEnd {
    if output.lines().any(|line| line.trim() == "SUCCESS") {
        TraceEnd::Completed { exit_code: Some(0) }
    } else if let Some(code) = output.lines().find_map(|line| {
        line.trim()
            .strip_prefix("FAILURE:")
            .and_then(|value| value.trim().parse::<i32>().ok())
    }) {
        TraceEnd::Completed {
            exit_code: Some(code),
        }
    } else if events.len() as u64 >= max_steps {
        TraceEnd::StepLimit
    } else if events.last().is_some_and(|event| event.trap) {
        TraceEnd::Trap {
            reason: "Sail RVFI trap".into(),
        }
    } else if events.last().is_some_and(|event| event.halt) {
        TraceEnd::Completed { exit_code: None }
    } else {
        TraceEnd::Error {
            message: "Sail ended without SUCCESS, FAILURE, trap, halt, or step limit".into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RVFI_FIXTURE: &str = include_str!("../tests/fixtures/sail-rvfi-add.txt");

    #[test]
    fn parses_a_complete_rvfi_record() {
        let events = parse_rvfi_text(RVFI_FIXTURE).expect("parse fixture");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].instruction, 0x0020_81b3);
        assert_eq!(events[0].pc_before, 0x8000_0000);
        assert_eq!(
            events[0].register_writes,
            vec![RegisterWrite { index: 3, value: 7 }]
        );
    }

    #[test]
    fn incomplete_record_is_rejected() {
        let error = parse_rvfi_text("rvfi_order: 0x0").expect_err("missing fields");
        assert!(error.to_string().contains("rvfi_insn"));
    }
}
