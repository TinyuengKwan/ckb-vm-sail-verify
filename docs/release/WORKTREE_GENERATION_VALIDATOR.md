# 工作树审计：历史生成差异记录的接入

2026-09-13。[生成记录校验器](../../scripts/release_generation_review.py)与
[组合入口](../../scripts/release_worktree_evidence.py)已接入 `audit_release.PARTIAL_CHECKERS`。
旧 `worktree-source-review-v1` 输入保持兼容；新输入可以同时携带源码审查和生成审查，
也可以明确留空其中一项。**任何组合都不能关闭 `worktree_audit` 或 Week6。**

## 旧生成格式的校验范围

- 生成报告必须属于固定记录 schema，四个生成阶段、两个采集阶段和 35 个引用文件
  不可省略或增加。核对原命令/工作目录、启动/进程/完成事件、退出码、日志哈希和时间顺序。
  目前仅支持记录中明确的 `/usr/bin/python3` 路径，不接受报告自选执行器或任意命令。
- 重新验证生成前后的节点清单，要求九个必需根及该入口的运行目录；依据前后父目录
  清单重算新 Rust 暂存根的初始缺席，不能凭空给已有目录补一个空基线。
- 从完整观察重新计算 delta，精确覆盖每一项审查记录，核对变化哈希、分类、非空理由、
  计数和未批准交付标志。备份映射、源码副本字节/大小/可执行位也与记录核对。
- 核对历史源码快照自身摘要和前后一致性，以及政策、Rust 提取报告、LLBC 和列出的
  Lean 模型与生成后观察的身份绑定。模型列表的记录绑定不是重新验证完整提取合同。
- 绑定原审查报告、`facts.json`、`reviews.json` 和 `review.py` 的字节；不运行该脚本，
  不把其中 CMake、归档或事务语义说明当成本校验器重新证明的事实。
- 引用路径不能越界或经过 symlink，所有引用在检查结束时再次核验。

校验只读取保存的观察与审查记录，不扫描当前整个输出树，不重新执行生成器、工具安装
校验或 kernel，也不认证记录作者。报告和哈希的自洽性不是防伪签名，更不是语义审批。
原[逐路径说明与专门检查](GENERATED_DELTA_REVIEW.md)仍保留各自独立的检查范围。

## 组合输入

聚合清单的 `evidence.worktree_audit` 继续采用仓库根相对 `{path, sha256}` 引用。
新组合 JSON 恰好包含：

- `schema_version: 1`、`kind: "worktree-record-review-v1"`、与清单相同的 `candidate`。
- `source_review`：已有源码组件报告的 `{path, sha256}`，或明确的 `null`。
- `generation`：恰好含 `producer` 和 `review` 两个 `{path, sha256}` 引用，或 `null`。
- `boundaries`：`release_claimed`、`week6_closed`、`generated_outputs_audited`、
  `candidate_approval_claimed`、`semantic_correctness_proven`、`kernel_executed`、
  `current_outputs_verified` 七项均为 JSON `false`。

两个组件不可同时为空。源码组件仍必须匹配当前完整源码，且组合检查结束时再次核对
源码身份；生成组件只返回其历史源码身份。两者不相同时，显式保留
`post_generation_source_delta_review`，不要求为了文档更新无限次重生成，也不将新源码
静默归入旧生成记录。候选字符串只是记录标签，绝不构成最终交付范围批准。

独立组合检查保留最终交付/语义审批、最终生成与 kernel/Rocq 连接、当前输出身份义务；
只有下述聚合连接检查可以单独移除执行连接项。缺失源码或生成组件时另列相应缺项。
组合检查成功仍由聚合器返回 `incomplete`、退出 2。
生成后的正式 `proof-check` 会再次生成 Rust/Sail，必须显式连接它最终留下的新身份。

## 本地回归与实跑记录

测试使用合成记录与临时 Git 仓库，不执行记录携带的生成命令。
[生成组件测试](../../scripts/tests/test_release_generation_review.py)覆盖删减/增加成员、
错误摘要、错误命令/进程/时间、旧 provenance、源码漂移、范围缩减、路径和保证升级。
[组合测试](../../scripts/tests/test_release_worktree_evidence.py)覆盖缺项、候选不符、
历史/当前源码不同、检查期间漂移，以及真实聚合函数必须继续报告未完成。

