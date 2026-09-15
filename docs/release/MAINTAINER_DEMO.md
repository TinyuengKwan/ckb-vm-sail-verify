# 维护者终端演示：实际录制、回放与证据验收

本页首次录像绑定修正前的 `32364dd…` 政策，仍可作为历史演示播放。
01:15 UTC [审计修正](REBUILT_AUDIT_CORRECTION.md)后的新录像已完成，
**当前播放命令与独立验收见[最新补跑记录](AUDIT_FIX_EVIDENCE_REFRESH.md)**。
下文保留首次运行的身份，不将旧录像改写为当前政策证据。

2026-09-13 已录制一段真实运行的本地演示，不只是脚本或静态截图。
它展示当前支持的差分流程及拒绝误报成功的行为；**不声称新 Lean kernel 执行、
clean-room、第三方复现或 Week6 发布通过**。录制由自动化执行，不冒称维护者本人操作。

## 播放

在仓库根执行（util-linux `scriptreplay`；只播放输出，不执行录像内命令）：

```sh
scriptreplay \
  --log-out artifacts/boundary-check/maintainer-demo-t4038phj/terminal.log \
  --log-timing artifacts/boundary-check/maintainer-demo-t4038phj/timing.log \
  --divisor 0.25
```

原始记录约 8.87 秒；上例四分之一速约 35 秒，便于阅读。可随时用 Ctrl-C 停止播放。
[终端输出](../../artifacts/boundary-check/maintainer-demo-t4038phj/terminal.log)可直接阅读；
[时间记录](../../artifacts/boundary-check/maintainer-demo-t4038phj/timing.log)保留事件延迟和字节长度。
两者都必须保留，不能用复制的文本冒充录像。

## 展示的实际命令

1. 以本轮已验收 runtime CLI 和正式 Sail emulator 重新运行完整 corpus / mutation：
   32 案例（ADD/ADDI/BEQ 为 13/10/9）、188 项适用 mutation 检测通过，4 项不适用。
2. 从演示刚产生的 `add-zero.json` 重放，逐项严格 trace 比较通过，退出 0。
3. 重放已最小化的已知 `0x0000107b` trap 输入，检测 `pc_after` 差异，退出 **1**。
   字幕明确这是预期的 unsupported 差异，不将它隐去或称为指令正确性证明。

每一步的完整 argv、开始/结束时间、真实退出码、原始 stdout/stderr 和产物均保存在
[演示目录](../../artifacts/boundary-check/maintainer-demo-t4038phj/)。录像显示实际执行命令与
从原始输出核验后生成的简短摘要；完整 JSON 没有省略出证据目录。
只录制输出，不录制 stdin，不打印完整环境变量，不产生发布或外部写入。

## 实测结果与身份

完整生产器于 **00:47:24–00:47:42 UTC** 运行并退出 0；实际 PTY 记录为
00:47:27–00:47:36。录制器和回放器都实际退出 0，输出分别对应同一 2,386 字节
终端内容；4 个时间事件共 8.865086 秒。已另以 Python `-O` 独立验收通过。

| 产物 | SHA-256 |
| --- | --- |
| [报告](../../artifacts/boundary-check/maintainer-demo-t4038phj/report.json) | `e72e1227d4951558d331e3addcbd413c53b503a23b8bbe0cd674c51f22ca7f61` |
| 终端输出 | `0fbed2a185406fa016b0daa3dfcd12300d3e61ff53749b52dea44095f9c72c8e` |
| 时间记录 | `9504260df45db39281d9d58ec989075df81eda1c19732c4ae50a5eeb2fc8820b` |

输入绑定 [本轮 runtime](../../artifacts/boundary-check/release-runtime-epku3001/report.json)
与 [本轮 trap 最小化](../../artifacts/boundary-check/release-trap-v2-1_qr4ufa/minimized/report.json)。
源码、政策、配置、引擎和录制/播放程序哈希在执行前后相等。
复用了这些已安装二进制与宿主环境，没有重新编译全工具链。

## 独立验收及重新录制

```sh
python3 -O scripts/release_demo.py --check artifacts/boundary-check/maintainer-demo-t4038phj/report.json
python3 scripts/release_demo.py \
  --runtime-report artifacts/boundary-check/release-runtime-epku3001/report.json \
  --trap-report artifacts/boundary-check/release-trap-v2-1_qr4ufa/minimized/report.json
```

录制默认创建新目录；`--out` 也只接受不存在的目录，不覆盖旧录像。
失败保留 `failed` 报告；完整验收失败时还保留候选报告，不将录制器退出 0 单独当作成功。
验收重新核对输入与原始报告、全部真实 trace / mutation、三阶段命令/退出码、摘要、
时间事件完整字节覆盖、终端文本及实际回放输出。缺文件、额外输出、拼接摘要、错误退出、
来源漂移和缺失边界标记均不能通过。哈希与日志绑定不等于可信第三方执行证明。

28 项新测试在普通 Python 与 `-O` 下通过，含真实 util-linux 录制/回放小用例及负测。
聚合器另外新增跨组件约束：录像必须引用与清单相同的 runtime 和 trap 报告；
不能以另一候选的成功录像替代本轮。聚合器现有 32 项测试在两种模式下通过。

## 接入 readiness

[v6 清单](local-readiness-20260913-v6.json) 增加 `maintainer_demo` 引用，v5 清单保留旧状态。
这补齐的是本地维护者演示交付项；Lean 当前全门禁仍待结束，clean-room、最终 worktree
审计、CI 下载、发布包、第三方复现和公开结论审查六类发布证据仍不可省略。

v6 聚合于 **00:50:13–00:50:24 UTC** 实跑，退出 2、`incomplete`；
[报告](../../artifacts/release-audit/run-o2fzc1g8/report.json) SHA-256 为
`1737fbee3a3240165f443a420fefc577c03aef6b97bf6fe60d8944746d660f4e`。
runtime、Rocq、Rust tests、mismatches 和 maintainer_demo 五项均重新验收通过，
Lean 与其余六项为 missing。完成后独立核对聚合前后快照、当前主/公开来源、
清单哈希和精确缺项集合通过。

本轮聚合器 32 项、release 组件（含演示）76 项、配对 20 项、最小化 21 项和 Rocq
16 项，共 **165 项检查器测试**在普通 Python 与 `-O` 下通过；不计作新的 Lean kernel 执行。
聚合器变更前源码及文档保留于 `artifacts/boundary-check/before-demo-gate-INu8JfaN`，
先前 v5 聚合报告不回写成包含演示的成功记录。
