# 公开 ADD decoder：限定工具基线与主门禁接入

2026-09-09。已落实 [public-policy.json](public-policy.json)，并将公开解码作为
`make proof-check BACKEND=lean` 的必需阶段。**首次集成实跑已通过，退出码为 0。**
本次于 19:49:20–20:22:51 UTC 完成，116 项测试、47 个公开子阶段和 1865 个干净构建任务通过。
报告文件、生成物与冻结身份已独立重验；不是用旧资格报告代替本次执行。
逐项要求、源码依据、精确报告哈希和保留边界见 [完成审计](COMPLETION_AUDIT.md)。

## 采纳身份及范围

生产源码仍为 `ckb-vm-1ffba3977da9-runtime-container-v1`：上游
`1ffba3977da9dcdef8092e9ab1fd2516b27ec939` 加既有 runtime-container 补丁。
本次没有新增 CKB 源码补丁、没有修改原主模型或替换全局安装工具。

新增的限定提取基线是：

- Charon `charon-89ac1181-cleanup-suffix-v1`，源码锚点
  `89ac118194b978d8cf753222c19f313521377aa0` 加清理返回尾段补丁。
- Aeneas `aeneas-379890b5-public-add-v2`，源码锚点
  `379890b54b4961dc7729e314c6eefdc09fe50981` 加函数指针、分支/共享借用及整数错误类型补丁。
- Rust nightly-2026-08-18，保留 full-MIR std；共同 Lean 4.31.0。
  精确补丁、二进制、入口及 include/opaque 配置见
  [extraction.json](toolchain/full-entry/extraction.json)。

配置匹配运行器 `DEFAULT_ISA = ISA_IMC | ISA_B`、VERSION2：MOP 关闭、真实初始化的冷缓存，
原始 ADD 字及 PC 任意，但保留明确的 size/取指合同。不是任意缓存/ISA/version 配置，
不涵盖 MOP-on 融合、非 ADD 指令或整个 VM 正确性。

`OuterAdd.cold_public_add_step` 从同一个 `w : BitVec 32` 出发，经真实公开 decoder、
Rust 生产执行和 Sail 原始解码/step，证明寄存器、PC/next-PC 及双方各自内存保持。
它不以 Rust 已解码为 ADD 或双方解码字段相等为前提。
状态关系、Rust size/load、Sail raw-fetch/入口/退休条件仍显式保留；统一物理内存对应、
生产 SparseMemory 实现、Rust opaque Machine 非空性和平台 reset 可达性仍未证明。

## 工具信任边界与审查依据

本次采纳的是**受审、固定的可信翻译工具基线**，不是翻译器变换的通用形式正确性证明。
`-checks` 未关闭，没有给生产模型加 fuel，也没有把工厂、MOP 或函数表改为 opaque。

政策固定七类资格证据：完整公开解码干净复验、九项借用行为审计、十六项函数指针回归、
Charon 双版本 UI 对照、失败诊断归因、守卫等价及循环等价证明。
它同时冻结 49 个检查器/证明/配置/补丁输入。未来更换工具或变更这些输入必须重新审查，
检查器不会自动接受新哈希。

上游全量测试**不是全绿**：Charon 对照共 435 项，433 项已执行用例退出码一致；
11 项选定输出差异已作结构审查，其中 7 项新增金样不符。
候选仍有 56 项金样不符、26 项命令失败、1 项缺少金样、1 项不检查输出、2 项忽略；
原工具已有 49 项金样不符。缺少 odoc/Miri/交叉目标及 clippy 覆盖等问题没有被本次采纳修复。
不刷新上游金样，不把共同失败记为 PASS；保留的全量测试限制见
[回归审计](toolchain/cfg-experimental/REGRESSION_AUDIT.md)。
这些哈希是身份固定，不是经过认证的上游二进制供应链证明。

## 主门禁流程

主门禁先重新生成主 Rust/Sail 输入并检查原主定理，再执行公开 decoder 阶段。
后者重新提取生产 Rust 公开入口，在全新目录编译主模型、支持库、字段/factory 层和公开层，
并分别按原主/字段/raw 政策及公开快照审计。它同时满足原来的主证明干净构建要求，
不需要再做一遍相同主依赖构建；原 137 项审计不会被公开层 158 项审计替代。

`public_decoder_gate.py` 强制传入 `--reextract-rust --clean-dependencies`，没有跳过或
复用历史报告的开关。它要求明确采纳政策，重新校验报告的 47 个阶段、实际日志、
生成物和全部审计文件，再向主报告写入 `public_decoder` 及主依赖 `clean_build` 证据。
底层生产检查器仍保留历史状态标签 `EXPERIMENTAL_PUBLIC_CHECK_PASS`；其
`main_gate_adopted=false` 表示它本身不作主门禁采纳决定，该决定由父层政策检查负责。

## 迁移差异和保留证据

主政策仅改变 `local_sources`、`configuration` 和 `outstanding_contracts`：新增调用层/公开政策
来源固定，说明新增解码范围，并将过期的“同码解码未关闭”说明替换为真实剩余取指边界。
原定理名、全部公理、精确类型/关系/合同指纹、wrapper 依赖、见证依赖及原工具哈希均未改变。
公开层 68 条定理、45 个定义及三个取指合同的快照也未改变。

主政策 SHA-256：`818ab391b46d92b0929ac8620600735f6c3aa2c44116d797c0deeaecb6c1e449`。
公开政策 SHA-256：`10b5ab173c36d9e7cf4ffca7d3467281397e11081115f07b6832ade6847dabf1`。

迁移前的主政策、报告、审计和日志及被修改的检查源码共 22 个文件保留在
[public-adoption-xQNXpE](../../../artifacts/boundary-check/public-adoption-xQNXpE/before-hashes.json)。
原主政策 SHA-256 为 `a65f8c972f4cfe0309c7006875dbf66816affce24439c5653fdc5ea8c1b16aa3`。
旧通过报告与首次干净复验的失败报告均保留，不改写为新政策下的通过。
Week5/6 计划文件保持原字节，coverage 不因此自动升级为完整指令 `proved`。

## 首次集成验收结果

本次[主报告归档](../../../artifacts/boundary-check/public-adoption-xQNXpE/after/artifacts/proof-check/report.json)
SHA-256 为 `4a92b85f7d18891407fcd295aa27d93c9690f604fc6370ec59bb98533b2794b3`，
[公开子报告](../../../artifacts/boundary-check/public-check-i12u8wjo/report.json)
SHA-256 为 `449c93663a44abd58d10c174b0f6f90aba82020fa5423cce071b037d8cee14a8`。
主报告明确记录 `main_gate_adopted=true`、`tool_adoption_claimed=true`；
保证等级仍是 `conditional`，`coverage=runtime-only`、`release_audit=false`。

全新公开运行目录初始 `.olean/.ilean` 数为 0；主依赖子树新建 1806 个 `.olean`，
公开目录全部阶段合计 1836 个（包含额外 decoder 和负测模块，不是 1836 条定理）。
仅复用固定 Lean 编译器及其标准库作为 Lean 编译输入；Rust full-MIR sysroot 使用固定既有版本，
不声称重建了编译器或 sysroot。生产 Rust 公开入口本次确实重新提取。

迁移后的主报告、主审计、16 个阶段日志及两份政策共 20 个文件另存于
`public-adoption-xQNXpE/after/`，逐一核验复制哈希；`before/` 和历史失败记录保留原样。
