//! End-to-end RVFI-DII differential tests.
//!
//! These drive the real CKB-VM interpreter against the real Sail emulator, so
//! they need `make sail-config` to have been run and are marked `#[ignore]`.
//! Run them with `make verify-dii` or
//! `cargo test -p ckb-vm-sail-diff -- --ignored`.
//!
//! Several of them are deliberately negative: a differential that cannot fail
//! is not evidence, so the same harness is shown locating a diverging
//! instruction stream, a missing final event, a trap divergence and a failing
//! engine.

use ckb_vm_sail_ckb_runner::{run_injected_program as run_ckb, InjectionConfig};
use ckb_vm_sail_core::{CompareResult, TerminalPolicy, TraceEnd};
use ckb_vm_sail_diff::{
    corpus::{week2_corpus, DEFAULT_SEED},
    encode::{add, addi},
};
use ckb_vm_sail_riscv_runner::{
    dii::parse_packet_hex, run_injected_program as run_sail, DiiConfig,
};
use std::{collections::BTreeMap, path::PathBuf, time::Duration};

const SAIL_BIN: &str = "deps/sail-riscv/build/c_emulator/sail_riscv_sim";
const SAIL_CONFIG: &str = "sail-model/build/ckb_vm_config.json";

/// Paths are relative to the workspace root, which is the manifest's parent.
fn workspace_path(relative: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(relative)
}

fn dii() -> DiiConfig {
    DiiConfig {
        sail_bin: workspace_path(SAIL_BIN),
        sail_config: workspace_path(SAIL_CONFIG),
        timeout: Duration::from_secs(60),
    }
}

fn compare(program_ckb: &[u32], program_sail: &[u32]) -> CompareResult {
    let ckb = run_ckb(program_ckb, InjectionConfig::default()).expect("CKB-VM run");
    let sail = run_sail(program_sail, &dii()).expect("Sail run");
    CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact)
}

#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn every_corpus_case_agrees_step_by_step() {
    let mut steps_by_family: BTreeMap<String, usize> = BTreeMap::new();

    for case in week2_corpus(DEFAULT_SEED) {
        let ckb = run_ckb(&case.instructions, InjectionConfig::default())
            .unwrap_or_else(|error| panic!("{}: CKB-VM run failed: {error:#}", case.id));
        let sail = run_sail(&case.instructions, &dii())
            .unwrap_or_else(|error| panic!("{}: Sail run failed: {error:#}", case.id));

        assert_eq!(
            ckb.trace.end,
            TraceEnd::InjectionComplete,
            "{}: the CKB-VM side did not run the whole program",
            case.id
        );
        assert_eq!(
            sail.trace.events.len(),
            case.instructions.len(),
            "{}: the Sail side committed a different number of instructions",
            case.id
        );
        assert_eq!(
            sail.raw_packets.len(),
            case.instructions.len() + 1,
            "{}: one packet per instruction plus the end-of-trace packet",
            case.id
        );

        let result =
            CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact);
        assert!(
            result.passed(),
            "{}: {:?}",
            case.id,
            result.mismatch.expect("a failed comparison has a mismatch")
        );
        *steps_by_family.entry(case.family.clone()).or_default() += result.compared_steps;
    }

    for family in ["ADD", "ADDI", "BEQ"] {
        assert!(
            steps_by_family.get(family).copied().unwrap_or_default() > 0,
            "{family} produced no compared steps"
        );
    }
}

#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn a_diverging_instruction_stream_is_located() {
    // The engines agree on the corpus, so divergence has to be introduced by
    // asking them to execute different programs: the same ADD writing a
    // different register.
    let setup = [addi(1, 0, 5), addi(2, 0, 7)];
    let ckb_program = [setup[0], setup[1], add(3, 1, 2)];
    let sail_program = [setup[0], setup[1], add(4, 1, 2)];

    let ckb = run_ckb(&ckb_program, InjectionConfig::default()).expect("CKB-VM run");
    let sail = run_sail(&sail_program, &dii()).expect("Sail run");
    let result = CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact);

    assert!(!result.passed(), "differing programs must not pass");
    let mismatch = result.mismatch.expect("mismatch");
    // Fields are compared in a fixed order, so the differing instruction word
    // is reported before the differing effect it produced.
    assert_eq!(mismatch.step, Some(2));
    assert_eq!(mismatch.field, "instruction");

    // The effect really did differ as well: both sides committed a write, to
    // x3 and to x4 respectively.
    assert_ne!(
        ckb.trace.events[2].register_writes,
        sail.trace.events[2].register_writes
    );
    assert_eq!(ckb.trace.events[2].register_writes[0].index, 3);
    assert_eq!(sail.trace.events[2].register_writes[0].index, 4);
}

#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn a_missing_final_event_is_detected() {
    let program = [addi(1, 0, 5), addi(2, 0, 7), add(3, 1, 2)];
    let result = compare(&program, &program[..2]);
    assert!(!result.passed(), "a shorter trace must not pass");
    let mismatch = result.mismatch.expect("mismatch");
    assert_eq!(mismatch.field, "trace_length");
    assert_eq!(mismatch.left, "3");
    assert_eq!(mismatch.right, "2");
}

