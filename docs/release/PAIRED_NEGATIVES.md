# 配对输入负测：独立产物、有限最小化与重放

2026-09-12。补齐已有两项真实引擎测试的独立证据；这是故意让双方执行不同程序的
比较器负测，不是“相同指令在两端执行不一致”的 CKB-VM 缺陷。

精确安装政策迁移后的当前执行见[本地证据更新](LOCAL_EVIDENCE_REFRESH.md)；
下述早期报告保留为历史记录，不再作为新政策证据。

## 入口与源码边界

在仓库根运行：

```bash
python3 scripts/paired_negative_evidence.py
```

默认创建唯一目录；`--out` 只接受新目录，`--budget` 限制每项案例的候选执行次数。
先检查固定环境，再在空 Cargo target 中构建 workspace 库；用 Rust 编译
[`paired_runner.rs`](../../scripts/fixtures/paired_runner.rs)，直接链接未修改的生产
runner、`CompareResult::compare_with_policy(..., Exact)` 和环境记录代码。
没有复制一份 Rust 比较器，没有修改 `crates/`、主 Makefile、Lean 定理或冻结政策。
此额外证据程序不是原来的 diff CLI 二进制，报告单独绑定它及所链接库的哈希。

配对输入 JSON 明确保留 `ckb_program` 与 `sail_program` 两个字段；输出记录各自
实际 trace、原始 Sail packet、公共注入初态、环境、首差异、终止策略和进程退出码。
检查器要求每侧 trace 对应它自己的输入，并用独立的字段比较重新核对 Rust 比较器
输出。不会把两条不同程序塞入 schema 3 的同一 `case.instructions`。

## 最小化范围

对双方原程序各自的非空有序子序列组成的配对，按**总指令数**递增穷举；所有更短
配对完成检查后才报告结果。预算耗尽、runner 错误、超时、不完整记录或最终复现失败
都不能通过。每个候选都真实执行两端，最后再次执行最小配对，再复制输入字节重放。

| 原负测 | 必须保留的观察 | 实测最小输入 |
| --- | --- | --- |
| 不同输入流 | 首差异是原 ADD 编码，且双方确实分别写入 x3 / x4 | CKB：`addi x1,x0,5; add x3,x1,x2`；Sail：`addi x1,x0,5; add x4,x1,x2` |
| 缺失末尾事件 | 完整共同前缀后出现 `trace_length`，CKB 比 Sail 长 | CKB：`addi x1,x0,5; addi x2,x0,7`；Sail：`addi x1,x0,5` |

第一项不能只剩两个零操作数 ADD：虽然编码不同，但没有保留原负测的实际寄存器
写入效果。第二项最小配对不再包含 ADD，这是长度检测负测，不是新增 ADD 语义证明。
这里的最小性只针对上述有限子序列空间，不涵盖任意替换指令、任意初态或空流；
不是 Lean kernel 定理，也不是相同根因的证明。

## 实跑证据

最终版本于 04:13:41–04:14:22 UTC 完成，54 阶段通过：环境/构建 3 阶段，
不同输入流 37 次双端执行、缺失末尾事件 12 次双端执行，另有各自一次复制输入重放。
两个最小结果总长度分别为 4 与 3；复制重放均预期退出 1，实际观察和原始 packet
与最终最小候选完全相同。整个采集命令退出 0 表示证据完成，不表示配对差分 PASS。

[报告](../../artifacts/boundary-check/paired-negatives-4ui2afuf/report.json) SHA-256：
`d54ef94c4659e5b61f61db290a5239dce00dc40b760f0df4cbf0c26e045bf608`。
报告中各 `cases.*.replay_argv` 是可再次执行的完整命令，使用单独的 `*-replay.input.json`。
搬迁时需重建并重新绑定工具路径；本机绝对路径不是跨机器安装说明。

预算为 2 的真实负测于 04:14:26–04:14:40 UTC 返回 2，只有两次候选，状态
`incomplete`，没有最小化完成汇总；验收器实际拒绝该报告。
[预算负测](../../artifacts/boundary-check/paired-negatives-74mx8ck8/report.json) SHA-256：
`26a2ced18ddfeeee82a192ae5e3e21cbe01b919d951f435ad82734f71f7d4eef`。

更早的 `paired-negatives-u_7j4cvc` 曾通过首轮实跑；随后格式化 Rust 证据程序并补齐
回归测试，最终重新执行生成上述新记录。旧目录保留，不改写其脚本身份。
20 项新增检查器测试普通及 `-O` 均通过；相关七组共 128 项检查测试也均通过两种模式。

## 聚合范围

[v3 清单](mismatch-inventory-20260912-v3.json) 现有三项语义负测都具备验收记录：
两项故意的配对输入差异和原有 `unsupported` trap。原 runtime corpus 32 项没有
意外 mismatch，完整 Rust 测试包含全部 10 项真实引擎测试，mutation 由原检查器
独立验收；出现失败不能仅靠写入分类而放行。

`mismatches=verified_existing_evidence` 只限这个明确的本轮观察集合，不涵盖所有历史、
未来或任意 ISA 失败。复用了本机工具/依赖缓存及现有 Sail emulator，不是 clean-room、
第三方复现或完整 Week6 发布验收。
