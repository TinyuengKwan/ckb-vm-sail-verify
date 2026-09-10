# full-MIR 解码入口实验：decode_raw 阶段证据

后续状态：实际公开方法的 MOP-off 路径已在新的隔离候选中接回最终 ADD 定理，见
[公开入口证明与依赖审计](../full-entry/README.md)。本页保留旧工具的阶段性证据和失败记录，
不将后续工具结果归到旧基线，也不刷新旧快照。

2026-09-09。沿用函数指针实验候选及原生产源码，没有新增 CKB 补丁，
没有修改已采纳 Aeneas、Lean 支持库、主证明或 raw ADD 门禁政策。
本目录不是新的生产工具基线，也不改变 Week5 验收范围。

## 已推进的边界

- [IteratorProof.lean](IteratorProof.lean)：真正提取共享 Vec 的 `IntoIterator` 函数体，
  证明 Rust `through_table` 的入口、命中、空表及顺序，不再以不透明迭代入口为前提。
- [OuterFactories.lean](OuterFactories.lean)：实际 RVC 工厂排除所有 ADD 编码，
  随后的实际 RV64 VERSION2 ADD 工厂返回正确字段和长度。
- [OuterInit.lean](OuterInit.lean)：真实 `new` 初始化 RVC/i/m/b 顺序、关闭 MOP，
  4096 项缓存初值均为 `(U64::MAX, 0)`。
- [OuterLoop.lean](OuterLoop.lean)：真实工厂循环选中 ADD，写入正确缓存项；
  读回写入项正确，其他索引保持不变。
- [OuterFetch.lean](OuterFetch.lean)：页内快速取指分支从内存接口读回的原始 32 位 ADD 字
  推出 `decode_bits` 的输出，不假设任何已解码指令。
- [OuterEntry.lean](OuterEntry.lean)：真实 `fresh_decoder` 与初态相连；
  对任意三组 5 位字段，PC=0、冷缓存、有界内存且 `execute_load32` 返回原始字时，
  **实际 `decode_raw`** 返回 ADD 内部指令和正确更新后的缓存。
- [OuterCache.lean](OuterCache.lean)：将实际索引计算推广到任意 PC，证明索引有界、
  命中不取指、失配调用真实工厂并更新正确位置，以及有界 PC 不会与初始 sentinel 混淆。
- [OuterPage.lean](OuterPage.lean)：跨页分支实际进行两次 16 位读取、检查 `pc+2` 不溢出，
  按低/高半字重组；对任意原始字证明低位判断与重组算术。
- [OuterGeneral.lean](OuterGeneral.lean)：`WordFetch` 只记录内存读取合同，覆盖两个取指分支。
  `decode_cold_word` 对任意 PC、任意满足 ADD 位模式的 32 位字，证明完整冷缓存
  `decode_raw` 路径。另证写入后的同 PC 命中，不要求再次成功取指。
- [OuterStep.lean](OuterStep.lean)：`cold_raw_add_step` 将新入口接回原生产执行定理，
  得到双方寄存器效果、PC/nextPC 更新及内存不变。不再要求提供已解码 ADD 结论。
- [OuterMemoryWitness.lean](OuterMemoryWitness.lean) 与 [OuterStepWitness.lean](OuterStepWitness.lean)：
  构造明确的内存接口见证，分别调用快速/跨页入口定理；联合既有 Sail 前提，实际调用
  新步骤定理，得到 x3=12、PC=`0x80000004`。

初期 PC=0 的定理保留作为回归；新总入口已量化任意 PC 和原始 ADD 字，包含 x0 和别名。
主入口仍要求 size/load 合同。快速分支要求页内位置；跨页分支要求两次读取成功及地址加 2
不溢出；这些不是解码结论，合同和构造器类型也纳入精确审计。
命中合同描述任意缓存记录；单字与 ADD 的整体定理从真实初始化的冷缓存开始，
没有宣称任意污染/过期缓存都与重新读到的字对应。

