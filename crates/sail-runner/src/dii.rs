//! Binary RVFI-DII client for the pinned sail-riscv emulator.
//!
//! The pinned revision only produces RVFI packets while an RVFI-DII socket is
//! connected (`--trace-rvfi` alone prints nothing), so this client is the only
//! way to obtain a Sail-side trace. The protocol implemented here is the one in
//! `deps/sail-riscv/c_emulator/rvfi_dii.cpp` and `model/core/rvfi_dii*.sail`:
//!
//! * the client writes 8-byte little-endian command words
//!   `(cmd << 48) | (time << 32) | insn`; command `1` injects an instruction and
//!   command `0` ends the trace;
//! * the emulator answers every injected instruction with one execution packet;
//! * the wire format defaults to v1, a 704-bit (88-byte) packet written
//!   least-significant byte first, so each field sits at a fixed byte offset;
//! * after the end-of-trace command the emulator sends one final packet with
//!   `rvfi_halt` set and then exits.
//!
//! No version negotiation is performed: v1 carries every field the current
//! commit-event protocol compares, and staying on the default keeps the
//! handshake free of state the emulator would have to be asked about.

use anyhow::{bail, Context, Result};
use ckb_vm_sail_core::{
    normalize_instruction_width, program::validate_program, CommitEvent, ExecutionTrace,
    MemoryAccess, RegisterShadow, TraceEnd, INJECTION_ENTRY,
};
use std::{
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddr, SocketAddrV4, TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread::sleep,
    time::{Duration, Instant},
};

/// Size of a v1 RVFI-DII execution packet: 704 bits.
pub const V1_PACKET_BYTES: usize = 88;

const CMD_END_OF_TRACE: u64 = 0;
const CMD_INSTRUCTION: u64 = 1;

#[derive(Debug, Clone)]
pub struct DiiConfig {
    pub sail_bin: PathBuf,
    pub sail_config: PathBuf,
    /// Deadline for the emulator to accept a connection and for every packet.
    pub timeout: Duration,
}

impl DiiConfig {
    pub fn new(sail_bin: impl Into<PathBuf>, sail_config: impl Into<PathBuf>) -> Self {
        Self {
            sail_bin: sail_bin.into(),
            sail_config: sail_config.into(),
            timeout: Duration::from_secs(30),
        }
    }
}

/// A Sail-side run: the normalized trace plus the bytes it was derived from.
///
/// `VERIFICATION.md` requires every recorded run to keep the raw Sail data, so
/// the packets are carried out of the session rather than dropped after
/// parsing.
#[derive(Debug, Clone)]
pub struct DiiOutcome {
    pub trace: ExecutionTrace,
    pub raw_packets: Vec<[u8; V1_PACKET_BYTES]>,
}

/// Run one injected program against the Sail model and return its trace.
pub fn run_program(program: &[u32], config: &DiiConfig) -> Result<DiiOutcome> {
    if program.is_empty() {
        bail!("an injected program must contain at least one instruction");
    }
    validate_program(program)?;
    if !config.sail_bin.is_file() {
        bail!(
            "Sail emulator not found: {} (run `make sail-config`)",
            config.sail_bin.display()
        );
    }
    if !config.sail_config.is_file() {
        bail!(
            "Materialized Sail config not found: {} (run `make sail-config`)",
            config.sail_config.display()
        );
    }

    let mut session = DiiSession::start(config)?;
    let result = session.drive(program);
    session.shutdown(result)
}

/// A running emulator plus its socket. Dropping it always reaps the child.
struct DiiSession {
    child: Child,
    stream: TcpStream,
    raw_packets: Vec<[u8; V1_PACKET_BYTES]>,
}

/// Why a session could not be started.
enum StartFailure {
    /// Another process bound the reserved port first. Nothing has been
    /// injected yet, so the same program can be started again on a fresh port.
    LostPortRace(anyhow::Error),
    Fatal(anyhow::Error),
}

/// How many times a lost port race is retried before giving up.
///
/// The lock below removes the race between sessions in one process; the retry
/// covers the remaining case of two independent processes running at once.
const START_ATTEMPTS: usize = 5;

