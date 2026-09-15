# v2 公开解码输入接入主证明门禁

2026-09-13：**首次 v2 全门禁于 01:02:50 UTC 失败**，原因是两处已证等价的 map
定义指纹漏迁移。后续已[修正精确审计和政策引用](REBUILT_AUDIT_CORRECTION.md)，
于 01:15:28–02:03:45 UTC 完成另一次[完整重跑及独立验收](REBUILT_GATE_ACCEPTANCE.md)，
本次退出 0。下文保留首次迁移的范围和身份，不将其失败改写为成功。
本次是公开解码器、full-MIR 和下层模型身份的迁移，不是完整新 Sail/基础工具链准入，
也不是 Week6 clean-room 或发布通过。

## 首次执行（已失败，保留记录）

```sh
make proof-check BACKEND=lean
```

本轮于 **2026-09-13 00:14:51 UTC** 启动。
对应[失败主报告归档](../../artifacts/boundary-check/before-rebuilt-audit-fix-6b2zn65c/proof-check-failed/report.json)。
配置、环境检查、Rust/Sail 重生成、主 kernel 和定理审计、17 组 / 231 项测试已通过。
公开 v2 两个根已实际重提取/翻译，无缓存 1,865 项主构建及各下层模块编译通过，
但 raw 精确定义审计拒绝两个旧指纹；公开剩余阶段未完成。
不要把下文的静态迁移审查或旧 PASS 当作本轮结果。
配套 runtime、Rust、负测和 Rocq 的新执行与独立验收见
[本地证据更新](V2_LOCAL_EVIDENCE_REFRESH.md)。

此前的主报告及整个 `artifacts/proof-check` 目录已复制到
`artifacts/boundary-check/before-rebuilt-gate-vxdznmjt/proof-check-v1`，复制进程退出 0。
[旧主报告](../../artifacts/boundary-check/before-rebuilt-gate-vxdznmjt/proof-check-v1/report.json)
仍为 SHA-256 `dbb8654592aea7dc90c9c5b9b3e1efc669256353e96dae11181c29dcfe2ba4cb`。
复制包含既有缓存和链接，不把该归档称为独立 clean-room。

## 首次迁移的政策与精确变化（后续身份见修正记录）

| 政策 | 本轮 SHA-256 |
| --- | --- |
| 主 step 政策 | `32364dd191802c39bb9b10cb567240ff3e0d964eb6ef105fdb6ed6524795ade4` |
| 新 `public-rebuilt-policy.json` | `731b3213e0c22a2a23b65992041be05bd9be7e3ca8c89b44515319143cd096df` |
| 新 `raw-rebuilt-policy.json` | `4f3e0c5af8983187182d63adb50267cb638fd3841104a9bd2b3c3ef29cc66585` |

原 `public-policy.json`、`raw-policy.json` 和字段政策保留，未覆写为新身份。
主调用层明确改用 `public-rebuilt-policy.json`，公开 clean-build 和验收器明确改用
`raw-rebuilt-policy.json`；没有尝试 v2 失败后退回 v1。独立旧 raw CLI 仍保留 v1 行为，
不是新主门禁的下层政策选择入口。

- 主政策除 `local_sources` 外的全部字段不变：只改变四个检查器/测试来源，增加一个
  v2 公开政策引用。主定理、合同、公理、主模型及原基础工具身份未改。
- 公开政策更新八个来源、增加七个来源，没有删除任何来源；配置、CKB 基线、
  既有保证边界不变，另明确保留 visitors 约束差异和历史诊断源码身份限制。
- 下层政策保留完整 `audit`、证明源码、scope、锁文件和字段政策，只改变两个已核验
  `Option.map` 模型身份、join 工具位置/哈希，并增加等价及原负测的准入关联。
  没有改写 Lean 定理、合同、关系定义或公理清单来迁就新模型。

迁移前完整源码快照保存在 `before-rebuilt-gate-vxdznmjt/payload`，快照身份为
`bd3506b1d9a473772c9865c81905f590c2eb12307e62d67ad634c88fe44b8f63`。
[迁移审查报告](../../artifacts/boundary-check/before-rebuilt-gate-vxdznmjt/migration-review.json)
SHA-256：`6d2c8b4598eec9b80c552d4eb4a2810d873f509e2612acf71a2083b1b9510989`。
它重新核验归档源码、精确字段/来源变化、当前新政策/输入、原 raw 审计不变和原计划
哈希不变；状态 `REBUILT_PUBLIC_MIGRATION_REVIEW_PASS_MAIN_RUN_PENDING` 是运行前审查，
明确不声称执行过新证明。

## 新输入链路

主门禁现在要求 [v2 安装输入](REBUILT_INPUT_ADMISSION.md)位于
`artifacts/decoder-inputs/rebuilt-v2`。包内归档与安装方式不变，原 candidate manifest
继续保存当时状态；当前主门禁的工具选择由新公开政策负责，而不是回写历史输入政策。

公开检查从 v2 的固定 `candidate/extraction.json` 读取配置，使用包内新 Charon、driver、
Aeneas 和 46 个 full-MIR 库。新 Cargo home/target/Charon cache 起始不存在，先执行
`cargo fetch --locked`，随后离线实际提取两个公开根。Aeneas 经显式 OPAM switch 执行，
不使用环境中任意同名工具。Rust 全安装和 OPAM 安装文件集合/哈希/权限/链接在提取前后
及独立验收时重算，并对照固定安装报告。

这仍依赖包外的已固定本地 Rust/OPAM 安装；路径来自固定证据，没有据此声称新 clone
只靠一个输入归档即可运行全流程。主 Sail/基础 Rust 翻译器和主 Lean 安装保持原政策。

公开阶段预期由 47 增至 **48**（增加固定锁下载），原 kernel 审计与两类公开负测仍为
必需。主门禁另加入 v2 输入/位置的两组测试。新增位置/运行环境/下层政策守卫共 10 项；
相关 decoder 测试 99 项在普通 Python 与 `-O` 下通过，公开测试 38 项、主门禁编排测试
18 项通过。这些测试和来源预检不代替正在进行的真实 Lean 编译。

## 后续

等待同一次主门禁结束，核对实际新报告、全部阶段、原定理/合同/公理、两类负测和最终
来源；失败则保留报告并修复具体问题。之后继续处理主 Sail/基础工具的剩余准入和完整
clean-room/release 剩余缺项，不因这次迁移调整 Week5/Week6 验收条款。
后续[维护者演示](MAINTAINER_DEMO.md)已具备本地验收证据，其余六类发布验收仍待完成。
