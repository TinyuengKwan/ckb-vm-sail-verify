# ADD 依赖与定理边界审计

版本说明：下文保留原始未修改 CKB 源码的历史审计分析（63 个文件级公理、141 项
一步定理依赖、opaque wrapper），不能用来描述新的容器化生产模型。
当前源码为 [upstream + 固定补丁](../extraction/ADOPTION.md)，wrapper 五个方法及两个
合同已有实际定义/证明；最终 `ProductionAdd.decoded_add_step` 为 137 项依赖。
当前权威清单与边界见 [PROOF_CHECK.md](PROOF_CHECK.md) 和 [step-policy.json](../audit/step-policy.json)，
Week 5 验收证据见 [WEEK5_EXIT.md](WEEK5_EXIT.md)。以下历史计数不充当新基线的验收结果。

本报告审计生产源码、Lean 生成物和支持库。寄存器层及 dispatch/PC 条件性一步定理
已完成，见 [寄存器层](ADD_REGISTERS.md) 和 [一步证明及扩大的公理清单](ADD_STEP.md)；
当前 ADD 完整指令覆盖仍为
`runtime-only`。两侧现已在共同 Lean 4.31.0 工程中完成实际 import 编译，兼容补丁和
门禁记录见 [兼容性报告](../compat/README.md)；导入本身不证明精化，已有精化仍依赖明确合同。

## 1. 证据基线与复现

审计基线为项目 commit `1ef21d7818029356e991dc3ed8a31b26859559e8` 的工作树：

| 项目 | 标识 |
|---|---|
| CKB-VM | `1ffba3977da9dcdef8092e9ab1fd2516b27ec939` |
| sail-riscv | `8f91355eee63a85738723603e23d32eecdd763dc` |
| Rust Lean 工程 | `leanprover/lean4:v4.31.0` |
| Sail Lean 工程 | 首次审计为 4.29.0；共同工程复查为 `leanprover/lean4:v4.31.0`，带已记录的类型作用域补丁 |
| `CkbVmProduction.lean` SHA-256（常量补齐后） | `1ecadb703f18cea0db18cad91012c5e2ed3d95a8a9beea02a52a1ca36fba3f51` |
| `InstsEnd.lean` SHA-256 | `0aaf3f0e9cfc0e25631e180f3a08142a60196701ff229c1071c2e0fd2e5028f3` |

完整生成版本见 [VERIFICATION.md](../../../VERIFICATION.md) §1、
[生成记录](../generated/rust/TOOLCHAIN.txt) 与两侧 `lake-manifest.json`。
Rust 生成物含 281 个 `def`、63 个 `axiom`；这不是 ADD 的依赖计数。
精确提取寄存器总数与 RA 后，它们从 axiom 变为纯定义；原基线为 279/65。
常量值引理及剩余前提见 [ADD_PREMISES.md](ADD_PREMISES.md)。
Aeneas 支持库通过本机路径引用，生成脚本核对 Charon/Aeneas 可执行文件版本及
支持库工具链；这些检查不能保证本地支持库未修改。共同工程锁定 mathlib 和传递
Git 依赖，并核对实际 checkout；后续 clean-room 门禁仍需核对本地 Aeneas 库的来源
与内容。现有 `proof-check` 已增加本地 Aeneas 源码内容及工具二进制哈希核验，
并与所记录的安装归档建立内容对应；这不是 clean-room 或上游签名认证，见
[门禁来源边界](PROOF_CHECK.md)。

在已生成并编译两侧模型的环境中，从仓库根运行诊断查询：

```bash
make proof-imports
(cd proof/lean/theorems && lake env lean ../audit/RustDependencies.lean)
(cd proof/lean/theorems && lake env lean ../audit/SailDependencies.lean)
```

[RustDependencies.lean](../audit/RustDependencies.lean) 与
[SailDependencies.lean](../audit/SailDependencies.lean) 只做 `#check` / `#print axioms`，
不包含定理、占位证明或新公理。查询成功表示符号可导入、依赖可检查，不是证明 PASS。
生成物或支持库变化后需重跑查询并复核本报告。此次共同工具链实现后，上述两项查询
已在 4.31.0 共同工程中重跑；常量补齐后再次运行 Rust 查询，均退出 0。
下面的归纳已移除常量值 axiom，未出现 `sorryAx`。

