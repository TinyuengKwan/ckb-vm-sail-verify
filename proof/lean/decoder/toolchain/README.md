# 原始 ADD 补充提取：工具基线与边界

本工具基线只用于 `proof/lean/decoder` 的独立检查。
不覆盖已固定的主 Aeneas 二进制，不改变主生产模型，不新增 CKB-VM 源码补丁。
生产源码仍是 `ckb-vm-1ffba3977da9-runtime-container-v1`，不能归到未打补丁的上游 commit。

## 身份

- Aeneas 源码：`379890b54b4961dc7729e314c6eefdc09fe50981`。
- Charon 源码及提取器：`89ac118194b978d8cf753222c19f313521377aa0`，版本 `0.1.247`。
- 补充工具 ID：`aeneas-379890b5-recover-nested-shared-joins-v1`。
- [补丁](aeneas-join-recovery.patch) SHA-256：`5a924e2a6e38696eae8211f6e01b1b181bc85b1c5ce0cbf5fb44766e915f0dd9`。
- 本机已审查二进制 SHA-256：`0f757f5e9a316ab7ecacf1a36923990ed65f22bf40c67a4bd4ef5284026bee2a`。
- 本机版本输出：`aeneas 379890b5-dirty`；不能只靠这个字符串标识工具。
- OCaml `5.2.1`；[实际安装包版本](opam-packages.txt)。共同 Lean 仍为 `4.31.0`。

[构建脚本](../../../../scripts/build_decoder_toolchain.sh) 在新的隔离目录克隆精确源码、
应用补丁并建立局部 opam switch，不改变全局 switch 或主工具。
本机工具由同等分步命令建立；脚本经过语法检查，未再次从空环境重建。
依赖版本列表不是供应链认证，亦未声称在不同机器或路径下重建字节相同的二进制。
新构建须复核来源、回归、生成物和二进制哈希后，人工更新独立政策；构建脚本不会接受新哈希。

## 补丁做什么

修改四个 OCaml 文件，使用工具原有的可恢复合流机制：

1. `collapse_ctx` 在非冻结抽象共享 loan 中发现具体共享 borrow 时，拒绝该合流。
2. `destructure_abs` 新增默认 `false` 的 `recoverable` 参数；四个已有
   “不支持嵌套借用”检查仍执行，失败时按调用方决定是否允许恢复。
3. 分支合流传递原有 `recoverable` 设置。恢复时保留各分支原环境并分别执行后续代码，
   不合并这些状态，不略过借用检查，也不把错误分支改成成功。
4. `-strict-joins` 和其他不可恢复调用仍报错；未修改通用 internal-error 断言。

这不是新增函数指针支持，也不是 Aeneas 翻译器正确性的形式化证明。

## 回归证据

[回归报告](../../../../artifacts/boundary-check/decoder-toolchain-VBwba1/tool-regressions-report.json)
保存日志和输入哈希：

- 原工具在[最小共享闭包例](decoder_shared_closure.rs)的 `InterpMatchCtxs.ml:230` 失败；
  补丁工具在 `-checks` 下提取成功，严格合流模式仍拒绝。
- [MiniProof.lean](../MiniProof.lean) 对**所有 bits/version 输入**证明实际提取函数符合独立分支规格；
  只使用三个标准逻辑公理。`Option.map` 也提取为定义，不接受其不透明行为。
- 上游 `joins.rs` 的严格模式生成物，以及 `nested-shared-borrows.rs` 的生成物，
  均与原工具逐字相同。
- 上游非法借用用例在原工具和补丁工具中均以相同的无效投影错误拒绝。

## 提取配置

[extraction.json](../extraction.json) 固定真实 `i::factory::<u64>(bits, VERSION2)` 调用入口、
opcode 常量、`Option.map` 实现及命名空间。四个非 ADD 比较方法沿用主证明的 opaque 边界，
避免支持库缺失 `core.convert.FromU64Bool` 字典造成的编译失败；没有把 decoder/factory/组装函数设为 opaque。
完整 factory 提取含其他指令分支，并不等于已证明其他指令正确。

`raw_add_step` 的精确公理数为 **158**，原主定理仍为 **137**。
新增 21 项均来自独立命名空间中的 `Register` 实例方法依赖；ADD 选中路径不调用这些方法。
不能把“未在 ADD 路径调用”写成“没有公理”。工厂分派、`Option.map`、`Rtype::new`、
长度设置及被证明的内部字段读取都有实际函数体；独立政策冻结精确依赖、类型和关键函数体。
没有接受 `sorryAx`、本机计算公理或额外的行为正确性公理。

## 仍未支持的外层

本节描述本页的**已采纳 join-recovery 工具基线**。后续另有
[函数指针实验候选](fnptr-experimental/README.md)，未覆盖本页的工具身份或正式政策。

真实 `DefaultDecoder::new` / `decode_raw` 的独立探针已生成无错误 LLBC，
但 Aeneas 在其 `Vec<InstructionFactory>` 类型失败：`TFnPtr/TFnDef` 不被支持。
最小 `Vec<fn>` 用例复现同一错误；单态化另在 Box/Vec 类型参数不变量处失败。
相关探针只是不成功的提取诊断，不是 cache、取指、factory 顺序或 MOP 的证明。

继续关闭这一层需要函数指针建模，或另行审查新的源码重构及生产基线；
不能把当前 factory 证明替代它，也不能静默将函数表声明为 opaque 后宣称完成。

2026-09-09 后续：新的 [full-MIR 与公开入口隔离候选](full-entry/README.md)
已提取函数表迭代、全部工厂和 MOP 函数体，证明公开方法 MOP-off 的 ADD 路径并连接最终定理。
该结果使用新的 Charon/Aeneas 基线，不改变本页已采纳工具身份。
后续已按 [公开 ADD 限定政策](../ADOPTION.md) 采纳并接入主门禁，首次集成实跑已通过；
上游全量回归的已知失败仍明确保留。
