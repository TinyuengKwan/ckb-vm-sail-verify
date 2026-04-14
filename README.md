# CKB-VM Sail Formal Verification PoC

> Formally verifying CKB-VM's RISC-V implementation against the official Sail specification.

## Overview

[CKB-VM](https://github.com/nervosnetwork/ckb-vm) is a RISC-V virtual machine used as the scripting VM in [Nervos CKB](https://nervos.org). This project aims to formally verify that CKB-VM's instruction execution semantics are equivalent to the [official RISC-V Sail specification](https://github.com/riscv/sail-riscv).

This is a Proof of Concept (PoC) that:
1. Generates Coq definitions from the Sail RISC-V model for the CKB-VM instruction subset
2. Builds a Coq abstraction of CKB-VM's Rust interpreter logic
3. Proves instruction-level equivalence between the two
4. Provides a differential testing framework for runtime validation

This project responds to [ckb-vm#190](https://github.com/nervosnetwork/ckb-vm/issues/190) ("Formally Verify CKB-VM via Sail"), open since 2021.

## Architecture

```
                    ┌──────────────┐
                    │  Sail RISC-V │
                    │  (Official   │
                    │   Spec)      │
                    └──────┬───────┘
                           │ sail --coq
                           ▼
                    ┌──────────────┐
                    │  Coq Spec    │
                    │  (Generated) │◄─── Ground Truth
                    └──────┬───────┘
                           │ prove equivalence
                           ▼
              ┌────────────────────────┐
              │  CKB-VM Coq Model     │◄─── Manual abstraction
              │  (from execute.rs)    │     of CKB-VM Rust code
              └────────────────────────┘

Differential Testing (Runtime Validation):

   ┌──────────┐     RVFI-DII      ┌──────────────┐
   │  CKB-VM  │◄───compare────►   │  Sail C Emu  │
   │  (Rust)  │  register state   │  (Generated)  │
   └──────────┘                   └──────────────┘
        ▲                               ▲
        └──── same RISC-V ELF ─────────┘
```

## CKB-VM Instruction Subset

CKB-VM implements a specific subset of the RISC-V ISA:

| Extension | Instructions | Sail Module |
|-----------|-------------|-------------|
| RV64I | Base integer (ALU, load/store, branch, jump) | `extensions/I/` |
| RV64M | Integer multiply/divide | `extensions/M/` |
| RVC   | Compressed instructions | `extensions/C/` |
| RV64B (Zba/Zbb/Zbc/Zbs) | Bit manipulation | `extensions/B/` |
| RV64A (Zaamo/Zalrsc) | Atomic instructions | `extensions/A/` |
| MOP (custom) | Macro-op fusion (WIDE_MUL, FAR_JUMP, etc.) | N/A (CKB-VM specific) |

## Project Structure

```
ckb-vm-sail-verify/
├── README.md                  # This file
├── Makefile                   # Build orchestration
├── LICENSE                    # MIT License
├── sail-model/
│   ├── ckb_vm_config.json     # Sail config for CKB-VM subset
│   └── README.md              # Sail model setup instructions
├── coq/
│   ├── _CoqProject            # Coq project file
│   ├── CkbVmSpec.v            # (Generated) Sail RISC-V Coq spec
│   ├── CkbVmSpec_types.v      # (Generated) Coq type definitions
│   ├── CkbVmModel.v           # CKB-VM interpreter Coq abstraction
│   ├── MachineState.v         # Machine state definitions
│   └── InstructionEquiv.v     # Equivalence proofs
├── differential-test/
│   ├── Cargo.toml             # Rust project manifest
│   └── src/
│       ├── main.rs            # Differential test runner
│       ├── ckb_vm_runner.rs   # CKB-VM execution driver
│       └── sail_runner.rs     # Sail emulator driver
├── scripts/
│   ├── generate_coq.sh        # Generate Coq from Sail
│   ├── build_sail_emulator.sh # Build Sail C++ emulator
│   └── run_differential.sh    # Run differential tests
└── doc/
    ├── architecture.md        # Verification architecture
    └── methodology.md         # Verification methodology
```

## Prerequisites

- [Sail](https://github.com/rems-project/sail) >= 0.20.1
- [Coq/Rocq](https://coq.inria.fr/) >= 9.0
- [coq-sail-stdpp](https://github.com/rems-project/coq-sail)
- [Rust](https://rustup.rs/) >= 1.75
- [sail-riscv](https://github.com/riscv/sail-riscv) (cloned locally)
- [ckb-vm](https://github.com/nervosnetwork/ckb-vm) (as Rust dependency)
- CMake >= 3.20

## Quick Start

```bash
# 1. Generate Coq spec from Sail RISC-V model
make coq-gen

# 2. Build and check Coq proofs
make coq

# 3. Run differential tests
make diff-test

# 4. Run everything
make all
```

## Verification Scope

### PoC Phase (This Project)

Target: 10 core instructions with full Coq equivalence proofs

| Instruction | Type | Verification Status |
|-------------|------|-------------------|
| ADD         | R-type ALU | Planned |
| SUB         | R-type ALU | Planned |
| ADDI        | I-type ALU | Planned |
| SLLI        | I-type Shift | Planned |
| SRLI        | I-type Shift | Planned |
| SRAI        | I-type Shift | Planned |
| LW          | I-type Load | Planned |
| SW          | S-type Store | Planned |
| BEQ         | B-type Branch | Planned |
| JAL         | J-type Jump | Planned |

### CKB-VM Semantic Differences from Standard RISC-V

1. **x0 register**: Forced to zero after each instruction write-back
2. **Memory model**: Fixed 4MB, no MMU/virtual memory, W^X enforcement
3. **ECALL**: A7-based syscall dispatch, 93 = exit
4. **Load reservation**: Single address (not reservation set)
5. **Versioned behavior**: VERSION0/1/2 with different boundary check semantics

### Future Phases (Post-PoC)

| Phase | Scope | Target Funding |
|-------|-------|---------------|
| Phase 2 | Full RV64I Coq proofs | Community Fund DAO |
| Phase 3 | M/C/B extension proofs | Community Fund DAO |
| Phase 4 | ASM mode verification (via Islaris) | Large Grant |

## How to Verify (Reproducible)

```bash
# Clone this repository
git clone https://github.com/TinyuengKwan/ckb-vm-sail-verify
cd ckb-vm-sail-verify

# Check Coq proofs compile (proves correctness)
make coq
# Expected: all .v files compile without errors

# Run differential tests (runtime validation)
make diff-test
# Expected: all tests pass, 0 mismatches

# Generate verification report
make report
```

## License

MIT

## Author

- TinyuengKwan (kwantinyueng@gmail.com)
- PLCT Lab intern, contributor to [sail-riscv](https://github.com/riscv/sail-riscv) and [sail](https://github.com/rems-project/sail)

## Acknowledgments

- [Nervos CKB](https://nervos.org) and the CKB-VM team
- [REMS Project](https://www.cl.cam.ac.uk/~pes20/rems/) at Cambridge for Sail
- [Spark Program](https://talk.nervos.org/t/spark-program/8751) by CKB Eco Fund

---

# CKB-VM Sail 形式化验证 PoC

> 使用官方 Sail 规范对 CKB-VM 的 RISC-V 实现进行形式化验证。

## 概述

[CKB-VM](https://github.com/nervosnetwork/ckb-vm) 是 [Nervos CKB](https://nervos.org) 区块链使用的 RISC-V 虚拟机。本项目旨在形式化验证 CKB-VM 的指令执行语义与[官方 RISC-V Sail 规范](https://github.com/riscv/sail-riscv)的等价性。

本项目是一个概念验证（PoC），包括：
1. 为 CKB-VM 指令子集从 Sail RISC-V 模型生成 Coq 定义
2. 构建 CKB-VM Rust 解释器逻辑的 Coq 抽象模型
3. 证明两者之间的指令级等价性
4. 提供差分测试框架进行运行时验证

本项目回应了自 2021 年以来一直开放的 [ckb-vm#190](https://github.com/nervosnetwork/ckb-vm/issues/190)（"通过 Sail 形式化验证 CKB-VM"）。

## 许可证

MIT
