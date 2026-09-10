# 原始 ADD 编码：公开 decoder 已限定采纳，主门禁复验中

2026-09-09 后续进展：实际生产 RV64 / VERSION2 `i::factory`、Sail `ext_decode`
与生产 ADD 最终执行定理的连接，已通过共同 Lean 4.31.0。独立门禁已全部通过，
见[本轮报告](../../../artifacts/boundary-check/raw-add-0__trc1y/report.json)。

最新进展：真实公开 `InstDecoder::decode` 的 MOP-off ADD 路径已接回双方执行定理，
并完成生产 Rust 重提取及全依赖干净构建的 47 阶段复验，68 条定理审计通过。
见[公开入口证明及复现边界](toolchain/full-entry/README.md)。
新工具已按 [限定政策](ADOPTION.md) 采纳并接入主 `proof-check`，首次集成实跑已通过；
以下原 factory 政策和历史报告保持不变。

```sh
python3 scripts/check_raw_add.py
```

- [RawEncoding.lean](RawEncoding.lean)：对任意 32 位字，`raw_add_iff` 证明合法 ADD 位模式
  恰好覆盖所有三组 5 位寄存器字段，包含 x0 及所有寄存器别名情形。
- [RustRawAdd.lean](RustRawAdd.lean)：真实 factory 选中 ADD，经过实际 `Option.map`、
  `Rtype::new`、长度设置函数，返回确定的内部指令。
- [DecodedRawAdd.lean](DecodedRawAdd.lean)：主模型的实际字段读取函数建立 `DecodedAdd`。
- [SailRawAdd.lean](SailRawAdd.lean)：推广完整 Sail 解码，含 ADD 前的提示指令及扩展分支。
- [RawAddStep.lean](RawAddStep.lean)：`raw_decoders_correspond` 和 `raw_add_step`
  不再要求调用方提供内部指令、`DecodedAdd`、Sail 的 ADD 解码结论或编号相等假设。
- [RawAddWitness.lean](RawAddWitness.lean)：闭合的共同前提见证，以及实际调用新定理的
  `raw_paired_step seed`，得到 x3=12、PC 增 4。

仍保留初始 `state_rel_pc`、Sail 初始化/无中断/有效取指/无 landing pad/退休前提。
`decodeContext` 只要求相关扩展检查可完成，不是 ADD 解码结论；
`decode_context_machine` 从 Machine privilege 和存在的 `mseccfg` 推出它。
见证不证明 reset 可达性或 opaque Rust `Machine` seed 非空。

使用[独立 Aeneas 工具基线](toolchain/README.md)和[提取配置](extraction.json)，
没有新增 CKB-VM 生产补丁或替换主工具。原主定理仍为 137 项公理；新最终定理为 158 项，
增加的是独立 Register 实例中 21 个未在 ADD 路径调用的方法依赖，不能从清单中省略。
没有接受 `sorryAx`、本机计算公理或额外行为正确性假设。

[固定政策](raw-policy.json)审计 15 个精确定理类型/公理集合及 18 个关键定义函数体。
新门禁重跑字段检查和运行穷举，重新提取、从零编译所有新模型/证明，再运行严格合流、
错误编码选择位、错误 rs2 字段归属，以及“能编译但多了 False 前提”的负测。
超时/资源耗尽不能算作本轮语义负测成功。首次门禁因低效位移篡改负测被停止，记录为失败；
最终采用直接检查错误寄存器字段的用例，已重跑通过。

支持库和已有 Sail/主证明依赖仍复用共同环境，不是全依赖图再次 clean-room 构建。
这是独立门禁，不是原 `proof-check` 新阶段，不改变 Week5 的 conditional 验收或总体覆盖。

## 字段层的独立证据

2026-09-09：独立补充检查 `python3 scripts/check_raw_add_fields.py` 已通过。
证据见 [本轮报告](../../../artifacts/boundary-check/raw-fields-a5hm75f7/report.json)
及 [Lean 环境审计](../../../artifacts/boundary-check/raw-fields-a5hm75f7/field-audit.json)。
这不是主 `proof-check` 的新增阶段，也不修改原最终定理或把完整 ADD 覆盖改为 `proved`。

## 已证明什么

[RawFields.lean](RawFields.lean) 导入真实提取的 Rust 定义和既有 Sail 模型。
它对**任意 `w : U32`**证明以下对应，不局限于 `0x002081b3` 或运行语料中的输入：

| Rust 实际函数 | Sail 位切片 |
|---|---|
| `instructions::utils::rd` | `w[11:7]` |
| `instructions::utils::rs1` | `w[19:15]` |
| `instructions::utils::rs2` | `w[24:20]` |
| `instructions::utils::opcode` | `w[6:0]` |
| `instructions::utils::funct3` | `w[14:12]` |
| `instructions::utils::funct7` | `w[31:25]` |

另证明 `index_val`：转换成 Rust `usize` 后仍是原 5 位寄存器编号；
`sail_reg_decode`：实际 Sail `encdec_reg_backwards` 在既定非 E 配置中返回对应 `Regidx`；
`operands_correspond`：两侧上述操作使用同一个原始输入的同一组切片。
该定理不假设解码字段相等，但也不声称 top-level decoder 已选择 ADD。

全部 9 个定理通过共同 Lean 4.31.0 检查，只依赖标准逻辑公理的子集
`propext / Classical.choice / Quot.sound`。没有 `sorryAx`、新增行为公理或本机计算公理。
早期候选使用 `bv_decide` 时，审计发现 `_native.bv_decide.*` 依赖，因此没有接受；
最终改为逐位展开和内核推导。

## 提取与检查方式