### 本轮 Lean 查询结果

两条命令均已执行，退出码为 0。以下为实际输出的归纳；`L` 表示
`propext`、`Classical.choice`、`Quot.sound` 三个标准逻辑公理。
Rust 符号省略 `ckb_vm_sail_extract`，Sail 符号省略 `LeanRV64D.Functions`。

| 查询对象 | `#print axioms` 的结果 |
|---|---|
| Rust 两个常量定义及其值引理 | 只有 L；不再有常量值 axiom |
| Rust `common.add`、`update_register`、`handle_add` | L，加 `bytes.bytes.Bytes`、`Aeneas.Std.core.fmt.Formatter` |
| Rust `U64...overflowing_add` | 无公理依赖 |
| Rust core `registers/set_register` | L，加 `bytes.bytes.Bytes`、`Aeneas.Std.core.fmt.Formatter` |
| Rust `instruction_length/extract_opcode` | 只有 L |
| Rust wrapper 的五个寄存器/PC 方法 | `propext`、`bytes.bytes.Bytes`、`Aeneas.Std.core.fmt.Formatter`、`DefaultMachine` 类型及所查询的方法 axiom 本身 |
| Rust `execute_production` | 上述依赖以及完整机器字典、其他指令分支的外部类型/函数，例如 memory、比较、其他位运算和 SupportMachine 方法；不再含 RA 或寄存器总数 axiom |
| Sail `rX_bits/wX_bits/execute_RTYPE/tick_pc` | 只有 L |
| Sail `run_hart_active/try_step` | L，加 reservation、随机数、平台输出、浮点辅助和 `sys_enable_experimental_extensions` 等全步骤依赖；`try_step` 还含 `valid_reservation` |

这些查询结果没有 `sorryAx`。这只描述所查询定义的传递声明依赖，不预先保证未来
定理的证明项不依赖未证明引理。`Bytes` 和 `Formatter` 等类型通过泛型 trait 的签名
进入列表，不表示 ADD 实际执行了内存 I/O 或格式化。
`#print axioms` 是声明依赖分析，不按 opcode 做执行路径分析：即使 ADD 子引理已
约简，最终定理若仍引用完整执行函数，其列表仍可能包含其他分支的外部声明。
需要同时记录这些声明与真正用于证明的行为前提，不能静默从报告删掉它们。

## 2. 生产调用边界

源码链路可在 [injection.rs](../../../crates/ckb-runner/src/injection.rs)、
[machine/mod.rs](../../../deps/ckb-vm/src/machine/mod.rs)、
[execute.rs](../../../deps/ckb-vm/src/instructions/execute.rs) 和
[提取入口](../../../crates/proof-extract/src/lib.rs) 定位：

```text
运行时 run_program → DefaultMachine::step
                         ├─ decoder.decode、cycle hook、add_cycles
                         └─ instructions::execute ← execute_production（提取根）
                              ├─ instruction_length、pc、update_pc
                              ├─ execute_instruction → handle_add
                              │                         └─ common::add
                              │                             ├─ registers、Slice.index_usize × 2
                              │                             ├─ Register<u64>::overflowing_add
                              │                             └─ update_register → set_register
                              └─ commit_pc
```

`InjectedMachine` 是双方共享的 Rust 类型别名，这保证提取入口与运行时使用相同机器
类型。它不证明 opaque 方法正确委托。提取根不包括 `step` 的取指、原始机器码解码
与计费，也不包括 runner 的注入、trace 归一化或 DII 协议。

CKB 输入 `Instruction` 是内部 `u64` 编码，不是原始 RISC-V `u32` 指令字。
`Rtype.rd/rs1/rs2` 从内部编码读取字段；`extract_opcode` 中 ADD 对应 dispatch 分支
`1`；`instruction_length` 从内部长度位读取字节数。指令对应关系必须约束这些字段。
仅给任意 `u64` 起名叫 ADD 不足以证明它会执行 ADD。

## 3. Rust 依赖逐项结论

