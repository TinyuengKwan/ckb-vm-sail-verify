# 当前状态

更新至 2026-10-10。范围定义见 [计划总览](plan/overview.md)；证据范围见 [覆盖矩阵](coverage.md)；
边界与已知缺口见 [语义缺口](semantic-gaps.md)。过程记录在 [`history/`](history/README.md)。

## 已发布

`week6-0.2.0`（2026-10-10）：候选 `08a6dd20d97f2aef636fdca57c7f6dd15f742f1c`，源码快照 `484ca0d4…`，
[release 408662700](https://github.com/TinyuengKwan/ckb-vm-sail-verify/releases/tag/week6-0.2.0)，
不可变。按 [发布与验收流程](RELEASE.md) 的六槽聚合，runtime、lean、rocq、clean_room、release 五槽
verified，`third_party` 为 deferred，普通与 `-O` 两种模式结论一致；聚合报告 SHA-256
`c7847003…` / `d32ec2fe…`。第三方复现待 CKB 官方按 [发布与验收流程](RELEASE.md) 开展，
`third_party_reproduced=false`。

| 资产 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `ckb-vm-sail-verify-week6-0.2.0.tar.gz` | 649,792,735 | `0f7f575c012dd39da8f24a53d73bc0410b74ee83aa5023aacf54accb4f43476b` |
| `ckb-vm-sail-verify-week6-0.2.0.tar.gz.sig` | 314 | `bee7ebab83337f9961328c048180d80c98e46f277a5420fb93f6ab8d10680a82` |
| `extra-installations.tar.xz` | 1,801,059,088 | `c8e8ca2797aeabcbee3935949f6ad6b622a40468d77a7f5d79a50b1854a67ff4` |

审批是所有者对候选 commit 的 SSH 签名 tag `week6-0.2.0`（签名者 `kwantinyueng@gmail.com`，
指纹 `SHA256:fhxGdS6E9GW7qqXlnIsFOWlqZTKYVqe+echXbA3/Tl0`），主包以同一密钥在命名空间
`ckb-vm-sail-release` 下签名。clean-room 在全新 KVM guest（环境 id `fa770674…`）内 11 阶段退出 0，
CI run [37977244862](https://github.com/TinyuengKwan/ckb-vm-sail-verify/actions/runs/37977244862)
三个任务成功、attestation 覆盖证据 bundle、外部两次下载相同、归档二进制重放通过。
VM 记录为操作者签署，不是平台签名执行。

`week6-0.1.0`（2026-09-30）：候选 `efd68db8b44077c4afa52cb12d13ff0814da9134`，
[release 399743221](https://github.com/TinyuengKwan/ckb-vm-sail-verify/releases/tag/week6-0.1.0)，
按当时的十二槽流程在 `ckb-spark-delivery-v1` 范围下交付，记录见
[`history/WEEK6_STATUS.md`](history/WEEK6_STATUS.md)。两个版本的产品代码与证明覆盖相同。

## 证据概况（候选 08a6dd2，全新 VM 实跑；与 efd68db 相同）

| 项 | 结果 | 边界 |
|---|---|---|
| 运行时差分 | 33 个注入案例（ADD 13 / ADDI 10 / BEQ 10），398 步，两端逐字段一致，每案例可重放 | 语料外输入不作声明；见覆盖矩阵 |
| Mutation | 6 类共 194 次注入全部被检出并定位到字段 | 对记录轨迹做的，不是对实现的变异测试 |
| Rust 测试 | 78 项通过 | — |
| Lean 4 | 生产关联的条件性 ADD 步精化定理由 kernel 检查；公理集合已审计，无 `sorryAx` | 显式前提、内存耦合、平台复位可达性、cycle 均在定理之外 |
| Rocq | 11 阶段 NO-GO，含最小复现 | 不计入证明覆盖 |
| clean-room | 11 阶段在全新 KVM guest 内退出 0；CI 三任务成功并有 attestation；外部双份下载与重放通过 | VM 记录为操作者签署，不是平台签名执行 |
| 第三方复现 | 未开始 | 交付后由 CKB 官方按文档开展 |

指令级状态仍为 `runtime-only`；ADD 的定理单独记在覆盖矩阵的"Theorem"列。
本仓库不声称 CKB-VM 整体或任何指令族已被完整形式化验证。

## 交付后事项

- 第三方复现：由 CKB 官方按 [发布与验收流程](RELEASE.md) 在全新环境中执行，交回签名声明后
  由所有者登记公钥、聚合器验收。在此之前不作任何复现声明。
- 文档勘误：`RELEASE.md` 第 4 步的命令应为 `python3 scripts/ci_evidence.py --run-id … --candidate … --out …`
  （没有 `collect` 子命令）；`release_package.py build` 的 `--out` 必须位于候选检出的 `artifacts/` 之下，
  否则最终聚合无法引用其记录。这两处在 `08a6dd2` 之后修正，不影响已发布版本。
