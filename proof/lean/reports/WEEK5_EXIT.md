# Week 5 Exit gate：逐项验收证据

后续状态：公开 ADD decoder 的独立 47 阶段干净复验已通过，限定工具政策已采纳并接入
主门禁，首次集成实跑已通过，见 [decoder 采纳记录](../decoder/ADOPTION.md)。
下文 12:06–12:35 的原 Week5 通过证据保持为历史结果，其主报告已
[单独归档](../../../artifacts/boundary-check/public-adoption-xQNXpE/before/artifacts/proof-check/report.json)，
不拿它替代新政策下的本次运行，也不改动 Week5/6 验收条款。

本轮目标是执行既有 Week 5 标准，不修改 Week 5/6 的验收条款。
状态：新增边界见证后的复验已通过。2026-09-09 12:06:28–12:35:10 UTC，完整
`make proof-check BACKEND=lean` 返回 0；主报告与其干净构建报告均为 `passed`。
新增内容见 [联合前提见证与边界验证](ADD_NONVACUITY.md)。
2026-09-07 的历史验收证据仍保留在 `artifacts/week5-review/`，不冒充本次结果。

## 未改动的要求

[Week 5](../../../docs/plan/week5.md) 的 Exit gate 原文：

> Lean 4 kernel 从干净构建检查 ADD 定理通过，无未说明 `sorry`/`axiom`；覆盖矩阵链接到定理名、生产 Rust 函数和 Sail 函数。Rocq 只有在 kernel 检查通过时才计入额外证明覆盖。

本轮开始时完整计划文件的 SHA-256：

- `docs/plan/week5.md`：`6ce1f7c509558a23670602ea3b66caf4560a0e08049f4819ff205f929f6c8bc8`
- `docs/plan/week6.md`：`354ee1e4401ef29339695c71219e42be799d1c8563d4a256b7d197138a77cb6c`

两份文件均保持原字节。它们“当前进展”里的旧阶段描述未改，本页记录后续实现与证据，
不以编辑进度说明或验收定义来制造完成。Week 6 的全环境 clean-room、第三方复现
和发布要求仍按原文保留，Rocq NO-GO 不算额外证明覆盖。

## 要求与实现的对应

| Week 5 项目 | 正式实现 / 检查证据 |
|---|---|
| 直接引用生产关联的双侧生成物 | [ProductionAdd.decoded_add_step](../theorems/ProductionAdd.lean) 的结论直接使用 `execute_production` 和 `try_step`；[来源清单](../extraction/ckb-source-baseline.json) 固定修改版身份 |
| operand read 对应 | [RustAdd.rust_read / rust_add](../theorems/RustAdd.lean)、[SailRegisters](../theorems/SailRegisters.lean) 和初态 `state_rel_pc`；最终 GPR 公式读取前态 operands |
| wrapping / sign extension 对应 | `addValue` 与 Sail 使用 64 位 bitvector 加法；本目标 RV64 ADD 无 ADDW 的 32→64 符号扩展操作；回绕引理及 signed/unsigned overflow corpus 均检查 |
| rd 写回与 x0 对应 | 最终定理 `rd ≠ 0 ∧ j = rd` 分支、[RegisterRegression](../theorems/RegisterRegression.lean) |
| PC 更新对应 | [RustDispatch](../theorems/RustDispatch.lean)、[SailDispatch](../theorems/SailDispatch.lean)、[SailRetirement](../theorems/SailRetirement.lean)；最终 PC/nextPC 均为旧 PC + 4 |
| 其他寄存器保持 | 最终定理对所有 `j : Fin 32` 的公式：非目标寄存器等于前态 |
| corpus 覆盖别名、rd=x0、wrapping | 本轮真实差分 [runtime-report.json](../../../artifacts/boundary-check/witness-review.oCqzJ3/runtime-report.json) 及逐案例 artifact；案例名单由实际报告核验 |
| 至少一个 ADD 负面 mutation 被捕获 | 本轮真实 188 次 mutation 的逐项结果与字段定位，包含 ADD 案例；不把 4 项不适用跳过算作成功 |
| 干净构建的 kernel 检查 | [check_lean_clean.py](../../../scripts/check_lean_clean.py) 全新目录、不带入模型/证明/Lean 依赖 `.olean`，`lake --no-cache build` 后独立导出最终定理 |
| 无未说明 sorry / axiom | [policy](../audit/step-policy.json) 枚举完整 137 项依赖、两个合同各 63 项并固定签名/关系；最终定理与合同不依赖 `sorryAx` |
| 追加的前提非空性证据，不修改 Exit gate | [SailContractWitness](../theorems/SailContractWitness.lean) 证明同一状态链上的联合 Sail 合同；[ProductionAddWitness](../theorems/ProductionAddWitness.lean) 相对于给定 Rust seed 应用原最终定理；五个见证均纳入精确依赖审计 |
| 覆盖矩阵连接三方符号 | [coverage.md](../../../docs/coverage.md) 明确链接正式定理、Rust 生产函数和 Sail 源/生成函数 |