下表的生成符号均位于 [CkbVmProduction.lean](../generated/rust/CkbVmProduction.lean)，
省略外层 namespace `ckb_vm_sail_extract`。源码常量见
[definitions/src/lib.rs](../../../deps/ckb-vm/definitions/src/lib.rs)，写回见
[utils.rs](../../../deps/ckb-vm/src/instructions/utils.rs)。

| 依赖 | 当前证据 | 对定理的影响 / 后续动作 |
|---|---|---|
| `ckb_vm.instructions.common.add` | 有生成 body；先读两个源操作数再写目标 | 可以证明寄存器效果；机器方法仍通过参数传入，不能将泛型函数的短 axiom 列表当成生产实例已证明 |
| `U64.Insts.Ckb_vmInstructionsRegisterRegister.overflowing_add` | 有 body；调用 Aeneas `core.num.U64.overflowing_add`，取结果对的第一项 | 支持库 `Std/Scalar/OverflowingOps/Add.lean` 用 `x.bv + y.bv` 定义结果；需证明与 Sail `BitVec 64` 的对应，ADD 不需要 ADDW 的符号扩展 |
| `Slice.index_usize` | 支持库有 body，越界返回失败 | 需寄存器集合和 `rs1/rs2 < 32` 不变量；不能只在双方已成功的假设下隐藏索引失败 |
| `ckb_vm.instructions.utils.update_register` | 有 body，先对寄存器总数取模，索引非零才写入 | 目标编号合法与寄存器总数共同决定 x0/普通写回；函数不会修复初态非零的 x0 |
| `ckb_vm_definitions.RISCV_GENERAL_REGISTER_NUMBER` | **`def ... : Std.Usize := 32#usize`**；源 initializer 已透明提取 | 值引理通过展开生成定义证明；不再需要常量成功/值前提 |
| `ckb_vm_definitions.registers.RA` | **`def ... : Std.Usize := 1#usize`** | 同样提取并检查；消除其他 dispatch 分支的常量 axiom，但不增加 ADD 覆盖范围 |
| `DefaultCoreMachine` 的 `registers/set_register/pc/update_pc/commit_pc` | 有 body；寄存器数组长度直接是 32；set 使用数组检查与更新，commit 使用 Clone | 可以证明 core 状态的操作规律，但不能替代生产 wrapper 的相应规律 |
| `DefaultMachine` 的上述五个方法及类型 | **opaque / axiom** | 生产实例实际选用这些方法；需明确架构投影及读取、局部写入、PC 更新和提交规律，或补机器检查的连接证明 |
| `handle_add`、`Rtype` 字段读取 | 有 body；内部字段读取使用移位、截断及 cast | 需证明字段与 Sail regidx 对应，并检查所用 Aeneas scalar 操作；不能仅审计 `common.add` 就宣称 dispatch 已覆盖 |
| `execute_instruction`、`extract_opcode`、`instruction_length`、`execute` | 有 body | ADD 分支选择与长度 4 都需要证明；随后连接 PC staging 和 commit |
| memory、SYSTEM、其他算术辅助 | 整个提取文件/生产字典包含相关 axiom；选中的 ADD body 不做数据内存操作、不调用比较辅助 | 全 dispatch 的声明依赖可能包含这些符号；必须对 ADD 分支约简并审计实际定理，不能将所有 axiom 都归为 ADD 必要前提，也不能直接宣称它们不在定理依赖中 |

原先“65 个 axiom 全来自三组显式 opaque”“DefaultMachine 是唯一缺口”“ADD 所有
依赖都有 body”的表述均不成立：生成文件还含跨 crate 常量和其他外部声明。
同时区分**未解释的函数/类型符号**与**规定这些符号行为的前提**；opaque 函数的
声明本身没有提供其正确性规律。

## 4. Sail 依赖与 PC 路径

实际函数全名是 `LeanRV64D.Functions.execute_RTYPE`，定义于
[InstsEnd.lean](../generated/sail/LeanRV64D/InstsEnd.lean)。调用 `.ADD` 时，body 读取
两个 `rX_bits`，执行 64 位加法，调用 `wX_bits`，返回 `RETIRE_SUCCESS`。

