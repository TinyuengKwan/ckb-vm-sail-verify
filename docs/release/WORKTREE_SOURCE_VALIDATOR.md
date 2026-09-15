# 工作树审计：源码部分验收器

2026-09-13。[源码验收器](../../scripts/release_worktree_source.py)已接入
[`audit-release`](../../scripts/audit_release.py) 的 `PARTIAL_CHECKERS`。
后续新增的[组合入口](WORKTREE_GENERATION_VALIDATOR.md)保留本 schema 兼容性，并可另外
校验历史生成差异记录；它不削减本源码组件的完整清单要求。
这是完整工作树审计的一项实现，不是将其关闭条件缩减为文件哈希检查。
**完整 `worktree_audit` 仍未关闭；未批准真实 release 候选的最终交付范围。**

## 实际检查范围

验收器不采用报告自选的文件子集，而是重新调用 `source_snapshot.capture()`，
核对主仓库、CKB-VM、Sail-RISC-V 的完整 tracked / unignored 源码清单、HEAD、
子模块 gitlink、已采纳 CKB 补丁及文件字节/可执行位。拒绝额外或遗漏的仓库、
源码文件和相对 HEAD 的差异审查项。删除、模式变化、未跟踪新文件也不能漏审。

每个差异审查项必须绑定对应变更对象的 canonical JSON SHA-256，并填写分类、
审查说明、审查者记录及至少一个有哈希的支持文件。支持文件路径禁止越界和 symlink；
遍历后重新检查报告、全部引用和完整源码快照，拒绝检查期间的漂移。
候选标签必须与聚合清单相同。不会执行审查记录里的命令，不改 Git index 或源码。

这些检查证明的是**源码身份、清单完整性与审查记录的绑定**，不证明说明内容正确、
审查者身份真实或已获用户批准。分类为 `historical` 也不意味着可以自动排除该文件；
它仍属于完整源码清单，必须有审查记录。

## 输入约定

聚合清单的 `evidence.worktree_audit` 使用既有 `{path, sha256}` 引用格式。
被引用 JSON 必须恰好包含：

- `schema_version: 1`、`kind: "worktree-source-review-v1"`、`candidate`。
- `snapshot`：仓库根相对路径及文件 SHA-256，指向完整 `source_snapshot.capture()` 输出。
  这里的文件 SHA-256 与输出内的 `snapshot_sha256` 是两种不同身份，不可互换。
- `reviews`：恰好三个仓库键 `.`、`deps/ckb-vm`、`deps/sail-riscv`；每个仓库的键集合
  必须等于其 `changes_from_head`。每项恰好含 `change_sha256`、`category`、`rationale`、
  `reviewed_by`、`evidence`。分类限 `production/proof/test/build/documentation/historical/mixed`。
- `boundaries`：`release_claimed`、`week6_closed`、`generated_outputs_audited`、
  `candidate_approval_claimed`、`semantic_correctness_proven` 五项均须为 JSON `false`，
  整数 `0` 不可替代。不得省略字段或添加 `approve` 等覆盖项。

快照与审查报告应保存到 Git 忽略的证据目录，避免将含自身哈希的报告塞入源码快照。
现有 [HEAD 差异复核](WORKTREE_DELTA_REVIEW.md)只是历史准备记录，不满足本 schema，
不能通过改名或替换哈希冒充逐项语义审查。历史 `v10` 的该 slot 继续保留 `null`。

## 聚合语义与尚缺的工作

- 没提供报告：`missing`。
- 提供报告但源码、候选或审查清单不合格：`invalid`，聚合退出 1。
- 源码部分验收通过：`incomplete`，仍列入 outstanding；无其他错误时聚合退出 2。

生成物不在源码快照中，必须另行建立完整输出范围、重建前后差异及来源对应；
最终交付范围和逐项语义审批也尚缺。即使源码部分通过，以上义务不能从旧 Lean PASS、
任意支持文件或审查者名字推出。后续须连接真实同候选的生成链与审批记录，
再实现完整工作树验收；不能把 `PARTIAL_CHECKERS` 简单移入通过表。

