//! Evidence-only executable linked to the unchanged workspace libraries.
//! Distinct inputs are intentional harness negatives, not same-code VM defects.
use ckb_vm_sail_ckb_runner::{run_injected_program as run_ckb, InjectionConfig};
use ckb_vm_sail_core::{CompareResult, TerminalPolicy};
use ckb_vm_sail_diff::artifact::{hex_bytes, Environment, InitialState};
use ckb_vm_sail_riscv_runner::{run_injected_program as run_sail, DiiConfig};
use serde_json::{json, Value};
use std::{env, error::Error, fs, path::Path};

fn run() -> Result<i32, Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 7
        || args[1] != "--input"
        || args[3] != "--sail-bin"
        || args[5] != "--sail-config"
    {
        return Err("usage: paired-runner --input JSON --sail-bin BIN --sail-config CONFIG".into());
    }
    let input: Value = serde_json::from_slice(&fs::read(&args[2])?)?;
    let object = input.as_object().ok_or("input must be an object")?;
    if object.len() != 3 || input["schema_version"] != json!(1) {
        return Err("unknown paired input schema".into());
    }
    let ckb_words: Vec<u32> = serde_json::from_value(input["ckb_program"].clone())?;
    let sail_words: Vec<u32> = serde_json::from_value(input["sail_program"].clone())?;
    if ckb_words.is_empty()
        || sail_words.is_empty()
        || ckb_words.len() > 256
        || sail_words.len() > 256
    {
        return Err("paired programs must each contain 1..256 words".into());
    }
    let config = InjectionConfig::default();
    let ckb = run_ckb(&ckb_words, config)?;
    let sail = run_sail(&sail_words, &DiiConfig::new(&args[4], &args[6]))?;
    // Invoke the actual production comparator, never a copied third semantics.
    let comparison =
        CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact);
    let passed = comparison.passed();
    let environment = Environment::detect(
        Path::new(&args[4]),
        Path::new(&args[6]),
        config.isa,
        config.version,
    );
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema_version": 1, "mode": "paired_programs", "programs": input,
            "initial_state": InitialState::default(), "environment": environment,
            "terminal_policy": "exact", "passed": passed, "comparison": comparison,
            "ckb_trace": ckb.trace, "sail_trace": sail.trace, "sail_raw_packets": hex_bytes(&sail.raw_packets),
            "error": null, "same_program_equivalence_claimed": false
        }))?
    );
    Ok(if passed { 0 } else { 1 })
}

fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("paired runner error: {error}");
            std::process::exit(2);
        }
    }
}
