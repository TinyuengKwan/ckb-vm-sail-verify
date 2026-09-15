# Week 4 — 双侧 Lean 4 生成与 Rocq/Coq Go/No-Go

## 实施状态补充

Week4 当时把生产重构路线改为直接提取生产调用图：`crates/proof-extract`
用共享的 `InjectedMachine` 调用生产 `instructions::execute`；该周终态尚未修改
`deps/ckb-vm`，也没有一份旧/新 ADD 语义实现需要做迁移差分。Week5 随后为可提取
`DefaultMachine` 的动态字段引入并采纳了
[runtime-container 补丁](../../proof/lean/extraction/ADOPTION.md)，所以“未修改 CKB-VM”只描述
Week4 历史终态，不是当前源码基线。现有入口测试覆盖 ADD、x0 和压缩指令 PC 增量；
它们不构成 decoder 或生产委托的形式化证明。

Rust/Sail 两侧 Lean 定义已有分别编译成功记录，Rocq 双侧尝试及 NO-GO 报告已存在。
共同 Lean 4.31.0 工程及 `make proof-imports` 已实现，兼容补丁和实测结论见
[兼容性报告](../../proof/lean/compat/README.md)。寄存器总数与 RA 已补齐生成定义和值检查。
GPR/PC 状态桥接及条件性 ADD 一步定理已完成，双方 dispatch 与 PC 更新已连接。
Week4 结束时生产 wrapper 方法仍有 opaque 缺口；后续容器化源码、重新提取及
[两个合同实例](../../proof/lean/theorems/WrapperContracts.lean)已经把五个寄存器/PC 委托
从最终定理公理集中移除。`MachineRuntime`、`Pause` 等类型和未选生产分支仍属于明确
TCB。详见 [ADD 审计](../../proof/lean/reports/ADD_AUDIT.md)。
以下任务和 exit gate 保留其验收目标，不因这些阶段性证据而视为全部完成。

## 任务

- 在 CKB-VM 上游友好的模块边界提取纯语义函数。
- 生产 Rust interpreter 调用这些函数，而非复制逻辑。
- 为 decoder→`DecodedInstruction`、effect→machine update 建 adapter。
- 增加旧路径/新路径 differential regression（迁移期间）。
- 记录 API 改动是否需要上游 PR。
- 通过 Charon/Aeneas 生成 Rust 侧 Lean 4 定义。
- 通过 Sail Lean backend 生成 Sail 侧 Lean 4 定义。
- 对同一 ADD 内核执行 Rocq 双侧生成、导入和状态桥接 spike。
- 保存 Rocq GO/NO-GO、最小复现与可信假设。

## 范围

只要求生产连接和生成 ADD；不在本周扩展到 memory、syscall 或更多定理。

## Exit gate

- 被证明函数在生产调用图可定位。
- adapter 测试覆盖 x0、PC advance 和 compressed size。
- 重新生成 Aeneas 输出不需要编辑生成文件。
- Sail Lean 生成物可由固定配置重建。
- Rocq spike 明确输出 GO 或 NO-GO；NO-GO 不替代 Lean 主线。
