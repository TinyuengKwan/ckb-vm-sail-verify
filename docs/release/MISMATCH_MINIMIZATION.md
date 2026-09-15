# Mismatch 分类、最小输入与真实重放

2026-09-11。新增 [minimize_mismatch.py](../../scripts/minimize_mismatch.py)，不修改
Rust 生产源码、Lean 定理或当前证明政策。该工具补充失败证据，不会把 mismatch 改成 PASS。

精确安装政策迁移后，已使用新 runtime CLI 再执行并验收；见[本地证据更新](LOCAL_EVIDENCE_REFRESH.md)。
下述旧报告不改写，新三项清单独立绑定当前轮次的 runner 和实际执行。

## 最小化的确切范围

对原始指令序列的所有**非空、保持顺序的子序列**，按指令数量递增重新运行两端。
保持的观察特征是首个差异字段和该事件的两端指令编码；绝对 PC 和事件序号可以随删去
前置指令而改变。这不是“相同根因”的自动证明，也不搜索所有可能的指令替换或初态。

原始失败必须先真实复现。更短候选没有完成检查、runner 失败、超时、预算耗尽、
工具/配置或环境身份变化、最终输入复现失败，均不能报告最小化完成。
预算耗尽返回 2，报告 `status=incomplete`、`minimum_proved=false`；普通失败返回 1。
只有完成搜索及最终再执行才返回 0、`status=minimized`。这里的最小性来自有限搜索，
不是 Lean kernel 定理。

脚本校验 schema 3、同一输入、共享零寄存器初态、严格终止比较、双侧非空 trace、
退出码、JSON 报告与 artifact 的一致性、观察环境和实际二进制/配置哈希。
每次尝试保留独立输入、stdout、stderr、实际 trace、退出码和哈希。
不执行 artifact 内的命令字符串；输出目录必须全新，原 artifact 不改写。

分类及理由单独记录为操作者解释。`unsupported` 不等于两端已被证明等价；
`ckb_candidate_defect` 也不等于已经确认 CKB 根因。默认仍是待分类。

## 已实测：仓库原有 trap 差异

使用现有 [真实负测](../../crates/diff-test/tests/dii_end_to_end.rs) 的三条指令：
`0x00500093 / 0x0000107b / 0x00700113`。中间编码触发已声明的 post-MVP trap 差异，
见[语义缺口](../semantic-gaps.md)。新 [输入 fixture](../../scripts/fixtures/trap-divergence-input.json)
明确为 `input_only`，没有模拟出来的 trace 或 PASS；需实际重放才能产生证据。

先执行 `cargo build --locked -p ckb-vm-sail-diff`，再用真实 CLI 采集该输入。
原始双端重放退出 1，首差异是 `pc_after`，不是 runner error。
最小化于 10:08:11–10:08:16 UTC 完成，四次尝试依次为：

| 尝试 | 输入 | 实际退出码 | 观察 |
| --- | --- | --- | --- |
| 原始再执行 | 三条原指令 | 1 | 同一 `pc_after` 差异 |
| 单条候选 | `0x00500093` | 0 | 两端一致，不保留 |
| 单条候选 | `0x0000107b` | 1 | 复现目标差异 |
| 最终再执行 | `0x0000107b` | 1 | 再次复现 |

最小结果是一条指令，已达到非空指令输入的长度下界。分类为 `unsupported`，
理由是仓库已经明确排除完整 trap 关系；不是新增 ADD 缺陷或 ADD 证明反例。
完成后又独立调用 CLI 重放最小 artifact，退出 1、同一观察特征；逐项重读四次尝试的
输入/输出哈希和比较结果。另实跑 `--max-evaluations 2`，确认退出 2、保留两次记录，
没有最小化成功标志。

| 证据 | SHA-256 |
| --- | --- |
| [原始实际 artifact](../../artifacts/boundary-check/trap-minimization-nyWJaJK1/original/trap-divergence-input.json) | `acf7ee539e3c054d004e4bf388224529976740df657d42ab3ecb3a4d8f4ab47a` |
| [最小化报告](../../artifacts/boundary-check/trap-minimization-nyWJaJK1/minimized/report.json) | `eabc396ea94fb5952a6cf47f323a4d99e6a2765590af207d6f9f0b8ab2fe983d` |
| [最小实际 artifact](../../artifacts/boundary-check/trap-minimization-nyWJaJK1/minimized/trial-00003/evidence/candidate.json) | `adb08dcb5b7d22ce26eeb77e894c6d7720023733920713531b535e42dd4eefcf` |
| [独立重放](../../artifacts/boundary-check/trap-minimization-nyWJaJK1/independent-replay.json) | `a931413a310519ff611c12a6d04ca4c415ed5e5cd3903662bde68ba0bc75b963` |
| [预算耗尽负测](../../artifacts/boundary-check/trap-minimization-nyWJaJK1/budget-two/report.json) | `fa4f82262d26100c7f3850b525fa635f29fa1027e7558b6b808fe55f0556c0d7` |