/// Serializes the window between reserving a port and the emulator binding it.
static STARTUP: Mutex<()> = Mutex::new(());

/// What the emulator prints when it cannot bind the port it was given.
///
/// Captured from the pinned emulator; `a_lost_port_race_is_recognized` pins
/// the string so a change upstream turns into a failing test rather than into
/// a flaky differential.
const BIND_FAILURE: &str = "Unable to set bind socket";

impl DiiSession {
    /// Start the emulator, retrying a lost port race.
    ///
    /// The port is reserved by binding and releasing a socket, so there is an
    /// unavoidable window before the emulator binds it. Under a parallel test
    /// run that window is lost often enough to matter, and the result is an
    /// emulator that exits immediately — an infrastructure failure that must
    /// not be reported as a differential result.
    fn start(config: &DiiConfig) -> Result<Self> {
        let mut lost_race = None;
        for _ in 0..START_ATTEMPTS {
            match Self::start_once(config) {
                Ok(session) => return Ok(session),
                Err(StartFailure::LostPortRace(error)) => lost_race = Some(error),
                Err(StartFailure::Fatal(error)) => return Err(error),
            }
        }
        Err(lost_race
            .expect("the loop only ends here after recording a lost race")
            .context(format!(
                "the Sail emulator lost the RVFI-DII port race {START_ATTEMPTS} times in a row"
            )))
    }

    fn start_once(config: &DiiConfig) -> std::result::Result<Self, StartFailure> {
        // Held until the emulator owns the port. Two sessions in one process
        // would otherwise be able to reserve the same port, and the loser
        // connects to the winner's emulator: upstream accepts exactly once and
        // then closes its listening socket, so the second client gets someone
        // else's session or a reset connection. A poisoned lock still
        // serializes correctly, so it is recovered rather than propagated.
        let _startup = STARTUP
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let port = reserve_port().map_err(StartFailure::Fatal)?;
        let mut child = Command::new(&config.sail_bin)
            .arg("--config")
            .arg(&config.sail_config)
            .arg("--rvfi-dii")
            .arg(port.to_string())
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .with_context(|| {
                format!(
                    "failed to spawn Sail emulator {}",
                    config.sail_bin.display()
                )
            })
            .map_err(StartFailure::Fatal)?;

        match connect(port, config.timeout, &mut child) {
            Ok(stream) => {
                stream
                    .set_read_timeout(Some(config.timeout))
                    .context("failed to set the RVFI-DII read timeout")
                    .map_err(StartFailure::Fatal)?;
                stream
                    .set_write_timeout(Some(config.timeout))
                    .context("failed to set the RVFI-DII write timeout")
                    .map_err(StartFailure::Fatal)?;
                Ok(Self {
                    child,
                    stream,
                    raw_packets: Vec::new(),
                })
            }
            Err(error) => {
                let _ = child.kill();
                // The child has already exited or has just been killed, so
                // reading its pipes to end-of-file cannot deadlock. Its
                // diagnostics are what distinguish a lost port race from a
                // genuinely broken emulator, so they are reported either way.
                let stdout = drain(child.stdout.take());
                let stderr = drain(child.stderr.take());
                let _ = child.wait();
                let lost_race = lost_port_race(&stderr);
                let error = error.context(format!(
                    "failed to reach the Sail RVFI-DII socket on port {port}; \
                     stdout: {stdout}; stderr: {stderr}"
                ));
                Err(if lost_race {
                    StartFailure::LostPortRace(error)
                } else {
                    StartFailure::Fatal(error)
                })
            }
        }
    }

