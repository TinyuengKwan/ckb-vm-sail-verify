# 当前状态

更新至 2026-10-09。范围定义见 [计划总览](plan/overview.md)；证据范围见 [覆盖矩阵](coverage.md)；
边界与已知缺口见 [语义缺口](semantic-gaps.md)。过程记录在 [`history/`](history/README.md)。

## 已发布

`week6-0.1.0`：候选 `efd68db8b44077c4afa52cb12d13ff0814da9134`，
[release 399743221](https://github.com/TinyuengKwan/ckb-vm-sail-verify/releases/tag/week6-0.1.0)，
不可变，三个资产（主包、主包 SSH 签名、固定工具包）。该版本在所有者定义的
`ckb-spark-delivery-v1` 范围下完成交付：十一项交付要求有机器验收记录，第三方复现按所有者
2026-09-28 的决定交由 CKB 官方接收后开展，`third_party_reproduced=false`。
完整记录见 [`history/WEEK6_STATUS.md`](history/WEEK6_STATUS.md)。

## 证据概况（候选 efd68db，全新 VM 实跑）

| 项 | 结果 | 边界 |
|---|---|---|
| 运行时差分 | 33 个注入案例（ADD 13 / ADDI 10 / BEQ 10），398 步，两端逐字段一致，每案例可重放 | 语料外输入不作声明；见覆盖矩阵 |
| Mutation | 6 类共 194 次注入全部被检出并定位到字段 | 对记录轨迹做的，不是对实现的变异测试 |
| Rust 测试 | 78 项通过 | — |
| Lean 4 | 生产关联的条件性 ADD 步精化定理由 kernel 检查；公理集合已审计，无 `sorryAx` | 显式前提、内存耦合、平台复位可达性、cycle 均在定理之外 |
| Rocq | 11 阶段 NO-GO，含最小复现 | 不计入证明覆盖 |
| clean-room | 16 阶段在全新 KVM guest 内退出 0；CI 五任务成功并有 attestation；外部双份下载与重放通过 | VM 记录为操作者签署，不是平台签名执行 |
| 第三方复现 | 未开始 | 交付后由 CKB 官方按文档开展 |

指令级状态仍为 `runtime-only`；ADD 的定理单独记在覆盖矩阵的"Theorem"列。
本仓库不声称 CKB-VM 整体或任何指令族已被完整形式化验证。

## 进行中

验收流程已按 [发布与验收流程](RELEASE.md) 简化（目标版本 `week6-0.2.0`）：证据槽从十二个减到六个、
所有者签名 tag 作为审批、单一验证基础、单一政策文件 [`policy.json`](release/policy.json)、过程记录
移出公开结论检查范围。`week6-0.2.0` 尚未冻结候选、尚未在全新 VM 中实跑，也尚未发布；
证明覆盖、产品代码与 `week6-0.1.0` 的任何内容不变。
