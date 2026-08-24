//! Replayable failure and evidence artifacts.
//!
//! `VERIFICATION.md` §6 fixes what a recorded run has to keep: tool versions,
//! the ISA configuration hash, the test identity and seed, the initial state,
//! both normalized event streams, the first differing field, the raw Sail data
//! and a replay command. An artifact written here is self-contained: replaying
//! it needs the artifact and the two engines, not the corpus generator that
//! produced it.

use anyhow::{Context, Result};
use ckb_vm_sail_core::{CompareResult, ExecutionTrace, INJECTION_ENTRY};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    process::Command,
};

use crate::{corpus::TestProgram, mutation::MutationSummary};

/// Bumped whenever the artifact layout changes in a way a reader must notice.
///
/// 2 added the build toolchain: without it a replayer cannot tell which
/// compilers produced the evidence, which `VERIFICATION.md` §6 requires.
pub const ARTIFACT_SCHEMA_VERSION: u32 = 2;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Environment {
    /// Commit of the verified production implementation, when it is a checkout.
    pub ckb_vm_commit: Option<String>,
    pub sail_riscv_commit: Option<String>,
    /// Version string reported by the emulator binary itself.
    pub sail_model_version: Option<String>,
    pub sail_bin: PathBuf,
    pub sail_config: PathBuf,
    pub sail_config_sha256: Option<String>,
    /// Raw CKB-VM ISA flag byte and its expansion.
    pub ckb_vm_isa_bits: u8,
    pub ckb_vm_isa: String,
    pub ckb_vm_version: u32,
    /// The build toolchain. `sail_model_version` above is the sail-riscv model
    /// release reported by the emulator; `sail_compiler` is the Sail compiler
    /// that generated it, which is a different version and a different pin.
    pub rustc: Option<String>,
    pub cargo: Option<String>,
    pub sail_compiler: Option<String>,
}