    fn drive(&mut self, program: &[u32]) -> Result<ExecutionTrace> {
        self.raw_packets.clear();
        let mut shadow = RegisterShadow::zeroed();
        let mut events = Vec::with_capacity(program.len());

        for (index, &bits) in program.iter().enumerate() {
            self.send(CMD_INSTRUCTION, bits)
                .with_context(|| format!("failed to inject instruction {index}"))?;
            let packet = self
                .receive()
                .with_context(|| format!("no execution packet for instruction {index}"))?;
            if index == 0 {
                started_from_reset(&packet)?;
            }
            if packet.halt {
                // The pinned model has no HTIF write path in DII mode, so this
                // is reported rather than folded into a normal termination.
                events.push(packet.into_event(&mut shadow));
                return Ok(ExecutionTrace::new(
                    events,
                    TraceEnd::Completed { exit_code: None },
                ));
            }
            events.push(packet.into_event(&mut shadow));
        }

        self.send(CMD_END_OF_TRACE, 0)
            .context("failed to end the RVFI-DII trace")?;
        let final_packet = self
            .receive()
            .context("no packet after the end-of-trace command")?;
        if !final_packet.halt {
            bail!(
                "the end-of-trace packet did not report rvfi_halt: {:?}",
                final_packet
            );
        }
        Ok(ExecutionTrace::new(events, TraceEnd::InjectionComplete))
    }

    fn send(&mut self, command: u64, instruction: u32) -> Result<()> {
        let word = (command << 48) | u64::from(instruction);
        self.stream
            .write_all(&word.to_le_bytes())
            .context("failed to write an RVFI-DII command word")?;
        self.stream
            .flush()
            .context("failed to flush an RVFI-DII command word")
    }

    fn receive(&mut self) -> Result<V1Packet> {
        let mut bytes = [0u8; V1_PACKET_BYTES];
        self.stream
            .read_exact(&mut bytes)
            .context("failed to read a full v1 execution packet")?;
        self.raw_packets.push(bytes);
        Ok(V1Packet::parse(&bytes))
    }

    /// Wait for the emulator to exit and fold its diagnostics into `result`.
    ///
    /// Closing the socket is what makes the emulator leave its command loop, so
    /// the pipes reach end-of-file on their own.
    fn shutdown(mut self, result: Result<ExecutionTrace>) -> Result<DiiOutcome> {
        let _ = self.stream.shutdown(std::net::Shutdown::Both);
        let stdout = drain(self.child.stdout.take());
        let stderr = drain(self.child.stderr.take());
        let status = self
            .child
            .wait()
            .context("failed to reap the Sail emulator");
        let raw_packets = std::mem::take(&mut self.raw_packets);

        match (result, status) {
            (Ok(trace), Ok(status)) if status.success() => Ok(DiiOutcome { trace, raw_packets }),
            (Ok(_), Ok(status)) => bail!(
                "the Sail emulator exited {status} after producing a trace; \
                 stdout: {stdout}; stderr: {stderr}"
            ),
            (Ok(_), Err(error)) => Err(error),
            (Err(error), Ok(status)) => Err(error.context(format!(
                "Sail emulator exited {status}; stdout: {stdout}; stderr: {stderr}"
            ))),
            (Err(error), Err(_)) => Err(error.context(format!(
                "Sail emulator could not be reaped; stdout: {stdout}; stderr: {stderr}"
            ))),
        }
    }
}

impl Drop for DiiSession {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Refuse a session that did not begin at the architectural reset state.
///
/// The whole comparison rests on both engines starting from the same state.
/// A client that reached an emulator another client had already advanced
/// would otherwise produce a trace that looks plausible and is wrong, which is
/// worse than a failure.
fn started_from_reset(first: &V1Packet) -> Result<()> {
    anyhow::ensure!(
        first.order == 0 && first.pc_rdata == INJECTION_ENTRY,
        "the first RVFI-DII packet is not from a reset emulator: \
         rvfi_order {} at pc {:#x}, expected order 0 at {INJECTION_ENTRY:#x}",
        first.order,
        first.pc_rdata
    );
    Ok(())
}

/// Whether the emulator's diagnostics say it could not bind its port.
fn lost_port_race(stderr: &str) -> bool {
    stderr.contains(BIND_FAILURE)
}

fn drain<R: Read>(source: Option<R>) -> String {
    let Some(mut source) = source else {
        return String::new();
    };
    let mut text = String::new();
    let _ = source.read_to_string(&mut text);
    text.trim().to_string()
}

/// Ask the kernel for a free loopback port, then release it for the emulator.
///
/// The emulator binds the port itself, so there is an unavoidable window
/// between the probe and its `bind`. A lost race can never produce a wrong
/// result — the emulator exits before accepting — and [`DiiSession::start`]
/// retries it on a fresh port.
fn reserve_port() -> Result<u16> {
    let listener = TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0))
        .context("failed to reserve a loopback port for RVFI-DII")?;
    let port = listener
        .local_addr()
        .context("failed to read the reserved port")?
        .port();
    drop(listener);
    Ok(port)
}

