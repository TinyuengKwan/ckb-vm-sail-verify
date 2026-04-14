# Week 1: Environment Setup & Instruction Mapping

## Objectives

- Set up complete build environment (Sail, Coq, CKB-VM, cross-compiler)
- Map CKB-VM's 158 internal opcodes to Sail RISC-V model modules
- Validate that Sail Coq generation works for the CKB-VM subset

## Tasks

1. **Install and verify toolchain**
   - Sail compiler >= 0.20.1 (`opam install sail`)
   - Coq/Rocq >= 9.0 + coq-sail-stdpp (`opam install coq coq-sail-stdpp`)
   - Rust nightly with CKB-VM compiling (`cargo build -p ckb-vm-sail-lib`)
   - RISC-V cross-compiler (for building test programs)

2. **Generate Coq from sail-riscv**
   - Run `scripts/generate_coq.sh` with the existing `sail-model/ckb_vm_config.json`
   - Debug any config issues (extension toggles, xlen, etc.)
   - Verify generated `.v` files compile with `coqc`

3. **Build CKB-VM instruction mapping table**
   - Read `ckb-vm/definitions/src/instructions.rs` (158 opcodes)
   - Map each opcode to its Sail model counterpart in `sail-riscv/model/extensions/`
   - Document unmapped items (MOP fusion, CKB-VM-specific)

4. **Build Sail C++ emulator**
   - Run `scripts/build_sail_emulator.sh`
   - Verify it can execute a minimal RISC-V ELF

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `doc/instruction_mapping.md` | CKB-VM opcode ↔ Sail model mapping table |
| Modify | `sail-model/ckb_vm_config.json` | Fix config if generation fails |
| Modify | `scripts/generate_coq.sh` | Adapt to actual sail-riscv build output paths |
| Add | `scripts/setup_env.sh` | One-shot environment setup script |

## Verification Criteria

- [ ] `make coq-gen` succeeds, producing `coq/generated/CkbVmSpec.v`
- [ ] `coqc coq/generated/CkbVmSpec.v` compiles without errors
- [ ] `cargo build --workspace` succeeds
- [ ] Sail C++ emulator runs a trivial ELF

---

# 第一周：环境搭建与指令映射

## 目标

- 搭建完整构建环境（Sail、Coq、CKB-VM、交叉编译器）
- 将 CKB-VM 的 158 个内部 opcode 映射到 Sail RISC-V 模型模块
- 验证 Sail Coq 后端对 CKB-VM 子集可正常工作

## 任务

1. 安装并验证工具链（Sail >= 0.20.1, Coq >= 9.0, coq-sail-stdpp, Rust）
2. 运行 `scripts/generate_coq.sh` 从 sail-riscv 生成 Coq，调试配置问题直到 `.v` 文件可用 `coqc` 编译
3. 阅读 `ckb-vm/definitions/src/instructions.rs`，建立 158 个 opcode 到 Sail 模型的完整映射表
4. 编译 Sail C++ 模拟器，验证能执行最小 ELF

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `doc/instruction_mapping.md` | CKB-VM opcode ↔ Sail 映射表 |
| 修改 | `sail-model/ckb_vm_config.json` | 根据实际生成结果修正配置 |
| 修改 | `scripts/generate_coq.sh` | 适配实际 sail-riscv 产出路径 |
| 新增 | `scripts/setup_env.sh` | 一键环境搭建脚本 |

## 验收标准

- `make coq-gen` 成功生成 `coq/generated/CkbVmSpec.v`
- 生成的 Coq 文件可编译
- `cargo build --workspace` 通过
- Sail C++ 模拟器能跑简单 ELF