内存见证是明确构造的 Lean `Memory Unit U64` 接口，未使用的方法失败，**不是** Rust
SparseMemory 的实现证明或物理内存耦合证明。联合步骤仍以既有 opaque `Machine` seed 为参数，
不证明该类型非空或 reset 可达。`cold_raw_add_step` 的 Rust 根仍是 `decode_raw`，
不是公开 `InstDecoder::decode`；上述结果不等于整台 VM 已闭合。

## 提取原因与复现

原预编译标准库的优化 MIR 会把共享 Vec 迭代入口展开为不透明 Vec 的内部字段，
使工具拒绝。使用固定 nightly 源码在隔离目录重建 std：

```sh
python3 scripts/experiments/build_decoder_sysroot.py --offline
```

[构建报告](../../../../../artifacts/boundary-check/decoder-sysroot-build-v7q4ktbr/report.json)
记录成功的新目录构建、46 个 rlib/rmeta 哈希及标准库 lockfile 前后校验。
使用 `always-encode-mir=yes`、`mir-opt-level=0`、`inline-mir=no`，不安装到全局 sysroot。
该 nightly 的产物位于 `debug/build/<crate>/<hash>/out`；脚本从这里构建 sysroot 链接。
`alloc` 的 rlib/rmeta 与上一轮独立构建相同，不宣称所有平台和编译产物都可字节复现。
新 sysroot 又实际完成了一次最小 Rust → LLBC → Lean 提取及四条迭代入口证明检查，
记录在该构建目录的 `charon-smoke-v2.log`、`aeneas-smoke.log`、
`kernel-smoke-model.log`、`kernel-smoke-iterator.log`。生成模型仅有源码路径注释的
绝对/相对写法差异，归一化仓库前缀后逐字相同。

[提取配置](extraction.json)固定 compiler、Charon、实验工具、包含/不透明列表和实际生产
[入口](OuterRoot.rs)。已归档 LLBC 的完整 Charon options 会再次写入检查报告。
独立检查命令：

```sh
python3 scripts/probes/probe_decoder_full_mir.py \
  --general \
  --inputs artifacts/boundary-check/decoder-sysroot-q8nI9W \
  --translator artifacts/boundary-check/decoder-fnptr-lx9JGu/aeneas-src/src/_build/default/main.exe
```

检查器从固定 LLBC **重新生成**两个模型，从空的新模块缓存编译模型及全部新证明。
它不重跑生产 Rust → LLBC，不重建 sysroot，复用主证明/raw ADD 的已构建依赖。
因此不是从源码开始的全依赖 clean-room 门禁。

与主模型一起导入时会出现自动生成的 discriminant 实例同名；兼容副本只增加一行
`import CkbVmProduction`，让原支持库分配不冲突的实例名。原始生成物保留，报告记录
原模型和兼容模型哈希；不修改 Rust 函数体或用手写函数替代提取定义。

## 审计及未关闭项

当前 [扩大后的复检报告](../../../../../artifacts/boundary-check/full-mir-check-ykre555d/report.json)
通过 26 个阶段：合计 56 条定理、25 个定义和 3 个读取合同声明类型。
报告 SHA-256：`69ea312f2e816dd9575d508f4226dc01ba654d253a9b69afd4c7029f8728f9a8`。
新模型/证明从空缓存编译，原 32 条快照也再次精确匹配；错误高半字、错误缓存/入口结果、
增加 False 前提的负测均通过，生产源码及受保护的旧政策/主报告哈希前后相同。

以下保留早期 PC=0 层的独立证据：

[独立复检报告](../../../../../artifacts/boundary-check/full-mir-check-5pktud3_/report.json)
已通过 18 个阶段，32 条定理及 16 个定义与快照精确相符；错误结果及弱化前提负测通过。
报告 SHA-256：`3bf022c3a29281fbc4f12d3b6ba9b6d0c4db7593eca49906745d45b3f8936000`。
外层生成物仍有 42 项不透明声明，完整记录在报告中；只有共享迭代入口的该项已消除，
不能说整个模型不再依赖不透明边界。首次复检因审计导出器语法错误失败，
保留在 `full-mir-check-luldz8_k`，没有将其算作通过。