fn connect(port: u16, timeout: Duration, child: &mut Child) -> Result<TcpStream> {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let deadline = Instant::now() + timeout;
    loop {
        if let Some(status) = child
            .try_wait()
            .context("failed to poll the Sail emulator")?
        {
            bail!("the Sail emulator exited {status} before accepting a connection");
        }
        match TcpStream::connect_timeout(&address, Duration::from_millis(200)) {
            Ok(stream) => return Ok(stream),
            Err(error) if Instant::now() >= deadline => {
                return Err(anyhow::Error::new(error).context("timed out"));
            }
            Err(_) => sleep(Duration::from_millis(20)),
        }
    }
}

/// A decoded v1 execution packet.
///
/// Field offsets follow `RVFI_DII_Execution_Packet_V1` in
/// `deps/sail-riscv/model/core/rvfi_dii_v1.sail`, which the emulator writes
/// least-significant byte first.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct V1Packet {
    pub order: u64,
    pub pc_rdata: u64,
    pub pc_wdata: u64,
    pub insn: u64,
    pub rd_wdata: u64,
    pub mem_addr: u64,
    pub mem_rdata: u64,
    pub mem_wdata: u64,
    pub mem_rmask: u8,
    pub mem_wmask: u8,
    pub rd_addr: u8,
    pub trap: bool,
    pub halt: bool,
    pub intr: bool,
}

impl V1Packet {
    pub fn parse(bytes: &[u8; V1_PACKET_BYTES]) -> Self {
        let word = |offset: usize| {
            u64::from_le_bytes(
                bytes[offset..offset + 8]
                    .try_into()
                    .expect("a fixed 8-byte window of a fixed-size packet"),
            )
        };
        Self {
            order: word(0),
            pc_rdata: word(8),
            pc_wdata: word(16),
            insn: word(24),
            // 32: rs1_rdata, 40: rs2_rdata — read operands are not part of the
            // commit-event protocol, and the pinned model leaves them zero.
            rd_wdata: word(48),
            mem_addr: word(56),
            mem_rdata: word(64),
            mem_wdata: word(72),
            mem_rmask: bytes[80],
            mem_wmask: bytes[81],
            // 82: rs1_addr, 83: rs2_addr.
            rd_addr: bytes[84],
            trap: bytes[85] != 0,
            halt: bytes[86] != 0,
            intr: bytes[87] != 0,
        }
    }

    /// Convert to a commit event, normalizing to what both sides can observe.
    pub fn into_event(self, shadow: &mut RegisterShadow) -> CommitEvent {
        let register_writes = shadow
            .observe(self.rd_addr, self.rd_wdata)
            .into_iter()
            .collect();
        let memory = if self.mem_rmask == 0 && self.mem_wmask == 0 {
            Vec::new()
        } else {
            vec![MemoryAccess {
                address: self.mem_addr,
                read_mask: u32::from(self.mem_rmask),
                write_mask: u32::from(self.mem_wmask),
                read_data: self.mem_rdata,
                write_data: self.mem_wdata,
            }]
        };
        CommitEvent {
            order: self.order,
            instruction: normalize_instruction_width(self.insn as u32),
            pc_before: self.pc_rdata,
            pc_after: self.pc_wdata,
            register_writes,
            memory,
            trap: self.trap,
            halt: self.halt,
        }
        .normalize()
    }
}

