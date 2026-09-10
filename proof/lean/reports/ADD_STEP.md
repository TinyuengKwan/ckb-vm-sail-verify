# ADD dispatch 与 PC：条件性一步精化

`make proof-step` 检查 [ProductionAdd.decoded_add_step](../theorems/ProductionAdd.lean)，直接连接
生成的 Rust `execute_production` 和 Sail `try_step`。2026-09-07 实测通过。
这是一条**对应解码结果及明确 Sail 前缀条件下**的定理；wrapper 委托已由
[两个实际合同实例](../theorems/WrapperContracts.lean) 证明。它不是无条件
生产正确性、raw decoder 正确性或完整 VM 证明。覆盖矩阵仍保持 `runtime-only`，
Theorem 栏单独记录此进展。

2026-09-09 增补：[联合前提见证](ADD_NONVACUITY.md) 在同一具体 Sail 状态链上
构造全部入口合同，并以 Rust seed 为唯一输入连接本通用定理。它补充非空性证据，
不替换本通用定理，也不证明 raw decoder 对应、reset 可达性或 `Nonempty Machine`。

同日后续：[公开解码层](../decoder/toolchain/full-entry/OuterPublicStep.lean)另证
`OuterAdd.cold_public_add_step`，从同一个原始 ADD 字推导双方解码并调用本执行层定理。
该新增根为 IMC+B、VERSION2、MOP-off 配置，依赖 158 项；本页原 137 项根及其显式参数不变。
限定工具采纳和主门禁接入已落实，首次集成复验通过，见 [采纳记录](../decoder/ADOPTION.md)。

## 实际连接的路径

| 侧 | 经生成定义验证的执行顺序 |
|---|---|
| Rust | `execute_production → execute`：读 PC、长度转 u64、计算 `PC + 4`、`update_pc → execute_instruction → handle_add → common.add → commit_pc` |
| Sail | `try_step`：计数器决策、写 increment 标志、检查 hart → `run_hart_active` 的正常 `.F_Base` 分支：中断/取指/解码/landing-pad 前缀、写 `nextPC := PC + 4`、`execute → execute_RTYPE ADD` → 检查成功退休时 hart active → `tick_pc`、条件性 minstret 更新、post-step 回调 |

Rust 分派选取内部 opcode 1；Sail 分派选取 `.RTYPE (rs2, rs1, rd, .ADD)`。
现有寄存器叶定理被复用，没有复制 ADD 实现。`stageCore`、`commitCore`、`stageSail`
和 `retiredState` 只是后态描述；生成入口与这些描述之间的等式均由 Lean 验证。
PC 更新不是外部行为假设，也没有拿手写的 `PC + 4` 执行器代替真实路径。

`state_rel_pc` 在已有全部 GPR 对应上增加 `Sail PC = some Rust.pc.bv`。
初态 PC 键必须存在；关系本身**不要求旧 next-PC 相等或 Sail 旧 nextPC 键存在**，
正常执行分支会在提交读取之前写入它；外围操作仍须满足各自的成功合同。
中间阶段建立 next-PC，提交后两侧均为旧 PC 加 4。
这里没有 PC 对齐假设；[联合见证](ADD_NONVACUITY.md)已给出具体取指/解码前提实例，
但不是任意 PC 的可满足性或平台 reset 可达性证明。

## 主定理结论

存在 `m'`、`s'`，同时满足：

- Rust 返回外层 `.ok (.Ok (), m')`，排除 Aeneas 失败及内层 VM 错误。
- Sail `try_step` 返回 `.ok false s'`。这里 `false` 是生成接口的正常 active 路径
  返回值，不是失败；子定理 `run_hart_add` 另证其内部结果为
  `.Step_Execute (RETIRE_SUCCESS, w)`。
- `state_rel_pc ProductionWrapper.view m' s'`；双方 PC、next-PC 都是旧 PC 加 4，模 `2^64`。
- 逐一给出 32 个 GPR 的效果，覆盖任意源/目标别名、x0 抑制和算术溢出。
- Rust core 投影的内存不变；Sail 内存在所列前缀 frame 条件下不变。
  **不是双方内存内容彼此相等的证明**，也不声称 opaque wrapper 的所有隐藏字段不变。

## 已证 wrapper 连接与剩余显式前提

源码采用 [upstream + runtime-container 补丁基线](../extraction/ADOPTION.md)，不是未修改
的上游 commit。`view m = m.inner`、`valid m = True`，任意给定机器均被接纳。
`registerDelegation` / `pcDelegation` 展开真实生成委托定义完成证明，不是新公理，
最终定理不再量化这些合同或有效性证明；这不等于构造 opaque runtime 或完整初态。

