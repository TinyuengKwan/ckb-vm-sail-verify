# ADD 剩余前提与证明边界

本文件记录常量补齐后的合同。寄存器层及 dispatch/PC 的条件性一步定理均已完成；
两个 wrapper 合同的具体生产实例现已证明；执行层仍显式接收解码与 Sail 前缀合同。
新增[公开解码根](../decoder/toolchain/full-entry/OuterPublicStep.lean)已从同一个原始 ADD 字
推导解码对应，仅保留状态/取指/Sail 就绪条件；限定采纳已落实，首次集成主门禁复验通过。
已证范围见 [寄存器层](ADD_REGISTERS.md) 和
[条件性一步精化](ADD_STEP.md)。wrapper/编码接口为
[AddPremises.lean](../theorems/AddPremises.lean)，常量值检查为
[ExtractedConstants.lean](../theorems/ExtractedConstants.lean)。两者都由
`make proof-imports` 编译；接口没有新增全局公理。正式实例位于
[WrapperContracts.lean](../theorems/WrapperContracts.lean)，由 `make proof-step` 一并检查。

常量阶段历史实测（2026-09-07）：两次完整 Rust 提取产物逐字节相同；共同构建通过 1841 个
Lake 任务，依赖锁不变；9 项隔离门禁测试通过。错误常量值 31 的证明被 Lean
拒绝，另加未证前提的污染证明也被公理依赖守卫拒绝，两项负测均返回 1。

## 1. 已消除的常量前提

Charon 原先将两个已到达的跨 crate 常量标为 `Foreign`。生成脚本增加精确的
`--include` 后，LLBC 中二者为 `Transparent`，Aeneas 输出为：

| 源常量 | 当前生成定义 | 作用范围 |
|---|---|---|
| `ckb_vm_definitions::RISCV_GENERAL_REGISTER_NUMBER` | `def ... : Usize := 32#usize` | ADD 的 `update_register` |
| `ckb_vm_definitions::registers::RA` | `def ... : Usize := 1#usize` | far-jump 等其他 dispatch 分支，不是 ADD 行为前提 |

没有修改 Rust 常量、复制实现或手改 Lean 生成物。生成的常量读取由 monadic bind
变成纯值引用，因而不再需要“常量成功返回 32/1”这一前提。
`register_count_eq`、`ra_eq` 通过展开生成定义和 `rfl` 证明；它们的实际公理依赖均
为 `propext`、`Classical.choice`、`Quot.sound`，**不是零公理**。
`#guard_msgs` 固定这一依赖范围，拒绝 `sorryAx`、新常量公理或其他额外依赖。

新生产基线文件级计数是 285 个 `def`、51 个 `axiom`。原 LLBC 的其余四个全局量为
`Register<u64>::BITS/SHIFT_MASK` 和标准库整数 `MIN/MAX`：前两者已有生成定义，
后两者由 Aeneas 标准库模型处理；没有其他待补的生成常量 axiom。
这不表示其他指令的外部函数/类型已补齐。

## 2. 生产 wrapper：精确到五个方法

`AddBoundary.Machine` 是提取根使用的生成类型，`machineOps` 复用生成的生产字典。
`production_dictionary` 以 `rfl` 核对其与 `execute_production` 实际使用的字典一致；
它只证明这个定义等式，不证明 wrapper 委托。

寄存器定理显式接收 `view : Machine → Core`、`valid : Machine → Prop` 及前两个方法合同；
一步定理还使用下列三个 PC 方法合同。
`Core` 直接是生成的 `DefaultCoreMachine U64 (SparseMemory U64)`，不是另写的理想机器。
采用受审容器化补丁后，wrapper 是真实生成 structure。`ProductionWrapper.view m = m.inner`，
`valid m = True`；任意给定机器均满足 valid。两个合同从实际委托定义和 core 操作引理
证明，足以串接 PC staging → ADD → commit。最终 `ProductionAdd.decoded_add_step`
内部提供实例；通用层定理仍保留抽象参数以供复用。后续已构造一个具体 Sail 联合见证，
但 opaque Rust 对象仍由 seed 提供，见 [联合前提见证](ADD_NONVACUITY.md)。

| 合同字段 | 所需规律 | 使用层次 |
|---|---|---|
| `RegisterDelegation.registers` | 在有效状态上，真实 wrapper 的读取结果等于生成 core 的读取结果 | ADD 寄存器叶引理 |
| `RegisterDelegation.set_register` | 对非零且小于 32 的索引，真实写入成功、保持有效性，投影后态等于生成 core 写入的成功后态 | ADD 寄存器叶引理 |
| `PcDelegation.pc` | 真实读取等于生成 core 的当前 PC 读取 | 含 PC 的生产执行 |
| `PcDelegation.update_pc` | 真实操作成功、保持有效性，投影结果等于生成 core 的 next-PC 更新 | 含 PC 的生产执行 |
| `PcDelegation.commit_pc` | 真实操作成功、保持有效性，投影结果等于生成 core 的 PC 提交 | 含 PC 的生产执行 |

