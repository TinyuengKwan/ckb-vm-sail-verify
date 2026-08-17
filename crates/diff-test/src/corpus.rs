//! The mandatory Week 2 corpus of shared-initial-state injected programs.
//!
//! Every case is a single instruction under test preceded by the instructions
//! that build its operands. Because both engines start from the architectural
//! reset state (all integer registers zero, PC at `INJECTION_ENTRY`) and are
//! then given the same instruction stream, the setup sequence *is* the shared
//! initial state — no ELF loader or platform stack participates.

use crate::encode::{add, addi, beq, materialize, nop};
use serde::{Deserialize, Serialize};

/// The corpus seed used when the caller does not pick one.
pub const DEFAULT_SEED: u64 = 0x5EED_0000_0002;

/// A replayable injected program.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TestProgram {
    pub id: String,
    pub description: String,
    /// Instruction family under test, as used by `docs/coverage.md`.
    pub family: String,
    /// Index of the instruction under test within `instructions`.
    pub focus_step: usize,
    /// Seed that produced this case, when it was generated rather than fixed.
    pub seed: Option<u64>,
    pub instructions: Vec<u32>,
}

impl TestProgram {
    fn new(id: &str, description: &str, family: &str, setup: Vec<u32>, tested: &[u32]) -> Self {
        let focus_step = setup.len();
        let mut instructions = setup;
        instructions.extend_from_slice(tested);
        Self {
            id: id.to_owned(),
            description: description.to_owned(),
            family: family.to_owned(),
            focus_step,
            seed: None,
            instructions,
        }
    }

    fn generated(mut self, seed: u64) -> Self {
        self.seed = Some(seed);
        self
    }

    /// The instruction the case exists to exercise.
    pub fn focus_instruction(&self) -> u32 {
        self.instructions[self.focus_step]
    }
}

/// Build the fixed part of the corpus plus the cases derived from `seed`.
pub fn week2_corpus(seed: u64) -> Vec<TestProgram> {
    let mut corpus = fixed_cases();
    corpus.extend(generated_cases(seed));
    corpus
}

fn setup2(rs1: u8, first: u64, rs2: u8, second: u64) -> Vec<u32> {
    let mut program = materialize(rs1, first);
    program.extend(materialize(rs2, second));
    program
}

