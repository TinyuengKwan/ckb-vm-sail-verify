# Lean 4 主证明路径

生产来源是[受审的 upstream + runtime-container 补丁](extraction/ADOPTION.md)，
不是未经修改的 CKB-VM commit。两侧生成物统一在 Lean 4.31.0 下构建。

## 已检查的定理

| 定理 | 结论 | 传递依赖 |
|---|---|---|
| [ProductionAdd.decoded_add_step](theorems/ProductionAdd.lean) | 已解码的 ADD 经生产 `execute_production` 与 Sail `try_step` 后，GPR、PC/next-PC 对应，各侧内存保持 | 137 项 |
| [OuterAdd.cold_public_add_step](decoder/toolchain/full-entry/OuterPublicStep.lean) | 从同一个原始 32 位 ADD 字出发，经真实公开 `InstDecoder::decode`（MOP 关闭、冷缓存）得到上述结论；解码对应是结论而非前提 | 158 项 |
| [AddWitness.sail_contracts_jointly_inhabited](theorems/SailContractWitness.lean) | 一个具体 Sail 状态同时满足全部 Sail 侧前提，排除 Sail 侧空洞 | 5 项 |

依赖项全部由 [step-policy.json](audit/step-policy.json) 与
[public-policy.json](decoder/public-policy.json) 逐项枚举并分类，无 `sorryAx`。

## 仍然显式保留的前提

- 初态关系 `state_rel_pc`、Rust 的 size/load 合同、Sail 的取指/入口/退休条件。
- 平台 reset 可达性：见证状态是直接构造的，不是从 `init_model` 推出的。
- Rust opaque `Machine` 的非空性：联合实例以 `seed : Machine` 为参数。
- 跨侧物理内存对应、生产 `SparseMemory` 实现、MOP 开启时的融合语义、非 ADD 指令。

因此报告标为 `conditional`，覆盖矩阵仍是 `runtime-only`。

## 命令

```bash
make proof-gen BACKEND=lean   # 生成并编译 Sail 侧
make proof-gen-rust           # 提取并编译 Rust 侧
make proof-imports            # 双侧共同 import
make proof-step               # 一步定理与依赖守卫
make proof-check BACKEND=lean # 完整门禁：重新生成、干净构建、审计、负测（约 35 分钟）
```

门禁的阶段划分和验收边界见 [reports/PROOF_CHECK.md](reports/PROOF_CHECK.md)。

## 目录

- `theorems/`：正式定理与 Lake 工程，见 [theorems/README.md](theorems/README.md)。
- `decoder/`：解码对应层与限定采纳的翻译器基线，见 [decoder/README.md](decoder/README.md)。
- `audit/`：依赖导出与 policy。
- `extraction/`：源码基线与提取配置。
- `compat/`：Sail 生成物的类型作用域适配，见 [compat/README.md](compat/README.md)。
- `generated/`：生成物，不手工编辑，已忽略。
- `reports/`：各阶段的历史报告，按时间顺序：
  [ADD_AUDIT](reports/ADD_AUDIT.md) →
  [ADD_REGISTERS](reports/ADD_REGISTERS.md) →
  [ADD_STEP](reports/ADD_STEP.md) →
  [ADD_PREMISES](reports/ADD_PREMISES.md) →
  [WEEK5_EXIT](reports/WEEK5_EXIT.md) →
  [ADD_NONVACUITY](reports/ADD_NONVACUITY.md)。
  它们记录当时的结论和边界，后来的进展不回写旧报告。
