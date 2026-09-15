# 条件性 ADD 证明验收门禁

2026-09-13：[正式主工具入口迁移](../../../docs/release/FORMAL_MAIN_INTEGRATION.md)
当时接入 `rebuilt-main-v1` 和政策 `7ced9f42…`，要求 28 主阶段、21 组 287 测试。
新正式完整执行于 06:26 UTC 完成，06:29 UTC 独立验收通过：28 主阶段、287 测试、
48 公开阶段及 68 公开定理。完整来源及归档见上述正式迁移记录。
下文 24/236 等已完成报告保持历史身份，不归到新政策；本次通过也不关闭 Week6。

当前政策为逐族案例修正后的 `b5bdc401…`，不是上述旧政策。
[本轮完整正式链](../../../docs/release/FORMAL_FINAL_EXECUTION.md)于 22:21 UTC 完成并独立验收，
同样为 28 主阶段、287 测试、48 公开阶段、68 定理；其 Lean/Rocq 报告已由
[最终执行连接检查](../../../docs/release/WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)
绑定到同一生成记录。这不关闭完整工作树或 Week6，也不改写旧报告身份。

入口：`make proof-check BACKEND=lean`。验收对象为
[ProductionAdd.decoded_add_step](../theorems/ProductionAdd.lean) 及新增必需的
[OuterAdd.cold_public_add_step](../decoder/toolchain/full-entry/OuterPublicStep.lean)，生产来源是
[受审 upstream + runtime-container 补丁](../extraction/ADOPTION.md)，不能归到原始干净 commit。

返回 0 要求本次重新生成、内核检查、来源/前提/公理审计、负向测试及干净构建全部通过。
保证等级仍为 `conditional`；指定配置下同码 ADD 解码不再是假设，取指/状态关系及 Sail
前缀/初始化条件保留，不提升完整指令的
`runtime-only` 状态，不代表 Week 6 的 `audit-release`。

公开 decoder 的限定工具采纳和来源迁移见 [ADOPTION](../decoder/ADOPTION.md)。
独立干净复验及首次集成主门禁实跑均已通过；后者于 2026-09-09 19:49:20–20:22:51 UTC
执行，116 项测试、公开子检查 47 个阶段及 1865 项干净构建任务通过。
报告哈希、归档和独立重验结果见 [完成审计](../decoder/COMPLETION_AUDIT.md)。

2026-09-13 公开调用层已迁移至 v2 输入；首次全门禁因两处已证等价 map 的定义指纹
漏迁移而失败。[精确修正](../../../docs/release/REBUILT_AUDIT_CORRECTION.md)后于
01:15:28–02:03:45 UTC 完成新一轮完整门禁，退出 0 并独立验收通过；
[成功归档](../../../docs/release/REBUILT_GATE_ACCEPTANCE.md)包含 24 主阶段、236 测试及 48 公开阶段，
不是沿用历史 PASS。主定理/合同/公理不变，
只迁移这两项已证等价定义及元数据引用；其余精确审计继续强制执行。

## 实际执行的检查

[check_proof.py](../../../scripts/check_proof.py) 顺序执行：

1. 校验 CKB 上游锚点、固定补丁、完整源码树、提取配置和源码 manifest；Sail 子模块
   要求固定 commit 且干净。校验所有证明/生成/门禁源码、工具二进制及版本、
   Aeneas 支持源码和固定共同 Lean 4.31.0。
2. 物化 Sail 配置、运行环境检查；真正重新运行 Charon/Aeneas 与 Sail 生成。
   检查生成源码、配置及 Rust `SOURCE_BASELINE.json` 的来源/LLBC/模型绑定。
3. `check_lean_imports.sh --step` 构建双侧模型、正式最终定理、两个 wrapper 合同、
   各层依赖 guards 与 17 条既有寄存器/step 回归引理，以及具体 Sail 联合见证和双侧实例。
   共同 Lake lock 不更新。
4. [ExportStepAudit.lean](../audit/ExportStepAudit.lean) 从 Lean 环境导出最终定理与合同
   的传递公理、定理类型、合同构造器和状态关系/投影/有效性定义；
   与独立固定的 [policy](../audit/step-policy.json) 精确匹配。新增见证独立审计依赖集合，
   并固定其类型/初态定义；原有 18 项边界不变，合计 31 项。
5. 执行 import 门禁、真实 Lean 负测、proof-check、源码基线及主/公开解码干净构建守卫测试。
6. [公开解码调用层](../../../scripts/public_decoder_gate.py) 核验限定工具政策，重新提取生产公开
   Rust decoder，使用原干净构建准备机制在全新目录重建主模型/支持库/字段/factory/公开层。
   原主定理 137 项、字段九条、raw 十五条、公开六十八条定理分别对照固定政策/快照。
   同时要求错误公开结果及 False 前提弱化被检测，独立复核全部证据文件。
   最后复查来源、生成物及主/公开政策没有漂移；不再重复执行一遍主依赖构建。

