# 原始 ADD 编码到公开解码及生产执行：完成审计

2026-09-09。范围沿用本轮 ADD 解码对应任务：正常 32 位 RV64 ADD，运行器的
IMC+B、VERSION2、MOP 关闭配置。不将“完整解码”扩大解释为全 ISA 正确性，
也不以仅字段拆分或手写工厂模型代替真实公开 decoder。

**验收通过**：首次集成的 `make proof-check BACKEND=lean` 已退出 0，主报告为 `passed`。
完成后独立重验了报告、阶段日志、模型、审计快照、冻结来源和采纳迁移。
结论限于下列已说明配置下的 ADD 解码与执行连接，不是无条件 VM 正确性或 release 验收。

## 逐项证据

| 要求 | 当前可核查的实现与证据 | 验收判定 |
| --- | --- | --- |
| 覆盖任意原始 ADD 字，而非单个样例 | [RawEncoding.lean](RawEncoding.lean) 的 `IsRawAdd` 只限制 opcode/funct3/funct7；`raw_add_iff`、`reconstruct` 覆盖全部 rd/rs1/rs2 组合 | 源码、raw 政策及本次干净内核复验通过 |
| 同一码字通过双方真实解码得到相同操作数 | [RawAddStep.lean](RawAddStep.lean) 的 `raw_decoders_correspond` 引用提取的 Rust factory 和 Sail `ext_decode`，并证明生产 `DecodedAdd`；后者不是输入前提 | 源码、内核复验和精确 raw 审计通过 |
| 不止 factory，连接真实公开 Rust decoder | [OuterPublic.lean](toolchain/full-entry/OuterPublic.lean) 的 `decode_cold_public_word`、`fresh_public_word` 引用实际 trait method；[OuterInit.lean](toolchain/full-mir/OuterInit.lean) 将初始值证明等于实际构造器结果 | 不是替代公开入口的手写定义；本次重提取、翻译、内核和快照审计通过 |
| 覆盖公开路径中的取指、工厂遍历、缓存 | [OuterGeneral.lean](toolchain/full-mir/OuterGeneral.lean) 的 `WordFetch` 覆盖单次 32 位读和页边界两次 16 位读；`decode_cold_word` 连接缓存未命中，`decode_written_hit` 证明已写项命中 | 内核/快照通过；内存读和地址条件显式保留，没有 decoder-result 合同 |
| 重接生产 ADD 定理、GPR 与 PC 效果 | [OuterPublicStep.lean](toolchain/full-entry/OuterPublicStep.lean) 的 `cold_public_add_step` 在同一结论中给出公开 decode、`execute_production`、Sail `try_step`、`state_rel_pc`、GPR、PC/next-PC 及双方各自内存保持 | 两根均通过干净内核与精确审计；原主根 137 项、新增根 158 项依赖 |
| 排除仅靠 runtime corpus 支撑 Sail 前提可满足性 | [OuterPublicWitness.lean](toolchain/full-entry/OuterPublicWitness.lean) 连接两种取指接口见证与 `cold_public_paired_step`，后者实例化 Lean Sail 初态并得出 x3=12、PC=0x80000004 | Lean 内核/快照通过；仍参数化 opaque Rust `Machine` seed，不能声称该类型非空或 reset 可达 |
| 正式记录源码与翻译工具身份 | [ADOPTION.md](ADOPTION.md)、[public-policy.json](public-policy.json)、[extraction.json](toolchain/full-entry/extraction.json)；复核 49 个冻结输入及七类资格证据 | 限定采纳已落实；不声称工具一般正确性或上游全量测试全绿 |
| 精确审计与负测，不能削弱前提换取通过 | [公开快照](toolchain/full-entry/audit-snapshot.json) 固定 68 条定理、45 个定义、三个合同；[证据验证器](../../../scripts/public_decoder_acceptance.py) 检查实际日志、生成物、类型/定义/依赖和两类语义负测 | 116 项测试、47 个子阶段及独立证据重验通过；错误结果被内核拒绝，额外 False 前提被类型审计检出 |
| 新源码重提取、零旧 Lean 缓存且主门禁必需 | [调用层](../../../scripts/public_decoder_gate.py) 强制 `--reextract-rust --clean-dependencies`；[干净构建器](../../../scripts/decoder_public_clean.py) 复制来源固定的源文件，仅复用固定 Lean 编译器及标准库 | 本次新 Rust 提取、初始 0 编译模块、1865 构建任务及最终全套审计通过；未复用旧通过报告 |
| 不归因到未经修改的上游 commit、不改旧验收条款 | 当前源码身份仍为 upstream `1ffba3977da9dcdef8092e9ab1fd2516b27ec939` + runtime-container-v1；旧政策/报告已归档，Week5/6 字节哈希相同 | 本次只改变主政策三部分；原定理、合同、见证、工具及主模型身份未改 |

