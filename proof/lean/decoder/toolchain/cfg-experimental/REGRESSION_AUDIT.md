# 清理尾段候选：原工具对照审计

2026-09-09。候选源码和两个冻结二进制未改变。本轮审查的是实际已有补丁的影响，
不是通过刷新金样制造全量测试通过。正式工具仍未采纳。

## 全集对照

命令：

```sh
python3 scripts/experiments/probe_charon_cleanup_regressions.py \
  --experiment artifacts/boundary-check/charon-cfg-OYcaoK --jobs 4
```

[报告](../../../../../artifacts/boundary-check/cleanup-regression-g6y486ux/report.json)
SHA-256：`a6d337c88c81de996d077215f65c9fca4cc6f618217dbdc6986572716463945c`。
脚本把全部 tracked tests 和两个新增 fixture 复制到两套独立目录，分别运行冻结的原工具
和候选 `charon ui_test`。原源码/金样的前后哈希相同；不调用会在失败时写回 `.out` 的 UI 包装器。
环境均为 nightly-2026-08-18，不安装或修改全局组件。

| 结果 | 原工具 | 候选 |
|---|---:|---:|
| 精确金样通过 | 356 | 349 |
| 金样不符 | 49 | 56 |
| 命令失败 | 26 | 26 |
| 缺少金样（新增 owned-error fixture） | 1 | 1 |
| 成功但按用例标记不检查输出 | 1 | 1 |
| 忽略 | 2 | 2 |

合计 435 个用例。433 个已执行用例的两侧退出码全部相同；422 个的**选定比较输出**
也相同，11 个不同。正常用例选择 stdout，known-failure/known-panic 选择 stderr，与上游
金样逻辑一致。只归一化 ANSI 颜色、CRLF 和 panic 线程数字 ID。
因此，原日志的 83 个失败不能全部归因于候选；也不能把两侧同样失败计为 PASS。

26 个命令失败中，24 个含缺失交叉目标的 E0463，两个常量转换用例同时报缺失 Miri 和
常量重建错误。检查 stderr 后，9 对完全相同、10 对仅行顺序不同、7 对还有其他诊断差异；
不能将“选定 stdout 相同”扩大成全部错误诊断相同。后七项已进一步归因，见下节；
仍然没有把命令失败改记为成功。
原工具的 49 个金样不符同样不是已解决的环境问题，仍需后续归因。

## 七项剩余 stderr 差异的归因

```sh
python3 scripts/experiments/audit_charon_failure_diagnostics.py \
  --report artifacts/boundary-check/cleanup-regression-g6y486ux/report.json
python3 scripts/experiments/test_charon_failure_diagnostics.py
```

[归因报告](../../../../../artifacts/boundary-check/cleanup-diagnostics-68visubv/report.json)
SHA-256：`ffd67769dec2b843a16a78a2518071e6c9863c7a3e71c418ea44a5a4e5b04fd3`。
重验原报告及各日志哈希后，26 项失败的诊断分类为：9 对相同、10 对仅行顺序变化、
7 对仅行顺序和最先失败目标的汇总行变化。七个用例为 `ml-multi-target-name-matcher-tests`、
`issue-1133-assoc-const`、`issue-1158-partial-dedup`、`issue-1213-merge-methods-when-missing`、
`multi-targets-3-dedup`、`multi-targets-file-ids` 和 `multi-targets`。

对这七项，两侧缺失 std 的实际诊断及其重复次数完全相同，唯一不同的行内容是
`translation for target ... failed with status exit status: 2` 中的目标。
被命名的目标在各自日志中确有 E0463；不是忽略新错误、丢掉重复诊断或放宽退出码。
七项单元测试覆盖了这些拒绝条件。

原因与原工具未修改的 `charon/src/bin/charon/main.rs` 一致：`translate_multi_target`
在线程中并行翻译各目标，每个线程失败时先打印汇总行，再调用 `handle_exit_status` 的
`process::exit` 退出整个进程。因此谁先打印汇总由调度决定。
该文件 SHA-256 为 `4ea2d4194fa72657ac1284ce7b483a5b185ec56267d2b96c1d69ba325d4d6d1a`，
已与基线 commit 的原文件逐字比较；候选 CFG 补丁不修改这一行为。

