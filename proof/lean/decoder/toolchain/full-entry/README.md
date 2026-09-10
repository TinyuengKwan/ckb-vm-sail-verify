# 真实公开解码入口的 ADD 对应（限定采纳，主门禁复验中）

当前状态：47 阶段独立干净复验通过，工具已按 [限定政策](../../ADOPTION.md) 采纳，
主 `proof-check` 已接入且首次集成实跑通过。下文保留各历史实验阶段的证据和当时边界，
其中“未采纳”不代表当前状态；尚未将本次主门禁运行计为通过。

2026-09-09。已从完整生产入口提取 Lean 模型，并将**同一个原始 32 位 ADD 编码**
经 Rust 公开 `InstDecoder::decode` 接回 Sail 解码及双方生产执行定理。
没有新增 CKB 源码补丁，没有把 MOP、函数表或任一工厂声明为 opaque。
生产源码身份仍是 `ckb-vm-1ffba3977da9-runtime-container-v1`，不能归到未经修改的上游 commit。

## 证明及精确边界

- [OuterPublic.lean](OuterPublic.lean)：证明实际公开方法在 MOP 关闭时调用真实 `decode_raw`；
  对任意 PC、任意 ADD 原始字证明冷缓存输出，并连接真实 `fresh_decoder` 构造函数。
  还明确证明 Rust harness 的 `decode` 调用该公开方法。
- [OuterPublicStep.lean](OuterPublicStep.lean)：`cold_public_add_step` 的结论同时包含真实
  公开解码、`execute_production`、Sail `try_step`、寄存器效果、PC/next-PC 及双方内存保持。
  不再以 Rust 已解码为 ADD 或两侧字段对应作为前提。
- [OuterPublicWitness.lean](OuterPublicWitness.lean)：快速/跨页两种取指见证，
  以及联合执行实例，得到 x3=12、PC=`0x80000004`。
- [OuterConversion.lean](OuterConversion.lean)：对实际提取的整数转换验证 0、最大有符号值、
  第一个溢出值和最大无符号值，包括真实错误构造器。

配置固定为 VERSION2、IMC+B、MOP 关闭、真实初始化的冷缓存；不是任意 ISA/version/cache
配置的正确性定理。MOP 函数体已提取，**不等于证明 MOP 开启时的融合语义**，
也不等于证明所有非 ADD 指令。

保留初态关系、Rust size/load 合同、Sail 原始取指/入口/退休及 active-hart 条件。
两侧取指合同提供同一个 `w`，不是假设两个解码器输出相等；从统一物理内存推出这两个合同
仍未证明。内存见证是明确构造的 `Memory Unit U64` 接口，不是生产 SparseMemory 实现证明。
联合执行仍以不透明 `Machine` seed 为参数，不证明其非空或平台 reset 可达性。

最终公开入口步骤定理的完整传递依赖为 **158** 项；联合见证为 **159** 项（额外 Bytes 类型）。
通用公开方法的 MOP-off 引理仅依赖三个标准逻辑公理；冷缓存公开入口为 25 项。
不会因某些方法不在 ADD 选中路径中使用便从依赖审计删除它们。
既有主定理的 137 项及 raw factory 补充政策保持不变。

## 提取与工具身份

隔离输入为 `artifacts/boundary-check/aeneas-branch-ZR2ur7/OuterClosedDepsV3.llbc`，
SHA-256：`ca80303e64e2010890d43f68bb70afe716a58d3ca568e2e9e831e81873911b10`。
完整工具、入口及提取身份记录在 [extraction.json](extraction.json)。
使用 [Charon 清理尾段候选](../cfg-experimental/README.md) 及
[Aeneas 分支候选 v2](../branch-experimental/README.md)，保留 `-checks` 和既有 join recovery。
原 full-MIR sysroot、harness、CKB 源码和 opaque 列表不变；额外包含：

```text
ckb_vm::machine::VERSION3
core::convert::num::{core::convert::TryFrom<i32, u64>}::try_from
core::num::error::TryFromIntError
core::num::error::IntErrorKind
```

Charon 的匹配发生在关联类型提升之前，所以 `TryFrom` 模式只有两个类型参数。
错误类型也必须纳入；该 nightly 的错误有 `IntErrorKind` 字段，与现有 Lean 支持库的 Unit
表示不同。候选通过 `AENEAS_EXTRACT_TRY_FROM_INT_ERROR=1` 仅停用该类型的旧 builtin 映射，
从真实 Rust 类型生成定义；没有修改共享支持库或手写替代转换。

新版完整模型生成耗时约 38 秒，内核编译通过。生成模型的兼容副本仅在 `import Aeneas`
后插入 `import CkbVmProduction`，解决自动实例命名冲突；所有函数体保持生成结果。
早期 V1 提取仍保留转换 opaque，V2 因错误类型 opaque 而翻译失败，V3 的旧 Unit 映射被
内核拒绝。这些失败日志保留，不计为通过；当前通过的是 v2 工具生成的 `closed-v4-model`。

## 审计与复检