后续已新增[生成物节点清单与差异计算](GENERATED_OUTPUT_INVENTORY.md)。该入口不跳过
所选树内的缓存/备份，支持追加独立运行目录；后续正式生成记录、差异说明和
[执行连接](WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)已有各自验收，
仍不自动补齐当前完整源码组件。新增代码及文档另属后续源码身份，下面测试报告
仍保留当时的快照，不视为当前完整工作树的新验收。

## 本轮完整源码来源记录

本节保留旧锚点；以下是 2026-09-14 首轮的历史快照，而非后续增量实现后的当前源码。
该轮审查范围为全部 1,818 个源码文件和 275 项 HEAD 差异（主仓库 273、CKB-VM 2、
Sail 无差异），不只取 policy 的子集。后续新增增量验收器及本页修改后，这份快照
不再代表当前源码；旧记录不改写。
精确身份、命令退出和是否通过，以[机器执行报告](../../artifacts/boundary-check/current-source-review-nkkGsErz/report.json)
及[原聚合输出](../../artifacts/boundary-check/current-source-review-nkkGsErz/audit/report.json)为准；
本节本身不是通过声明。

逐路径来源审查分为三类：与完整正式链冻结源码逐字/模式相同；与后续执行连接验证
冻结源码相同；明确列出的后续状态文档更新。每项都绑定当前 HEAD change 摘要、类别、
具体来源及有哈希的支持记录。旧快照中存在一个文件，不表示那个文件被编译、运行，
或已证明其全部语义；源码清单与测试覆盖必须区分。

CKB 的两个变化仍由已采纳补丁及源码基线守卫约束，不称为干净上游 commit。
历史 probe、OPAM export、旧 readiness JSON 仍列入当前源码清单，不能以“历史材料”
省略；保留它们不等于批准打包或证明全部辅助入口。
后续文档包括 current policy/历史 policy 的区分和最新执行连接说明；不改写旧报告。

[逐项来源审查记录](../../artifacts/boundary-check/current-source-review-nkkGsErz/source-review.json)
使用现有 schema，`reviewed_by` 明示为 Codex 的字节/来源审查，不是独立第三方认证。
所有语义正确性、最终候选批准及发布声明均为 false。完整来源绑定即使通过，也不表示
275 项改动的全部语义已经获批，更不改变原 Week6 的 clean-room/发布要求。
完整审查器必须重新计算当前快照、拒绝遗漏/额外条目，并在结束时再次核对全部来源。

该轮源码组件的实际验收状态由上述报告记录，不回写 v10 或此前的生成组件专用报告。

## 正式生成后源码增量与 v2 组合入口

2026-09-14 新增[增量验收器](../../scripts/release_source_increment_review.py)。
它比较正式生成时与当前的两份**完整文件清单**，不是两份 `changes_from_head` 的交集。
新增、删除、内容变化、仅模式变化以及恢复为 HEAD 原值的回退都必须完整列出。
两端 Git HEAD、子模块 gitlink 和已采纳 CKB 基线不得改变。

增量报告恰含 `schema_version: 1`、`kind: "worktree-source-increment-review-v1"`、
`candidate`、`before`、`after`、`changes`、`reviews`、`boundaries`。
两端引用使用仓库根相对路径及文件 SHA；快照的内部摘要则必须分别等于已经验收的
生成组件与当前源码组件给出的身份。`after` 还须在检查前后等于实际完整源码。
每个 change 含 `operation/before/after`；逐仓库 reviews 的成员必须恰等于完整差异，
审查行使用上文相同六字段，并绑定这个增量对象的摘要，而非 HEAD 差异摘要。
五项源码边界加 `fresh_execution_claimed`、`historical_generation_source_replaced`、
`current_outputs_verified` 必须全部为 JSON `false`。