生成 core 的寄存器读取返回长度固定为 32 的数组切片；写回、PC 更新和提交都有
body。合同对**整个 core 投影**约束后态，包含其他寄存器、内存及无关 core 字段的
frame 条件；寄存器操作及 PC 暂存/提交性质已从生成 body 推导并连接到生产入口。
不声称 wrapper 的 syscall/debugger/decoder 等全部隐藏状态不变。

只对非零目标要求 `set_register` 委托：抑制 x0 写入必须从生成的 `update_register`
证明，不能假设底层 setter 自带抑制。若 `rd = 0`，仍须保证源寄存器读取成功。
不需要为 ADD 另加内存读写、四个比较函数、`ecall/ebreak`、ISA/version 查询的行为
公理，因为选中的 ADD 路径不调用它们。完整生产字典的声明依赖仍含这些符号，不能
从最终 `#print axioms` 报告中静默删除。

## 3. 状态和输入条件，不是新的公理

寄存器叶引理选择生成的 `common.add machineOps` 与 Sail `execute_RTYPE ... .ADD`：

- `valid m`；CKB x0 初值为零，32 个 GPR 与 Sail 对应，比较值使用 `U64.bv`。
- Sail x1–x31 对应键存在；x0 的读取由生成定义返回零。不能用“存在的键值相等”
  代替键存在性，也不限制所有寄存器初值为零。
- `rd/rs1/rs2 < 32` 且与 Sail 的 5 位 `regidx` 对应；允许任意源/目标别名。
- 两个寄存器委托合同。常量、加法模 `2^64`、索引成功、x0 抑制及 Sail 回调的
  frame 性质由已有定义证明，不作为“ADD 已执行正确”的假设。

包含 CKB PC/dispatch 时，额外使用 `PcDelegation` 和 `DecodedAdd`：后者逐项写明
`extract_opcode inst = ok 1#u16`、`instruction_length inst = ok 4#u8` 及三个字段
读取等式和界限。这里的 `inst` 是内部 `u64` 编码，不是原始 `u32` 机器码；这些
条件本身不是 decoder 正确性证明。新增公开解码层从任意满足 ADD 位模式的原始字
证明这些条件，见 [逐项审计](../decoder/COMPLETION_AUDIT.md)；本执行层接口保持不变。
项目范围仍是 RV64、VERSION2 的正常 32 位 ADD；不扩展到 C.ADD、ADDW、MOP 或 JIT。

## 4. Sail 完整步骤：不得隐藏的额外义务

寄存器叶引理不需要 hart/中断/取指前提，也不推进 PC。当前一步定理已连接生成的
`run_hart_active` / `try_step`，按以下方式处理外围：

1. 前缀读取成功：`cur_privilege` 等所读状态已初始化，`dispatchInterrupt` 返回
   `none`；`ext_fetch_hook (fetch ())` 走 `.F_Base w`，`ext_decode w` 得到对应
   `.RTYPE (rs2, rs1, rd, .ADD)`，landing-pad 检查不走 trap 分支。前缀操作的
   GPR/PC/数据内存 frame 性质通过 `ActiveAddPath` 显式列出，并已有具体 Sail 联合见证。
   新公开根使用不含解码结果的 `RawFetchPath`，在内部推导 `ActiveAddPath`。
   这些合同命名每个中间状态，没有假设 `execute` 或整个 step 的结果。
2. 真实 `.F_Base` 分支内的 `nextPC := PC + 4` 及后续 `tick_pc` 已连接。
   `state_rel_pc` 要求当前 PC 键存在；旧 nextPC 无显式存在/对应要求，正常路径先写后读。
3. `StepEntry` 显式约束 `should_inc_minstret` 决策及其 frame；`hactive` 和
   `RetireReady` 列出两个 hart 检查、increment 标志和有条件的计数器键需求。
   退休及计数器两条分支均已证明；当前生成模型 RVFI 开关为 false，启用配置尚未覆盖。
   所选前后 step hook 和回调由生成 body 展开，不增加“回调正确”的新公理。

这些合同已足以形式化证明所选正常路径的一步结论。`AddWitness.sail_contracts_jointly_inhabited`
进一步在同一具体模型状态链上证明了联合可满足性，并由 `paired_step seed` 连接最终定理；
这**不是最弱条件集、任意正常初态的证明或实际平台 reset 可达性证明**。
Sail monad 失败、非成功退休、Rust 外层失败与内层
VM 错误已在相应合同下排除；无条件生产正确性仍不可宣称。

翻译器、固定依赖、本地 Aeneas 来源及其已有 `sorry` 仍按
[ADD 审计](ADD_AUDIT.md) 和 [VERIFICATION.md](../../../VERIFICATION.md) 记录。
寄存器与一步定理的传递 axioms 和显式参数均已审计，并以精确清单守卫；一步定理的
依赖为 137 项，不能套用叶定理的较小清单。`make proof-step` 检查新定理，覆盖仍为
`runtime-only`。[proof-check](PROOF_CHECK.md) 现已接入重新生成及完整依赖/前提审计，
以 `conditional` 验收。新增公开根的 158 项依赖另按固定快照检查，不能沿用 137 项清单。
通用初态/取指/Sail 就绪条件、物理内存对应和 `audit-release` 仍未关闭；
不能再将新增根的同码解码对应列为假设。