独立内核审计记录在
[public-audit-rtb154td](../../../../../artifacts/boundary-check/public-audit-rtb154td/report.json)。
既有 **56** 条定理的精确类型、完整公理集合及三个读取合同类型全部保持不变。
新公开入口的 8 条定理通过；另有 4 条转换边界检查通过。

[候选快照](audit-snapshot.json) 冻结合计 68 条定理、45 个定义函数体和三个读取合同类型。
与旧 full-MIR 定义快照相比，i/rvc 工厂因分支整理改变；`Rtype.new` 仅改变两个自动生成
证明常量的共享引用名（转为 `R4type.new._proof_1/_proof_2`）。对应通用定理原样重编译通过；
旧快照不覆盖、不自动刷新。公开方法、完整 MOP 的函数及闭包方法也纳入定义审计。

独立复检命令（不是主 proof-check）：

```sh
python3 scripts/probes/probe_decoder_public.py \
  --inputs artifacts/boundary-check/aeneas-branch-ZR2ur7
```

检查器从固定 LLBC 重新生成两个模型，在空的新缓存重编译所有本层模块，比较固定快照，
并要求错误公开结果被内核拒绝、额外 False 前提被类型审计发现。
默认模式复用主证明/raw 字段依赖，不重新提取 Rust、不重建 sysroot，
不是完整 clean-room 构建。新增的 Rust 重提取模式见下。

[独立复检报告](../../../../../artifacts/boundary-check/public-check-aysye06h/report.json)
已通过全部 **28** 个阶段，状态为 `EXPERIMENTAL_PUBLIC_CHECK_PASS`；68 条定理、45 个定义和
三个读取合同类型与候选快照精确相符，错误结果和弱化前提负测通过。
报告 SHA-256：`bd29793808985683a54177421bbb4549d238b9ee0f7554ba8bd6460616e645e5`。
生产源码基线检查前后通过，主报告、主模型和旧政策哈希不变。

补丁归档审查后再次执行了
[增强复检](../../../../../artifacts/boundary-check/public-check-7mlua7wx/report.json)：**30** 个阶段通过，
新增 Charon 源码/二进制身份与两侧补丁可应用性检查，原 68 条定理和全部快照仍精确匹配。
报告 SHA-256：`5af6710338464b5719104f8e6e34a1a137d9941727e841809f0a1323c19bb82d`。
只修复归档补丁遗漏的上下文行，未修改候选工具实现或任一证明模型；
详细的原工具对照及残余问题见 [Charon 回归审计](../cfg-experimental/REGRESSION_AUDIT.md)。

原函数指针的 16 条回归及错误参数顺序、非法签名负测在 v2 工具下再次通过，见
[回归报告](../../../../../artifacts/boundary-check/fnptr-regression-4u6h18fe/report.json)。
共享借用的九项行为审计及错误循环回边/False 前提负测也已通过，见
[借用回归](../branch-experimental/BORROW_REGRESSIONS.md)。
该阶段尚未完成工具采纳；后续限定采纳见 [ADOPTION](../../ADOPTION.md)。
Charon 全量失败仍保留，限定采纳不表示全量测试通过，也不改写 Week5 验收条款。

## 从真实 Rust 重新提取的复验

```sh
python3 scripts/probes/probe_decoder_public.py \
  --inputs artifacts/boundary-check/aeneas-branch-ZR2ur7 --reextract-rust
python3 scripts/tests/test_decoder_public_source.py
```

[Rust 重提取报告](../../../../../artifacts/boundary-check/public-check-7tj_85_6/report.json)
通过全部 **32** 个阶段，状态仍为 `EXPERIMENTAL_PUBLIC_CHECK_PASS`，
`rust_reextracted=true`；报告 SHA-256：
`a83392d9c3756ed2ffacacbf5c2090a0d15f6091907fffd96a9dc87b3a5b3720`。

该模式固定提取配置、harness、Cargo manifest/lock、迭代 fixture、rustc commit 和 full-MIR
sysroot 全部库文件的哈希。生产 crate 由既有源码基线守卫核验，仍直接作为 path dependency。
在全新 Cargo target 中以 `--locked --offline` 编译生产依赖及公开入口，再重新提取迭代 fixture。
随后从新 LLBC 生成模型，而不是继续使用归档 LLBC 的函数体。

本次两个 LLBC 与归档输入的差异仅为输出路径和 `short_names` 列表顺序；
排序后的名字条目相同。两个生成 Lean 模型均与既有候选逐字一致，
68 条定理、45 个定义及三个合同类型的固定快照全部匹配。
选项比较仅允许 `dest_file` 改变，不豁免 include/opaque、入口、sysroot 或检查开关；
十项 Python 测试（普通及 `-O` 模式）验证这些守卫。

这次不再复用生产 Cargo target，但仍复用既有源码目录、已构建的 full-MIR sysroot、
Lean 支持库及主证明/raw 字段依赖。因此不是工具链重建、全依赖干净构建或主门禁采纳。
原始生产补丁、主模型、主报告和主/raw 政策保持不变。