- [Regs.lean](../generated/sail/LeanRV64D/Regs.lean)：`rX_bits/wX_bits` 将 5 位
  `regidx` 转为寄存器编号；`rX` 对 x0 返回 `zero_reg`，`wX` 对 x0 不写入。
- [RegType.lean](../generated/sail/LeanRV64D/RegType.lean)：当前 `regtype` 为 64 位；
  `regval_from_reg/regval_into_reg` 是恒等转换，`zero_reg` 为零。
- 支持库 `Sail/ConcurrencyInterfaceV1.lean`：`SailM` 基于 `EStateM`；寄存器在
  `SequentialState.regs` 映射中，`readReg` 在键缺失时返回 `.Unreachable`。
  状态关系必须保证相应寄存器键存在，不能仅断言“存在的值相等”。
- [Callbacks.lean](../generated/sail/LeanRV64D/Callbacks.lean)：当前生成的
  `xreg_full_write_callback`、`pc_write_callback` 返回 `()`。`wX` 仍经过
  `xreg_write_callback` 和寄存器名称转换；证明需展开这些生成定义。
  这不证明 C 模拟器的 RVFI 输出或网络协议。

**`execute_RTYPE` 不推进 PC。** 完整路径在
[Step.lean](../generated/sail/LeanRV64D/Step.lean)：

```text
try_step → run_hart_active
             ├─ dispatchInterrupt、fetch、ext_decode、landing-pad 检查
             └─ F_Base 正常分支：nextPC := PC + 4
                                  → execute → execute_RTYPE ... ADD
         → 正常退休且 hart active
         → tick_pc → PC := nextPC
         → minstret / RVFI / post-step 等外围处理
```

`tick_pc` 位于 [PcAccess.lean](../generated/sail/LeanRV64D/PcAccess.lean)。只证明
`common.add ↔ execute_RTYPE ADD` 能得到寄存器效果引理；要交付包含 PC 的精化定理，
必须再连接双方生成的执行/提交路径。手写 `PC + 4` 的函数不能代替这个连接。

## 5. 定理合同（寄存器层与条件性一步已实现，合同实例待证明）

### 寄存器效果引理

剩余合同的可编译接口和逐层义务已记录于 [ADD_PREMISES.md](ADD_PREMISES.md)，
`state_rel` 和下述寄存器效果结论已实现，入口为 `make proof-registers`。
下文的一步合同也已通过 `make proof-step` 检查；具体前缀及初始化条件见 `ADD_STEP.md`。

输入是同一个 `rd/rs1/rs2 ∈ [0,31]`、对应的生成机器状态和 Sail 状态。定义架构
投影，将 CKB 的 `U64.bv` 与 Sail 的 `BitVec 64` 对应。状态关系要求全部 32 个 GPR
对应、CKB x0 为零；Sail x1–x31 键存在。机器委托缺口逐项列为前提，常量值已不再是前提。

对于 opaque 的生产 wrapper，委托前提表达下列局部规律（用抽象投影
表示寄存器、当前 PC、待提交 PC 和数据内存；投影尚无实现，方法合同已编译）：

| 方法 | 需要的成功与 frame 规律 |
|---|---|
| `registers` | 成功返回长度 32、逐项对应寄存器投影的快照 |
| `set_register m i v` | 在 `0 < i < 32` 时成功，仅更新第 i 项；保持当前/待提交 PC、其他寄存器和数据内存。x0 写入抑制由 `update_register` 证明，不假设此底层方法自行抑制 |
| `pc` | 成功返回当前 PC 投影 |
| `update_pc m p` | 成功设置待提交 PC 为 p，保持当前 PC、寄存器和数据内存 |
| `commit_pc` | 成功把待提交 PC 赋给当前 PC，保持寄存器和数据内存 |

这些方法规律需与生成的生产字典绑定。为一个另写的理想机器证明它们，再直接将
结论称为生产 wrapper 正确是不成立的。写操作还须保持有效状态 invariant，
以支持连续组合；可编译合同未提供任何投影或委托规律的实例。

寄存器定理已从两个寄存器方法前提出发证明两侧执行成功，且对于旧状态值
`v = (R[rs1] + R[rs2]) mod 2^64`：