fn fixed_cases() -> Vec<TestProgram> {
    vec![
        // ---- ADD ---------------------------------------------------------
        TestProgram::new(
            "add-zero",
            "add x3, x1, x2 with both operands zero",
            "ADD",
            setup2(1, 0, 2, 0),
            &[add(3, 1, 2)],
        ),
        TestProgram::new(
            "add-all-ones-wraps",
            "add x3, x1, x2 with x1 all ones and x2 = 1, wrapping to zero",
            "ADD",
            setup2(1, u64::MAX, 2, 1),
            &[add(3, 1, 2)],
        ),
        TestProgram::new(
            "add-signed-overflow",
            "add x3, x1, x2 crossing the signed maximum into the signed minimum",
            "ADD",
            setup2(1, 0x7fff_ffff_ffff_ffff, 2, 1),
            &[add(3, 1, 2)],
        ),
        TestProgram::new(
            "add-signed-underflow",
            "add x3, x1, x2 crossing the signed minimum downwards",
            "ADD",
            setup2(1, 0x8000_0000_0000_0000, 2, u64::MAX),
            &[add(3, 1, 2)],
        ),
        TestProgram::new(
            "add-unsigned-overflow",
            "add x3, x1, x2 with both operands all ones",
            "ADD",
            setup2(1, u64::MAX, 2, u64::MAX),
            &[add(3, 1, 2)],
        ),
        TestProgram::new(
            "add-rd-aliases-rs1",
            "add x1, x1, x2 writes back into its first source",
            "ADD",
            setup2(1, 0x0123_4567_89ab_cdef, 2, 0x1111_1111_1111_1111),
            &[add(1, 1, 2)],
        ),
        TestProgram::new(
            "add-rd-aliases-rs2",
            "add x2, x1, x2 writes back into its second source",
            "ADD",
            setup2(1, 0x0123_4567_89ab_cdef, 2, 0x1111_1111_1111_1111),
            &[add(2, 1, 2)],
        ),
        TestProgram::new(
            "add-all-operands-alias",
            "add x1, x1, x1 doubles a register in place",
            "ADD",
            materialize(1, 0x4000_0000_0000_0001),
            &[add(1, 1, 1)],
        ),
        TestProgram::new(
            "add-rd-is-x0",
            "add x0, x1, x2 must discard its result",
            "ADD",
            setup2(1, 5, 2, 7),
            &[add(0, 1, 2)],
        ),
        TestProgram::new(
            "add-writes-back-the-same-value",
            "add x3, x1, x2 storing the value x3 already holds, which changes \
             no architectural state",
            "ADD",
            {
                let mut setup = setup2(1, 5, 2, 7);
                setup.extend(materialize(3, 12));
                setup
            },
            &[add(3, 1, 2)],
        ),
        // ---- ADDI --------------------------------------------------------
        TestProgram::new(
            "addi-zero",
            "addi x1, x0, 0 from the reset state",
            "ADDI",
            vec![],
            &[addi(1, 0, 0)],
        ),
        TestProgram::new(
            "addi-maximum-immediate",
            "addi x1, x0, 2047 at the positive immediate boundary",
            "ADDI",
            vec![],
            &[addi(1, 0, 2047)],
        ),
        TestProgram::new(
            "addi-minimum-immediate",
            "addi x1, x0, -2048 at the negative immediate boundary, which must \
             sign-extend across the full register",
            "ADDI",
            vec![],
            &[addi(1, 0, -2048)],
        ),
        TestProgram::new(
            "addi-signed-overflow",
            "addi x2, x1, 1 crossing the signed maximum",
            "ADDI",
            materialize(1, 0x7fff_ffff_ffff_ffff),
            &[addi(2, 1, 1)],
        ),
        TestProgram::new(
            "addi-all-ones-wraps",
            "addi x2, x1, 1 with x1 all ones, wrapping to zero",
            "ADDI",
            materialize(1, u64::MAX),
            &[addi(2, 1, 1)],
        ),
        TestProgram::new(
            "addi-negative-into-zero",
            "addi x2, x1, -2048 with x1 = 2048, landing exactly on zero",
            "ADDI",
            materialize(1, 2048),
            &[addi(2, 1, -2048)],
        ),
        TestProgram::new(
            "addi-rd-aliases-rs1",
            "addi x1, x1, -1 decrements in place",
            "ADDI",
            materialize(1, 0x8000_0000_0000_0000),
            &[addi(1, 1, -1)],
        ),
        TestProgram::new(
            "addi-rd-is-x0",
            "addi x0, x1, 5 must discard its result",
            "ADDI",
            materialize(1, 5),
            &[addi(0, 1, 5)],
        ),
        // ---- BEQ ---------------------------------------------------------
        TestProgram::new(
            "beq-taken-forward",
            "beq x1, x2, +8 with equal operands; the next injected instruction \
             therefore executes at the branch target",
            "BEQ",
            setup2(1, 42, 2, 42),
            &[beq(1, 2, 8), addi(3, 0, 1)],
        ),
        TestProgram::new(
            "beq-not-taken-forward",
            "beq x1, x2, +8 with unequal operands; execution falls through",
            "BEQ",
            setup2(1, 42, 2, 43),
            &[beq(1, 2, 8), addi(3, 0, 1)],
        ),
        TestProgram::new(
            "beq-taken-backward",
            "beq x1, x2, -8 with equal operands jumps back over its setup",
            "BEQ",
            setup2(1, 0, 2, 0),
            &[beq(1, 2, -8), addi(3, 0, 7)],
        ),
        TestProgram::new(
            "beq-not-taken-backward",
            "beq x1, x2, -8 with unequal operands must not jump back",
            "BEQ",
            setup2(1, 1, 2, 2),
            &[beq(1, 2, -8), addi(3, 0, 7)],
        ),
        TestProgram::new(
            "beq-x0-x0-always-taken",
            "beq x0, x0, +8 from the reset state; the injected stream is \
             positional, so the following instructions run at the target",
            "BEQ",
            vec![],
            &[beq(0, 0, 8), nop(), addi(3, 0, 1)],
        ),
        TestProgram::new(
            "beq-sign-boundary-operands",
            "beq x1, x2, +8 comparing the signed minimum against the signed \
             maximum, which are unequal",
            "BEQ",
            setup2(1, 0x8000_0000_0000_0000, 2, 0x7fff_ffff_ffff_ffff),
            &[beq(1, 2, 8), addi(3, 0, 1)],
        ),
        TestProgram::new(
            "beq-equal-all-ones",
            "beq x1, x2, +12 with both operands all ones",
            "BEQ",
            setup2(1, u64::MAX, 2, u64::MAX),
            &[beq(1, 2, 12), nop(), nop(), addi(3, 0, 1)],
        ),
    ]
}