组合报告使用 `schema_version: 2`、`kind: "worktree-record-review-v2"`，在 v1 的
所有字段之外必须提供 `source_increment`（可为 `null`）。非空时，两端组件缺一不可。
v1 继续兼容，且不能偷带 v2 字段。增量验证成功只移除
`post_generation_source_delta_review`，不会把不同源码标成 `source_snapshots_match: true`，
也不会重写历史执行来源、补做 kernel 或证明增量说明的全部语义。

`schema_version: 3` / `kind: "worktree-record-review-v3"` 继续保留 v2 的
`source_increment`，并增加可为 `null` 的 `output_identity`。非空输出组件须通过
[当前输出身份复核](CURRENT_OUTPUT_REVIEW.md)，且其最终 24 根重扫必须绑定已验证的当前
完整源码快照；否则拒绝，不能用旧观察或不同源码下的相同文件冒充当前身份。成功只移除
`current_generated_output_identity`。`current_outputs_verified` 仍保持 `false`，因为记录
身份与非语义分类不等于生成物语义或最终交付审批。v1/v2 不能夹带 v3 字段。

本轮计划刷新全部 1,820 个源码文件、277 项 HEAD 差异的来源记录，复用旧记录时要求
对应 HEAD change 的字节/模式/基线身份完全一致；新增或变化项另行说明。
历史生成到当前的增量单独重新计算并逐路径绑定说明。实际数量、冻结身份、测试和
聚合结果以[本轮机器报告](../../artifacts/boundary-check/source-increment-final-kqqBU9l9/report.json)、
[增量报告](../../artifacts/boundary-check/source-increment-final-kqqBU9l9/source-increment.json)及
[原聚合输出](../../artifacts/boundary-check/source-increment-final-kqqBU9l9/audit/report.json)为准，
本段预先记录范围，不预宣告执行通过。

[首轮失败记录](../../artifacts/boundary-check/source-increment-review-lGItyVUB/report.json)保留：
复制记录脚本时替换测试数误改了历史报告 SHA 中的数字串，启动身份检查即拒绝，
`stages` 为空，未执行测试或聚合。第二轮在新目录修正精确哈希，不重写失败报告或
历史正式证据。两轮之间仅更新本页的记录链接与失败说明，源码快照须重新冻结。
[第二轮记录](../../artifacts/boundary-check/source-increment-review-v2-5nINXNeP/report.json)中，
普通模式 230 项通过；发现标题变更会使状态页旧锚点失效，主动终止优化模式测试
（退出 -15），未进入来源审查和聚合。第三轮恢复旧标题锚点后重新冻结，前两轮均
保留原退出结果；前次普通模式通过不替代第三轮完整双模式回归。

新验收器的[测试](../../scripts/tests/test_release_source_increment_review.py)包含完整差异、
回退/模式变化、遗漏/额外审查、端点混用、引用漂移及真实增量检查连接组合入口。
快照捕获与已有端点组件在单元测试中使用 fixture，不能当作真实仓库执行证据。
源码/增量记录均是完整性与来源绑定，不认证审查人或替代最终语义审批。
即使真实聚合接受本组件，`worktree_audit` 仍为 `incomplete`；当前完整生成物身份和
最终交付范围/语义审批继续保留，clean-room、第三方与发布条款也不因此关闭。

## 验证和证据身份

[25 项源码组件测试](../../scripts/tests/test_release_worktree_source.py)使用真实临时 Git
仓库，覆盖完整增删/模式/子模块差异、候选混用、越界与 symlink、遗漏审查、伪造或
漂移的快照/支持文件、保证升级，以及通过真实聚合分支仍然 incomplete。
测试记录中的审查者与候选均为 synthetic fixture，不是本项目审批。
另有聚合器和源码快照回归；本轮执行结果以
[测试报告](../../artifacts/boundary-check/worktree-source-validator-hun1jgn8/report.json)为准。

本次修改了聚合器、其测试及来源清单。v10 历史运行及旧源码复核报告保持原字节，
**它们的完整审计器来源快照不再等于当前源码**；不是本轮新聚合 PASS。
原主证明政策、定理、生成模型和原始计划不因本实现而改变。
本轮测试不替代重跑证明、clean-room、CI 下载、独立第三方或发布验收。
