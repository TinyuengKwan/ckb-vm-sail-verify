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
| `DefaultMachine` delegation is an axiom | The production wrapper carries `Box<dyn Syscalls>`, `Box<dyn Debugger>` and a `dyn Fn` cycle hook. Aeneas: "Dynamic trait types are not supported yet", so the type cannot be translated | `DefaultCoreMachine` and `common::add` translate with real bodies; the wrapper's delegation between them does not. ADD touches none of the `dyn` fields, but any ADD theorem must state the delegation as a premise rather than assume it. Recorded in `proof/lean/expected_rust_build_status.txt` |
| `bool -> u64` conversions do not translate | `Register<u64>::{eq,lt,lt_s,logical_not}` are all `.into()` from `bool`; Aeneas emits `core.convert.FromU64Bool`, which its Lean library does not define, and the generated file does not compile with them in | They are extracted as opaque. ADD uses none of them; **BEQ uses `eq`**, so the mandatory BEQ work has to resolve this before it can have a theorem |
| Two Lean toolchains | The Sail-side model needs Lean v4.29.0; the Aeneas Lean library needs v4.31.0 and mathlib4 | Both sides compile, but in separate lake projects. A refinement theorem referencing both cannot be stated until this is unified |
| Aeneas library carries `sorry` | Four declarations in the Aeneas Lean library are `sorry`: `Slice.get_unchecked` and its spec, and two in `StringIter` | The ADD path uses `Slice.index_usize`, which carries none. Listed in `VERIFICATION.md` §5 as trust base; a theorem reaching the others must say so |
| Compiling is not proving | The Lean model now builds, which says the definitions are well-formed and nothing more | There is no Rust-side generation, no state bridge and no ADD refinement theorem yet. `make proof-build` reporting ok must not be read as proof evidence |

## Scope exclusions

- Only CKB VERSION2 Rust interpreter is in the current runtime and proof claim.
- Mandatory runtime scope is ADD, ADDI and BEQ; MUL is a stretch goal.
- The mandatory theorem is production-linked ADD in Lean 4.
- Rocq/Coq reports compatibility GO/NO-GO unless an additional theorem passes its kernel.
- ASM/JIT equivalence requires another connection layer.
- A extension is unsupported by the pinned ckb-vm 0.24.0 public decoder and is post-MVP.
- Memory, MOP, ECALL, cycles, VERSION0/1 and platform claims are post-MVP.

No gap may be handled by truncating traces, dropping a field, or converting an execution error to successful termination.
