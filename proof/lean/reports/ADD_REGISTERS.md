# ADD 寄存器层条件性证明

`make proof-registers` 已用 Lean 4.31.0 检查通过（2026-09-07）。它检查两个完整
生成库、实际寄存器效果定理、公理依赖守卫和边界回归；不是完整一步的 `proof-check`。
生成函数、兼容补丁和依赖锁沿用 [ADD 审计](ADD_AUDIT.md)，本次没有改写生成语义。

## 定理与状态关系

[AddRegister.add_registers](../theorems/AddRegisters.lean) 直接比较：

- Rust 生成的 `ckb_vm.instructions.common.add AddBoundary.machineOps`；
- Sail 生成的 `Functions.execute_RTYPE ... .ADD`。

`machineOps` 是提取根实际使用的生产字典，不是另造的理想字典。
[StateRel.lean](../theorems/StateRel.lean) 中的 `state_rel view m s` 对全部
`i : Fin 32` 要求 Sail 的 GPR 值等于 `(gpr (view m) i).bv`。
Sail x0 定义为零，因此该条件强制 Rust x0 为零；x1–x31 通过 `get?` 读取，必须
真的存在，不能用缺键默认值满足关系。关系不包含 PC、内存或平台状态对应。
`key 0 = PC` 只是未使用的哨兵：所有 x0 读取/写入在访问键之前分支返回。

输入是任意有关联的初态、任意 `rd/rs1/rs2 : Fin 32`、`valid m`，以及两个
`RegisterDelegation` 方法合同。Sail 参数使用同一索引的 5 位编码，Rust 使用
经证明保值且小于 32 的 `Usize`。不假设源/目标互异，不限制其他寄存器为零。

结论存在后态 `m'`、`s'`，同时满足：

1. Rust 外层 `Result` 成功；Sail monad 成功且结果为 `RETIRE_SUCCESS`。
2. `valid m'`、`state_rel view m' s'`。
3. 对每个 GPR，若 `rd ≠ 0` 且索引等于 `rd`，新值为旧源值之和模 `2^64`；
   否则保持原值。因此覆盖溢出、x0 抑制、全部寄存器别名情况。
4. 整个 core 投影和整个 Sail 后态分别等于 `putCore`、`putGpr`。它们是描述后态的
   更新表达式，不是被拿来替代生产函数的实现。

[RustAdd.lean](../theorems/RustAdd.lean) 从生成 body 推导数组读取成功、核心 setter
成功及局部更新、合法索引取模不变、真实 u64 wrapping-add 的位向量值、x0 抑制。
[SailRegisters.lean](../theorems/SailRegisters.lean) 从生成 body 推导全部读写分支，
包括寄存器命名/写入回调不额外改变状态，再展开 ADD 分支。

`putCore_frame` 证明投影 PC、next-PC、内存保持；`putGpr_pc` 证明 Sail 的 PC、
nextPC 键不变，`putGpr_frame` 证明其内存、选择源、周期数和输出保持。
这些可通过主定理中的后态等式使用。没有假设 PC 键存在，也没有证明双方 PC/内存
彼此对应。Rust opaque wrapper 的其他隐藏字段不在该 frame 结论内。

## 信任与剩余前提

[AddRegisterAxioms.lean](../theorems/AddRegisterAxioms.lean) 用 `#guard_msgs` 固定
主定理传递依赖的完整 **63 项**：3 个标准逻辑公理、6 个 opaque 类型、54 个
opaque 操作声明。不存在 `sorryAx`，没有新增全局公理来证明寄存器效果。
完整生产字典把未选路径的声明也带入依赖，清单没有将它们隐藏或标为已消除。
Sail ADD 与 Sail PC-frame 引理的依赖仅为 `propext`、`Classical.choice`、`Quot.sound`。
上游 Aeneas 两个 Slice、两个 StringIter 的既有 `sorry` 警告仍会出现，但不在
主定理传递依赖中；不声称整个导入闭包无占位。

传递公理清单不能代替显式参数审计。`view`、`valid` 和两个 wrapper 委托规律仍
在本通用引理中保持参数化；正式最终定理已用 `view = m.inner`、`valid = True`
及两个已证合同实例消除 wrapper 参数，见 [一步定理](ADD_STEP.md)。
常量值、数组界限、加法、x0 抑制和回调效果不再是待证前提。
详见 [剩余义务](ADD_PREMISES.md)。

下一层 PC/dispatch 已通过 [条件性一步定理](ADD_STEP.md) 连接到 `execute_production`
与 `try_step`。wrapper 委托实例已证明；解码字段对应和 Sail 前缀的成功与 frame 仍是明确合同，
通用定理仍保留这些条件。[联合见证](ADD_NONVACUITY.md) 已在一个具体 Sail 模型状态
证明前缀合同，并相对于给定 Rust seed 连接最终定理。
后续[公开解码根](../decoder/toolchain/full-entry/OuterPublicStep.lean)已从同一个原始 ADD 字
推导解码对应，保留取指/Sail 就绪条件；首次集成主门禁复验已通过。
平台 reset 可达性、opaque Rust Machine 非空性和物理内存对应仍未证明，
完整 ADD 指令覆盖仍是 `runtime-only`。

## 回归

[RegisterRegression.lean](../theorems/RegisterRegression.lean) 检查最大 u64 加一回绕、
x0 丢弃、`rd=rs1`、`rd=rs2`、全部别名、缺失 x1 键拒绝和非零 Rust x0 拒绝。
隔离门禁测试为 `python3 scripts/tests/test_lean_imports.py`，同时测试寄存器证明模式的
目标选择、编译失败和缓存 panic 拒绝；这些模拟测试不替代真实 Lean 编译。

寄存器阶段历史实测：完整门禁通过 1849 个 Lake 任务，14 项隔离门禁测试通过。独立临时副本
中的两项负测均返回 1：把最大 u64 加一的结果写成 1 被内核拒绝；用新增公理替代
`add_registers` 的证明后，原公理清单守卫准确报告额外的 `injected_pollution`。
仓库内的证明未被这些污染副本覆盖。Rust/Sail ADD 生成文件与根依赖锁哈希保持不变。
