# 当前候选公开结论全量复核

本轮以完整项目源码清单中的全部 Markdown 为封闭范围，而不是只抽查 README、coverage
等六份主要文档。机器清单逐份固定文档哈希、含保证性关键词的段落摘要、文档类别、
结论类别和本地链接；当前证据检查器重新打开 runtime、Rust tests、Lean、Rocq、
mismatch、演示、工作树及聚合报告。

这项复核关闭的是 `public_claims` 证据槽，不是整个 release：它不查询远端，不重新执行
kernel/runtime，不代替 clean-room、CI 下载、版本包、最终交付范围批准或独立第三方。
审查者明确记录为 Codex，`independent_third_party=false`。

## 文档范围规则

- `current_assurance`：README、Verification Guide、当前状态、coverage、semantic gaps、
  当前证明/工具入口；必须映射到一个或多个当前证据类别。
- `technical_boundary`：架构、方法、格式及局部证明说明；技术结论必须保留适用范围。
- `normative_plan`：Week1–6 和总计划只定义要求，不能作为已经执行的证据。
- `historical_record`：带具体时间/候选身份的阶段报告按原身份保留；后续结果不回写，
  也不能用旧 PASS 支持当前政策。
- `format_or_navigation`：只说明目录、格式或导航，不承担执行完成结论。

完整集合由当前 `source_snapshot` 动态枚举；新增、删除或修改任一 Markdown 都会使已封存
报告失效。构建/生成目录和子模块自己的上游文档不被混入“本项目公开结论”集合；三仓源码
身份仍由独立工作树记录覆盖。

## 当前可公开使用的结论

1. 当前 native 证据为 33 个注入案例（ADD/ADDI/BEQ = 13/10/10）、398 个提交步、
   194 个适用 mutation、33 次复制重放；仅覆盖固定输入/配置和已观察字段。
2. 当前 Rust 默认 workspace 验收为 78 项，其中 10 项真实双引擎测试；不是所有 Rust
   状态或 CKB-VM 路径的完备证明。
3. 当前 Lean 门禁为 28 主阶段、287 项检查、48 个公开阶段和 68 个公开定理；最终 ADD
   结论仍为 `conditional` / `runtime-only`，依赖和前提边界不因 kernel PASS 消失。
4. Rocq 为 11 阶段的具体 NO-GO：八阶段成功、三个指定模型/最小复现拒绝，
   `extra_proof_coverage=false`。
5. 三类语义负测和维护者演示均绑定当前 runtime/Rust 证据；有限最小化不证明一般根因。
6. 当前来源和 24 根输出身份已有完整记录；工作树仍等待最终交付范围及语义批准。
7. 当前聚合仍为 `incomplete`。在本项接入之前，缺少 clean-room、worktree、CI 下载、
   release package、第三方和 public claims；本项通过后也只能移除最后一项。

所有上述结论必须与 [coverage](../coverage.md)、[semantic gaps](../semantic-gaps.md)、
[当前 Week6 清单](../WEEK6_STATUS.md)和机器证据共同阅读，不能缩写为“CKB-VM 已形式化验证”。

## 本次修正的过期边界

- [Week4 计划记录](../plan/week4.md)现在把“未修改 `deps/ckb-vm`”限定为该周历史终态，
  并连接后来采纳的 runtime-container 补丁和 wrapper 合同实例。
- [架构文档](../architecture.md)不再声称 state relation 待实现、wrapper 委托未实例化或
  当前无需补丁；同时把首包 order/PC 明确为注入约定，而非平台 reset 证明。
- [Verification Guide](../../VERIFICATION.md)不再把旧 v10 称为当前清单，当前本地 v3
  入口与旧政策历史记录分开。
- [Sail 配置说明](../../sail-model/README.md)更新为当前 `8f91355e…` submodule 和正式
  `8eb1fb6b…` Sail 源码构建，旧 `27224ccb` 组合只保留历史失败身份。

## 机器验收

生产检查器为 [release_public_claims.py](../../scripts/release_public_claims.py)，负测为
[test_release_public_claims.py](../../scripts/tests/test_release_public_claims.py)。正式复核报告
保存在 [当前本地证据目录](../../artifacts/boundary-check/public-claims-final-v1-20260914/evidence-final-v2/report.json)；
报告、源码内 review manifest 及源码外 execution manifest 的具体 SHA-256 以聚合清单引用
为准。运行期证据引用不写回 review manifest，避免完整源码工作树报告递归包含自身哈希；
任一端变化仍会使最终 evidence report 失效。

检查器不把“所有链接存在”当成自然语言正确性的证明：每份文档还必须出现在显式 review
清单中并绑定保证性段落摘要和结论类别。反过来，人工 review 标记也不能替代机器证据；
八类当前组件会重新验收，任何来源、政策、文档、段落、链接或报告变化都会拒绝旧记录。

本页所指 `evidence-final-v2` 在 `43218a71…` 源码下实际通过，不回写其结论。
后续新增外部槽验收器和固定信任政策后，当前源码身份已改变；发布候选必须另建报告
重新验收全部文档和组件，不能以该历史 PASS 代替新身份。

## 2026-09-15 证据引用分类修正

新鲜 clone 不含被 Git 忽略的 `artifacts/`，而文档中有 344 个链接指向其中的本地记录；原验证器要求每个本地链接
目标存在，会让 clean-room 内的公开结论阶段必然失败。现在 `local_links` 按源码快照分类：快照内的目标必须存在；
指向 `artifacts/` 且不在快照内的链接只检查语法与不逃逸，计为 `evidence_links_not_shipped_with_source`；
其它本地链接仍必须存在。结果字段在宿主与 guest 中一致，因此聚合器对同一报告的复核不会因环境不同而失败。
这不是把证据引用当作已验证链接：未随源码交付的记录仍要靠发布包和独立第三方复现提供。
