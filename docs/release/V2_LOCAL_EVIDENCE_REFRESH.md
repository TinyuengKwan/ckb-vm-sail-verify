# v2 公开输入迁移后的本地证据更新

本页记录 v5 支持证据补跑。后续已新增[实际维护者演示](MAINTAINER_DEMO.md)，
当前 [v6 清单](local-readiness-20260913-v6.json) 将其接入；下述 v5 聚合状态保留历史含义。

2026-09-13。当前主政策为
`32364dd191802c39bb9b10cb567240ff3e0d964eb6ef105fdb6ed6524795ade4`，
公开入口已采用 [rebuilt-v2 政策](REBUILT_GATE_MIGRATION.md)。
**完整主门禁仍在运行；本页不是 Lean 新 PASS、clean-room 或 Week6 发布通过。**
2026-09-12 的[旧证据与清单](LOCAL_EVIDENCE_REFRESH.md)保持历史身份，不回写旧报告。

## 本轮实际执行与独立验收

| 组件 | 新报告 | 实际结果（UTC） |
| --- | --- | --- |
| runtime / mutation / 复制重放 | [release-runtime-epku3001](../../artifacts/boundary-check/release-runtime-epku3001/report.json) | 00:22:56–00:23:36；35 阶段、32 案例（ADD/ADDI/BEQ 为 13/10/9）、188 项适用 mutation、32 次重放通过；4 项 mutation 不适用 |
| Rust workspace 默认测试 | [release-rust-tests-8z94lst1](../../artifacts/boundary-check/release-rust-tests-8z94lst1/report.json) | 00:22:57–00:23:22；7 个二进制、78 项测试含全部 10 项真实引擎测试，0 ignored / filtered-out；5 个 doctest 目标、0 项 doctest |
| 两类配对输入负测 | [paired-negatives-j5qpp8l9](../../artifacts/boundary-check/paired-negatives-j5qpp8l9/report.json) | 00:25:23–00:26:07；37 / 12 次尝试及两次复制重放，双方最小总长度为 4 / 3 条指令 |
| trap 最小化 | [release-trap-v2-1_qr4ufa](../../artifacts/boundary-check/release-trap-v2-1_qr4ufa/minimized/report.json) | 00:27:11–00:27:16；4 次实际执行，单条 `0x0000107b` 保留 `pc_after` 差异 |
| Rocq spike | [run-70gr5bdr](../../artifacts/rocq-spike/run-70gr5bdr/report.json) | 00:23:49–00:28:46；十阶段确认原 Rust result-type / Sail `e_div` 两侧 NO-GO，进程退出 0，额外证明覆盖为零 |

以上各组件已另以 Python `-O` 独立重读输入、工具、命令、日志和 trace。
[新三项负测清单](mismatch-inventory-20260913-v5.json) 的完整验收也已通过，
确认 trap 使用的确为本轮 runtime CLI，不以同名文件代替二进制身份。
runtime / Rust / 配对程序在各自空 Cargo target 中实际构建；它们仍复用宿主、依赖
下载缓存和正式政策中的既有 Sail emulator，不是 [候选新 Sail 模拟器实测](REBUILT_SAIL_RUNTIME.md)。

Rocq 本轮只复译现有 Rust LLBC、检查现有 Sail Rocq 源码，没有重新生成 Sail 输入，
不把上一轮单独重生成的执行计入本轮十阶段。

## 保留的失败与最小性边界

trap 首次补跑 [release-trap-v2-NKJ9gnYM](../../artifacts/boundary-check/release-trap-v2-NKJ9gnYM/minimized/report.json)
于 00:25:43–00:25:45 被环境检查拒绝，报告 `failed`、`minimum_proved=false`。
诊断为 `replay environment differs or is unidentified: sail_compiler`：直接 shell
继承的 Sail 编译器身份不等于原 artifact 的固定身份。未修改检查器或原 artifact；
随后在新目录使用已有 `probe_release_runtime.environment()` 固定环境重跑。
首次失败报告 SHA-256 为
`ef7b20622a53856f154d6b2c6a4c74564e9910a3c571bb46904a3bc3ba951687`。

成功运行以原三条指令 artifact 为输入，首先重新执行原程序，再搜索短候选并重复最终
结果。分类仍是已声明的 `unsupported`，不是自动证明的根因。
trap 的最小性只覆盖非空、保持顺序的子序列；配对负测只覆盖双方各自非空子序列的
最小总长度。两种不同输入的负测不构成同程序 ISA 等价证明。

## 聚合器跟随正式门禁，不降低要求

`release_evidence.py` 的必需主阶段从 22 增至 **24**，测试从 206 增至 **231**，
增加 `test_decoder_rebuilt_inputs`（15 项）和 `test_decoder_rebuilt_locations`（10 项）。
公开验收要求 **48** 个阶段。原来源、工具、生成模型、定理类型、合同、公理、见证、
clean-build 和负测检查均保留；这里的计数是当前完整验收要求，不是运行中的完成数。

`audit_release.py` 改为绑定 v2 公开政策，并新增下层政策、输入准入、输入目录三项
mandatory pin。连同主政策与原三份计划，共八项 pin；旧清单因缺项或过期被拒绝。
runtime 生产器也增加四份 v2 政策/目录来源，因此实际补跑支持证据，不替旧报告改哈希。

聚合器 29 项、release 组件 48 项、配对 20 项、最小化 21 项、Rocq 16 项，共
**134 项检查器测试**在普通 Python 和 `-O` 下通过。这些另行测试不计入主门禁的 231 项。

## 本轮 readiness 清单

[v5 清单](local-readiness-20260913-v5.json) 固定上述新证据及八项当前政策/计划哈希。
`lean` 明确为 `null`：迁移后的完整主门禁未结束，不能以旧 v1 PASS 补位。
另七项完整发布验收仍缺失。清单标签不是发布版本，聚合器仍没有 release 成功路径。

`python3 -O scripts/audit_release.py --manifest docs/release/local-readiness-20260913-v5.json`
于 00:34:51–00:34:59 UTC 实际完成，退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-z7f4rrrm/report.json) SHA-256：
`ffcd278b4cdd6f8fac8bc0933ef79b2210801786742d91d06c27b9f09e06076b`。
四项支持证据为 `verified_existing_evidence`；Lean 和原七项发布义务共八项 `missing`。
随后独立核对聚合前后快照、清单哈希、两层正式源码身份及精确缺项集合通过。

下一步先等待同一次主门禁及公开子门禁完成，独立复核通过后建立后续版本清单；
本轮 v5 保留“主门禁待完成”的真实状态。后续演示进展见页首；主 Sail/基础工具准入、
完整 clean-room、最终源码差异审计、CI 下载、发布包、独立第三方和公开结论审查仍须继续。