## 使用

在仓库根、已安装固定环境后执行；`NEW_ORIGINAL`、`NEW_MINIMIZATION` 应选全新目录。
第一条重放命令预期退出 1，必须检查它是语义差异而非基础设施错误。
最小化工具会自行重新检查该前提，不接受错误结果冒充 mismatch。

```bash
cargo build --locked -p ckb-vm-sail-diff
target/debug/ckb-vm-sail-diff --replay scripts/fixtures/trap-divergence-input.json \
  --json --artifact-dir NEW_ORIGINAL
python3 scripts/minimize_mismatch.py \
  --artifact NEW_ORIGINAL/trap-divergence-input.json --output NEW_MINIMIZATION \
  --classification unsupported --rationale 'Known post-MVP trap-path divergence; see docs/semantic-gaps.md'
```

报告的 `minimized_artifact` 可交给 `cargo run --locked -p ckb-vm-sail-diff -- --replay ...`。
报告还保存了本次实际二进制/配置路径的完整重放 argv 和 shell 转义后的命令；搬迁时
应使用接收方固定工具路径，不能假装本机绝对路径可在任何机器直接运行。
**重放最小失败预期仍退出 1；最小化工具退出 0 不代表差分通过。**

19 项测试在普通 Python 与 `-O` 下通过，覆盖有限搜索次序、重复指令、未检查的短输入、
错误退出、报告不一致、空 trace、初态/环境变化、预算、不可复现与旧目录保护。

## 尚未关闭的发布要求

本条真实 trap 差异已具备分类、最小输入及重放证据；不由此声称所有历史负测、
未来 mismatch 或整个 release 都已处理。发布聚合门禁仍需枚举本轮所有失败，将它们
链接到对应分类/缩减/重放记录，并保留不支持的范围。上述负测不扩大 ADD/ADDI/BEQ
的形式证明覆盖，也不自动进入 `proof-check` 的固定测试清单。

## 2026-09-12 清单接入与边界修正

修正最小化工具对 `trace_length` 的位置检查：合法位置是双方 trace 的共同长度，
不要求该索引在较短 trace 内存在。相同长度、错误位置及布尔值位置均拒绝。
新增两项回归测试，总计 21 项普通和 `-O` 均通过。工具仍明确要求双侧非空 trace，
没有将此修改扩大为任意空流或配对输入的最小化支持。

旧报告绑定旧脚本，保持历史身份不改写。本轮使用已经验收的 runtime CLI 二进制和
CMake 固定 Sail 编译器环境重新采集 trap，并在 03:50:09–03:50:13 UTC 实测最小化。
四次退出仍为 `[1, 0, 1, 1]`，最小输入 `0x0000107b`，首差异 `pc_after`，解释为
已声明的 `unsupported`，不是自动证明根因。[新报告](../../artifacts/boundary-check/release-trap-F9FXIqZ6/minimized/report.json)
SHA-256：`94d56ea4b213b77dd3f21b7e2ea741c119fc9e56ab628d2a520051c2572a67bf`。

新增 `release_mismatch_evidence.py`，重新读取实际 trace、输入与日志哈希、工具身份，
按原搜索顺序重新核对每次候选与最终重复；不只信任 `minimum_proved`。
[v2 的三项清单](mismatch-inventory-20260912.json) 绑定当前 runtime 和 Rust 测试报告。
当时两项仍未关闭；随后 v3 已补齐，[见配对证据](PAIRED_NEGATIVES.md)：

- `a_diverging_instruction_stream_is_located`：两端执行的输入不同，需要保存双方程序、
  trace、配对重放及相应最小化证据；不能套用单一同码输入的 artifact。
- `a_missing_final_event_is_detected`：Sail 输入是 CKB 输入的短前缀，同样需要配对输入
  证据，不能把不同长度的两条执行流伪装成相同程序。

这些测试本轮均实际通过，但独立 artifact 验收不同于测试断言通过。
失败的 runtime/Rust 报告不会因列入此清单而获准；mutation 矩阵继续由专门的检查器
验收，runner error 和空矩阵由对应负测检查，不能把它们解释成可最小化的语义结果。
当时聚合结果为 `mismatches=incomplete`；现在 [v3 清单](mismatch-inventory-20260912-v3.json)
这三项均已重新验收通过，仍不代表所有历史或未来失败的完整清单。
