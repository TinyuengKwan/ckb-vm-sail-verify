# ADD：联合前提见证与未关闭边界

更新：原始 ADD 字到双方解码的连接现已由[公开解码根](../decoder/toolchain/full-entry/OuterPublicStep.lean)
证明，另有 [公开联合见证](../decoder/toolchain/full-entry/OuterPublicWitness.lean)。
限定采纳与主门禁接入已落实，首次集成复验已通过，见 [采纳记录](../decoder/ADOPTION.md)。
下文 12:06–12:35 的报告及原工具提取失败是此前见证阶段的历史证据，不能代替本次复验。

2026-09-09 见证阶段：完整 `make proof-check BACKEND=lean` 于 12:06:28–12:35:10 UTC
复验通过。共同 Lean 4.31.0 的源码级干净构建完成 1864 个任务，初始编译模块数为 0，
生成 1805 个新 `.olean`；73 项测试通过，其中真实 Lean 负测为 18 项。
主门禁及独立干净环境均核验了新增见证，见
[完成核验](../../../artifacts/boundary-check/witness-review.oCqzJ3/completion-audit.json)
和 [本轮主报告快照](../../../artifacts/boundary-check/witness-review.oCqzJ3/final-proof-report.json)。
原通用 `ProductionAdd.decoded_add_step` 没有被一个具体例子替换，
其定理类型、137 项公理依赖及原有 18 个边界哈希均保持不变。

## 已新增的形式化证据

[SailContractWitness.lean](../theorems/SailContractWitness.lean) 构造一个具体 Sail 模型状态：

- PC 为 `0x80000000`，内存中四个小端字节为 `b3 81 20 00`，即 `ADD x3,x1,x2`。
- x1=5、x2=7，其余 GPR 为零；所有非零 GPR 键均存在。
- machine privilege、active hart；初始化计数器、interrupt、landing-pad 等实际读取的 CSR。
- 4 KiB 可执行 PMA 区域；第一项 TOR PMP 覆盖取指地址，其余项关闭；HTIF 未映射。
- `minstret=0`，退休计数使能。入口写入已存在的相同 flag，已证明不改变状态。

`counter_decision`、`no_interrupt`、`fetch_add`、`decode_add`、`no_landing_pad`
都针对真实生成函数证明，不以“读取/解码/退休成功”作为参数，不改写生成物。
PMP 的两次半字读取亦由生成函数展开验证。

`sail_contracts_jointly_inhabited` 是一个**不带参数的存在性定理**：同一个初态上的
`StepEntry`、其 `prepared` 状态上的 `ActiveAddPath`、该路径 `ready` 状态上的
`RetireReady`，以及额外的 active-hart 条件同时成立。
它不是三个互不相关的合同实例，也不是再次假设合同可满足。

[ProductionAddWitness.lean](../theorems/ProductionAddWitness.lean) 进一步证明：

- `internal_decoded`：具体 CKB 内部编码 `0x020102000301` 满足实际提取的字段读取合同。
  它不是原始 32 位指令，也不是 Rust decoder 正确性证明。
- `initial_related seed`：重设 seed 的 core 寄存器、PC/next-PC 和 VERSION2 后，
  与上述 Sail 初态满足 `state_rel_pc`；不要求调用者提供该关系的证明。
- `paired_step seed`：**应用已有通用最终定理**并在内部提供全部合同证明，得到双方成功执行、
  全部 GPR/PC 的后态关系、x3=12、PC/next-PC=`0x80000004`，以及各侧内存保持。

## 不能据此宣称关闭的部分

1. **Rust opaque 对象的非空性。** `paired_step` 仍有 `seed : Machine` 参数，
   用它提供 SparseMemory、Pause 和 MachineRuntime 等 opaque 对象。
   `valid=True` 不等于构造出了 Machine；本工作没有证明无条件的 `Nonempty Machine`。
   因而双侧联合实例是相对于给定 seed 的证据，不能称为最终全部前提的无条件非空性证明。
2. **从 reset/初始化流程可达。** Sail 见证是直接构造的模型状态，不是从 `init_model`、
   boot 或 runtime corpus 的平台状态推导出来的。没有证明任意正常初态都满足合同。
   原通用定理中的 Sail 初始化合同仍然保留。
