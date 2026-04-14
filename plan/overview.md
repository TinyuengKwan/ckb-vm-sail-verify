# Project Overview: CKB-VM Sail Formal Verification PoC

## Goal

Prove that CKB-VM's RISC-V instruction execution is equivalent to the official Sail specification, using Coq theorem proving and differential testing.

## Verification Architecture

```
Sail RISC-V (official spec)
        │
        ├── sail --coq ──► Coq definitions (ground truth)
        │                        │
        │                  prove equivalence
        │                        │
        │                  CKB-VM Coq model (hand-written from execute.rs)
        │
        └── sail --cpp ──► C++ emulator ──► differential testing
                                                   │
                                             CKB-VM (Rust) ──► compare traces
```

## Timeline

8 weeks, 3 phases:

| Phase | Weeks | Focus |
|-------|-------|-------|
| Infrastructure | 1-3 | Environment setup, instruction mapping, diff-test framework |
| Formal Proofs | 4-6 | Coq generation, CKB-VM model, equivalence proofs |
| Integration | 7-8 | Full test coverage, documentation, Spark deliverables |

## Deliverables

1. **Coq proofs** for 10+ core instructions (ADD, SUB, ADDI, SLLI, SRLI, SRAI, LW, SW, BEQ, JAL, MUL)
2. **Differential testing framework** comparing CKB-VM against Sail C++ emulator
3. **Instruction mapping document** between CKB-VM opcodes and Sail model
4. **Methodology document** for extending verification to the full instruction set
5. **Roadmap** for Phase 2+ (Community Fund DAO scale)

## Key Technical Decisions

- **Verify Rust interpreter first**, not ASM. ASM verification requires Islaris-level tooling.
- **Target VERSION2** (current production) only. Versioned behavior diffs are documented but not proved.
- **MOP fusion instructions** verified as compositions of standard instructions, not against Sail.
- **Sail Coq backend** via `sail --coq --dcoq-undef-axioms` with the official sail-riscv project.

## Repository Layout

```
lib/            Shared Rust library (state, runner, CKB-VM wrapper)
crates/         Binary tools (diff-test CLI, future: trace-dump)
coq/            Coq proofs (hand-written + generated from Sail)
sail-model/     Sail configuration for CKB-VM subset
scripts/        Build automation
doc/            Architecture & methodology docs
plan/           This directory — weekly plans
```

---

# 项目总览：CKB-VM Sail 形式化验证 PoC

## 目标

使用 Coq 定理证明和差分测试，证明 CKB-VM 的 RISC-V 指令执行语义与官方 Sail 规范等价。

## 验证架构

上层：Sail RISC-V 官方规范通过 `sail --coq` 生成 Coq 定义（真值来源），与手动编写的 CKB-VM Coq 模型进行等价性证明。

下层：Sail 通过 `sail --cpp` 生成 C++ 模拟器，与 CKB-VM Rust 实现进行差分测试（运行时验证）。

## 时间线

共 8 周，分三个阶段：
- 第 1-3 周：基础设施搭建（环境配置、指令映射、差分测试框架）
- 第 4-6 周：形式化证明（Coq 生成、CKB-VM 模型、等价性证明）
- 第 7-8 周：整合收尾（全面测试、文档完善、Spark 交付物）

## 交付物

1. 10+ 条核心指令的 Coq 等价性证明
2. CKB-VM vs Sail 差分测试框架
3. CKB-VM 指令集与 Sail 模型的映射文档
4. 可扩展的验证方法论文档
5. Phase 2+ 路线图（面向 Community Fund DAO）

## 关键技术决策

- 先验证 Rust 解释器模式，不验证 ASM 汇编模式（后者需要 Islaris 级工具链）
- 仅针对 VERSION2（当前生产版本），版本差异记录但不做证明
- MOP 融合指令作为标准指令的组合来验证，不需要 Sail 模型参与
- 使用官方 sail-riscv 项目的 Coq 后端生成规范

## 仓库结构

- `lib/` — 共享 Rust 库（状态定义、CKB-VM 驱动）
- `crates/` — 二进制工具（差分测试 CLI）
- `coq/` — Coq 证明（手写 + Sail 生成）
- `sail-model/` — CKB-VM 子集的 Sail 配置
- `scripts/` — 构建自动化脚本
- `doc/` — 技术文档
- `plan/` — 本目录，周计划