## 本次正式证明边界

生产基线为 `ckb-vm-1ffba3977da9-runtime-container-v1`，即上游 commit 加固定补丁，
不是未经修改的 CKB-VM commit。源码版本、提取配置、工具与生成物哈希均由门禁核验。

[WrapperContracts](../theorems/WrapperContracts.lean) 固定 `view = m.inner`、`valid = True`，
从真实生成方法证明 `RegisterDelegation` 和 `PcDelegation`。最终定理不再接受这两个
合同参数；没有以新的行为 axiom 或空有效性不变量补洞。

仍保留初态 `state_rel_pc`、对应 `DecodedAdd`、Sail `StepEntry`、`ActiveAddPath`、
`RetireReady` 和 active-hart 条件。它们不直接假设最终 ADD 执行结果，但本轮没有从
统一原始编码和平台 reset 流程推出这些条件。
新增无参数存在性定理已在一个直接构造的 Sail 模型状态上证明这组 Sail 合同同时成立，
排除合同本身互相矛盾的疑虑；`paired_step seed` 进一步提供初态关系与解码字段合同，
应用原通用定理证明 x3=12、PC/next-PC=`0x80000004` 及后态关系。
它仍需要 Rust `seed : Machine`，不证明无条件的 `Nonempty Machine`。
memory 结论是各侧保持，不是跨侧内存等价。
因此这是明确前提下的生产关联 ADD 定理，不宣称完整指令或整个 VM 无条件正确。

137 项分类为 3 个标准逻辑公理、6 个 Rust/Aeneas opaque 类型、54 个其他 Rust
opaque 操作和 74 个 Sail 外部声明。wrapper 五个方法公理已消除。
四处已知 Aeneas `sorry`（Slice get_unchecked 及 spec、StringIter next/fold）仍明确
记录，不在本定理/合同的依赖中。完整清单与解释见 [PROOF_CHECK.md](PROOF_CHECK.md)。

## 复现与权威报告

本轮正式结果：

- 从零编译完成 1864 个 Lake 构建任务，产生 1805 个新 `.olean`；初始编译模块数为 0。
  复核了新目录的完整导入路径、Aeneas 源码和所有 Git 依赖的固定 revision/干净状态。
- 正式与干净环境的定理审计均通过：最终 137 项依赖，两个 wrapper 合同各 63 项，
  均无 `sorryAx`；原有 18 个边界哈希不变，当前 31 个边界条目全部精确匹配。
  新增五个见证的依赖均属于原 137 项集合；Sail 联合见证为 5 项，双侧实例为 137 项。
- 73 项测试通过：import 门禁 19、真实 Lean 负测 18、proof-check 18、来源守卫 12、
  干净构建守卫 6；另有 17 条既有 Lean 回归引理由内核检查。
- 本轮真实 runtime：32 案例、188 次已应用 mutation 全部通过，4 项不适用跳过。
  其中 ADD 为 13 案例、209 个比较步，76 次已应用 mutation 全部检测并正确定位。
- Week 5/6 完整计划文件与本轮开始时逐字一致；覆盖矩阵三方链接均已核对。

本次通过的是正式门禁按“先生成、再干净构建”顺序执行的 `clean-lean-o_l00b9k`。
较早一次运行因同步测试文案而主动取消，已保留失败/取消记录，没有计为 PASS。
原始 Rust decoder 的真实 factory 提取探针在固定 Aeneas 的分支合流处失败，
单独记录为 `extraction-failed`；不把这个诊断失败算作形式化门禁成功，也不宣称解码已证明。

逐项机器可读核验见 [completion-audit.json](../../../artifacts/boundary-check/witness-review.oCqzJ3/completion-audit.json)，
依赖差异复核见 [policy-review.json](../../../artifacts/boundary-check/witness-review.oCqzJ3/policy-review.json)，
本轮主报告的稳定快照见 [final-proof-report.json](../../../artifacts/boundary-check/witness-review.oCqzJ3/final-proof-report.json)。

```bash
make ckb-baseline
make proof-check BACKEND=lean
cargo run --locked -p ckb-vm-sail-diff -- --corpus --mutate --json --artifact-dir artifacts/boundary-check/witness-review.oCqzJ3/corpus
```

干净 clone 先按源码基线说明显式运行 `make ckb-baseline-apply`。
证明主报告是 [artifacts/proof-check/report.json](../../../artifacts/proof-check/report.json)，
其中 `clean_build` 指向本次新目录及独立审计结果；单看旧日志不能证明本轮成功。
干净构建复用固定 Lean 编译器及标准库，不复用项目/第三方 Lean 支持库的编译产物，
不等于重装所有工具、验证运行二进制来源或完成 Week 6 发布。

`docs/coverage.md` 的完整指令状态仍是 `runtime-only`，Theorem 栏单独链接本条件性
内核定理；不通过把状态改成 `proved` 来代替实际证明和检查。