/// The checked-in packet fixture pins the wire format of the pinned emulator.
/// This is the direction that catches a *stale* fixture: the unit test would
/// keep passing against captured bytes that the emulator no longer produces.
#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn the_packet_fixture_still_matches_the_live_emulator() {
    const FIXTURE: &str = include_str!("../../sail-runner/tests/fixtures/sail-rvfi-dii-v1.hex");
    let expected = parse_packet_hex(FIXTURE).expect("parse fixture");

    // The program the fixture header documents.
    let program = [addi(1, 0, 5), addi(2, 0, 7), add(3, 1, 2)];
    let live = run_sail(&program, &dii()).expect("Sail run").raw_packets;

    assert_eq!(live.len(), expected.len());
    for (index, (live, expected)) in live.iter().zip(&expected).enumerate() {
        assert_eq!(
            live, expected,
            "packet {index} differs from the checked-in fixture; if the \
             submodule moved, re-capture it and record the new commit"
        );
    }
}

/// Compressed instructions are not part of the mandatory Week 2 scope, but the
/// width normalization both sides depend on is claimed to be in place, so it is
/// exercised here rather than only asserted in `docs/semantic-gaps.md`.
#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn a_compressed_instruction_is_normalized_on_both_sides() {
    // c.addi a0, 1 / c.addi a0, -1 / addi x1, x0, 5, injected with a zeroed
    // upper half so that a 16-bit instruction is unambiguous on the wire.
    let program = [0x0000_0505u32, 0x0000_157d, addi(1, 0, 5)];
    let ckb = run_ckb(&program, InjectionConfig::default()).expect("CKB-VM run");
    let sail = run_sail(&program, &dii()).expect("Sail run");

    let result = CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact);
    assert!(
        result.passed(),
        "{:?}",
        result.mismatch.expect("a failed comparison has a mismatch")
    );

    // Both sides report sixteen bits and a two-byte program counter advance.
    assert_eq!(ckb.trace.events[0].instruction, 0x0505);
    assert_eq!(sail.trace.events[0].instruction, 0x0505);
    assert_eq!(
        ckb.trace.events[0].pc_after - ckb.trace.events[0].pc_before,
        2
    );
    // The following 32-bit instruction still advances by four.
    assert_eq!(
        ckb.trace.events[2].pc_after - ckb.trace.events[2].pc_before,
        4
    );
}

/// Traps are outside the Week 2 corpus, but the two engines part ways there,
/// so the divergence is pinned rather than left to be rediscovered.
#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn a_trapping_instruction_diverges_and_is_reported_not_hidden() {
    // addi x1, x0, 5 / an illegal encoding / addi x2, x0, 7
    let program = [addi(1, 0, 5), 0x0000_107b, addi(2, 0, 7)];
    let ckb = run_ckb(&program, InjectionConfig::default()).expect("CKB-VM run");
    let sail = run_sail(&program, &dii()).expect("Sail run");

    // Both engines flag the illegal instruction at the same address.
    assert!(ckb.trace.events[1].trap && sail.trace.events[1].trap);
    assert_eq!(
        ckb.trace.events[1].pc_before,
        sail.trace.events[1].pc_before
    );

    // CKB-VM stops there; Sail enters its trap handler and keeps retiring, and
    // its rvfi_order does not advance across the trapping instruction.
    assert_eq!(ckb.trace.events.len(), 2);
    assert!(matches!(ckb.trace.end, TraceEnd::Error { .. }));
    assert_eq!(sail.trace.events.len(), 3);
    assert_eq!(sail.trace.events[1].order, sail.trace.events[2].order);

    let result = CompareResult::compare_with_policy(&ckb.trace, &sail.trace, TerminalPolicy::Exact);
    assert!(!result.passed(), "a trap divergence must not pass");
    let mismatch = result.mismatch.expect("mismatch");
    assert!(
        mismatch.field == "pc_after" || mismatch.field == "trace_length",
        "unexpected first difference: {mismatch:?}"
    );
}

#[test]
#[ignore = "needs the built Sail emulator; run with `make verify-dii`"]
fn a_failing_engine_is_an_error_rather_than_a_pass() {
    let program = [addi(1, 0, 5)];

    let missing_emulator = DiiConfig {
        sail_bin: workspace_path("deps/sail-riscv/build/c_emulator/does-not-exist"),
        ..dii()
    };
    let error = run_sail(&program, &missing_emulator).expect_err("a missing emulator is an error");
    assert!(error.to_string().contains("Sail emulator not found"));

    // A load has no CKB-VM memory observation, so it is refused on both sides
    // instead of comparing an absent event against an observed one.
    let load = [0x0001_3083];
    assert!(run_ckb(&load, InjectionConfig::default()).is_err());
    assert!(run_sail(&load, &dii()).is_err());
}
