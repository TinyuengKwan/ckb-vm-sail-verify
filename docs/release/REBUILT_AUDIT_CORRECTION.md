# v2 门禁失败定位与精确审计迁移修正

2026-09-13。首次 v2 全门禁 **失败**，不是 PASS。两处已证等价的模型定义指纹
漏迁移，另发现主政策的公开入口引用仍指向 v1。现已完成精确修正，另一次全门禁于
**02:03:45 UTC 退出 0 并独立验收通过**，详见[完整验收](REBUILT_GATE_ACCEPTANCE.md)。
**Week6 未关闭。** 本项未采纳主 Sail/基础翻译器的新二进制。

## 保留的实际失败

首次 `make proof-check BACKEND=lean` 于 **00:14:51–01:02:50 UTC** 执行，make 退出 2，
主检查器退出 1。主 kernel、定理审计、17 组 / 231 项测试通过；公开两个 Rust 根真实
提取/翻译通过，无项目缓存主构建 **1,865 jobs** 完成，各下层模块编译通过。
随后 raw ADD 精确审计拒绝 `definitions` 差异，公开余下阶段没有完成。

- [失败主报告归档](../../artifacts/boundary-check/before-rebuilt-audit-fix-6b2zn65c/proof-check-failed/report.json)：
  `81329bb66afc7d9cfd0cc76213aeefc8e4c73f66776e54f7e1356620b4855657`。
- [失败公开报告](../../artifacts/boundary-check/public-check-n_ykvm28/report.json)：
  `8324724c80bd4fc4129b315b8acce76b7e1d4a697c5066f5613ea68f6f095cfa`。
- 原完整 `artifacts/proof-check`（约 8.8 GB）已复制到上述归档目录，复制进程退出 0。
  归档包含缓存/链接，不是独立 clean-room；未将失败报告改成成功。
- 修改前源码快照及 payload 保存于 `before-rebuilt-audit-fix-6b2zn65c`，
  快照文件 SHA-256 为 `5c32629949c3183bd8e865fb2f4185694e60462cf22a31ebdee71de5d67611ff`，
  完整源码身份为 `b3958c7f1a32c20e01dcea488ad7a7b66d2f42a535e436d7733bdea807325ccb`。

## 定位：漏迁移的正是两处已证等价定义

本次 raw 审计的完整摘要与先前
[lower-map-kernel](../../artifacts/boundary-check/lower-map-kernel-0v7r0ook/raw-audit.json)
相同；定理类型、公理集合和其余定义均未变。只有以下两个 `Option.map` 定义不同于旧政策：

| 定义命名空间 | 旧定义指纹 | 本次及已证明模型的指纹 |
| --- | --- | --- |
| `RawDecodeFactory.core.option` | `616c5e923f2e7750a925f40491b062345b123c0bb71781cd780661a885c95e01` | `a74085a72240faa6c09145a9902e139a18a39c94d1491b5eea2a0b9ee698b8c3` |
| `decoder_shared_closure.core.option` | `d0afccb81aa4aad8c6de22c1183241ecc69f55a26011766029f4afb58348dd94` | `168e09602a0a048c47577d912bb4482b7ef357577b46982c1fb0ec5b150e5f3f` |

此前迁移仅更新整个模型的身份，却错误要求 raw `audit` 完全保持旧值；相关旧测试也
固化了这一错误要求。本次修正不是忽略 `definitions`，而是将这两项固定为已证明模型的
精确指纹。任何第三项定义、定理类型或公理变化仍被拒绝。

[已有四条等价定理](../../scripts/fixtures/lower-model-equivalence/LowerMapEquivalence.lean)
涵盖泛型输入和 `call_once` 的全部 `Result` 情形，含整体函数等式；
[固定类型导出器](../../scripts/fixtures/lower-model-equivalence/ExportLowerMapAudit.lean)
防止额外 `False` 前提冒充等价。审查重新绑定新定义与等价证明中的定义，核对归档命名空间
映射后的旧定义指纹，没有改写 Lean 模型、定理或允许任意归一化。

准入元数据明确增加两份原始审计身份：raw 审计
`2d400d57ef6fc84ef77d4ff32a88b82bd49051cfc2939ac63a32a261f67dda9d`；map 等价审计
`733245c1e5ae5ac8034de1fac53b65f33e36a9c543d9bab7816122275f8549f3`。
旧 `raw-policy.json` 保持字节不变，仍实际拒绝新模型；只有 v2 下层政策接受已审两项。

## 公开入口引用守卫

主政策的 `configuration.required_public_decoder_policy` 由
`proof/lean/decoder/public-policy.json` 修正为实际执行的
`proof/lean/decoder/public-rebuilt-policy.json`。新增守卫检查声明与执行入口一致，
缺失、v1 或其他政策路径均拒绝。隔离副本先以 14 项普通 / `-O` 测试验证了该修正，
其[报告](../../artifacts/boundary-check/policy-link-candidate-tNNvZ3wD/report.json)
明确记录旧引用被拒绝、修正引用被接受，未修改正式输入。

## 正式迁移与新运行

| 政策 | 当前 SHA-256 |
| --- | --- |
| main step | `ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f` |
| public rebuilt | `63dd6ab1965a50c208d5779b217718d0b349671566ba6de725037d28fb3f19e4` |
| raw rebuilt | `a67b275f94ba0797705eec57c31595a9da05f2c70e26c8f011e320a64c1e7b84` |

[迁移审查](../../artifacts/boundary-check/before-rebuilt-audit-fix-6b2zn65c/migration-review.json)
SHA-256 为 `e55e66bc903c3ee7e98cb26b549dd8364b43f749f28f15f0d10094309269f49e`。
精确核对主政策仅一个元数据字段与两个来源引用变化、公开政策仅五个来源和 raw 引用变化、
raw 政策仅两处指纹及两项审计关联变化；原生成模型、生产工具、主定理/合同、公理和计划不变。
这是只读迁移审查，不是新 kernel PASS。

decoder 102 项、公开检查 40 项、主编排 18 项、聚合器 32 项测试通过；decoder、公开及
聚合器也在 `-O` 下通过。新增五项守卫回归纳入原主测试组，主验收总数从 231 增至
**236**；仍为 **24 个主阶段 / 48 个公开阶段**，不减少任何阶段或负测。

新一轮 `make proof-check BACKEND=lean` 于 **01:15:28–02:03:45 UTC** 完整执行退出 0，
[成功归档及独立验收](REBUILT_GATE_ACCEPTANCE.md)明确绑定本次 24 / 48 阶段，而非旧 PASS。
政策变化使 v6 readiness 及其配套报告不再适用于当前身份，旧报告/录像保留历史状态。
runtime、Rust 测试、配对负测、trap 及演示的[新执行和独立验收](AUDIT_FIX_EVIDENCE_REFRESH.md)
已完成。Rocq 首次因并发输入漂移失败，在 Rust 生成结束后重跑并独立验收原 NO-GO。
[v7 清单](local-readiness-20260913-v7.json)保留当时 Lean 结果留空的历史状态；
[v8 清单](local-readiness-20260913-v8.json)现已连接本次成功 Lean 归档。
