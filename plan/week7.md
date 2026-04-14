# Week 7: Full Diff-Test Coverage & Semantic Gap Analysis

## Objectives

- Run differential tests against all CKB-VM supported extensions (I, M, C, B, A)
- Document every semantic gap between CKB-VM and standard RISC-V
- Produce the instruction mapping document as a deliverable

## Tasks

1. **Expand diff-test to M, C, B, A extension tests**
   - Add rv64um (multiply/divide) test ELFs
   - Add rv64uc (compressed) test ELFs
   - Add B-extension arch-test ELFs
   - Add rv64ua (atomic) test ELFs

2. **Document semantic differences**
   - CKB-VM VERSION0/1/2 behavioral diffs (load boundary check bug)
   - x0 enforcement timing (per-instruction vs on-read)
   - FENCE/FENCE.I as no-ops
   - Simplified atomic reservation (single address)
   - Memory: no MMU, flat 4MB, W^X

3. **Complete instruction mapping document**
   - Full table: all 158 CKB-VM opcodes → Sail function name (or "CKB-VM only")
   - Annotate which are proved, which are diff-tested, which are neither

4. **Test edge cases**
   - Division by zero behavior
   - Maximum shift amounts
   - Memory boundary access
   - Misaligned access handling

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Modify | `doc/instruction_mapping.md` | Complete mapping table with verification status |
| Add | `doc/semantic_gaps.md` | CKB-VM vs standard RISC-V differences |
| Modify | `crates/diff-test/src/main.rs` | Extension-specific test filtering |
| Modify | `scripts/run_differential.sh` | Support per-extension test runs |

## Verification Criteria

- [ ] Diff-test covers I, M, C, B, A extensions
- [ ] All tests pass or divergences are documented with cause
- [ ] `doc/instruction_mapping.md` covers all 158 opcodes
- [ ] `doc/semantic_gaps.md` complete

---

# 第七周：全面差分测试与语义差异分析

## 目标

- 对 CKB-VM 支持的所有扩展（I, M, C, B, A）运行差分测试
- 记录 CKB-VM 与标准 RISC-V 的每一处语义差异
- 完成指令映射文档（交付物）

## 任务

1. 将差分测试扩展到 M/C/B/A 扩展的测试 ELF
2. 记录语义差异：版本行为差异、x0 处理方式、FENCE 处理、原子操作简化、内存模型差异
3. 完成 158 个 opcode 的完整映射表，标注验证状态（已证明 / 已差分测试 / 未覆盖）
4. 测试边界情况：除零、最大移位量、内存边界访问、非对齐访问

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 修改 | `doc/instruction_mapping.md` | 完成全量映射表 |
| 新增 | `doc/semantic_gaps.md` | CKB-VM vs 标准 RISC-V 差异文档 |
| 修改 | `crates/diff-test/src/main.rs` | 按扩展过滤测试 |

## 验收标准

- 差分测试覆盖 I/M/C/B/A 全部扩展
- 所有差异有文档记录
- 158 个 opcode 映射表完成