[实验快照](audit-snapshot.json)固定 32 条定理的精确类型/全部公理及 16 个实际定义的函数体哈希。
取指定理只依赖标准逻辑公理；`decode_raw_zero` 的 25 项包括标准逻辑、Formatter 和
独立 Register 实例中非 ADD 方法的传递依赖。没有隐去这些依赖，也不接受 `sorryAx` 或 native。
检查还覆盖错误入口结果、错误缓存结果，以及能编译但额外添加 `False` 前提的弱化定理。
该快照仅约束本实验，不是正式工具采纳。

任意 PC 的新增层由 [general-audit-snapshot.json](general-audit-snapshot.json) 另行冻结，
不刷新原 32 条快照。新增 24 条精确定理、9 个定义函数体和 3 个读取合同声明类型。
`cold_raw_add_step` 为 158 项依赖；与原 raw factory 定理数量相同，但独立 Register 方法
来自新的 `OuterDecodeCandidate`，不是同一个依赖列表。`cold_paired_step` 为 159 项，
额外的 `OuterDecodeCandidate.bytes.bytes.Bytes` 是接口中未使用操作提到的不透明类型，
不是新的内存行为正确性公理。`--general` 还把高半字读取故意替换成低半字，要求跨页见证被拒绝。

完整公开 `decode` 的提取包含 MOP，曾运行约 32 分钟、占用约 22 GiB 后因资源压力
被显式终止（退出 143）；后续 60 秒诊断退出 124，均不是证明或语义负测成功。
输入/日志保存在 `artifacts/boundary-check/decoder-sysroot-q8nI9W/OuterFullMir.llbc`、
`aeneas-outer-full.log` 和 `aeneas-outer-diagnostic.log`。诊断表明已进入 MOP 相关函数翻译，
尚不能据此断定具体哪一个内部步骤导致膨胀。

后续 [定向诊断](../../../../../artifacts/boundary-check/outer-general-fuhHWv/mop-diagnostic-report.json)
将已证明的四个工厂模块仅在诊断输入中设为 opaque，未改变任何证明模型。
严格、顺序执行的探针在 60 秒时停于 `rule_add3`（`decode_mop::closure#1`），退出 124。
同一函数的未重构 ULLBC JSON 函数体为 428,806 字节，结构化 LLBC 为 44,916,885 字节；
两组 options 只差 `ullbc` 和输出路径。约 105 倍的膨胀已出现在前端产物，下一步定位
Charon 控制流重构及结构化清理阶段，尚未断言是哪一个具体 pass 导致。
该诊断不证明 MOP，也不把诊断中的不透明工厂带入已通过的模型。

后续 [清理尾段隔离实验](../cfg-experimental/README.md) 已用带 `String` 错误的独立 Rust
用例复现膨胀。新的候选 Charon 变换将生产 `rule_add3` 函数体从约 44.9 MB 降至 0.48 MB，
真实公开入口的完整 LLBC 已重新生成；未修改 CKB 源码或扩大 opaque 列表。
但 Aeneas 在 180 秒期限结束时仍未完成，定向日志仍停在该函数的符号执行。
候选工具完整回归尚未通过，未被采纳，不能将前端成功写成公开解码证明完成。

后续 [Aeneas 分支实验](../branch-experimental/README.md) 已解除上述后端障碍，
实际公开 `decode` 的 MOP-off 分支连接、最终 ADD 连接及依赖审计已在
[新候选](../full-entry/README.md) 完成。工具/政策采纳仍未完成。
生产内存实现、物理耦合和 opaque Machine seed 非空性仍是明确边界，不能把接口见证
当成这些事实的证明；MOP 开启时的语义也未证明。公开入口目标没有被缩减为 `decode_raw`。
