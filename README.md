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
├── deps/
│   └── sail-riscv/          # Official Sail RISC-V model (git submodule)
├── lib/                     # Shared Rust library
│   └── src/
│       ├── state.rs         # StepState, trace comparison
│       └── runner.rs        # CKB-VM step-by-step driver
├── crates/
│   └── diff-test/           # Differential testing CLI
├── coq/                     # Coq formal proofs
│   ├── MachineState.v       # Machine state definitions
│   ├── CkbVmModel.v         # CKB-VM interpreter model
│   └── InstructionEquiv.v   # Equivalence proofs
├── sail-model/              # Sail config for CKB-VM subset
├── scripts/                 # Build & generation scripts
├── doc/                     # Technical documentation
└── plan/                    # Weekly development plans
```

## Quick Start

```bash
# Clone with submodules
git clone --recursive https://github.com/YourUser/ckb-vm-sail-verify
cd ckb-vm-sail-verify

# Or init submodules after clone
make init

# Build everything
make all

# Individual targets
make coq-gen       # Generate Coq from Sail
make coq           # Compile Coq proofs
make sail-emu      # Build Sail C++ emulator
make diff-test     # Run differential tests
make help          # Show all targets
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

sail-riscv 模型作为 git submodule 位于 `deps/sail-riscv/`，首次克隆时使用 `git clone --recursive`。

详细计划见 `plan/` 目录。
