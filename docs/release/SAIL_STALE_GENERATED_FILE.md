# Sail 干净重生成发现的旧文件残留

2026-09-12。完整模型核验发现一个真实的 clean-room 缺口：原正式生成目录与政策
包含当前生成器不再输出的文件。**不得把旧文件拷回新生成目录来制造政策匹配。**

## 原失败证据

[原比较报告](../../artifacts/boundary-check/sail-model-identity-v1weq3h5/report.json)
于 16:05:37 UTC 结束，状态 `failed`，SHA-256：
`d1e781d3fd31700364597a295566cdf64842af49e8c7207d83abaa5efa4a5dde`。
旧固定 Sail 的 C++、Lean、Rocq 三后端生成及原兼容补丁应用均成功；
在将干净生成的 Lean 文件清单与既有政策对照时拒绝，未进入新编译器阶段。
这不是编译失败，也不是新编译器造成的模型差异。

原政策对应 163 项 `.lean` / `lean-toolchain`；干净输出对应 162 项。
没有新文件，共同 162 项全部逐字节相同，唯一多余文件为：

`LeanRV64D/Specialization.lean`

SHA-256：`4ff811a4e3c8f24ae26b03b34afcfcae9020e32caf0b99701c908c4d3478b72e`。

## 来源及机制

该文件与 Sail 历史 commit `3b7af38d66466ecadad563158b07ce2f82fe05da` 的
`src/sail_lean_backend/Sail/Specialization.lean` 完全一致，唯一渲染步骤是将
`THE_MODULE_NAME` 替换为 `LeanRV64D`；已实际比较完整字节及 SHA-256。
该历史模板在 `namespace Sail` 下定义包装函数。

当前固定编译器 `8eb1fb6b…` 的 Lean 后端选择 `SpecializationV1.lean` 或
`SpecializationArchSem.lean`；本项目选择前者，定义位于 `namespace LeanRV64D`。
现有生成模型和项目证明源码中未找到直接 import 旧 `LeanRV64D.Specialization` 的语句。
仅靠这一搜索尚不能替代下面的实际 kernel / 导入环境检查。

`scripts/generate_proof_model.sh` 的安装步骤为 `mkdir -p` 后 `cp -R "$SOURCE"/. "$DESTINATION"/`。
这是叠加复制，不会移除当前输出中已不存在的旧文件，因此无法保证目标目录等于干净生成清单。
来源对应和复制机制说明了残留问题；不把它误记成新 Sail 生成了不同 ADD 函数。

## 独立清理与 kernel 演练

```sh
python3 scripts/probes/probe_sail_stale_cleanup.py
```

入口通过现有 source-only 构建准备函数复制原模型、定理和支持源码到新目录，
不复制旧 `.olean` / `.ilean`。只将新副本中上述精确哈希的文件移到新报告目录的
`quarantine/Specialization.lean`，可恢复；原正式目录中的文件保持原样。
剩余 162 项必须与真实干净生成物逐字节一致。

使用此前独立安装的 Lean 4.31.0，重建原九个主模型/定理/见证目标，
并由原 `ExportStepAudit.lean` 与检查器核验原定理、合同、见证和完整依赖/边界。
附加 Lean 检查从实际导入环境读取模块清单，要求存在 `SpecializationV1` 且不存在旧模块。
该演练不执行公开 decoder 的全部额外定理，不更新政策或修改正式生成器。
支持库源码采用原准备函数的本机 shared Git checkout，不声称完整 Week6 clean-room。

本轮演练 `sail-stale-cleanup-w3osvf64` 已于 16:40:10 UTC 完成并返回 0，
状态为 `isolated_stale_file_removal_main_kernel_and_boundary_match`。
[报告](../../artifacts/boundary-check/sail-stale-cleanup-w3osvf64/report.json) SHA-256：
`90f6557852fb9f68b771307f014f0763f1a528d4d35d71e167bae477fd0fd9c2`。
1,864 个构建任务及随后定理/模块审计通过；主根仍为原 137 项依赖。
实际导入环境的 4,048 个模块包含 `SpecializationV1`，不含旧 `Specialization`。
另以 `python3 -O` 独立复核报告/日志/输入、162 项干净模型、完整定理/合同/见证审计、
Rust 与定理副本、Aeneas 支持源码及十个 Git 支持库的源码和固定 revision。
原工作区文件与政策未变，隔离副本中移出的文件仍可从 quarantine 恢复。

## 新编译器侧继续比较

```sh
python3 scripts/probes/probe_sail_candidate_model.py
```

新入口绑定上述失败报告和已完成的干净基线输出，在新的空 candidate 构建目录生成
C++ / Lean / Rocq，再逐文件比较。显式复用先前基线生成证据，不伪称两侧都在本次重建。
原报告与输出不改写；不重启已经终止的旧进程，也不向新模型补入旧文件。

该入口只允许报告上述精确单文件政策差异；改动共同文件、缺少其他文件、增加文件、
改变旧文件身份或重新塞回旧文件都会拒绝。即便 raw 模型一致，也返回 2、保持
`existing_policy_matched=false`，等待正式生成/政策迁移，不作为发布 PASS。
本轮 `sail-candidate-model-rjsls7ks` 于 16:41:32 UTC 完成，**返回 1、比较失败**。
[报告](../../artifacts/boundary-check/sail-candidate-model-rjsls7ks/report.json) SHA-256：
`1bd3ed428d37923841ab351bd83529778adcda47d9d4edca6c51dffcb03a3e49`。
五个执行阶段均成功；Lean 的 165 个原始文件和 Rocq 的两个文件逐字节一致，
但 C++ 源码与头文件不同，schema 相同。错误为 `raw candidate model differs`，
未进入候选适配阶段。初步 diff 包含生成标签及字段的变化；未把它归结为纯路径差异，
也未通过归一化绕过。新工具身份仍不采纳，原失败报告保留。
8 项候选比较测试和 6 项隔离清理测试普通与 `-O` 均通过。

## 关闭所需

清理副本的 kernel/边界复验已完成。[正式精确安装与单文件政策迁移](SAIL_INSTALL_MIGRATION.md)
现已接入，保留原批准工具，完整主/公开 proof-check 已于 17:36:37 UTC 通过；
主报告和公开子报告的精确哈希、运行范围见该迁移记录。这只关闭旧文件残留问题，
不是新 Sail 工具资格通过。
新 Sail 的 C++ 差异属于独立工具采纳问题，不能以 Lean / Rocq 一致代替调查。
不能只改生成物哈希，也不能因为文件看似未引用就略过正式回归。