## 全依赖源码构建模式（独立复验通过，已接入主门禁）

```sh
python3 scripts/probes/probe_decoder_public.py \
  --inputs artifacts/boundary-check/aeneas-branch-ZR2ur7 \
  --reextract-rust --clean-dependencies
python3 scripts/tests/test_decoder_public_clean.py
```

新增模式在同一证据目录准备主证明、双侧生成源码、Aeneas 支持库及固定 revision 的
Lean 包依赖。构建前要求整个新目录没有 `.olean` / `.ilean`，导入路径只能指向该目录
或固定 Lean 编译器标准库，然后以 `lake --no-cache build` 编译。
字段/factory 的既有生成 **源码** 经原政策校验后逐文件复制，重新编译并导出字段与 raw
审计；不复制其旧 `.olean`。主定理仍须通过原主政策审计，再检查公开入口的固定快照和负测。

只有全部步骤及末尾源码复核成功，报告才设置 `clean_dependency_build=true`。
上面的 32 阶段历史报告没有运行此模式，不能用来宣称全依赖干净构建已通过。
此模式也不等于重新生成主 Rust/Sail/字段/factory 源码、重建编译器/full-MIR sysroot，
或正式采纳 Charon/Aeneas 候选；公开入口的 Rust 重新提取仍由另一个显式开关要求。
六项专用守卫测试验证：仅源码输入可以到达 `--no-cache` 构建；旧 `.olean`、旧 `.ilean`、
外部依赖缓存路径及符号链接逃逸均在编译前被拒绝；直接 Lean 审计必须收到已验证的
导入路径。它们不代替完整内核构建结果。

首次实测 [public-check-jg5ksa56](../../../../../artifacts/boundary-check/public-check-jg5ksa56/report.json)
完成 1865 个 Lake 构建任务，但随后因新增脚本漏传 `LEAN_PATH`、审计找不到 `ProductionAdd`
而失败。已修复路径传递并添加专门回归；该历史报告保持 `FAIL`，不计为全依赖验收通过。
修复后的正式模式须从另一个新目录完整重跑，不能靠重写此报告或复用其缓存获得通过。

修复后在另一全新目录完成了
[public-check-4zyu9gx5](../../../../../artifacts/boundary-check/public-check-4zyu9gx5/report.json)：
**47 阶段全部通过**，状态 `EXPERIMENTAL_PUBLIC_CHECK_PASS`，
`rust_reextracted=true`、`clean_dependency_build=true`。
报告 SHA-256：`9a5811804b4be414dcee340ba79ccac03de0df7cacf1fd4bb75c1869499e7da4`。
初始 `.olean` / `.ilean` 为 0；1865 个 Lake 任务完成，整个证据树最后包含 1836 个新 `.olean`
（含后续解码层及负测模块，不把该数冒称为主构建任务数）。

主定理原 137 项审计通过；字段九条、raw 十五条及本层六十八条定理均通过各自固定快照。
公开层四十五个定义、三个取指合同类型和语义负测全部匹配。
支持库仍有此前登记的四处 `sorry` 警告，但本次审计的这些定理不依赖 `sorryAx`。
主模型、主/raw 政策、主报告及生产源码基线保持不变。下述独立证据校验器也重新读取并
接受了这份报告；这关闭全依赖干净复验缺口，不等于完成工具正式采纳或主门禁接入。

接入准备：[public_decoder_acceptance.py](../../../../../scripts/public_decoder_acceptance.py)
要求完整 47 阶段、源码重提取及干净依赖标记，并重新读取主/字段/raw/公开入口审计，
逐项核验定理类型、定义、合同、依赖、日志和三个固定生成物哈希。
它还复核错误结果负测和 False 前提类型差异，不能仅凭报告中的 `PASS` 或公理计数通过。
17 项测试可运行 `python3 scripts/tests/test_public_decoder_acceptance.py`；已确认旧的非干净通过报告
与首次干净构建失败报告均被拒绝。该模块本身不作工具采纳决定；主门禁调用方
必须实际运行生产检查器，不能把验收历史报告当作本次执行。

[主门禁调用层](../../../../../scripts/public_decoder_gate.py) 已接入，首次集成复验通过：
要求独立采纳政策、固定配置和保留信任边界；强制调用重新提取及干净构建，不提供复用
历史报告或降级到旧检查的开关。它固定 49 个检查器/证明/配置/补丁输入，并核对
工具回归、守卫/循环等价证明等七类资格证据。十项调用层测试通过；政策文件缺失时停止。
本次主门禁于 2026-09-09 20:22:51 UTC 返回 0，116 项测试及全部 47 个公开阶段通过。
新子报告 [public-check-i12u8wjo](../../../../../artifacts/boundary-check/public-check-i12u8wjo/report.json)
SHA-256 为 `449c93663a44abd58d10c174b0f6f90aba82020fa5423cce071b037d8cee14a8`；
主报告及政策归档、独立重验和边界见 [完成审计](../../COMPLETION_AUDIT.md)。