/// Decode the captured-packet fixture format: one hexadecimal packet per
/// non-comment line.
pub fn parse_packet_hex(text: &str) -> Result<Vec<[u8; V1_PACKET_BYTES]>> {
    let mut packets = Vec::new();
    for (number, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        anyhow::ensure!(
            line.len() == V1_PACKET_BYTES * 2,
            "line {} is {} characters, not the {} of a v1 packet",
            number + 1,
            line.len(),
            V1_PACKET_BYTES * 2
        );
        let mut packet = [0u8; V1_PACKET_BYTES];
        for (index, byte) in packet.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&line[index * 2..index * 2 + 2], 16)
                .with_context(|| format!("line {} is not hexadecimal", number + 1))?;
        }
        packets.push(packet);
    }
    anyhow::ensure!(!packets.is_empty(), "no packets in the fixture");
    Ok(packets)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Captured from the pinned emulator when another process already holds
    /// the port it was given. A change to this diagnostic upstream must break
    /// this test rather than silently turn the retry back into a flake.
    const LOST_RACE_STDERR: &str = "using 43091 as RVFI port.\n\
         Unable to set bind socket: Address already in use\n\
         Reading RVFI DII command failed: Bad file descriptor";

    #[test]
    fn a_lost_port_race_is_recognized() {
        assert!(lost_port_race(LOST_RACE_STDERR));
    }

    #[test]
    fn an_unrelated_startup_failure_is_not_retried_as_a_port_race() {
        assert!(!lost_port_race(""));
        assert!(!lost_port_race(
            "Failed to parse configuration file: unexpected token"
        ));
    }

    use ckb_vm_sail_core::{RegisterWrite, TraceEnd};

    /// Captured from the pinned emulator for `add x3, x1, x2` with x1=5, x2=7.
    fn add_packet() -> [u8; V1_PACKET_BYTES] {
        let mut bytes = [0u8; V1_PACKET_BYTES];
        bytes[0..8].copy_from_slice(&2u64.to_le_bytes()); // order
        bytes[8..16].copy_from_slice(&0x8000_0008u64.to_le_bytes()); // pc_rdata
        bytes[16..24].copy_from_slice(&0x8000_000cu64.to_le_bytes()); // pc_wdata
        bytes[24..32].copy_from_slice(&0x0020_81b3u64.to_le_bytes()); // insn
        bytes[48..56].copy_from_slice(&12u64.to_le_bytes()); // rd_wdata
        bytes[84] = 3; // rd_addr
        bytes
    }

    /// The third instruction of a program is not a reset state: a session that
    /// received this as its *first* packet reached an emulator someone else
    /// had already advanced.
    #[test]
    fn a_session_that_did_not_start_from_reset_is_refused() {
        let advanced = V1Packet::parse(&add_packet());
        let error = started_from_reset(&advanced).expect_err("order 2 is not a reset state");
        assert!(
            error.to_string().contains("not from a reset emulator"),
            "{error}"
        );

        let mut first = add_packet();
        first[0..8].copy_from_slice(&0u64.to_le_bytes());
        first[8..16].copy_from_slice(&INJECTION_ENTRY.to_le_bytes());
        assert!(started_from_reset(&V1Packet::parse(&first)).is_ok());
    }

    #[test]
    fn a_v1_packet_decodes_at_the_documented_offsets() {
        let packet = V1Packet::parse(&add_packet());
        assert_eq!(packet.order, 2);
        assert_eq!(packet.pc_rdata, 0x8000_0008);
        assert_eq!(packet.pc_wdata, 0x8000_000c);
        assert_eq!(packet.insn, 0x0020_81b3);
        assert_eq!(packet.rd_addr, 3);
        assert_eq!(packet.rd_wdata, 12);
        assert!(!packet.trap && !packet.halt && !packet.intr);
        assert_eq!(packet.mem_rmask, 0);
    }

    #[test]
    fn a_reported_write_becomes_an_event_only_when_state_changes() {
        let mut shadow = RegisterShadow::zeroed();
        let event = V1Packet::parse(&add_packet()).into_event(&mut shadow);
        assert_eq!(
            event.register_writes,
            vec![RegisterWrite {
                index: 3,
                value: 12
            }]
        );
        assert!(event.memory.is_empty());

        // The same packet again writes the value x3 already holds.
        let repeat = V1Packet::parse(&add_packet()).into_event(&mut shadow);
        assert!(repeat.register_writes.is_empty());
    }

    #[test]
    fn a_write_to_x0_is_never_an_event() {
        let mut bytes = add_packet();
        bytes[84] = 0; // rd_addr = x0
        let event = V1Packet::parse(&bytes).into_event(&mut RegisterShadow::zeroed());
        assert!(event.register_writes.is_empty());
    }

    #[test]
    fn a_memory_access_survives_into_the_event() {
        let mut bytes = add_packet();
        bytes[56..64].copy_from_slice(&0x8000_1000u64.to_le_bytes());
        bytes[64..72].copy_from_slice(&0xdead_beefu64.to_le_bytes());
        bytes[80] = 0xff;
        let event = V1Packet::parse(&bytes).into_event(&mut RegisterShadow::zeroed());
        assert_eq!(
            event.memory,
            vec![MemoryAccess {
                address: 0x8000_1000,
                read_mask: 0xff,
                write_mask: 0,
                read_data: 0xdead_beef,
                write_data: 0,
            }]
        );
    }

    /// Packets captured from the pinned emulator. If the wire format or the
    /// model's reporting changes under a submodule bump, this fails rather
    /// than silently reinterpreting the bytes.
    #[test]
    fn the_pinned_emulator_fixture_decodes_to_the_expected_trace() {
        const FIXTURE: &str = include_str!("../tests/fixtures/sail-rvfi-dii-v1.hex");
        let packets = parse_packet_hex(FIXTURE).expect("parse fixture");
        assert_eq!(packets.len(), 4, "three instructions plus end-of-trace");

        let mut shadow = RegisterShadow::zeroed();
        let events: Vec<_> = packets[..3]
            .iter()
            .map(|packet| V1Packet::parse(packet).into_event(&mut shadow))
            .collect();

        // addi x1, x0, 5 / addi x2, x0, 7 / add x3, x1, x2 from 0x80000000.
        assert_eq!(
            events
                .iter()
                .map(|event| event.instruction)
                .collect::<Vec<_>>(),
            vec![0x0050_0093, 0x0070_0113, 0x0020_81b3]
        );
        assert_eq!(
            events
                .iter()
                .map(|event| event.pc_before)
                .collect::<Vec<_>>(),
            vec![0x8000_0000, 0x8000_0004, 0x8000_0008]
        );
        assert_eq!(
            events.iter().map(|event| event.order).collect::<Vec<_>>(),
            vec![0, 1, 2]
        );
        assert_eq!(
            events[2].register_writes,
            vec![RegisterWrite {
                index: 3,
                value: 12
            }]
        );
        assert!(events.iter().all(|event| !event.trap && !event.halt));
        assert!(events.iter().all(|event| event.memory.is_empty()));

        // The end-of-trace reply carries rvfi_halt and nothing else.
        let end = V1Packet::parse(&packets[3]);
        assert!(end.halt);
        assert_eq!(end.order, 0);
        assert_eq!(end.insn, 0);
        assert_eq!(end.pc_rdata, 0);
        assert!(!end.trap);

        // The trace this fixture stands for.
        let trace = ExecutionTrace::new(events, TraceEnd::InjectionComplete);
        assert_eq!(trace.events.len(), 3);
    }

    #[test]
    fn a_malformed_fixture_line_is_rejected() {
        assert!(parse_packet_hex("# only a comment").is_err());
        assert!(parse_packet_hex("00ff").is_err(), "short line");
        let bad = "z".repeat(V1_PACKET_BYTES * 2);
        assert!(parse_packet_hex(&bad).is_err(), "not hexadecimal");
    }

    #[test]
    fn a_compressed_instruction_is_reported_as_sixteen_bits() {
        let mut bytes = add_packet();
        bytes[24..32].copy_from_slice(&0x0000_0505u64.to_le_bytes());
        let event = V1Packet::parse(&bytes).into_event(&mut RegisterShadow::zeroed());
        assert_eq!(event.instruction, 0x0505);
    }
}
