# Week 2: Differential Testing Framework

## Objectives

- Get the diff-test CLI working end-to-end (CKB-VM vs Sail C++ emulator)
- Run CKB-VM's existing ISA compliance tests through the framework
- Identify and document any behavioral differences

## Tasks

1. **Finalize Sail trace parsing**
   - Run Sail emulator with `--trace` on sample ELFs, capture actual output format
   - Update `crates/diff-test/src/sail_runner.rs` to parse real trace output
   - Extract full register state (not just PC) — may require RVFI-DII or custom Sail patches

2. **Integrate CKB-VM test artifacts**
   - Locate riscv-tests ELFs (from `ckb-vm/tests/artifact/spec/`)
   - Add `--test-dir` integration to run full ISA compliance suite
   - Record pass/fail per test

3. **Handle CKB-VM specific behaviors**
   - ECALL dispatch (syscall 93 = exit)
   - Memory size limit (4MB)
   - Filtered comparison: skip cycle count, skip CKB-VM-only state

4. **CI-ready test runner**
   - `make diff-test` runs the suite and reports results
   - Exit code reflects pass/fail

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Modify | `crates/diff-test/src/sail_runner.rs` | Real trace parsing based on actual Sail output |
| Modify | `crates/diff-test/src/main.rs` | Add summary reporting, exit codes |
| Add | `lib/src/trace.rs` | Trace serialization (JSON) for debugging |
| Modify | `lib/src/lib.rs` | Re-export trace module |
| Modify | `scripts/run_differential.sh` | Point to CKB-VM test artifact directory |

## Verification Criteria

- [ ] `make diff-test` runs against rv64ui/rv64um/rv64uc test suite
- [ ] All passing CKB-VM tests also pass in differential mode
- [ ] Any divergence is documented with root cause

---

# 第二周：差分测试框架

## 目标

- 让差分测试 CLI 端到端工作（CKB-VM vs Sail C++ 模拟器）
- 用 CKB-VM 现有 ISA 合规测试跑通框架
- 发现并记录行为差异

## 任务

1. 用实际 Sail 输出格式完善 trace 解析（可能需要 RVFI-DII 或者修改 Sail trace 输出以包含完整寄存器状态）
2. 集成 CKB-VM 的 `tests/artifact/spec/` 目录中的 riscv-tests ELF
3. 处理 CKB-VM 特有行为（ECALL 分发、4MB 内存限制）
4. 让 `make diff-test` 可在 CI 中运行

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 修改 | `crates/diff-test/src/sail_runner.rs` | 适配真实 Sail 输出格式 |
| 修改 | `crates/diff-test/src/main.rs` | 汇总报告、退出码 |
| 新增 | `lib/src/trace.rs` | Trace 序列化（JSON），方便调试 |
| 修改 | `scripts/run_differential.sh` | 指向 CKB-VM 测试目录 |

## 验收标准

- `make diff-test` 跑通 rv64ui/rv64um/rv64uc 测试集
- CKB-VM 自身能通过的测试在差分模式下也通过
- 所有差异有记录和根因分析
