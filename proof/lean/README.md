# Lean 4 Main Proof Path

Planned imports:

1. Sail `generated_lean_rv64d` output under `generated/sail/`;
2. Aeneas translation of the provisional
   `crates/ckb-runner/src/semantics.rs` target under `generated/rust/`;
3. handwritten relation and theorem files under `theorems/`.

The mandatory six-week acceptance target is ADD. ADDI and BEQ are runtime-differential
targets in this MVP and become proof targets only after the ADD production connection
and theorem are complete.

This directory currently contains no theorem and therefore supports no `proved`
coverage entry.

The provisional target must be replaced by, or connected to, a production-called
CKB-VM function before the ADD theorem can count as project proof coverage.
