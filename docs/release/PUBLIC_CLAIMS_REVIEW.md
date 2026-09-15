# 主要公开文档的核心结论复核

2026-09-13。已审查 README、Verification Guide、coverage、semantic gaps、Lean 门禁说明
及 Rocq spike 六份主要文档中的核心状态、覆盖和边界表述，并修正下列矛盾。
**这是有限范围的文档复核，不是最终 release 结论审计通过。**
没有把全部历史文档、工作树差异、下载发布页或第三方材料视为已审完；
`audit-release` 的 `public_claims` 条款仍缺失。

## 已修正的问题

1. Lean 门禁说明仍写“新正式完整执行尚待完成”。改为 06:26 UTC 完整执行、06:29 UTC
   独立验收完成；原 24/236 等记录明确保留历史身份。
2. coverage 将 2026-09-12 的 22/206/47 称为最新。改为历史记录，并指向当前正式
   `rebuilt-main-v1` 的 28 主阶段、287 测试、48 公开阶段和 68 公开定理。
3. Rocq 顶部仍称新正式运行待完成，且“没有任何类型检查通过的定义”过强。
   改为 11 阶段完整实跑及独立复核已完成；八阶段成功，三个指定拒绝。
   完整生成模型仍为 NO-GO，但支持文件和类型文件可以通过，不计额外证明覆盖。
4. CI 文档把触发配置写成普遍的实际执行事实，且把所有 push 都列为触发。
   改为 `main` push、PR、schedule、手动触发的声明，明确差分 job 依赖 fast 成功。
   上传/下载步骤的存在不代表本候选已运行到该步，也不代表全部案例已从下载包重放。
5. “架构复位态”的措辞可能被理解成一般平台 reset 保证。改为注入测试的约定初态；
   明确会话保护只检查首包 order/PC，不验证全部初始寄存器，也不证明 Lean 初态关系或
   平台 reset 可达性。
6. “上游从未测试某组合”不能由两份 workflow 配置推出。改为这些配置不证明指定组合
   已通过双侧验收；发布版问题限定到曾实际失败的组合，不扩大到所有 Sail 发行版。
7. Verification Guide 中按推进顺序保存的旧“尚未采纳/待完成”段落增加历史范围说明，
   避免与后文的新正式完成记录冲突。历史失败及原始机器报告不改写。

## 结论与证据对应

| 可使用的结论 | 直接依据 | 必须同时保留的限制 |
| --- | --- | --- |
| 生产来源为 upstream＋受审 runtime-container 补丁 | [源码基线](../../proof/lean/extraction/ckb-source-baseline.json)、[采纳记录](../../proof/lean/extraction/ADOPTION.md) | 不是原始未修改 CKB-VM commit，也不是一般重构等价证明 |
| 32 案例、395 提交步严格比较 | [原始 runtime 报告](../../artifacts/boundary-check/formal-native-gWE5WMRA/runtime/corpus-mutations.stdout)及逐案例 artifact；ADD 13/209、ADDI 10/69、BEQ 9/117 | 仅固定输入/配置；不是所有指令语义或取指测试 |
| 六类 mutation，188 项适用、4 项不适用 | 同一 runtime 的矩阵及逐案例实际 trace，重新按独立比较逻辑校验 | 不适用项不计为检测成功；不存在由数量推出的形式化证明 |
| 当前正式条件性 ADD 门禁通过，28/287/48/68 | [固定正式归档](../../artifacts/boundary-check/formal-main-acceptance-hnOBopcM/main/report.json)、[原独立验收](../../artifacts/boundary-check/formal-main-acceptance-hnOBopcM/report.json) | `assurance=conditional`、`coverage=runtime-only`、`release_audit=false` |
| 内部根 137、公开根 158 项传递依赖受审 | [主政策](../../proof/lean/audit/step-policy.json)、正式归档的 Lean 导出及公开子报告 | 有明确 TCB，不是“零公理”；库中存在 `sorry` 不等于最终根含 `sorryAx`，也不能以导入成功代替传递审计 |
| 指定配置下同原始 ADD 字连接两侧解码和 GPR/PC 效果 | [实际公开定理](../../proof/lean/decoder/toolchain/full-entry/OuterPublicStep.lean)及对应正式 kernel 记录 | VERSION2、IMC+B、MOP off、冷 decoder；`WordFetch`、大小/边界、状态关系、Sail 前缀/退休等前提仍在 |
| Sail 联合前提有模型内见证 | [具体见证及说明](../../proof/lean/reports/ADD_NONVACUITY.md) | 双侧实例仍接收 Rust seed；不推出一般 `Nonempty Machine` 或 reset 可达性 |
| Rocq 11 阶段复现 NO-GO | [新正式 Rocq 报告](../../artifacts/rocq-spike/run-iu08clul/report.json)：三个指定拒绝、八个成功阶段 | 进程成功表示复现预期阻塞，不是两个完整模型通过或新增定理 |
| CI 源码含 runtime 上传/下载/单案例重放步骤 | [工作流源码](../../.github/workflows/ci.yml) | 源码不是远端执行证据；本轮没有再次查询远端，不将 05:12 UTC 的零运行观察当作永久现状 |
| 六项本地组件已有验收证据，Week6 仍未关闭 | [v10 实际聚合](../../artifacts/release-audit/run-37dt_nkr/report.json) | clean-room、worktree audit、CI 下载、release、第三方和最终公开结论六类仍缺失 |

## 本次证据复查

[复查报告](../../artifacts/boundary-check/public-claims-review-Jhid6mOw/report.json)记录六份修改后文档
的精确 SHA-256、证据引用、统计值及正式源码前后身份。
实际运行时间为 08:49:40–08:49:41 UTC，退出 0；报告 SHA-256：
`934891c51e8a6af29dd7491361cf92c929548cea31b5e0facf6757d9154e45ae`。
[执行代码](../../artifacts/boundary-check/public-claims-review-Jhid6mOw/check.py)由新的 Python `-O`
进程实际运行：重开 v10 引用的证据；核对 28 个主阶段日志、21 组测试的 287 项计数，
核对公开子报告及依赖数；重新验证 32 个原始 runtime artifact 和 mutation 矩阵，
重算三个指令族的提交步；核对 Rocq 和聚合的实际状态。
这不是重新执行 Lean kernel、runtime、远端 CI 或全部组件验收器。

已检查这些文档的 136 个本地链接存在性和已知过期句子是否消除；这种检查不证明所有自然语言
结论语义正确或审计完备。人工对照的范围和未关闭部分以上表为准。
正式 v10 审计所覆盖的源码及其六份组件引用未变，原机读报告、v10 清单与原计划未改。
修改后的文档不属于早先 `810b71aa…` 冻结源码归档；发布前须冻结新的文档身份并审查差异，
不能将旧归档中保留的过期文字无声当作已更新。

最终还须逐项覆盖拟发布的全部保证性结论、实际版本/包/下载入口和完整 TCB；
建立能拒绝缺项或来源变化的 release 级结论检查，并在真实候选上运行。
本次有限复核不能替代这些步骤，也不能以“修正了几处过期文档”制造 Week6 PASS。
