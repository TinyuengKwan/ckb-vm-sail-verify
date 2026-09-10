# Aeneas 短路返回及共享借用连接实验记录

后续状态：v2 已按 [公开 ADD 限定政策](../../ADOPTION.md) 采纳；全局原工具不变。
下文保留实验阶段记录及当时的“未采纳”状态。全量测试失败没有被限定采纳变成通过。

2026-09-09。与 [Charon 清理尾段实验](../cfg-experimental/README.md) 配合，
在不更改 CKB 生产源码、不将 MOP 或工厂变成 opaque 的前提下提取实际公开解码入口。
本目录不是正式工具基线；Lean 检查提取后模型，也不等于证明编译器变换保持 Rust 语义。

## 候选 v1

[组合补丁](aeneas-branch-experimental.patch) 基于 Aeneas
`379890b54b4961dc7729e314c6eefdc09fe50981`，包含之前的函数指针和 join recovery 修改。
补丁 SHA-256 为 `3c61840ccb47da116a3652ff70d193d3225849d78be9fd299ea4e1c231aa0382`。
隔离二进制 `artifacts/boundary-check/aeneas-branch-ZR2ur7/candidate-bin/aeneas`
SHA-256 为 `f0712a613a22ab34ec1fa128aa96d715051b4121ca1647e559c86652401ccf00`。

新增部分：

- `AENEAS_FACTOR_RETURN_GUARDS=1` 启用保守的短路返回整理：仅针对尾部布尔条件链、
  空/StorageDead 旁支和没有内层分支的返回叶子，将**完整原返回叶子**放在新布尔条件之后。
  条件顺序、守卫中的操作和失败清理保持原位；拒绝投影写入及依赖守卫赋值局部量的叶子。
- reduction、duplicate collapse 和 preflight 一致排除没有左右标记的抽象值。
  它们不参加双侧标记合并，不必为了连接无关标量而展开其内部共享引用。
- 匹配连接后的上下文时，只把两侧 `equal_abs` 完全相同的抽象固定为自身，
  为其内容建立身份映射；不因父抽象 ID 出现在内容中便把父抽象固定。
- 两个诊断环境开关只记录分支数量和借用检查位置；生产生成时未启用。

保留 `-checks`，不增加 fuel 或关闭原有借用检查。完整提取仍使用既有 join recovery：
遇到不支持的工厂连接时保留原分支上下文并复制后续计算。
`-strict-joins` 完整输入仍在 i 工厂的嵌套借用处拒绝，不能声称全部严格连接已支持。

## 证据与限制

真实完整输入 `OuterCleanupChecked.llbc` 用 v1 在 40.534 秒生成 Lean，包含公开方法、
MOP 和四个工厂的函数体；该模型及既有外层证明均通过内核检查。
但公开方法的传递依赖增加了 `VERSION3` 和 `I32.TryFrom<u64>` 两个 opaque 项，
因此后续仍在提取这两个定义，不能仅因 MOP 关闭便从审计名单删去它们。

[GuardedFactored.rs](GuardedFactored.rs) 是小型诊断参考，不是生产源码替代品。
[GuardEquivalence.lean](GuardEquivalence.lean) 对所有输入证明：原始含 owned error 的短路
fixture 经新变换生成的模型，与参考 fixture 经旧工具生成的模型相等。
[GuardCounterexample.lean](GuardCounterexample.lean) 构造反转返回守卫后结果不同的具体反例，
[RejectWrongGuard.lean](RejectWrongGuard.lean) 的错误等式必须被内核拒绝。
这些检查仅用 Lean 常规逻辑公理，无 `sorry` 或 native 决策。

日志及原模型保留在 `artifacts/boundary-check/aeneas-branch-ZR2ur7/`：
`kernel-equivalence-v2.log`、`kernel-counterexample.log`、
`kernel-reject-wrong-guard-v2.log`。早期负测因缺少 Decidable 而失败的日志不计为语义负测。
共享引用/循环的另两个 fixture 已进一步补上九项精确审计及行为证明，见
[共享借用回归](BORROW_REGRESSIONS.md)；不等于完成工具全量回归或变换正确性证明。

候选独立复检和原函数指针回归已完成，证据见下；Charon 金样差异已分类审查，
但全量失败闭环及正式工具采纳仍未完成。
新的公开入口证明见 [full-entry](../full-entry/README.md)；主政策及旧实验快照不自动刷新。

## 候选 v2：提取新版整数错误类型

[v2 组合补丁](aeneas-branch-v2.patch) 在 v1 上增加一个显式开关：
`AENEAS_EXTRACT_TRY_FROM_INT_ERROR=1` 停用 `TryFromIntError` 的旧 builtin 类型映射。
所用 nightly 已将该类型从 Unit 改为包含 `IntErrorKind` 的结构；仅纳入 Rust 函数体而
沿用旧类型会被 Lean 内核拒绝。新开关让实际 Rust 类型随函数一起提取，没有改变支持库。
这不是一般性的自动标准库版本适配；该输入需要明确包含两个错误类型的真实定义。

v2 补丁 SHA-256：`956a3b1b895c9ffee8376d7cc8f2440efcedba8592908bac8b58c4a07b7c387d`。
二进制 `aeneas-branch-ZR2ur7/candidate-v2-bin/aeneas` SHA-256：
`1fe7040d9dc5dc2af5320722c23199eddb2d1d540a303f7fcbaa7cb0defacaae`。
两版二进制和补丁均保留，当前隔离源码对应 v2；正式工具未改变。

v2 生成的 owned-error 守卫模型与已证明等价的 v1 模型逐字相同，SHA-256：
`c9a0a533a6875b9ac6abff4c78cfe2d2defbd14495cbe9489c2a3373c6c8571f`。
原 16 条函数指针回归及错误参数顺序/非法签名负测已复检通过：
[fnptr-regression-4u6h18fe](../../../../../artifacts/boundary-check/fnptr-regression-4u6h18fe/report.json)。
该次使用单独的复检副本，指向 v2 补丁及两个显式环境开关，未修改原回归门禁的工具身份。
完整公开输入的 68 条证明和新独立检查器见 [full-entry](../full-entry/README.md)。
仍须审查 Charon 全量回归差异和两个工具的变换边界，不能因此宣称已正式采纳。

后续 [Charon 原工具对照审计](../cfg-experimental/REGRESSION_AUDIT.md) 已分离出
11 个选定输出变化和既有失败，并修复补丁归档问题；公开入口的增强复检再次通过 30 个阶段。
全量环境失败、借用/清理变换的进一步检查和正式采纳仍未关闭。

共享借用的后续核验已通过 14 阶段，包括任意 `u32` 次数循环、两次累计更新、
错误回边的实际反例轨迹及 False 前提弱化负测；见 [详细边界](BORROW_REGRESSIONS.md)。