本次独立保存的[执行目录](../../artifacts/boundary-check/generated-review-validator-DX8llPwq/)
包含测试日志和一次仅携带真实生成组件的命令行聚合。19:59:00–20:01:23 UTC，
33 项生成组件、16 项组合入口、25 项原源码组件和 42 项聚合器测试在普通 Python / `-O`
两种模式下通过，共 232 次完成。[复核报告](../../artifacts/boundary-check/generated-review-validator-DX8llPwq/report.json)
SHA-256：`c9f5ee9db0952f10c93ad2236edf4cfb5e1f6210c7746fa8c6f7b4a89471025c`。

[真实聚合报告](../../artifacts/boundary-check/generated-review-validator-DX8llPwq/audit/report.json)
核对 40 个引用与全部 10,021 项差异绑定，工作树项为 `incomplete`，命令按预期退出 2；
其他十一项在这份专用清单中显式为 `missing`，不表示删除或否定其他历史证据。
聚合报告 SHA-256：`c9791b4f09a64cf6637540f65526ea3624bf05731fa64e93eab8f28152b60996`。
该清单没有替换 v10，没有冒填当前源码审查，也没有复用旧 Lean/Rocq 为新生成状态背书。
校验器源码/原始 pin 的首尾哈希单独绑定；文档更新不回填旧生成源码快照。

## 正式链记录分支

2026-09-13 23:26:44 UTC，新[正式链格式校验器](../../scripts/release_formal_generation_review.py)
已经由原组合入口接入实际聚合。按 producer 的 `kind` 分派，旧生成 schema 不变，
不改写[正式执行](FORMAL_FINAL_EXECUTION.md)或[46,651 项审查](FORMAL_DELTA_REVIEW.md)的历史字节。

新分支核对五个原阶段（两次完整采集、`proof-check`、`proof-spike`、独立验收）的命令、
事件、原始退出码、时间顺序、日志和归档；完整重算新 Rust/public 输出根及 delta。
源码首尾摘要、政策、LLBC 和列出的模型与观察对应；归档 main 和 Rocq 的生成身份一致。
审查报告、事实、逐路径记录、双模式测试及第二进程复验记录都绑定到这一轮执行。
最终再次核对全部引用，不导入或执行任何证据目录的 `run.py` / `review.py`。

这些是记录绑定检查，不是重新验证归档/Git/缓存分类的语义，不认证作者，也不重扫
当前输出或重跑 kernel。新返回值 `recorded_main_rocq_generated_identity_matches=true`
只表示被引用记录内的生成身份对应；不会自行关闭聚合清单的最终执行连接义务。

新增[41 项测试](../../scripts/tests/test_release_formal_generation_review.py)，连同旧生成 33 项、
组合入口 16 项、源码组件 25 项和聚合器 42 项，在普通 Python / `-O` 下共完成 314 次测试。
包括坏命令/退出/范围/源码/模型/成员/引用拒绝，以及真实组合与聚合函数保持未完成。

[本轮执行报告](../../artifacts/boundary-check/formal-review-validator-XAumR9dq/report.json)
于 23:19:17–23:26:44 UTC 完成，外层退出 0、`errors=[]`；SHA-256：
`33c1e6a2847ab27e200d6f4d0712718a257aa5eb2eac1616ec666d0ce92b0724`。
源码首尾身份为 `487b6cc9aca4c27d005700271182fba2913627b09e40ada0904522e6fc0dcf96`，
终态后核对全部 24 个绑定记录文件；本页等后续文档更新不回填该快照。
相对正式链冻结快照的 8 份文档和 4 个校验器/测试文件增量另有完整记录，未作交付审批。

