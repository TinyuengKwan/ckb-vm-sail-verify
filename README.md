# CKB-VM Sail Formal Verification PoC

> Formally verifying CKB-VM's RISC-V implementation against the official Sail specification.

## Overview

[CKB-VM](https://github.com/nervosnetwork/ckb-vm) is the RISC-V virtual machine powering [Nervos CKB](https://nervos.org). This project formally verifies that CKB-VM's instruction execution semantics are equivalent to the [official RISC-V Sail specification](https://github.com/riscv/sail-riscv).

Responds to [ckb-vm#190](https://github.com/nervosnetwork/ckb-vm/issues/190) ("Formally Verify CKB-VM via Sail"), open since 2021.

## Project Structure

```
ckb-vm-sail-verify/
├── Cargo.toml              # Workspace root
├── Makefile                 # Build orchestration
├── lib/                     # Shared Rust library
│   └── src/
│       ├── lib.rs           # Re-exports
│       ├── state.rs         # StepState, trace comparison
│       └── runner.rs        # CKB-VM step-by-step driver
├── crates/
│   └── diff-test/           # Differential testing CLI
│       └── src/
│           ├── main.rs      # CLI entry point
│           └── sail_runner.rs
├── coq/                     # Coq formal proofs
│   ├── _CoqProject
│   ├── MachineState.v       # Machine state definitions
│   ├── CkbVmModel.v         # CKB-VM interpreter model
│   └── InstructionEquiv.v   # Equivalence proofs
├── sail-model/              # Sail RISC-V configuration
│   └── ckb_vm_config.json   # CKB-VM instruction subset
├── scripts/                 # Build & generation scripts
├── doc/                     # Technical documentation
└── plan/                    # Weekly development plans
```

## Quick Start

```bash
make help          # Show all targets
make coq-gen       # Generate Coq from Sail
make coq           # Compile Coq proofs
make diff-test     # Run differential tests
make all           # Everything
```

## CKB-VM Instruction Subset

| Extension | Description | Sail Module |
|-----------|-------------|-------------|
| RV64I     | Base integer | `extensions/I/` |
| RV64M     | Multiply/divide | `extensions/M/` |
| RVC (Zca) | Compressed | `extensions/C/` |
| RV64B     | Bit manipulation (Zba/Zbb/Zbc/Zbs) | `extensions/B/` |
| RV64A     | Atomic (Zaamo/Zalrsc) | `extensions/A/` |
| MOP       | Macro-op fusion (CKB-VM custom) | N/A |

## License

MIT

---

# CKB-VM Sail 形式化验证 PoC

本项目使用 RISC-V 官方 Sail 规范，对 CKB-VM 的指令执行语义进行形式化验证。

回应 [ckb-vm#190](https://github.com/nervosnetwork/ckb-vm/issues/190)（自 2021 年以来一直开放）。

详细计划见 `plan/` 目录。