这关闭的是七项**诊断差异的归因**，不是缺失目标/Miri 的环境修复，不证明多目标提取正确，
也不改变原有 26 项命令失败或 49 项基线金样不符的计数。

## 11 个输出变化

以下是对差异和原函数的结构审查，不是全部变换的形式正确性证明。未批准更新上游金样。

| 用例 | 观察到的变化 / 证据边界 |
|---|---|
| `mem-discriminant-from-derive` | 已算出比较结果的分支带清理返回；默认 true 赋值合并到其余分支之后。 |
| `closures` | `Option::Some` 路径附加原共享 Drop/清理/return；`None` 构造移到该路径退出之后。 |
| `issue-1051-missing-loop-jump` | 清理和 continue 移到非返回分支之后；额外获得下述全迭代区间 Lean 等价证明。 |
| `guarded-owned-error` | 新 fixture，无上游金样；是先前 47.7 MB→0.44 MB 的目标变化。候选的守卫整理另有所有输入等价回归，不能据此宣称原巨大 LLBC 与候选已直接形式比较。 |
| `issue-120-bare-discriminant-read` | `Some` 返回 1 并执行原 Drop；`None` 返回 0 的路径继续执行公共清理。 |
| `issue-70-override-provided-method.3` | 三个方法的 false 路径执行清理返回，true 路径的调用移到分支之后；Drop 的正常/异常次序是审查重点。 |
| `issue-708-from-str-mismatched-generics` | 上游标记 no-check-output；RawVec 分配的成功/错误分支及清理重新组织，退出状态未改变，不算金样通过。 |
| `invalid-reconstruct-assert` | 仍为上游预期失败；诊断中的 ULLBC 块编号和复制的 Drop/清理尾段改变，不表示该功能已修复。 |
| `slice_index_range` | 原工具就不符金样；成功 Some 分支提前返回，None 构造共享到其余路径。 |
| `traits` | false 分支执行原 Drop 后返回，true 分支保留 trait 调用及其异常清理。 |
| `vec-reconstruct-move-values` | 原工具就不符金样；false 分支清理返回，true 路径 Vec 构造和原 Drop 移到其后。 |

其中 7 项从原工具的 golden-pass 变成候选 golden-mismatch。其余为两个已有 mismatch、
一个不检查输出的用例和一个缺少金样的新 fixture。没有新增命令失败，但这不是独立语义判定器。

## 循环差异的 Lean 核验

对原始 `issue-1051-missing-loop-jump.rs`，分别用冻结原工具和候选以 `--preset=aeneas`
提取，再用同一个冻结 Aeneas v2 生成两个命名空间。两份模型均通过内核。
[LoopJumpProof.lean](LoopJumpProof.lean) 证明：

- 对任意 Range I32，两个实际循环体相等。
- 对任意 Range I32，两个实际循环函数相等。
- 两个真实入口相等；候选入口结果确为 `.ok ()`。

四条引理均仅依赖 `propext`、`Classical.choice`、`Quot.sound`。
[LoopJumpNegative.lean](LoopJumpNegative.lean) 把入口结果错误写为 panic，被明确 Type mismatch 拒绝。
证据保存在 `artifacts/boundary-check/charon-cfg-OYcaoK/` 的 `LoopJump{Baseline,Candidate}.llbc`、
`loop-*-model/`、`loop-equivalence-kernel-v6.log` 和 `loop-negative-kernel.log`。
此前求值证明失败的 v1–v4 日志保留，不计为通过，不使用其中错误恢复产生的 `sorryAx`。

## 归档与后续

修复了发布补丁末尾缺失的空白上下文；当前 SHA-256 为
`17f5c34ca63f66987498331d9712b8affb00e25867e4746b5b660893d3d6eebf`。
它与候选源码 git diff 逐字相同，已在原文件副本正向 `git apply --check`、候选源码反向
`git apply --reverse --check` 验证。旧损坏字节已保留，未改旧报告；实际函数没有更改。
公开解码检查器现在同时校验 Charon 二进制/源码/补丁、两侧补丁可应用性，并拒绝 Python `-O`。

这一步关闭了“无法区分补丁回归”和“发布补丁不可应用”的问题，但没有完成全量环境测试、
全部 Drop/unwind 变换的机器检查或正式采纳。下一步应补齐这些检查的合理范围并落实工具政策，
不能只凭本表把编译器补丁当作已经形式验证。
