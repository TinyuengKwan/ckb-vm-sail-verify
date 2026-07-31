# Week 6 — Clean-room、报告与发布

## 任务

- 完成 `VERIFICATION.md`，区分当前可运行基线与本轮新增验收命令。
- 固化环境检查、smoke、mutation、Lean proof 和 Rocq spike 入口。
- 更新 coverage matrix、semantic gaps、可信计算基和保证边界。
- 为每个 mismatch 保存分类、最小输入和重放命令。
- 发布版本、配置哈希、CI 日志与下载 artifact。
- 录制面向 CKB-VM 维护者的简短演示。
- 检查所有公开结论均能追溯到证据。

## Clean-room 验证

- 递归 clone 与固定 submodule commit。
- 安装锁定 Rust、Sail、Aeneas/Charon、Lean 4 和 Rocq/OPAM spike。
- 重建合并配置与双方生成物。
- 运行 Rust tests、runtime differential、mutation、Lean proof 与 Rocq spike。
- 检查生成后 worktree clean 或差异已被明确审计。
- 让第三方仅依据文档完成一次复现。

## Release gate

- ADD、ADDI、BEQ 至少 10 个案例完成双端严格比较。
- 5 类 mutation 全部被检测。
- Lean 4 ADD 定理由 kernel 检查通过，且生产连接可审计。
- Rocq/Coq GO/NO-GO 有最小复现；只有 kernel 通过才计入额外证明。
- 零未说明 `sorry`/`Admitted`/`Axiom`，或上游生成假设进入审计 allowlist。
- release 包含版本、哈希、覆盖、非目标和重放 artifact。
- 文档不包含超出证据的“CKB-VM 已形式化验证”声明。

未满足的项目按限制发布，不修改验收定义来制造完成状态。load/store、MOP、A、ECALL、cycle、VERSION0/1 与 ASM/JIT 保持 post-MVP/unsupported。