3. **不能把分别构造的编码当作桥接证明。** 本页见证阶段只证明此例的 Sail 解码和 CKB
   内部编码字段。后续公开层已用真实 Rust decoder 证明同码桥接，不再是当前未关闭项；
   但它仍保留双方取指同一原始字的接口合同，不证明实际物理内存对应。
4. **范围没有扩张。** 不新增跨侧内存等价、整个 VM/run 循环、MOP/JIT 或源码补丁等价的结论。
   正式生产身份仍是原受审 upstream-plus-patch 基线。

## 原固定工具的历史解码提取结果

真实文件是 `deps/ckb-vm/src/instructions/i.rs`。固定 Charon 从
`ckb_vm::instructions::i::factory` 提取成功，LLBC `has_errors=false`；固定 Aeneas
在 `i.rs:66–69` 的分支合流处报告 `InterpMatchCtxs.ml:230` 内部错误并返回 2。
该位置属于完整 factory 中的 JALR 分支，不是已定位到 ADD 分支本身的语义错误。
未产生完整 factory 的可验收 Lean 模型，也没有修改生产源码或刷新正式提取配置来绕过错误。
这是该固定工具链和提取入口的失败证据，不表示所有替代配置或未来工具版本都不可行。

可复跑命令：

```bash
python3 scripts/probes/probe_add_decoder.py
```

失败时命令返回非零，证据保存在新建的 `artifacts/boundary-check/decoder-*` 目录。
它是边界诊断，不是可把预期失败算作成功的 `proof-check` 子门禁。即使未来翻译成功，
也仍需 Lean 编译、同码解码证明及生产 decoder 的 factory 选择/cache/MOP 边界审查。
本次结果见 [decoder 报告](../../../artifacts/boundary-check/decoder-9bjx6wm6/report.json)。

字段阶段的[原始编码验证](../decoder/README.md)曾作为独立补充检查通过：六个真实 Rust
字段读取与 Sail 位切片对任意 32 位输入对应，另连接了 Sail 寄存器编号解码。
生产 factory 的全部 32768 个 ADD 编码也通过运行检查。当时完整 factory 的分派/组装、
任意 ADD 的完整 Sail `ext_decode` 推广和外层 DefaultDecoder 尚未关闭；
这些历史补充证据不归入上文主 `proof-check` 的 73 项测试。
此后三层均已由 Lean 证明连接；当前剩余边界及新主门禁的实际状态见
[完成审计](../decoder/COMPLETION_AUDIT.md)，不改写上文旧报告的证明范围。

## 依赖审计

新增证明不增加全局公理，无 `sorryAx`；所有依赖均属于原最终定理的受审集合。
这里不使用“零公理”表述：

| 声明 | 传递公理数 |
|---|---:|
| `sail_contracts_jointly_inhabited` | 5 |
| `decode_add` | 4 |
| `internal_decoded` | 3 |
| `initial_related` | 7 |
| `paired_step` | 137 |

Sail 联合见证的 5 项为三个标准逻辑公理及现有的 `plat_term_write`、
`sys_enable_experimental_extensions` 声明；这是依赖足迹，不是新增这些操作的成功假设。
审计现覆盖 31 个类型/定义边界、原 wrapper 合同和上述五个见证。
见 [导出证据](../../../artifacts/boundary-check/witness-review.oCqzJ3/lean-audit.json)
及 [政策差异复核](../../../artifacts/boundary-check/witness-review.oCqzJ3/policy-review.json)。

新增负测覆盖错误取指字节、缺失解码 CSR、不可执行 PMA、缺失退休计数器、
Rust 初始寄存器不一致，以及向双侧实例暗加 `False` 前提。
最后一项必须由定理类型审计拒绝：仅检查公理集合不足以发现这种前提强化。
本轮另复跑 32 个 runtime 案例与 188 次适用 mutation，均通过，4 项不适用跳过；
这份运行证据不替代上述 Lean 见证，也不消除原始解码边界。

这些增强补充 Week5 的证明边界证据，不修改 Week5/6 的验收标准，
也不将完整指令覆盖从 `runtime-only` 改为 `proved`。
