# Verification Architecture

## Overview

This document describes the architecture of the CKB-VM formal verification project.

## Verification Layers

### Layer 1: Formal Specification (Sail RISC-V -> Coq)

The ground truth is the [official RISC-V Sail specification](https://github.com/riscv/sail-riscv),
which is the authoritative formal model of RISC-V ISA semantics adopted by RISC-V International.

Using Sail's Coq backend (`sail --coq`), we generate Coq definitions that capture the
instruction-level semantics for the CKB-VM instruction subset (RV64IMCB + A).

### Layer 2: CKB-VM Model (Manual Coq Abstraction)

We manually construct a Coq model of CKB-VM's Rust interpreter logic, based on the
`handle_*` functions in `ckb-vm/src/instructions/execute.rs`.

This model captures:
- Register file operations (32 x 64-bit, x0 hardwired to zero)
- PC advancement (4 bytes for standard, 2 bytes for compressed)
- ALU operations with wrapping arithmetic
- Memory load/store with little-endian byte ordering
- Branch/jump semantics with sign-extended offsets

### Layer 3: Equivalence Proofs (Coq)

For each target instruction, we prove in Coq that the CKB-VM model function produces
the same state transition as the Sail specification function.

### Layer 4: Differential Testing (Runtime)

As a complementary validation, we execute the same RISC-V ELF binaries on both CKB-VM
and the Sail C++ emulator, comparing execution traces step-by-step.

## CKB-VM Specific Considerations

### Versioned Behavior

CKB-VM has three versions (VERSION0, VERSION1, VERSION2) with different semantics
for some instructions (notably load boundary checking). The PoC targets VERSION2
(current production version).

### MOP Fusion Instructions

CKB-VM's Macro-Operation Fusion (MOP) instructions are optimizations that fuse
sequences of standard RISC-V instructions into single operations:

| MOP Instruction | Fused Sequence | Verification Strategy |
|-----------------|---------------|----------------------|
| WIDE_MUL | MULH + MUL | Prove: fused result = sequential execution |
| FAR_JUMP_REL | AUIPC + JALR | Prove: fused result = sequential execution |
| ADC | 5-instruction 128-bit add | Prove: fused result = sequential execution |

These do not require Sail model involvement -- we prove in Coq that the fused
operation produces the same result as executing the constituent instructions
sequentially.

### Memory Model Differences

| Aspect | Standard RISC-V | CKB-VM |
|--------|----------------|--------|
| Address space | Configurable | Fixed 4MB |
| Virtual memory | Sv39/48/57 | None |
| Page permissions | PMP | W^X (per-page) |
| Reservation | Reservation set | Single address |

The PoC models CKB-VM's simplified memory model directly.

## Tool Chain

```
sail-riscv/model/*.sail
    │
    ├─── sail --coq ──► coq/generated/CkbVmSpec.v         (formal spec)
    │
    └─── sail --cpp ──► sail_riscv_sim                   (C++ emulator)
                              │
                              └─── differential-test ──► compare traces
                                         │
ckb-vm/src/instructions/execute.rs       │
    │                                    │
    ├─── manual abstraction ──► coq/CkbVmModel.v         (CKB-VM model)
    │                                    │
    │                            coq/InstructionEquiv.v        (proofs)
    │
    └─── ckb-vm Rust library ──► differential-test ──► compare traces
```