/// Cases whose operands come from the seed rather than from a boundary table.
///
/// The generator is a fixed SplitMix64 so a seed alone reproduces the case; no
/// external random number generator version can change the corpus.
fn generated_cases(seed: u64) -> Vec<TestProgram> {
    let mut random = SplitMix64::new(seed);
    let mut cases = Vec::new();

    for index in 0..3 {
        let (left, right) = (random.next(), random.next());
        cases.push(
            TestProgram::new(
                &format!("random-add-{index}"),
                &format!("add x3, x1, x2 with x1 = {left:#018x} and x2 = {right:#018x}"),
                "ADD",
                setup2(1, left, 2, right),
                &[add(3, 1, 2)],
            )
            .generated(seed),
        );
    }

    for index in 0..2 {
        let base = random.next();
        let immediate = (random.next() % 4096) as i32 - 2048;
        cases.push(
            TestProgram::new(
                &format!("random-addi-{index}"),
                &format!("addi x2, x1, {immediate} with x1 = {base:#018x}"),
                "ADDI",
                materialize(1, base),
                &[addi(2, 1, immediate)],
            )
            .generated(seed),
        );
    }

    for index in 0..2 {
        let left = random.next();
        // Half of the generated branches compare equal operands.
        let right = if index % 2 == 0 { left } else { random.next() };
        cases.push(
            TestProgram::new(
                &format!("random-beq-{index}"),
                &format!("beq x1, x2, +8 with x1 = {left:#018x} and x2 = {right:#018x}"),
                "BEQ",
                setup2(1, left, 2, right),
                &[beq(1, 2, 8), addi(3, 0, 1)],
            )
            .generated(seed),
        );
    }

    cases
}

/// SplitMix64, reproduced here so the corpus does not depend on a random
/// number generator crate whose stream could change between versions.
struct SplitMix64 {
    state: u64,
}

impl SplitMix64 {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    fn next(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ckb_vm_sail_core::program::validate_program;
    use std::collections::BTreeSet;

    #[test]
    fn the_corpus_covers_every_mandatory_family() {
        let corpus = week2_corpus(DEFAULT_SEED);
        let families: BTreeSet<_> = corpus.iter().map(|case| case.family.as_str()).collect();
        assert_eq!(
            families,
            BTreeSet::from(["ADD", "ADDI", "BEQ"]),
            "the mandatory Week 2 scope is exactly ADD, ADDI and BEQ"
        );
        for family in ["ADD", "ADDI", "BEQ"] {
            assert!(
                corpus.iter().filter(|case| case.family == family).count() >= 3,
                "{family} needs more than a token case"
            );
        }
        assert!(corpus.len() >= 10, "Week 3 already requires ten cases");
    }

    #[test]
    fn every_case_is_replayable_and_supported() {
        for case in week2_corpus(DEFAULT_SEED) {
            assert!(!case.instructions.is_empty(), "{} is empty", case.id);
            assert!(
                case.focus_step < case.instructions.len(),
                "{} points past its own program",
                case.id
            );
            validate_program(&case.instructions)
                .unwrap_or_else(|error| panic!("{}: {error}", case.id));
        }
    }

    #[test]
    fn case_identifiers_are_unique() {
        let corpus = week2_corpus(DEFAULT_SEED);
        let ids: BTreeSet<_> = corpus.iter().map(|case| case.id.clone()).collect();
        assert_eq!(ids.len(), corpus.len());
    }

    #[test]
    fn the_seed_reproduces_the_corpus_and_a_new_seed_changes_it() {
        assert_eq!(week2_corpus(1), week2_corpus(1));
        assert_ne!(week2_corpus(1), week2_corpus(2));
        // Only the generated tail may move with the seed.
        assert_eq!(
            week2_corpus(1)
                .into_iter()
                .filter(|case| case.seed.is_none())
                .collect::<Vec<_>>(),
            week2_corpus(2)
                .into_iter()
                .filter(|case| case.seed.is_none())
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn boundary_operands_are_actually_present() {
        // A corpus that claims boundary coverage must contain the boundary
        // words, not merely case names that mention them.
        let corpus = week2_corpus(DEFAULT_SEED);
        let case = corpus
            .iter()
            .find(|case| case.id == "add-signed-overflow")
            .expect("case exists");
        let setup: Vec<u32> = case.instructions[..case.focus_step].to_vec();
        let outcome = ckb_vm_sail_ckb_runner::run_injected_program(
            &setup,
            ckb_vm_sail_ckb_runner::InjectionConfig::default(),
        )
        .expect("run setup");
        assert_eq!(outcome.registers[1], 0x7fff_ffff_ffff_ffff);
        assert_eq!(outcome.registers[2], 1);
    }
}
