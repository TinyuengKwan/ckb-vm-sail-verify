# Week 5 — 生产关联的 Lean 4 ADD 精化

## 目标

完成一条真实的 Lean 4 ADD 定理，直接引用生产关联的 Rust 生成物与 Sail 生成物。

## 当前进展

2026-09-07：已采用正式源码基线 `ckb-vm-1ffba3977da9-runtime-container-v1`
（上游 commit + 固定补丁），落实完整源码身份校验和提取配置，见
[采用决议与审计清单](../../proof/lean/extraction/ADOPTION.md)。两个 wrapper 合同和
免委托参数的最终定理已在隔离模型证明；正式生成物与该模型相同，但正式合同、
axiom guards 与 policy 尚未迁移。因此当前 `proof-check` 明确拒绝新基线，不能沿用旧 PASS。
下一步是迁移合同/最终定理、复核 141→137 的精确依赖变化并重跑正式门禁；
解码对应、Sail 初态合同及 clean-room/release 验收仍未完成。

以下记录是原始未修改源码和旧 policy 的已完成工作：

`make proof-step` 已检查 `AddStep.decoded_add_step`，直接连接生成的
`execute_production` 与 Sail `try_step`，覆盖 GPR、dispatch、PC/next-PC 和正常退休。
这是明确 wrapper 委托、对应解码结果及 Sail 前缀/frame 合同下的结论；具体合同实例
和干净发布验收仍未完成。范围、固定配置与 141 项公理依赖见
[一步证明报告](../../proof/lean/reports/ADD_STEP.md)。
`make proof-check BACKEND=lean` 已接入重新生成、源码/工具身份核验、最终定理
141 项公理及显式前提审计、回归与负向测试，输出 `conditional` 报告。
它不替代本页要求的干净发布验收，也不证明具体合同实例，见
[门禁边界](../../proof/lean/reports/PROOF_CHECK.md)。

## 证明内容

- operand read 对应。
- wrapping/sign extension 对应。
- rd 写回与 x0 对应。
- PC 更新对应。
- 其他寄存器保持。

## 差分内容

- runtime corpus 覆盖寄存器别名、rd=x0 与 wrapping 边界。
- ADD 至少一个负面 mutation 能被 runtime diff 捕获。

## Exit gate

Lean 4 kernel 从干净构建检查 ADD 定理通过，无未说明 `sorry`/`axiom`；覆盖矩阵链接到定理名、生产 Rust 函数和 Sail 函数。Rocq 只有在 kernel 检查通过时才计入额外证明覆盖。