## 本次集成运行

- 命令：`make proof-check BACKEND=lean`，`2026-09-09T19:49:20Z` 开始，
  `2026-09-09T20:22:51Z` 结束，实际退出码 0。
- [主报告归档](../../../artifacts/boundary-check/public-adoption-xQNXpE/after/artifacts/proof-check/report.json)
  为 `passed`，SHA-256 `4a92b85f7d18891407fcd295aa27d93c9690f604fc6370ec59bb98533b2794b3`。
  工作位置仍为 [artifacts/proof-check/report.json](../../../artifacts/proof-check/report.json)，
  将来重跑会更新该位置；本次归档不随之覆盖。
- 9 组测试实际日志合计 116 项：19 + 18 + 18 + 12 + 6 + 10 + 6 + 17 + 10，均为 OK。
- [公开子报告](../../../artifacts/boundary-check/public-check-i12u8wjo/report.json)
  SHA-256 `449c93663a44abd58d10c174b0f6f90aba82020fa5423cce071b037d8cee14a8`，47 阶段通过。
  子检查器历史标签仍为 `EXPERIMENTAL_PUBLIC_CHECK_PASS`；采纳决定由父门禁作出，
  主报告明确为 `main_gate_adopted=true`、`tool_adoption_claimed=true`。
- 初始编译模块 0，主依赖子树新 `.olean` 1806 个，整个公开目录 1836 个。
  这两个模块计数范围不同，均不同于 Lake 的 1865 个构建任务。
- [迁移审计](../../../artifacts/boundary-check/public-adoption-xQNXpE/migration-audit.json)
  的 `MIGRATION_REVIEW_PASS_MAIN_RUN_PENDING` 状态保持原样，未改写为主运行通过。

完成后另行运行 `public_decoder_acceptance.validate`、`public_decoder_gate.check_policy`，
核对其结果与父报告一致，并复核全部 16 个主阶段日志哈希和 9 组测试的实际 OK 标记。
生产源码身份、主政策三个迁移部分及 Week5/6 原字节哈希也再次核对通过。
本次通过报告、主审计、16 个主阶段日志及两份政策共 20 个文件归档于 `after/`，
复制前后哈希一致。完整记录见 [最终核验](../../../artifacts/boundary-check/public-adoption-xQNXpE/completion-audit.json)。

## 保留边界

解码结果相等的假设已经从公开最终根移除，不能再将它列作未关闭前提。
仍保留 `state_rel_pc`、Rust memory-size/load、Sail 原始取指/入口/退休条件。
`WordFetch` 和 `RawFetchPath` 的对象是同一个原始字，但这不是两套物理内存实现之间的证明。
本次也不证明实际 SparseMemory、任意缓存状态、多步自修改代码、MOP-on 融合、非 ADD 指令、
opaque Rust Machine 非空性或平台 reset 可达性。工具变换仍属于已说明的可信基线。

这些边界不能由单个非空见证、抽象内存接口、相同公理数量或 runtime 测试自动消除。
主门禁最终通过时仍应报告 `conditional`，而非全 VM `proved` 或 release 验收。
