# 精确安装政策迁移后的本地证据更新

本页为 2026-09-12 历史记录；当前政策已迁移，见
[2026-09-13 v2 输入迁移后的证据更新](V2_LOCAL_EVIDENCE_REFRESH.md)。
下述 v4 清单不适用于当前政策，旧报告保持原身份。

2026-09-12。当时主政策为
`9308acea6d1dd3d6d1a3be2b4c9e7b6cb7e0f8bc34d698dcdf9705c740e5fb9a`。
本次不修改政策、定理、生产源码或批准工具；旧报告及 v3 清单保留历史身份。
旧 runtime、Rust、配对负测和 Rocq 报告绑定旧政策，不能只改引用哈希充作新执行。

## 实际补跑与独立复核

| 组件 | 新报告 | 实际结果 |
| --- | --- | --- |
| Lean 主/公开门禁 | [主报告归档](../../artifacts/boundary-check/before-rebuilt-gate-vxdznmjt/proof-check-v1/report.json) | 22 个主阶段、206 项测试、47 个公开子阶段通过；详见[迁移记录](SAIL_INSTALL_MIGRATION.md) |
| runtime / mutation / 复制重放 | [release-runtime-yu6dnc03](../../artifacts/boundary-check/release-runtime-yu6dnc03/report.json) | 17:46:33–17:47:15 UTC；32 案例、188 项适用 mutation、32 次复制重放通过，4 项 mutation 不适用 |
| workspace Rust 测试 | [release-rust-tests-ww5kz9l8](../../artifacts/boundary-check/release-rust-tests-ww5kz9l8/report.json) | 17:46:34–17:47:01 UTC；7 个测试二进制 / 78 项测试，含全部 10 项引擎测试；5 个 doctest 目标、0 项 doctest，无忽略或过滤 |
| 两类配对输入负测 | [paired-negatives-p0kznt5e](../../artifacts/boundary-check/paired-negatives-p0kznt5e/report.json) | 17:46:35–17:47:20 UTC；37 / 12 次尝试和两次复制重放，最小双方总长度为 4 / 3 条指令 |
| trap 最小化 | [release-trap-8s833qk0](../../artifacts/boundary-check/release-trap-8s833qk0/minimized/report.json) | 17:47:37–17:47:42 UTC；使用新 runtime CLI 四次执行，单条 `0x0000107b` 保持 `pc_after` 差异 |

runtime、Rust 和配对程序各用全新 Cargo target，复用宿主系统、依赖下载缓存和既有
Sail emulator。trap 保留旧原始 artifact 作为输入/观察基准，以新 CLI 首先重新执行原三条
程序，再检查短候选及最终重复；不是重新标记旧最小化报告。分类仍为已声明的
`unsupported`，最小性仅限非空、保持顺序的子序列，不证明根因或 ISA 等价。

上述各项已独立重读输入、日志、程序/库身份及完整 trace；新
[三项负测清单](mismatch-inventory-20260912-v4.json) 在 Python `-O` 下通过完整验收，
绑定同一轮 runtime / Rust 报告，并确认 trap 确实使用该 runtime 二进制。
报告精确 SHA-256 由该清单及后续 readiness 清单固定。

## 检查器变更

`release_evidence.py` 增加必需的 `test_sail_model_transaction` 阶段和 21 项测试计数，
完整 Lean 清单从 21 阶段 / 185 测试变为 22 / 206。
缺少新阶段、测试数减少、失败完成日志均拒绝；没有放宽原来源、模型、合同、见证或公开证据验收。
聚合器 26 项测试、release 组件 48 项、配对 20 项、最小化 21 项、Rocq 16 项，
共 131 项在普通 Python 和 `-O` 下通过。它们是本次另行执行的检查器测试，
不能计入主门禁的 206 项或称为新的 Lean kernel 执行。

## Rocq 输入重生成

先实际执行 `./scripts/generate_proof_model.sh rocq`，再执行 `make proof-spike`。
精确生成安装成功，新 `rv64d.v` 和 `rv64d_types.v` 与保留的旧模型逐字节相同：

- `rv64d.v`：`614d81c62619816362e2450faa08b8f41304f68e1fcda541bc7ca614832a6a06`。
- `rv64d_types.v`：`a5d41ecaeb78951da2ea5d5f2b7f7e9a183cd004cace1b22d209dc192cba2224`。

旧正式目录保留于 `proof/rocq/generated/.sail-install-m0fd17n6/previous`，
旧后端输出保留于 `deps/sail-riscv/build/.sail-generation-r048axsz/previous`，未删除。
随后 `make proof-spike` 于 17:47:47–17:52:20 UTC 完成，退出 0，十个阶段确认原两侧
NO-GO 和最小复现。[新报告](../../artifacts/rocq-spike/run-g9_1a_9v/report.json) SHA-256：
`4cbcffd9c102714683d3b253103959d677450974532106d1b45dfd36b0ac6c2e`。
已以 Python `-O` 独立复核新政策、来源、全部阶段日志、具体诊断、模型及最小复现身份。
这里退出 0 表示 NO-GO 被正确复现，额外 Rocq 证明覆盖仍为零。
十阶段报告本身只记录 Rust LLBC 复译；前面的 Sail 重生成是单独执行，不伪装成该报告内阶段。

## 新清单聚合结果

`python3 -O scripts/audit_release.py --manifest docs/release/local-readiness-20260912-v4.json`
于 17:52:59–17:53:18 UTC 完成，退出 2、`status=incomplete`。
[聚合报告](../../artifacts/release-audit/run-du7w5vuk/report.json) SHA-256：
`8d205b69efa7e60e4be53972cfb78439c8bec78736abcfa0720a49b3b9d2fcf0`。
runtime、Lean、Rocq、Rust tests、mismatches 五项均为 `verified_existing_evidence`。
完成后另行核对聚合前后输入快照与当前源码一致，清单哈希相符，七项缺失精确等于原必需集合。
聚合器未重新执行 kernel 或引擎，也不声称发布完成。

## 未关闭范围

本项只更新政策迁移后的本地证据。未采纳任何独立重建的新翻译器，未完成同一候选的
全工具安装/重提取链、CI 下载、发布、演示或第三方复现。Week6 七类完整验收仍未关闭。
