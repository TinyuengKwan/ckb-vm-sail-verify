# Semantic Gaps and Blocking Differences

## Active foundation gaps

| Gap | Current behavior | Current six-week handling |
|---|---|---|
| Sail RVFI activation | Upstream `--trace-rvfi` prints packets only in RVFI-DII socket mode | Week 2 mandatory: implement a binary DII client; empty output remains an error |
| CKB data-memory observation | `DefaultMachine::step` exposes state but not committed read/write callbacks | Post-MVP; load/store remain unsupported rather than dropping memory fields |
| Initial state | ELF loaders/platform stacks differ | Week 2 mandatory: drive shared single-step states through DII |
| ECALL/HTIF | CKB exit syscall and Sail HTIF have different platform contracts | Excluded from the current MVP and reported explicitly |
| Trap text | Error strings are implementation-specific | Use closed comparison categories for supported cases; full trap relation is post-MVP |
| Cycles | CKB cycle accounting is not an architectural Sail field | Excluded from the current MVP; cycle-limit failure remains a distinct termination |
| Compressed instruction fetch | CKB adapter currently fetches 32 raw bits | Normalize 16/32-bit width before compressed instructions enter supported coverage |

## Scope exclusions

- Only CKB VERSION2 Rust interpreter is in the current runtime and proof claim.
- Mandatory runtime scope is ADD, ADDI and BEQ; MUL is a stretch goal.
- The mandatory theorem is production-linked ADD in Lean 4.
- Rocq/Coq reports compatibility GO/NO-GO unless an additional theorem passes its kernel.
- ASM/JIT equivalence requires another connection layer.
- A extension is unsupported by the pinned ckb-vm 0.24.0 public decoder and is post-MVP.
- Memory, MOP, ECALL, cycles, VERSION0/1 and platform claims are post-MVP.

No gap may be handled by truncating traces, dropping a field, or converting an execution error to successful termination.