门禁没有自动刷新 policy、跳过生成/测试或接受“预期 blocked”的成功分支。
新运行先写 `running`，失败写 `failed`，不能沿用旧 PASS；固定报告目录禁止并发发布。
日志中的 PANIC 即使退出 0 也拒绝。

[联合前提见证](ADD_NONVACUITY.md) 消除了“没有任何 Sail 联合合同实例”的证据缺口。
双侧实例仍需 Rust seed，通用初始化仍未关闭；新公开入口定理关闭指定配置下的同码 ADD
解码桥接。历史失败提取探针不计为成功阶段，工具全量测试的已知失败仍见采纳边界。

## 干净构建的具体范围

公开阶段每次新建 `artifacts/boundary-check/public-check-*/clean/`，不删除或移动原有用户构建目录。
独立 `check_lean_clean.py` 仍可检查原主定理，但不替代主门禁的公开解码阶段：

- 从源码复制手写定理、Rust/Sail 生成模型与 Aeneas 支持库，不复制任何旧
  `.lake`、`.olean`、`.ilean` 或本机构建库。
- 按共同 lock 从本地固定 Git 对象重新 checkout mathlib、lean-sail 等全部 Git 依赖；
  不继承这些依赖的编译产物，开始时确认项目树中已编译 Lean 模块数为 0。
- 使用 `lake --no-cache build`，不下载编译缓存，不运行 `lake update`。
  `LEAN_PATH` 只允许新目录与固定 Lean 编译器的标准库；外部旧支持库路径会被拒绝。
- 构建后检查模型/证明源码和 lock 与正式输入一致，重新检查最终定理依赖与签名。

复用固定 Lean 编译器及其标准库，不从源码重建编译器本身。这满足本周干净证明构建，
不是 Week 6 的工具安装、全流程第三方 clean-room 或二进制供应链认证。

## 137 项最终依赖及合同审计

| 分类 | 数量 | 边界 |
|---|---:|---|
| 标准 Lean 逻辑 | 3 | propext、Classical.choice、Quot.sound |
| Rust/Aeneas opaque 类型 | 6 | Bytes、Formatter、DefaultDecoder、SparseMemory、MachineRuntime、Pause |
| wrapper 五个方法公理 | 0 | 已由真实生成定义及两个合同证明替代 |
| 其他 Rust/Aeneas opaque 操作 | 54 | 完整生产字典/dispatch 的其余外部操作 |
| Sail 外部操作 | 74 | 完整 dispatch/step 的浮点、reservation、随机数、平台输出等 |

全名逐项列在 policy，不按命名空间通配放行。相对旧 141 项，只移除 DefaultMachine
类型和五个方法公理，新增 MachineRuntime、Pause 类型；没有其他依赖集合变化。
两个合同分别依赖 63 项，均不引入额外行为公理。最终定理与合同均不依赖 `sorryAx`。

Aeneas 支持库仍有四处已知 `sorry`：Slice 的 get_unchecked 及其 spec、
StringIter 的 next/fold。它们不在本定理/合同的传递依赖中，不宣称整个导入闭包无占位。
未选分支的外部声明仍如实保留在最终依赖清单。

## 剩余显式条件

`ProductionWrapper.view m = m.inner`、`valid m = True`，任意给定机器满足 valid；
寄存器和 PC 委托合同已证明，不再是最终定理参数。这不构造 opaque runtime 或初始机器。

原内部定理仍需提供初态 `state_rel_pc`、Rust `DecodedAdd`、Sail `StepEntry`、
`ActiveAddPath`、`RetireReady` 与 active-hart 条件。没有假设 ADD 的最终执行结果，
但尚未从统一原始字及具体平台初态推出这些条件。
新增[联合见证](ADD_NONVACUITY.md) 已在一个直接构造的 Sail 模型初态证明这组 Sail
条件同时成立，并相对于给定 Rust seed 实例化最终定理；这不证明 reset 可达性、
`Nonempty Machine`。新增 `cold_public_add_step` 则从原始 ADD 字和明确取指条件推出
两侧解码及后态，不再要求调用方提供 `DecodedAdd` / ADD 路径结论。

固定 `get_config_rvfi=false`、`get_config_print_instr=false`。
结论涵盖 GPR、PC/nextPC、正常退休和双方各自 memory frame，不是跨侧内存等价，
不覆盖 Rust 整体 step/计费、一般 ISA/配置的 decoder 正确性、RVFI exporter、
trap/中断/compressed 执行路径。
RV64 ADD 的结果宽度为 64，无 ADDW 的窄化后符号扩展义务。

## 报告与维护

主报告：`artifacts/proof-check/report.json`；正式导出：同目录 `lean-audit.json`。
干净构建另保留新目录、初始缓存计数、导入路径、依赖 revision、编译日志及独立审计。
完成 Week 5 的逐项证据汇总见 [WEEK5_EXIT.md](WEEK5_EXIT.md)。

维护时先审查源码和证明变化，再重新导出精确依赖与类型，最后人工核对 policy diff。
删去公理也需要复核。历史源码采用 manifest 中的 `proof_acceptance` 是采用时的状态，
当前证明验收由独立 step-policy 和本次执行报告决定。
