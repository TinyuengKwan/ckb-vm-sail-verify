# 精确审计修正后的配套证据补跑

2026-09-13。绑定[修正后的正式政策](REBUILT_AUDIT_CORRECTION.md)，主 SHA-256 为
`ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f`。
旧 v6 报告和录像不回写，新结果来自实际执行，不是替旧清单更换哈希。
当时 Lean 门禁尚在运行；后于 01:15:28–02:03:45 UTC 完成并独立验收通过，见
[完整验收与 v8 清单](REBUILT_GATE_ACCEPTANCE.md)。本页保留配套补跑及 v7 当时结果；Week6 未完成。

## 已完成并独立验收

| 组件 | 报告 | 实际结果（UTC） |
| --- | --- | --- |
| runtime / mutation / 重放 | [release-runtime-rq_u6bg_](../../artifacts/boundary-check/release-runtime-rq_u6bg_/report.json) | 01:15:29–01:16:09；32 案例、188 项适用 mutation、32 次复制重放通过，4 项 mutation 不适用 |
| Rust workspace 默认测试 | [release-rust-tests-lbzt57o5](../../artifacts/boundary-check/release-rust-tests-lbzt57o5/report.json) | 01:15:30–01:15:54；7 个测试二进制 / 78 项测试，含全部 10 项真实引擎测试；5 个 doctest 目标、0 项 doctest，0 ignored / filtered-out |
| 两类配对语义负测 | [paired-negatives-eo1eh276](../../artifacts/boundary-check/paired-negatives-eo1eh276/report.json) | 01:15:31–01:16:15；37 / 12 次搜索与两次复制重放，双方最小总长度为 4 / 3 条指令 |
| trap 最小化 | [release-trap-audit-fix-0k1c4qjl](../../artifacts/boundary-check/release-trap-audit-fix-0k1c4qjl/minimized/report.json) | 以本轮新 CLI 实际执行 4 次，单条 `0x0000107b` 保持 `pc_after` 差异；分类仍为 unsupported |
| 维护者演示 | [maintainer-demo-g4y21e4e](../../artifacts/boundary-check/maintainer-demo-g4y21e4e/report.json) | 01:20:07–01:20:23；真实录制与回放成功，重新运行 corpus/mutation、ADD 重放和预期退出 1 的 trap 重放 |
| Rocq 重跑 | [run-uwaywsl6](../../artifacts/rocq-spike/run-uwaywsl6/report.json) | 01:22:01–01:26:55；十阶段确认原两侧 NO-GO 与最小复现，额外证明覆盖为零 |

上述各组件均已以 Python `-O` 另行独立验收；
[新 mismatch 清单](mismatch-inventory-20260913-v7.json) 也已完整验收，绑定相同 runtime / Rust
报告与实际 runtime 二进制。最小性范围仍为非空、保持顺序的子序列，不是根因等价证明。
本轮复用已安装宿主工具与正式 Sail emulator；不是整个环境重新安装或候选新 Sail 工具采纳。

## 当前演示播放

```sh
scriptreplay \
  --log-out artifacts/boundary-check/maintainer-demo-g4y21e4e/terminal.log \
  --log-timing artifacts/boundary-check/maintainer-demo-g4y21e4e/timing.log \
  --divisor 0.25
```

原始记录约 7.70 秒，上例约 31 秒；只播放终端输出，不执行录像内命令。
报告 SHA-256：`d5cee494fa8c35377ed7920eb4202ede4c8cb6e60a70c757bcd4a6e13dcbc3e0`；
终端输出 SHA-256：`915545ee2dac30e9524f62fac72958247de0eb9fc2fda5c8c025d9bdd4fba4f3`；
时间记录 SHA-256：`ac106b6792bfccb5737152a411ebdffc9cf6f5c581cccde6eda55f139d5c005d`。
4 个时间事件覆盖 2,393 字节实际终端输出。字幕明确 conditional / unsupported 与未发布边界。
实现和验证范围见[演示说明](MAINTAINER_DEMO.md)，首次录像仍保留历史身份。

## Rocq 并发漂移失败与重跑

首次补跑 `make proof-spike` 于 01:15:32–01:21:02 UTC 失败，
[run-04_wmmps](../../artifacts/rocq-spike/run-04_wmmps/report.json) SHA-256：
`92adc8f600b5afc0bbbd2a8e0682a471195e86c6e5a0c9ef3c1482492b6e9780`。
十个子阶段完成原诊断后，最终来源检查发现 `SOURCE_BASELINE.json` 和
`target/CkbVmProduction.llbc` 被同期主门禁的 Rust 重生成改写，正确拒绝成功声明。
该报告不计作新 NO-GO 验收，也没有放宽来源检查。

主门禁已明确完成 `generate-rust` 并进入 `kernel-step` 后，才在新目录重新执行 spike。
不要把 `make proof-spike` 与仍可能改写根目录 LLBC 的 `make proof-check` 生成阶段并发；
等待生成阶段结束或完整主命令结束。重跑仍仅复译 Rust LLBC，复用现有 Sail Rocq 源码，
不声称从零重生成两侧输入或增加 Rocq 证明覆盖。
重跑于 01:26:55 UTC 完成、make 退出 0，并已用 Python `-O` 独立验收来源、模型、
全部阶段日志、具体诊断及最小复现；报告 SHA-256：
`859fcf5dfa9703e2e35dede755efaae411404a0dec9848fe8b19aed9559021ba`。

## v7 清单

[新清单](local-readiness-20260913-v7.json) 绑定当前八项政策/计划身份以及本页全部新报告，
`lean` 仍为 `null`，不引用运行中的报告或用旧 v1 PASS 补位。v6 清单与失败 Rocq 报告保持不变。

`python3 -O scripts/audit_release.py --manifest docs/release/local-readiness-20260913-v7.json`
于 **01:28:49–01:29:00 UTC** 实跑，退出 2、`incomplete`。
[聚合报告](../../artifacts/release-audit/run-x4uigh95/report.json) SHA-256：
`730b59bc48b56ffb522d5f14bf452d127c629511bd3e083ec41fda5efb521f2b`。
runtime、Rocq、Rust tests、mismatches、maintainer_demo 五项重新验收通过；Lean 与原六项
发布义务仍缺失。完成后独立核对当前输入与聚合前后快照、清单哈希和精确缺项集合通过。

## 其余边界

新完整主门禁仍须等待终态，不能将运行记录填成通过证据。
clean-room、最终 worktree 审计、CI 下载、发布包、第三方复现及公开结论审查六类仍未关闭。
