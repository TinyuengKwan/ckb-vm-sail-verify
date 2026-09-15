# v2 公开解码主门禁完整验收

**2026-09-13 01:15:28–02:03:45 UTC**，修正后的 `make proof-check BACKEND=lean`
完整运行退出 **0**。原失败没有改写；本页记录的是另一次真实重生成、证明检查和独立验收。
保证仍为 conditional / runtime-only，**Week6 未关闭，未发布**。

## 可复核证据

- [成功主报告归档](../../artifacts/boundary-check/approved-rebuilt-proof-YQTKZPMC/report.json)：
  SHA-256 `4385aea4114c1aedc07d7db392d641d46089ed12842ded83bcd4e0b2396ac4a6`。
  同目录保留全部 24 个主阶段日志和 `lean-audit.json`，共 26 个文件，约 2.8 MB。
  它是证据复制归档，不是第三方或完整 clean-room 副本。
- [本次公开子报告](../../artifacts/boundary-check/public-check-hp24b9i1/report.json)：
  SHA-256 `5f7ad050967c8bd9d8bb3e515a857201165b7c13fd789d631f21624149ba5763`。
  独立生成、无项目缓存构建目录与全部公开日志仍保留在该唯一目录。
- 原可重写输出仍在 `artifacts/proof-check/report.json`。新 readiness 清单引用归档路径，
  不依赖该固定文件名永远保持不变。

主检查共 **24 阶段、17 组 / 236 项测试**。公开检查共 **48 阶段**，实际重提取公开
decoder 和 iterator，再从源码完成 **1,865 项**依赖构建；开始时项目已编译模块为零。
主、字段、raw 与公开精确审计全部通过，包含 **68 条公开定理**。
错误公开结果被拒绝；能编译的 `False` 前提弱化版本仍被精确类型/依赖审计拒绝。

运行退出后，另以 `python3 -O` 调用 `release_evidence.check_lean`，重新检查当前政策、
来源、生成物、全部主日志/测试计数、主审计、主子报告关联和公开完整证据链，返回通过。
这次独立验收是对已有运行证据的复核，不声称又执行了一次 kernel。

## 修正范围没有扩大

当前 main / public / raw 政策仍分别为 `ca6e062b…`、`63dd6ab1…`、`a67b275f…`，
完整身份及迁移前失败、两处 `Option.map` 等价证明见
[精确审计修正](REBUILT_AUDIT_CORRECTION.md)。本次真正通过了此前失败的 raw 定义审计。
没有忽略整个 `definitions`、增加行为公理、改写生成 Lean 或删掉负测。

主根仍有 **137 项**传递依赖，wrapper 五个方法行为公理仍为零；
共同状态关系、取指和 Sail 就绪合同保留。范围仍限 RV64 ADD、VERSION2、IMC+B、
MOP 关闭、真实新 decoder cache；不扩展到物理内存、reset 可达性或完整 VM 证明。

本次正式采用的是 v2 公开调用层与下层模型输入；**主 Sail/基础翻译工具仍使用原政策**。
[生产 Rust 暂存及主工具预检](REBUILT_PRODUCTION_RUST.md)是另行记录的未采纳结果，
不能将其新工具身份归到本次主门禁。

## Week6 清单

[v8 readiness 清单](local-readiness-20260913-v8.json)新增上述 Lean 归档，保留同一政策下
已验收的 runtime、Rust 测试、Rocq NO-GO、mismatch 清单及维护者演示。
其余 **clean-room、最终 worktree 审计、CI 下载重放、release 包、独立第三方复现、
公开结论审计**六类义务仍留空。聚合入口没有 release 成功路径，完整条款仍按原计划验收。

v8 于 **02:06:32–02:08:06 UTC** 实际聚合，退出 2、`incomplete`。
[聚合报告](../../artifacts/release-audit/run-na0_m08b/report.json) SHA-256：
`506b0859dc0653b56de601a4086dd9db349de20d1fd50169af8a60d07ff40ca7`。
全部六项已提供组件重新验收通过，缺项恰为上述六类；没有发布或 Week6 完成声明。
