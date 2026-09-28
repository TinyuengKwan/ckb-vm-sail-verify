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
- 提供可仅依据文档复现的完整交付材料；第三方复现交由 CKB 官方接收后开展，
  不作为本次星火计划交付的前置条件，也不要求交付前指定复现者或登记其公钥。
  未取得实际结果前必须标注“交付后待 CKB 官方复现”，不得记为通过或官方认可。

## Release gate

- ADD、ADDI、BEQ 至少 10 个案例完成双端严格比较。
- 5 类 mutation 全部被检测。
- Lean 4 ADD 定理由 kernel 检查通过，且生产连接可审计。
- Rocq/Coq GO/NO-GO 有最小复现；只有 kernel 通过才计入额外证明。
- 零未说明 `sorry`/`Admitted`/`Axiom`，或上游生成假设进入审计 allowlist。
- release 包含版本、哈希、覆盖、非目标和重放 artifact。
- 文档不包含超出证据的“CKB-VM 已形式化验证”声明。

未满足的项目按限制发布，不修改验收定义来制造完成状态。load/store、MOP、A、ECALL、cycle、VERSION0/1 与 ASM/JIT 保持 post-MVP/unsupported。

## 2026-09-28 所有者明确调整的交付范围

原条款“让第三方仅依据文档完成一次复现”移至交付后的接收方验证。
这是所有者针对面向 CKB 的星火计划交付所作的范围调整，不是第三方执行证据，
也不表示 CKB 官方已承诺、开始或完成复现。clean-room、CI 外部下载重放、源码/输出审批、
签名及不可变发布、证明边界等其余要求不变。

聚合器保留十二个证据槽，第三方为空时显示 `deferred_to_recipient`；其余十一项全部验收后，
仅可在 `acceptance_scope=ckb-spark-delivery-v1` 下关闭本次 Week6 交付。
`outstanding` 仍列出尚未验证的证据（含第三方），`delivery_outstanding` 只列交付阻塞项，
`post_delivery` 单列交付后事项，`third_party_reproduced=false` 保持真实边界。
若以后提供第三方报告，仍须严格验收，不能把无效报告当作延期而忽略。
