# Semantic Gaps and Blocking Differences

## Closed in Week 2

| Gap | How it was closed | Cost |
|---|---|---|
| Sail RVFI activation | `crates/sail-runner/src/dii.rs` speaks the binary RVFI-DII protocol; the emulator produces one v1 packet per injected instruction | Direct ELF runs still produce no RVFI and remain an explicit error |
| Initial state | Direct instruction injection starts both engines from the architectural reset state (all integer registers zero, PC `0x80000000`) and executes the same instruction stream, so no ELF loader or platform stack participates | Register setup must be *executed* (`encode::materialize`), which lengthens each case |
| Compressed instruction fetch | `normalize_instruction_width` drops the upper half on both sides when the two low bits mark a compressed instruction; exercised end to end by `a_compressed_instruction_is_normalized_on_both_sides` | A compressed instruction must be injected with a zeroed upper half. Compressed instructions are still outside the corpus, so `docs/coverage.md` claims no compressed coverage |

## Active gaps

| Gap | Current behavior | Current six-week handling |
|---|---|---|
| CKB data-memory observation | `DefaultMachine::step` exposes state but not committed read/write callbacks | Load, store and AMO instructions are refused by `core::program::validate_program`; they are reported as unsupported rather than compared with a missing field |
| Same-value register writeback | CKB-VM exposes register *state*, so a write of the value a register already holds is invisible; RVFI reports it | Both sides are reduced to architectural state changes by `core::event::RegisterShadow`. A defect that writes the already-held value to the correct register is therefore not detectable by this observer |
| Read operands | RVFI v1 carries `rs1`/`rs2` addresses and data, and the pinned model leaves them zero | Not compared; the commit-event protocol is about committed effects |
| Positional injection | RVFI-DII does not fetch from memory: the k-th injected word executes wherever the PC is. The CKB mirror writes each word at the current PC before the step and invalidates the decoder cache | Both sides therefore run the same instruction stream. Memory outside the injected word is zero, so this is not a test of instruction *fetch* |
| ECALL/HTIF | CKB exit syscall and Sail HTIF have different platform contracts | SYSTEM instructions are refused by `validate_program`; excluded from the current MVP |
| Trap text | Error strings are implementation-specific | The per-event `trap` flag is compared; a trapping instruction ends the CKB trace with an error while Sail continues into its handler, so traps surface as termination mismatches. A full trap relation is post-MVP |
| Cycles | CKB cycle accounting is not an architectural Sail field | Excluded from the current MVP; cycle-limit failure remains a distinct termination |
| Instruction ordering | `rvfi_order` is `minstret`, which does not advance for an instruction that traps | Only matters once trapping instructions enter the corpus; today an order difference is a reported mismatch |
| Sail releases do not build sail-riscv's Lean target | At sail-riscv `27224cc` with released Sail 0.20.2 the generated Lean model failed at target 10 of 131 (`unknown namespace LeanRV64D.Defs`). Upstream runs its two targets on two different Sail builds and never tested that pair | Closed by moving both pins together: sail-riscv `8f91355e` and a Sail source build at `8eb1fb6b`. The cost is that the Sail pin is now a commit rather than a release, so `verify_environment.sh` pins the full version string -- a release build reporting the same number is rejected. Recorded in `proof/lean/expected_build_status.txt` |
| Rocq route is NO-GO | Measured, both halves: Aeneas's Rocq `Primitives.v` defines `result A`, shadowed by Rocq 9.1's prelude `result A E`, so the generated file fails at its first trait declaration; and the Sail-side `rv64d.v` needs `e_div`, absent from the released `rocq-sail-stdpp 0.20.2` that the pinned source Sail outgrew | Recorded in `proof/rocq/SPIKE.md` with a minimal reproduction; `make proof-spike` reproduces it and fails if either half starts passing. The mandatory Lean 4 backend is unaffected, and per the plan a NO-GO does not substitute for it |
| Wrapper production connection | The reviewed runtime-container patch exposes `DefaultMachine` and five real register/PC methods; `MachineRuntime` and `Pause` remain opaque types | Both contracts and `ProductionAdd.decoded_add_step` are now formal sources, with 137 exact dependencies audited. Concrete decoded-input/Sail initialization contracts and full refactor equivalence remain outside this result. See `proof/lean/reports/PROOF_CHECK.md` |
| External constant extraction (resolved) | Exact Charon includes now retain register count 32 and RA 1 as pure generated definitions | `ExtractedConstants.lean` checks their values and standard-logic-only axiom footprint in `proof-imports`. No constant-value premise remains; wrapper delegation is also proved. See [remaining premises](../proof/lean/reports/ADD_PREMISES.md) |
| Same-word public ADD decoding | The actual Rust public decoder and Sail raw decoder are connected for VERSION2, IMC+B, MOP off and a fresh cache | `OuterAdd.cold_public_add_step` has 158 audited dependencies; the independent clean check and first integrated main run passed. Size/load, Sail fetch/readiness, physical-memory coupling and reset boundaries remain explicit. See [scoped adoption](../proof/lean/decoder/ADOPTION.md) |
| ADD leaf effects do not include PC | Rust `common.add` and Sail `Functions.execute_RTYPE ... ADD` only implement register effects | The production step theorem now connects Rust `execute` with Sail `run_hart_active` and `tick_pc`. The separately extracted public decoder derives the decoded-input correspondence; initial-state and fetch/readiness contracts remain explicit. Cycle accounting remains outside the theorem |
| `bool -> u64` conversions do not translate | `Register<u64>::{eq,lt,lt_s,logical_not}` are all `.into()` from `bool`; Aeneas emits `core.convert.FromU64Bool`, which its Lean library does not define, and the generated file does not compile with them in | They are extracted as opaque. The selected ADD body uses none of them; BEQ uses `eq`, so a future BEQ theorem must resolve it. BEQ is a mandatory runtime target, not a mandatory theorem in this MVP |
| Sail enum derivation on common Lean | Both projects now use 4.31.0, but the original Sail `Defs.lean` panics when deriving enum `BEq` in a noncomputable section | Generation/build scripts apply the one-line computable-scope adapter. `proof-imports` checks full libraries, shared imports and rejects fresh/cached compiler panics. See [compatibility evidence](../proof/lean/compat/README.md); this is not compatibility of unmodified Sail output |
| Aeneas library carries `sorry` | Four declarations in the Aeneas Lean library use `sorry`: `Slice.get_unchecked` and its spec, and two in `StringIter` | Direct ADD reads use `Slice.index_usize`; audit the eventual theorem's transitive axioms and explicit premises instead of assuming unused imports or helpers cannot introduce `sorryAx`. See `VERIFICATION.md` §5 |
| Compiling is not proving | Lean 4.31.0 gates include the GPR leaf and `make proof-step` for conditional dispatch/PC refinement | Wrapper contracts are proved; decoded-input and framed Sail prefix contracts remain explicit. The final theorem's 137 transitive axioms and fixed RVFI=false scope are audited; proof-check also requires a clean kernel build. Import success alone is not proof evidence |

## Scope exclusions

- Only CKB VERSION2 Rust interpreter is in the current runtime and proof claim.
- Mandatory runtime scope is ADD, ADDI and BEQ; MUL is a stretch goal.
- The mandatory theorem is production-linked ADD in Lean 4.
- Rocq/Coq reports compatibility GO/NO-GO unless an additional theorem passes its kernel.
- ASM/JIT equivalence requires another connection layer.
- A extension is unsupported by the pinned ckb-vm 0.24.0 public decoder and is post-MVP.
- Memory, MOP, ECALL, cycles, VERSION0/1 and platform claims are post-MVP.

No gap may be handled by truncating traces, dropping a field, or converting an execution error to successful termination.
