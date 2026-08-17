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

## Scope exclusions

- Only CKB VERSION2 Rust interpreter is in the current runtime and proof claim.
- Mandatory runtime scope is ADD, ADDI and BEQ; MUL is a stretch goal.
- The mandatory theorem is production-linked ADD in Lean 4.
- Rocq/Coq reports compatibility GO/NO-GO unless an additional theorem passes its kernel.
- ASM/JIT equivalence requires another connection layer.
- A extension is unsupported by the pinned ckb-vm 0.24.0 public decoder and is post-MVP.
- Memory, MOP, ECALL, cycles, VERSION0/1 and platform claims are post-MVP.

No gap may be handled by truncating traces, dropping a field, or converting an execution error to successful termination.
