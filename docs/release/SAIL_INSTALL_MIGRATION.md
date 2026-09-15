# Sail 精确生成安装与单文件政策迁移

2026-09-12。针对[干净重生成发现的历史残留](SAIL_STALE_GENERATED_FILE.md)，
已接入生产安装修复，并按限定范围更新主政策。**完整主/公开 proof-check 已通过，且已独立复核。**
此次不采纳新 Sail 二进制或新 full-MIR sysroot，不改变公开 decoder 政策、CKB 补丁或定理边界。

## 采纳依据

旧批准 Sail 的干净 Lean 生成加原适配，与旧政策的唯一区别为缺少
`LeanRV64D/Specialization.lean`；其余 162 项逐字节相同。
只在隔离副本中移走这个文件后，从零项目/支持库编译缓存重建 1,864 个任务成功，
原主定理、合同、见证及边界审计保持一致，主根仍为 137 项依赖。
实际导入环境包含 `SpecializationV1` 而不包含旧模块。

隔离 kernel 报告 SHA-256：
`90f6557852fb9f68b771307f014f0763f1a528d4d35d71e167bae477fd0fd9c2`。
它不覆盖公开 decoder 的完整附加定理，因此仍要求下面的正式全量回归。

新 Sail 的 Lean / Rocq 原始输出一致，但 C++ 两文件不同，三后端比较整体失败。
这一独立工具身份问题未被本次文件清单迁移豁免。

## 生产改动

`scripts/generate_proof_model.sh` 现在调用 `scripts/sail_model_transaction.py`：

1. 对同一 CMake build 的两个后端加互斥锁；核验源码目录与配置路径。
2. 将旧后端生成目录移到相邻、唯一命名的备份目录，强制 CMake 重新生成。
3. 将新输出复制到独立 staging 目录；拒绝链接、特殊文件和编译缓存。
4. 对 staging 执行原 Lean 适配与工具链固定，核验配置未漂移。
5. 保留旧正式目录的完整备份，再将 staging 安装为正式目录。

生成、适配或发布失败时恢复原目录名，保留失败产物及 transaction 记录。
不递归删除原目录或旧缓存，不把旧文件叠加复制回新输出。备份位置随命令输出记录，
之后若要清理应另行明确范围；本次不清理备份。

`configure_lean_project.sh` 的可选目录参数只允许本项目 generated 目录内的
`.sail-install-*/staged`，无参数行为保持不变。21 项新测试包含真实适配脚本的 staging
及幂等检查，并覆盖失败恢复、链接拒绝和并发互斥；普通 Python 和 `-O` 均通过。
既有 19 项 import 测试及 18 项主门禁测试也通过，主门禁已接入这 21 项新回归。

## 精确政策范围与归档

迁移前源码快照、政策、生成模型清单及原 proof-check 顶层报告/日志保存在
[sail-install-migration-vv_mytr1](../../artifacts/boundary-check/sail-install-migration-vv_mytr1/archive.json)。
原主报告没有丢弃，见[归档的上一轮报告](../../artifacts/boundary-check/sail-install-migration-vv_mytr1/previous-proof-check/report.json)。
唯一命名的旧子构建目录继续保留在原位置。

- 旧主政策：`c8315684cf73d118703f98982e79303943d8c52d49e72d99117de25301b3a1af`。
- 新主政策：`9308acea6d1dd3d6d1a3be2b4c9e7b6cb7e0f8bc34d698dcdf9705c740e5fb9a`。
- 新 Sail 模型清单身份：`bccb25934e427c008c7e1b7e0dc329eff61b9a6780ad9db18ca2299cca522d5f`。
- 公开政策保持 `e2643499ef13d20ed1797dca4d2e6192851fdad0b0e6e53ffc41247ce85fd0b4`。

[限定迁移审查](../../artifacts/boundary-check/sail-install-migration-vv_mytr1/review.json)
为 `MIGRATION_REVIEW_PASS_FULL_PROOF_PENDING`：仅允许四个相关源码 pin 更新、
两个新实现/测试 pin 加入以及精确单文件清单变化。
Rust 模型身份、所有工具二进制/版本、依赖版本、主定理/合同/见证/边界和原计划均不变。
审查入口从不写政策；它核对已审查并显式编辑后的政策差异，不能任意刷新哈希。
报告中的 `model_difference` 是相对旧政策的拒绝记录；新清单必须严格等于隔离 kernel 的 162 项输入。

## 正式回归

```sh
make proof-check BACKEND=lean
```

原批准工具上的完整主/公开门禁于 16:47:47–17:36:37 UTC 完成，退出 0。
[主报告归档](../../artifacts/boundary-check/before-rebuilt-gate-vxdznmjt/proof-check-v1/report.json) SHA-256：
`dbb8654592aea7dc90c9c5b9b3e1efc669256353e96dae11181c29dcfe2ba4cb`。
22 个主阶段、15 组 / 206 项回归均通过；生产精确安装后的 162 项清单符合新政策，
主 kernel 的 1,864 个构建任务和原 137 项根依赖审计通过。
[公开子报告](../../artifacts/boundary-check/public-check-n6k9tcqx/report.json) SHA-256：
`bec8300f294443e20f22c6ae122b62408a98bbd75c2c046388cd42b2654444c0`。
47 个公开阶段通过，包括实际 Rust 重提取、全新 source-only 依赖构建（1,865 个任务）、
公开根 158 项依赖审计、错误结论拒绝和削弱前提审计负测。
更新后的发布证据检查器另以 Python `-O` 独立重读政策、来源、全部日志及公开证据，
确认 22 阶段 / 206 测试及 68 个公开定理检查项。新增阶段缺失、测试数减少、失败日志负测
纳入聚合器 26 项测试，普通 Python 和 `-O` 均通过；这次复核不是另一次 kernel 执行。
[安装后的独立复核](../../artifacts/boundary-check/sail-install-migration-vv_mytr1/installed-review.json)
确认 `live_model_matches_new_policy=true`。
旧正式模型完整保留于 `proof/lean/generated/.sail-install-_htu8fir/previous`，
旧后端输出保留于 `deps/sail-riscv/build/model/.sail-generation-doaxyw_4/previous`。
已另行逐项核对前者仍是旧 163 项模型，包含原精确哈希的旧文件，未删除备份。
此次通过只关闭这项生成可复现性缺口，不等于全部工具独立重建、完整 clean-room、
第三方复现或 Week6 发布完成。
