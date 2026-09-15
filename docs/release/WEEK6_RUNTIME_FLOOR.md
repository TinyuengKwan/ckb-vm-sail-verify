# Week6 逐指令族案例门槛修正

2026-09-13。复核原始 `docs/plan/week6.md` 发现此前 32 案例的分布为
ADD 13 / ADDI 10 / BEQ 9，**不满足三类各至少 10 个案例**。
旧报告的严格比较和 mutation 结果仍是历史证据，但此前验收器仅检查总数至少 10
及三类均出现，不能据此关闭 Week6 的逐族案例门槛。原始验收要求没有改变。

## 实现

在原 corpus 末尾新增 `beq-self-target`，保留全部旧案例、随机算法和默认 seed：
先用 `ADDI x31, x0, 5` 建立操作数，再注入 `BEQ x31, x31, 0` 和 `ADDI x3, x0, 1`。
目标是核对零位移 taken 分支的 PC，以及随后在同一 PC 注入的指令效果；
不是内存取指循环或一般平台执行证明。当前 corpus 因此为 33 项（13 / 10 / 10）。

Rust 原有 corpus 单元测试改为每族至少 10；发布 runtime 验收器独立从逐案 artifact
统计每族数量，拒绝总数虽为 30、某族只有 9 的记录。Python 合成样本扩为每族 10，
新增回归逐一测试 ADD、ADDI、BEQ 不足，合成记录不当作执行证据。

## 来源迁移

变更前完整源码快照及四份待修改文件已保存到
[审查目录](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/)。生成后原有源码增量
精确为 12 个主仓库路径：7 份文档、3 个审计 helper、2 个测试；两侧依赖仓库无变化。
这批记录不等于最终候选交付审批。

本次正式主政策仅更新 `local_sources["crates/diff-test/src/corpus.rs"]`：
`8781dee01230e2f781cb26f15ca69d81083263a9ade8c6f66e755b9a92a3ed3a`
→ `0a2f89d2a03e391201c0304594adf60397f6cc54c7e7e0fde599e529321c5551`。
其余 93 项正式本地来源和全部定理、合同、前提、公理清单、模型预期身份、配置、工具与
CKB upstream-plus-patch 基线不变。政策 SHA-256 从 `7ced9f42…` 变为
`b5bdc4017628cb065f273a278c7d7458bb6d93b4572eaca0e4788e519e6ab2c3`。

旧生成 Rust provenance 绑定旧政策，必须通过新正式生成重新建立来源；旧 Lean/Rocq
报告不能冒充新政策的通过记录。本次优先实测 runtime/Rust，明确不声明重生成或 kernel
已经完成。旧 v10、原生成记录和前轮审计报告保留原字节及旧身份。

## 执行状态

20:10:17–20:13:19 UTC 的[完整运行及独立验收](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/report.json)
退出 0，报告 SHA-256：`6b3de2e180cb7121c537e1ddea04d5d511fab6233cf12446affe465fa4f5a49c`。
锁定工具安装与完整源码首尾核对一致；使用初始不存在的 Cargo home 和两个独立新 target。

- [runtime 报告](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/runtime/report.json)：
  33 案例 / 398 步严格比较，ADD 13/209、ADDI 10/69、BEQ 10/120；33 个复制输入全部重放。
  SHA-256：`9dd5ad2edd901c5edbcc41366e309860840d3bd45b4208c811d9b8af45f5f269`。
- 完整 198 项 mutation 矩阵中，194 项适用且全部定位正确，4 项无寄存器写入而不适用；
  PC、trap、长度、终止各 33 项，寄存器索引和值各 31 项。不适用项不计通过。
- [Rust 报告](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/rust-tests/report.json)：
  7 个二进制 / 78 项测试全部执行，含 10 项真实引擎测试；ignored、filtered-out 均为 0。
  5 个 doctest 目标全部执行、共 0 项 doctest，不把目标数当作证明或测试数。
  SHA-256：`650e32f4403b70e914f9aff2ce0fe8bafaf6f76bd598684be409b42dbffbf88b`。
- 新 BEQ 在两侧均从 `0x80000004` 跳到自身；随后注入指令在该 PC 写入 `x3 = 1`，
  三个事件逐字段一致。完整旧 corpus 也重跑，没有只验证新增案例。
- 22 项 runtime 检查器测试双模式通过，共 44 次完成；真实旧 13/10/9 artifact 被新门禁
  以单类数量不足准确拒绝。

[独立边界复核](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/boundary-report.json)
确认旧提取 provenance 和 v10 清单因旧政策被拒绝；18 项原 proof-check 守卫双模式通过，
共 36 次完成。该报告 SHA-256 为 `6ed897cb4487ac7e97b6f28689e494945633132cde79bc2922dc1e214fd756f7`。
这些守卫测试不替代 kernel。现已满足本地逐族案例数量和严格比较要求；继续复用有哈希
记录的已建 Sail emulator，不宣称 fresh Sail 构建或 clean-room。

20:15:02–20:15:54 UTC 的[新清单实际聚合](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/native-audit/report.json)
完成：runtime 和 Rust tests 为 `verified_existing_evidence`，其余十项明确 `missing`，
整体 `incomplete`、退出 2。报告 SHA-256 为
`26d14ef05924b0aab4792f381dad205a73d95540bb815c1c7ba1782d82964066`；
[清单](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/native-manifest.json)
SHA-256 为 `ecf98504bff151fee42218f0668c2b829da813b7f5c8e955b7e9b13754fc1877`。

本节在执行结束后追加，完整源码快照保留执行时身份，不回填报告。新清单只接入
本次 runtime/Rust 组件；上述 20:15 UTC 聚合时，新正式生成、Lean/Rocq、配套 mismatch/demo
和发布义务均明确缺项，不把历史生成审查或旧证明报告归到新政策。

后续[新政策正式链](FORMAL_FINAL_EXECUTION.md)已于 22:21:00 UTC 完成生成、Lean/Rocq
及独立验收，保留新的原始报告和完整差异。本文 native 报告在重生成后也通过只读复验。
[配套 mismatch/demo 与新六项聚合](FINAL_SUPPORT_REFRESH.md)随后完成。
[正式输出 delta 的逐路径说明](FORMAL_DELTA_REVIEW.md)已复验；后续增量、最终交付范围和
发布义务仍未关闭；原 native-only 专用聚合报告不回写为六项通过。
