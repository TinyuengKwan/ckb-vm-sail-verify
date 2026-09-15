# 正式链 46,651 项输出差异说明

2026-09-13 23:06:48 UTC，新记录及第二进程只读复验均退出 0。
本页说明[正式链](FORMAL_FINAL_EXECUTION.md)已经封存的完整差异，不批准最终交付，
不重新扫描当前全部输出，也不增加 kernel 证明覆盖。

## 记录与复验

- [审查报告](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/report.json)：
  `all_recorded_formal_deltas_explained_final_scope_pending`，46,648 项新增、3 项修改、无删除。
  SHA-256：`6bd6b61d4149c2627e645b5318509ce8163d668ff64cca8aa822da12aa1be6fa`。
- [事实记录](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/facts.json)：
  SHA-256：`48110f33ec436c712a15c63845101c433d05e0a75203c3091cb8d940c03d1525`。
- [逐路径说明](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/reviews.json)：
  SHA-256：`e5dd37438e1269d816a690a9df353149bb4e05ee7906426ef39e6a7c27a803aa`。
  每项绑定原始 change 哈希；未知文件、未知链接和未绑定修改均拒绝，不按生产目录笼统放行。
- [复验退出记录](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/check-review-finished.json)
  与[日志](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/check-review.log)
  保存原命令、PID、时间、退出 0 和日志身份。复验重新计算完整说明，并核对记录及审查器哈希。
- [26 项回归测试](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/test_review.py)
  在[普通模式](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/test-review-ordinary-finished.json)
  和[`-O` 模式](../../artifacts/boundary-check/formal-delta-review-v2-qjTJofy1/test-review-optimized-finished.json)
  均通过，共 52 次测试完成；覆盖未知条目拒绝、LLBC 额外改变拒绝、摘要越界声明和 JSON 往返。

原正式报告的 110 个绑定文件全部重验；重新计算前后完整快照的 delta 与原记录精确相同。
封存源码身份为 `a06055b4c7460fcd9273527f34fd1e399b34d6e87b8e882af11d93476529530c`。
本次检查会重读选定源码、归档和 Git blob；缓存等其余条目按封存快照分类，
不声称对当前全部约 25 GB 输出重新计算哈希。

## 已说明的内容

- 3,628 份生产源码副本绑定完整冻结清单；202 份 clean 项目副本另核对来源。
  Rust lakefile 仅允许指向该 clean 目录中 Aeneas 支持源码的明确路径替换。
- 351 个保留原节点精确对应五组事务备份及旧 LLBC；三个安装事务均保存旧值且未修改政策。
- 78 个 Cargo 归档及 2,739 个包内文件绑定两份 Cargo.lock，读取归档成员比较、不展开执行。
  包来源/字节对应不证明包安全性或语义正确性。
- 10 个锁定 Git 依赖的 9,668 个源码条目按固定 commit 的 blob、大小和执行位核对，
  包含三个按原文字面比较、不跟随的符号链接。另有一个未展开的 gitlink，见下节。
- 248 份支持源码、13 份下层证明、公开 harness、模型连接、实际阶段日志与输出分别绑定。
  故意加入 `False` 的三个负测文件明确不是生产定理；Rocq 仍为 NO-GO，无额外证明。
- 缓存与 Git/Cargo 元数据保留单独类别，每项 `candidate_delivery_approved=false`。
  proofwidgets 的 16 位十六进制输入哈希标记仅按元数据说明，未重算其哈希算法。

三个修改项分别为：

1. `target/CkbVmProduction.llbc`：611 个唯一 short-name 行仅重排、输出目标路径改变，
   其余 JSON 精确相同。没有重写原 LLBC，也不由此主张一般翻译器正确性。
2. Rust `SOURCE_BASELINE.json`：仅 `llbc_sha256` 和 `rebuilt_extraction` 改变，
   新报告链接及模型哈希已核对；生成 Lean 模型字节未变。
3. Lean `step-build.log`：当前文件匹配封存后值，最后 20 行精确出现在归档 kernel 日志中。
   旧日志字节未恢复，只保留旧快照身份；不声称完整新旧日志逐字节比较或完整日志等同。

## 明确不满足的交付条件

全部 10 个 clean 依赖副本的 `.git/objects/info/alternates` 指向本机主项目的对象库，
不是自包含 clone；独立编译记录不能据此称为完整环境 clean-room。
aesop 的 `lean_packages/std` gitlink 固定为
`c2130e653bc1057f8f21196a9b89987d84fe247b`，在完整快照中只是空目录，
没有已展开的子模块源码。本次没有补拉、修改或把它当作已验证子模块。

后续[负测/演示输出](FINAL_SUPPORT_REFRESH.md)和正式链终态后的文档增量不在本次 delta 内。
后续[新格式工作树部分验收](WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)已接入，
23:26:44 UTC 实际聚合核对 133 个引用和全部差异，六项证据仍被接受、工作树仍未完成。
旧六项聚合报告保持原样；[最终执行连接](WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)
已于 23:42:59 UTC 另以真实聚合关闭，下一步须完成当前源码、后续增量及最终交付范围审查。
最终候选批准、clean-room、CI 下载、发布包、独立第三方和公开结论验收仍待完成。
报告所有最终审计、交付、release、Week6、第三方及新 kernel 声明均为 false。

## 保留失败尝试

[首版复验](../../artifacts/boundary-check/formal-delta-review-hRUH9DvE/check-review-finished.json)
真实退出 1：内存中的事务映射使用 tuple，JSON 读回为 list，导致直接比较失败。
诊断确认唯一不同事实键为 `transaction_mappings`，逐路径记录全部一致。
新审查器从构造时使用 JSON 原生 list，补两项回归测试；未放宽复验比较。
新旧 facts/reviews 文件哈希相同，但首版失败记录、脚本及测试保持原样，不回填为通过。
本页及状态更新不属于旧冻结源码快照，也不改变原 Week6 验收标准。