[新清单](../../artifacts/boundary-check/formal-review-validator-XAumR9dq/manifest.json)
保留先前六项证据引用，新增工作树生成组件；候选标签不是批准的 release 版本。
[实际聚合](../../artifacts/boundary-check/formal-review-validator-XAumR9dq/audit/report.json)
SHA-256：`0dac1bdc7adc7546b7d95b0c7807831f5d1779267be29dea1881dccd5c345ce9`。
六项仍为 `verified_existing_evidence`；工作树核对 133 个引用、46,651 项差异后为 `incomplete`，
其余五类仍为 `missing`；原聚合命令退出 2，录制器未将它改成退出 0。

上述 23:26 记录中，当前完整源码组件、正式链后的源码增量、当前输出身份、最终交付范围/
语义审批，以及与聚合中 Lean/Rocq 组件的最终连接均显式待办。后续还须审查支持输出。
没有关闭工作树审计、clean-room、CI 下载、发布包、第三方或公开结论验收。

## 聚合中的最终执行连接

2026-09-13 23:42:59 UTC，执行连接义务已由新入口的真实聚合关闭，其他义务不变。
正式生成校验器现在返回已绑定的 `formal_reports.lean/rocq` 路径与 SHA-256；
[组合模块](../../scripts/release_worktree_evidence.py)在各聚合组件检查完成后核对：

- 两项都必须是独立检查器实际返回的 `verified_existing_evidence`，不能只有报告中的 PASS。
- 两项引用必须与生成记录绑定的路径和哈希完全相同，且结束时再读引用，拒绝漂移/符号链接。
- 缺项或检查失败保留 `final_generation_kernel_and_rocq_linkage`；不相干的已验收引用使工作树项
  `invalid`、聚合退出 1。完全对应才移除这一项，不改变其他待办或工作树 `incomplete` 状态。

由此避免将各自通过、却来自不同执行的证据拼接。固定报告的其他字节相同副本也不自动
成为被指定的引用；若要迁移证据位置，应显式重建绑定记录，而非绕过路径检查。
旧生成格式及仅源码组件不会据此获得执行连接结论。

新测试包括检查顺序变化、同字节异路径、单侧缺失、另一轮报告、检查后文件变化等。
正式生成 43 项、组合 36 项、聚合 48 项、旧生成 33 项、源码 25 项，普通 Python / `-O`
双模式共完成 370 次测试。

[执行报告](../../artifacts/boundary-check/formal-execution-linkage-gNYKSGdf/report.json)
于 23:35:01–23:42:59 UTC 完成，外层退出 0、`errors=[]`；SHA-256：
`e07b8beae71bf5e8e2b6c220452ca5191ff20bc682a387fdfca6289ccf6bf6ab`。
源码首尾身份为 `cf40456d61ecf02e1fa77bc6a2727cae37ffec1f68d966d9a76bb99356648ff5`，
全部 29 个绑定记录文件已在终态后复核；本页后续更新不回填该快照。

[实际聚合报告](../../artifacts/boundary-check/formal-execution-linkage-gNYKSGdf/audit/report.json)
SHA-256：`1eb75c15ff65a7873bdb167b4d69418c8a85f8e7ae40eefbbb0ffb6ec76df060`，
六项证据仍被接受、工作树仍 `incomplete`、另外五类缺失；原始退出码仍为 2。
其中 `formal_execution_linkage.status=verified_existing_evidence_linkage`，绑定
`formal-final-kfncD8ln/main/report.json` 和同轮 `rocq/report.json`，未生成新 kernel 证据。

[引用变更重放](../../artifacts/boundary-check/formal-execution-linkage-gNYKSGdf/linkage-mutation-replay.log)
重新核验真实工作树记录，再使用聚合中已验收的结果检查连接。将 Lean 引用改成同字节但
未绑定的 `artifacts/proof-check/report.json` 被明确拒绝；删除 Rocq 验收结果则恢复待办。
这是对引用的测试，不声称修改后的输入重新通过了 Lean/Rocq 独立验收或 kernel。

现在工作树还剩四项：完整当前源码审查、正式链后的源码增量审查、当前生成输出身份、
最终交付范围/语义审批。clean-room、CI 下载、发布包、第三方和公开结论验收仍缺失，
Week6 不因此关闭；旧 23:26 聚合及所有冻结记录保留原字节。
