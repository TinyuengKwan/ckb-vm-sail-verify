# Week 4 — 双侧 Lean 4 生成与 Rocq/Coq Go/No-Go

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