字段函数位于私有 `utils` 模块，外部 Rust wrapper 不能直接调用。
从依赖 crate 入口提取时，Aeneas 的内联清理只留下底层 `x`，不能据此冒称六个函数均已保留。
本方案直接在**未改动的生产 CKB-VM crate** 中，以六个实际函数为 Charon roots，
再用 Aeneas 的独立 `RawDecodeExtract` namespace 生成 `LocalFields.lean`。
这保留了六个字段函数和 `x` 的真实函数体，不复制或手写 Rust decoder。

[检查脚本](../../../scripts/check_raw_add_fields.py) 每次创建新证据目录，并执行：

1. 核验既有生产基线、主政策的源码/工具哈希、共同 Lean 环境和 CKB crate 的依赖锁。
2. 重新提取、翻译，核验独立生成物哈希；从零编译新字段模型和证明模块。
3. 导出精确公理、定理类型及函数体，与 [field-policy.json](field-policy.json) 比较。
4. 检查三类隔离负测：错误 Sail 位切片、错误 Rust `rd` 位移，以及暗加 `False` 前提。
   前两项须编译失败；最后一项虽能编译，定理类型审计必须拒绝它。
5. 运行生产 factory 穷举检查，再核验正式源码/生成物、主政策和补充政策均未发生漂移。

政策是人工复核后的固定输入，检查脚本不会自动刷新它。
新模型和证明模块不复用旧 `.olean`，但支持库及既有 Sail/主证明导入复用原共同环境；
这不是整个依赖图的再次干净构建，更不是 Week6 clean-room 或发布验收。

## 运行时穷举结果

[RuntimeCheck.rs](RuntimeCheck.rs) 直接调用生产 `i::factory::<u64>(bits, VERSION2)`：

- 全部 `32 × 32 × 32 = 32768` 个合法 ADD 编码，检查 opcode、长度和三个寄存器字段。
- 196608 次非 ADD 邻近检查，改变 opcode/funct3/funct7 位后不得仍被判为 ADD。
- 32768 次已解码目标寄存器篡改，检查器全部检出。

这些检查通过，但只属于有限域的运行证据，不是 Rust factory 的 Lean 语义证明，
也没有检查 DefaultDecoder 的 cache、取指或 MOP。
运行 harness 使用独立、离线解析的 Cargo lock；报告保留其哈希与实际锁文件，
不冒称它就是生产 workspace 的锁，也不提供运行二进制来源认证。

## 当前剩余边界与历史提取失败

1. **Rust factory 分派与组装**：已由本页开头的新通用定理连接，不再只有字段或运行证据。
2. **Sail 完整解码路径的推广**：已对任意 ADD 原始字证明，而非仅具体 `0x002081b3`。
3. **外层生产 decoder**：已证明 factory 顺序、取指、cache 及公开方法的 MOP-off ADD 路径，
   并完成限定工具采纳及首次集成主门禁实跑，MOP 开启时的融合语义仍未证明。
4. reset 可达性、Rust seed 非空性及其他原有边界不因本轮字段证明而消失。

历史字段阶段测试了原固定工具链的 7 种完整 factory 提取变体，包括固定 u64/VERSION2 入口、
单态化、常量值模式、直接 crate 的早期 MIR、显式 opcode 常量初始化器。
Charon 均生成无错误 LLBC，但 Aeneas 全部失败，见
[失败变体报告](../../../artifacts/boundary-check/raw-decoder-QSAprb/factory-variants-report.json)。
默认常量模式主要仍在 `i.rs:66–69` 的 JALR 分支合流处失败；单态化/常量模式还暴露
其他内部错误。这些失败不算作补充门禁的成功阶段，也不证明所有未来工具/配置都不可行。

已采纳的隔离补充工具已打通 factory，但其真实 `DefaultDecoder::new` / `decode_raw` 探针
失败于 `Vec<InstructionFactory>` 的函数指针类型，最小用例复现，单态化也未打通。
见[独立失败探针与工具回归](../../../artifacts/boundary-check/decoder-toolchain-VBwba1/tool-regressions-report.json)。
这些失败不计为证明成功，factory 证明不能替代外层 factory 顺序、cache、取指或 MOP。
继续该层需要函数指针建模，或另行审查新的源码重构和正式生产基线；不能静默设为 opaque 后宣称关闭。

2026-09-09 后续：[新的函数指针实验候选](toolchain/fnptr-experimental/README.md)
已通过 16 条最小回归定理、负测及外层探针的 Lean 编译，未修改生产源码或已采纳工具。
该轮的共享 Vec 迭代入口和内存方法仍有不透明边界，完整外层对应定理尚未建立；
候选没有被 raw ADD 政策或主 proof-check 采纳，上述 factory 证明的依赖/结论不变。

同日后续：[隔离 full-MIR 实验](toolchain/full-mir/README.md)已消除共享迭代入口的不透明声明，
证明实际工厂顺序、RVC 排除、ADD 循环与缓存更新；后续已将真实冷缓存 `decode_raw`
推广到任意 PC、原始 ADD 字及两种取指分支，并连接到原生产 ADD 执行定理。
还补了内存接口和联合步骤见证，但不等于生产 SparseMemory 实现或物理内存耦合证明。
再后续：[真实公开入口](toolchain/full-entry/README.md) 已提取完整 MOP 函数体，并将
MOP-off 的公开 decode 接回最终 ADD 定理；158 项依赖没有额外版本/转换公理。
旧 56 条定理的精确类型/依赖保持不变，新增公开入口、取指及联合执行见证已通过内核检查。
其后的限定工具采纳及主门禁连接见 [ADOPTION](ADOPTION.md)。MOP-on 语义与生产内存实现
仍未关闭；未改变上面的已采纳 factory 定理或其政策。
