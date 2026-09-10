# 函数指针提取候选：未采纳为正式工具基线

2026-09-09：原始 ADD 的已采纳 factory 证明保持不变；本目录继续处理真实
`DefaultDecoder` 的函数表。**这是工具实验及回归证明，不是完整 decoder 对应定理。**

同日后续：[full-MIR 隔离实验](../full-mir/README.md)使用同一候选工具，已提取并证明真实
共享 Vec 迭代入口，进一步证明工厂顺序、ADD 选择、缓存更新；后续已推广到任意 PC、
两种取指分支的冷缓存 `decode_raw`，并连接到生产 ADD 执行定理。
下文的 43 项不透明声明和迭代失败描述属于本目录原报告，不是后续实验的当前结论；
完整公开 decoder 及最终连接仍未完成，工具仍未正式采纳。

## 结果

[独立实验报告](../../../../../artifacts/boundary-check/fnptr-regression-cqj3wxvy/report.json)
通过 21 个阶段，报告 SHA-256：
`d54ba95c37698bc714ec49b899bad9d91ad6845dc1432a5e7b7467c11167562b`。

- [16 条回归定理](FnPtrProof.lean) 检查未知回调、两分支选择、失败和发散传播、
  两项表初始化/索引/越界、不同函数项实例、循环命中/继续/结束。
  精确公理列表只含标准逻辑公理或为空；没有 `sorryAx`、native 或新增行为公理。
- 原已采纳工具仍以不支持箭头类型拒绝同一个输入；候选工具通过。
- 交换间接调用实参后的模型仍可编译，但回归定理失败。
- 借用参数、外部 ABI、隐藏 `'static` 借用结果、unsafe 和零参数函数均拒绝。
- 真实 `DefaultDecoder` 的初始化、`decode_raw`、`decode_bits` 和循环体有实际定义，
  补齐常量、沿用四个非 ADD 比较方法的 opaque 边界后，整个外层探针模型通过 Lean 编译。
  **其共享 Vec 迭代入口和 SparseMemory 方法仍是不透明声明**，报告列出全部 43 项。
- 新模型没有复用旧 olean；Lean/Aeneas 标准库及主证明依赖缓存复用，非全图 clean build。
- [旧用例回归](../../../../../artifacts/boundary-check/decoder-fnptr-lx9JGu/legacy-regressions-report.json)：
  严格 joins、嵌套共享借用、已证明的最小闭包生成物逐字不变；
  非法借用仍在 `InterpPaths.ml:227` 拒绝。

循环回归从显式构造的标准库迭代器开始，不证明 Rust `through_table` 的
不透明 `IntoIterator` 入口；不能借此宣称整个 for 循环生产连接已关闭。

## 候选身份及限制

- Aeneas：`379890b54b4961dc7729e314c6eefdc09fe50981`。
- Charon：`89ac118194b978d8cf753222c19f313521377aa0` / `0.1.247`。
- [组合补丁](aeneas-fnptr-experimental.patch) SHA-256：
  `a8ef142bd11bf29a923649920f95ae15b730f5d4aaf1ed5da5b9ec8a27e4e3c9`。
  它从上述上游 commit 应用，已包含旧 join-recovery 补丁，不能重复叠加。
- 本机候选二进制 SHA-256：
  `504cd66e34a386174fd763b41fb7fd91f50ab00f8edd5c811562365defcd6554`。
- 源码/构建位于
  `artifacts/boundary-check/decoder-fnptr-lx9JGu/aeneas-src`；
  独立 clone，复用旧隔离 OCaml 5.2.1 switch 和只读 Charon 源码，未改全局工具/支持库。

新增处理包括函数指针的类型、转换、符号间接调用、无借用签名的投影/上下文比较，
以及函数项 trait 实例的命名区分。间接调用被保守标记为可失败和可发散。
只支持非空标量参数、闭合无借用结果的安全 Rust ABI；拒绝复杂借用、
unsafe/foreign/variadic、零参数 thunk 和 fuel 模式。转换后签名必须相等，
未知调用保留为实际的 `f args` 及 Result 绑定，不假定回调成功。

命名修正保留不同 Rust 函数项的身份，解决 `set_instruction_length_2` 与
`set_instruction_length_4` 被生成同名实例的问题。因此某些旧 factory 内部标识符会变，
不能用候选工具直接替换已冻结工具并声称生成物相同。
这些有限回归也不是翻译器正确性的形式化证明。

## 原报告的未关闭项与后续状态

1. 共享 `Vec::IntoIterator`：三个泛型占位的 include 没有匹配 Charon 提取前的签名。
   改用 `IntoIterator<_>` / `IntoIterator<&_>` 后，实际入口有 LLBC 函数体，
   但预编译标准库 MIR 已展开到不透明 Vec 的内部字段，Aeneas 拒绝。
   失败证据：实验目录的 `FnPtrCasesV4.llbc`、`FnPtrCasesV5.llbc` 及
   `aeneas-cases-v5.log`、`aeneas-cases-v6.log`。不能忽略错误或把新入口公理当成已证明。
2. 真实 factory 顺序及 ADD 的 RVC 排除、cache 初始化/命中/更新、实际取指与同一原始字的联系。
3. 配置中 MOP 的边界、外层到已采纳 raw ADD 定理的连接，以及新的类型/依赖/非空性审计。
4. 候选工具若正式采纳，需要另行固定工具、提取配置和审计政策；本次没有执行采纳。

迭代入口及部分外层合同已在上述 full-MIR 实验推进；其余精确边界见后续报告。
不要通过改生产 CKB 源码或新增未经披露的行为前提掩盖这一缺口。

## 重跑实验

在仓库根目录、既有共同 Lean 4.31.0 依赖已构建的环境中：

```sh
python3 scripts/experiments/probe_decoder_fnptr.py \
  --translator artifacts/boundary-check/decoder-fnptr-lx9JGu/aeneas-src/src/_build/default/main.exe \
  --outer-llbc artifacts/boundary-check/decoder-fnptr-lx9JGu/OuterScoped.llbc
```

[检查器](../../../../../scripts/experiments/probe_decoder_fnptr.py) 校验候选源码 commit/组合补丁，
重新提取最小 Rust 用例并从空新模块缓存检查；外层输入是带哈希的既有 LLBC，
不是本脚本重新提取的生产源码。探针使用的原生产入口保存在旧实验目录
`decoder-toolchain-VBwba1/outer/lib.rs`，仍是实际 `DefaultDecoder::new::<u64>`
和 `decode_raw` 调用，没有替代函数表实现。

原生产源码仍是 `ckb-vm-1ffba3977da9-runtime-container-v1`；
原主政策、主 PASS 报告、raw ADD 政策和已采纳补充工具的哈希前后相同。
本次未新增 CKB-VM 补丁，未扩张 Week5 验收，也未接入主 proof-check。