impl Environment {
    /// Collect what can be observed about this run without trusting the docs.
    pub fn detect(sail_bin: &Path, sail_config: &Path, isa: u8, ckb_vm_version: u32) -> Self {
        Self {
            ckb_vm_commit: git_head("deps/ckb-vm"),
            sail_riscv_commit: git_head("deps/sail-riscv"),
            sail_model_version: emulator_version(sail_bin),
            sail_bin: sail_bin.to_path_buf(),
            sail_config: sail_config.to_path_buf(),
            sail_config_sha256: file_sha256(sail_config),
            ckb_vm_isa_bits: isa,
            ckb_vm_isa: describe_isa(isa),
            ckb_vm_version,
            rustc: tool_version("rustc", &["--version"]),
            cargo: tool_version("cargo", &["--version"]),
            sail_compiler: tool_version("sail", &["--version"]),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitialState {
    pub pc: u64,
    /// Every integer register at the architectural reset value.
    pub integer_registers: String,
}

impl Default for InitialState {
    fn default() -> Self {
        Self {
            pc: INJECTION_ENTRY,
            integer_registers: "x0..x31 = 0".to_owned(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Replay {
    /// Re-runs exactly this program from the artifact alone.
    pub from_artifact: String,
    /// Re-derives the case from the corpus generator, when it came from one.
    pub from_corpus: Option<String>,
}

/// One recorded run of one program against both engines.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Artifact {
    pub schema_version: u32,
    pub case: TestProgram,
    /// The injected program as hexadecimal words; this is what a replay uses.
    pub instructions_hex: Vec<String>,
    pub environment: Environment,
    pub initial_state: InitialState,
    pub passed: bool,
    /// `match`, `unclassified_mismatch`, `runner_error` or `unsupported`.
    pub classification: String,
    pub comparison: Option<CompareResult>,
    pub error: Option<String>,
    pub ckb_trace: Option<ExecutionTrace>,
    pub sail_trace: Option<ExecutionTrace>,
    /// Raw 88-byte v1 RVFI-DII packets exactly as received.
    pub sail_raw_packets: Vec<String>,
    pub replay: Replay,
}

impl Artifact {
    /// Rebuild the injected program from the artifact's own hexadecimal words.
    ///
    /// The words are the replay input, so a corrupt or hand-edited artifact
    /// fails here instead of quietly running a different program.
    pub fn program(&self) -> Result<TestProgram> {
        let mut instructions = Vec::with_capacity(self.instructions_hex.len());
        for (index, word) in self.instructions_hex.iter().enumerate() {
            let digits = word
                .strip_prefix("0x")
                .with_context(|| format!("instruction {index} is not 0x-prefixed: {word}"))?;
            instructions.push(
                u32::from_str_radix(digits, 16)
                    .with_context(|| format!("instruction {index} is not hexadecimal: {word}"))?,
            );
        }
        anyhow::ensure!(
            !instructions.is_empty(),
            "the artifact contains no instructions to replay"
        );
        anyhow::ensure!(
            instructions == self.case.instructions,
            "the artifact's hexadecimal program disagrees with its recorded case"
        );
        Ok(TestProgram {
            instructions,
            ..self.case.clone()
        })
    }

    pub fn write(&self, directory: &Path) -> Result<PathBuf> {
        std::fs::create_dir_all(directory)
            .with_context(|| format!("failed to create {}", directory.display()))?;
        let path = directory.join(format!("{}.json", self.case.id));
        let json = serde_json::to_string_pretty(self).context("failed to serialize an artifact")?;
        std::fs::write(&path, json + "\n")
            .with_context(|| format!("failed to write {}", path.display()))?;
        Ok(path)
    }

    pub fn read(path: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path)
            .with_context(|| format!("failed to read {}", path.display()))?;
        let artifact: Self = serde_json::from_str(&text)
            .with_context(|| format!("failed to parse artifact {}", path.display()))?;
        anyhow::ensure!(
            artifact.schema_version == ARTIFACT_SCHEMA_VERSION,
            "artifact schema version {} is not the supported {ARTIFACT_SCHEMA_VERSION}",
            artifact.schema_version
        );
        Ok(artifact)
    }
}

/// Replayable record of one mutation matrix run.
///
/// The per-case artifacts record what the two engines did; this records what
/// the comparator did when the recorded traces were deliberately damaged.
#[derive(Debug, Clone, Serialize)]
pub struct MutationArtifact<'a> {
    pub schema_version: u32,
    pub environment: &'a Environment,
    pub seed: u64,
    /// The single command that reproduces this run locally.
    pub replay: String,
    pub summary: &'a MutationSummary,
}

pub fn write_mutation_summary(
    directory: &Path,
    environment: &Environment,
    seed: u64,
    summary: &MutationSummary,
) -> Result<PathBuf> {
    std::fs::create_dir_all(directory)
        .with_context(|| format!("failed to create {}", directory.display()))?;
    let artifact = MutationArtifact {
        schema_version: ARTIFACT_SCHEMA_VERSION,
        environment,
        seed,
        replay: format!("cargo run -p ckb-vm-sail-diff -- --corpus --mutate --seed {seed}"),
        summary,
    };
    let path = directory.join("mutations.json");
    let json =
        serde_json::to_string_pretty(&artifact).context("failed to serialize the mutation run")?;
    std::fs::write(&path, json + "\n")
        .with_context(|| format!("failed to write {}", path.display()))?;
    Ok(path)
}

pub fn hex_words(instructions: &[u32]) -> Vec<String> {
    instructions
        .iter()
        .map(|word| format!("0x{word:08x}"))
        .collect()
}

pub fn hex_bytes(packets: &[[u8; 88]]) -> Vec<String> {
    packets
        .iter()
        .map(|packet| {
            let mut text = String::with_capacity(packet.len() * 2);
            for byte in packet {
                text.push_str(&format!("{byte:02x}"));
            }
            text
        })
        .collect()
}

/// Expand the CKB-VM ISA flag byte. `IMC` is the baseline rather than a bit.
fn describe_isa(isa: u8) -> String {
    let mut names = vec!["IMC"];
    if isa & ckb_vm::ISA_B != 0 {
        names.push("B");
    }
    if isa & ckb_vm::ISA_MOP != 0 {
        names.push("MOP");
    }
    names.join("+")
}

/// First line of `<tool> <args>`, or `None` when the tool is not on `PATH`.
///
/// `None` is recorded rather than substituted: an artifact that cannot say
/// which compiler produced it must say so. `make verify-env` and the CI report
/// gate both require these to be present.
fn tool_version(tool: &str, arguments: &[&str]) -> Option<String> {
    let output = Command::new(tool).args(arguments).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    Some(text.lines().next()?.trim().to_owned())
}

fn git_head(directory: &str) -> Option<String> {
    let output = Command::new("git")
        .args(["-C", directory, "rev-parse", "HEAD"])
        .output()
        .ok()?;
    output
        .status
        .success()
        .then(|| String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn emulator_version(sail_bin: &Path) -> Option<String> {
    let output = Command::new(sail_bin).arg("--version").output().ok()?;
    output
        .status
        .success()
        .then(|| String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn file_sha256(path: &Path) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    let digest = Sha256::digest(&bytes);
    Some(format!("{digest:x}"))
}

#[cfg(test)]
mod tests {
    /// A recorded toolchain must be the real one, and a tool that is not there
    /// must be recorded as absent rather than as a plausible default.
    #[test]
    fn the_build_toolchain_is_read_from_the_tools_themselves() {
        let rustc = super::tool_version("rustc", &["--version"]).expect("rustc runs the tests");
        assert!(rustc.starts_with("rustc "), "{rustc}");
        assert!(
            !rustc.contains('\n'),
            "only the first line is recorded: {rustc}"
        );
        assert!(super::tool_version("ckb-vm-sail-no-such-tool", &["--version"]).is_none());
    }

    use super::*;
    use ckb_vm_sail_core::TraceEnd;

    fn artifact() -> Artifact {
        let case = TestProgram {
            id: "example".into(),
            description: "example case".into(),
            family: "ADD".into(),
            focus_step: 0,
            seed: Some(7),
            instructions: vec![0x0050_0093, 0x0020_81b3],
        };
        Artifact {
            schema_version: ARTIFACT_SCHEMA_VERSION,
            instructions_hex: hex_words(&case.instructions),
            case,
            environment: Environment {
                ckb_vm_commit: None,
                sail_riscv_commit: None,
                sail_model_version: None,
                sail_bin: PathBuf::from("sail_riscv_sim"),
                sail_config: PathBuf::from("config.json"),
                sail_config_sha256: None,
                ckb_vm_isa_bits: 3,
                ckb_vm_isa: "IMC+B".into(),
                ckb_vm_version: 2,
                rustc: Some("rustc 1.97.1".into()),
                cargo: Some("cargo 1.97.1".into()),
                sail_compiler: Some("Sail 0.20.2".into()),
            },
            initial_state: InitialState::default(),
            passed: true,
            classification: "match".into(),
            comparison: None,
            error: None,
            ckb_trace: Some(ExecutionTrace::new(vec![], TraceEnd::InjectionComplete)),
            sail_trace: Some(ExecutionTrace::new(vec![], TraceEnd::InjectionComplete)),
            sail_raw_packets: hex_bytes(&[[0u8; 88]]),
            replay: Replay {
                from_artifact: "cargo run -p ckb-vm-sail-diff -- --replay artifacts/example.json"
                    .into(),
                from_corpus: None,
            },
        }
    }

    #[test]
    fn an_artifact_round_trips_through_a_file() {
        let directory =
            std::env::temp_dir().join(format!("ckb-vm-sail-artifact-{}", std::process::id()));
        let path = artifact().write(&directory).expect("write");
        let restored = Artifact::read(&path).expect("read");
        assert_eq!(restored.case, artifact().case);
        assert_eq!(
            restored.program().expect("program").instructions,
            vec![0x0050_0093, 0x0020_81b3]
        );
        std::fs::remove_dir_all(&directory).expect("clean up");
    }

    #[test]
    fn a_replay_refuses_an_artifact_whose_program_was_edited() {
        let mut artifact = artifact();
        artifact.instructions_hex[1] = "0x00208133".into();
        let error = artifact.program().expect_err("mismatch is refused");
        assert!(error.to_string().contains("disagrees"));

        let mut artifact = self::artifact();
        artifact.instructions_hex[0] = "00500093".into();
        assert!(artifact.program().is_err(), "unprefixed words are refused");
    }

    #[test]
    fn the_isa_byte_is_recorded_with_its_expansion() {
        assert_eq!(describe_isa(0), "IMC");
        assert_eq!(describe_isa(ckb_vm::ISA_B), "IMC+B");
        assert_eq!(describe_isa(ckb_vm::ISA_B | ckb_vm::ISA_MOP), "IMC+B+MOP");
    }

    #[test]
    fn packet_bytes_are_recorded_verbatim() {
        let mut packet = [0u8; 88];
        packet[0] = 0xab;
        packet[87] = 0x01;
        let hex = hex_bytes(&[packet]);
        assert_eq!(hex[0].len(), 176);
        assert!(hex[0].starts_with("ab00"));
        assert!(hex[0].ends_with("0001"));
    }
}