- `rd ≠ 0` 时，新 `R[rd] = v`；`rd = 0` 时所有 GPR 保持不变；
- x0 仍为零，其余寄存器保持；不要求源/目标寄存器互异，因此覆盖 `rd=rs1`、
  `rd=rs2`、`rs1=rs2`；
- PC 在这两个叶函数的边界保持不变，数据内存不变；相关投影 frame 引理已证明。

CKB 的 `common.add` 返回 Aeneas `Result Mac`；`execute` 还包着 Rust 自身的
`core.result.Result Unit Error`。完整一步必须同时排除外层失败与内层 VM 错误。
Sail 需区分 monad 执行失败与 `ExecutionResult` 中的非法指令/异常，不能只比较一个
“成功”标签。

### 包含 PC 的生产执行精化（条件性定理已实现）

在前述关系上增加 PC 对应，固定 VERSION2、RV64 和项目 ISA 配置，指定正常的
32 位 ADD（长度 4、内部 opcode/寄存器字段与 Sail `.RTYPE (rs2, rs1, rd, .ADD)`
对应）。不纳入压缩 C.ADD、ADDW、MOP 或 ASM/JIT。
Sail 的 PC 键需存在；旧 nextPC 不要求预先对应，由正常分支写入后再读取。
平台键需求由 `StepEntry`、`ActiveAddPath`、`RetireReady` 明确给出，读取不是总函数。

Sail 外围的具体前提必须随所选生成入口写出：hart active、无待处理中断、取指/解码
给出该 ADD、不触发 landing-pad 异常、所读平台/CSR 键已初始化、配置对应。
这些应约束外围行为，不能把“ADD 执行结果已正确”写进前提造成循环论证。
初态允许合法的任意寄存器值和 PC；不把 runtime corpus 的全零复位态或 64 KiB
注入窗口无故加入数学引理。

已证结论包括成功退休、GPR/PC 关系保持、两侧 PC/next-PC 都等于旧 PC 加 4
（模 `2^64`）、各侧内存保持（Sail 前缀内存保持是显式合同）。计数器可变化，
当前生成 RVFI 开关为 false；不声称任意 RVFI 配置或两台机器整个状态相等。

decoder/fetch 对应和 wrapper 委托仍作为前提时，交付名称必须标明这是**对应解码
结果及所列委托前提下**的生产 ADD 精化。共享类型、源码调用图与测试不消除这些
前提。无取指、计费、trap 全关系、完整 VM 或 RVFI exporter 正确性结论。

## 6. 后续门禁

1. 已完成共同 Lean 4.31.0 下的实际双侧 import 编译；使用严格的 `make proof-imports`
   回归检查，保留兼容补丁及依赖锁。这一项不是 ADD 定理通过。
2. 已补齐两个可提取常量及内核值检查；剩余五个 wrapper 方法的精确合同和内部
   ADD 编码条件已形式化。后续需实例化这些合同或证明生产连接，不用新公理代替。
3. 寄存器及双方 PC/dispatch 连接已直接引用生成符号并通过；下一步为实际状态证明合同。
4. 寄存器定理已执行 `#print axioms` 和显式参数审计，完整 67 项依赖以守卫固定；
   新一步定理的完整 141 项清单也已固定，包含额外 Sail opaque 声明。标准逻辑公理、支持库
   假设、opaque 声明和未证委托规律应分别说明；`sorryAx` 不得作为完成的证据。
   泛型函数的参数化操作不会全部出现在其 axiom 列表中，而完整 dispatch 查询又会
   包含未选分支，所以这两种查询都不能代替最终定理审计。
5. `proof-check` 已接入实际生成/编译/定理检查，及公理/显式前提/来源的精确基线。
   它只验收 `conditional` 保证，不实例化合同，见 [门禁说明](PROOF_CHECK.md)。现有
   [check_proof_model.sh](../../../scripts/check_proof_model.sh) 在符合记录的 `blocked`
   情况也返回 0，因此不能只沿用其退出码来判定证明完成。

共同工具链、条件性一步定理及审计门禁已实现；具体合同和发布工作仍待完成，ADD 覆盖状态不提升。