| 前提 | 精确作用 | 当前边界 |
|---|---|---|
| `state_rel_pc ProductionWrapper.view m s` | 所有 GPR 对应（含 x0）以及 PC 对应 | 调用前的初态关系仍是条件 |
| `DecodedAdd` | Rust 内部 u64 编码的 opcode、长度 4、三个寄存器字段对应 | 本执行层接收该合同；新增公开根已从原始 ADD 字通过真实 decoder 推导它 |
| `StepEntry` | `cur_privilege` 读取、实际 `should_inc_minstret` 决策成功；记录决策后状态及 GPR/PC/内存 frame | 已在一个具体模型初态推导；通用初始化与 reset 可达性仍未证明 |
| `ActiveAddPath` | 按顺序记录 `dispatchInterrupt = none`、`fetch = F_Base w`、`ext_decode = RTYPE ADD`、`is_landing_pad_expected = false` 及各中间状态 | 前缀成功与其总 GPR/PC/内存 frame 是明确合同；不假设整个状态不变，不假设 ADD 执行结果 |
| `hactive`、`RetireReady` | 开始 dispatch 时及执行 ADD 前的 hart active；increment 标志存在；标志为 true 时 minstret 键存在 | 全部要求在 ADD body 前的已命名状态上成立；非增量路径不要求计数器键存在 |

`ArchFrame` 只约束 GPR、当前 PC 和 Sail 内存，允许前缀改变其他平台字段。
实际取指若会更新页表内存，不能直接套用这里的内存 frame，必须证明相应模式下
frame 成立或明确扩大关系。`noLandingPad` 选择 false 是充分条件，不声称是最弱前提。
`RetireReady.increment` 描述前缀完成时的真实标志，不默认它与更早的决策值相等。

两个输入分别为 CKB 内部 `inst : U64` 与 Sail 原始 `w : BitVec 32`，通过上述
对应解码结果连接；没有偷偷假设二者数值相同。本执行层本身不证明编码转换，
该连接已由新增公开解码层提供。

## 固定配置与公理审计

当前生成的 `get_config_print_instr ()` 和 `get_config_rvfi ()` 都是 `false`。
证明展开这些生成定义；它不是任意配置定理，尤其不覆盖 RVFI 打开后的额外读取和
记录更新，更不是运行时 RVFI exporter 的正确性证明。前后 step hook 和所选回调
由当前生成 body 展开。计数器增量两条分支都已证明。

[AddStepAxioms.lean](../theorems/AddStepAxioms.lean) 用精确 `#guard_msgs` 清单锁定：

| 定理 | 传递 axiom 数 |
|---|---:|
| `ProductionAdd.decoded_add_step` / 通用 `AddStep.decoded_add_step` | 137 |
| `rust_production_add` | 63 |
| 两个 `ProductionWrapper` 合同（各自） | 63 |
| `run_hart_add` | 76 |
| `sail_try_step_add` | 77 |

主定理为 3 个标准逻辑公理、60 个 Rust/Aeneas opaque 声明及 74 个 Sail opaque
声明的并集，没有 `sorryAx`，没有新增全局公理来填证明。Rust 部分与寄存器定理的
清单相同；Sail 完整分派新增了 `RiscvExtras.lean` 中的浮点、随机数、reservation、
终端及实验扩展声明，包括未选路径的声明，**不是它们已被证明或从依赖中消除**。
不能沿用 Sail 寄存器叶引理仅有 3 个标准逻辑公理的结论描述此一步定理。
上游 Aeneas 的 4 个既有 `sorry` 警告仍被记录，但不在这些定理的传递依赖中。

Rust 生成物已随受审补丁再生成；根依赖锁保持不变。完整来源与精确依赖见
[policy](../audit/step-policy.json) 和 [审计门禁](PROOF_CHECK.md)。
本次引用的 `Step.lean` SHA-256 为
`a4b8d4863b9869a6ddf9f0e724fc73da6e7c03d51f23747ca22a0a4d82a2b620`，
`PcAccess.lean` 为 `3a140f0ee40354c4534c207f2f8088865f4d62e7c8414ecad9bf68ed7a3cd9b2`。

## 验证与下一步

```bash
make proof-step
python3 scripts/tests/test_lean_imports.py
python3 scripts/tests/test_lean_step.py
```

2026-09-07 的正式步骤构建通过 1861 个 Lake 任务。当时 19 项 import 门禁测试和 12 项真实 Lean
负测分别检查构建失败封闭、双方错误 PC 效果、wrapper 投影/有效性/写回错误、
公理污染以及不改变公理集合的额外 `False` 前提（由签名审计拒绝）。负测只改临时
副本。`StepRegression.lean` 另有 10 个内核检查的边界引理，涵盖 PC/计数器回绕、
x0 仍推进 PC、旧 next-PC 无关、缺失 PC 拒绝及计数器键的条件性需求。

后续新增具体 Sail 联合见证与 `paired_step seed`；新增证明及负测见
[非空性边界](ADD_NONVACUITY.md)。通用初始化/可达性与 Rust opaque
对象的非空性仍未消除，不因 Week 5 的条件性定理验收而被宣布已证明。
原始 ADD 解码对应已由新增公开根推导；实际取指接口合同和物理内存耦合仍是边界。
`make proof-check BACKEND=lean` 现已接入重新生成、来源及最终定理公理/前提审计，
详见 [门禁说明](PROOF_CHECK.md)。它以 `conditional` 验收上述定理，另强制全新目录的
模型/证明/Lean 依赖重建；`proof-step` 只是其构建子步骤，`audit-release` 尚未完成。
