# Charon 清理尾段实验记录（非通用变换正确性证明）

后续状态：该固定补丁已按 [公开 ADD 限定政策](../../ADOPTION.md) 采纳，主门禁首次集成
实跑已通过。下文是实验阶段记录；全量测试失败及变换信任边界仍保留，不刷新旧报告为 PASS。

最新复核见 [原工具对照审计](REGRESSION_AUDIT.md)：435 项对照完成，
未新增命令失败，确认 11 个选定输出变化（其中 7 个新金样差异）；另有循环模型等价证明。
归档补丁已修复且可应用。以上不等于全量测试通过或工具正式采纳。

2026-09-09。目标是解除公开 `InstDecoder::decode` 提取的资源障碍，
不更改 CKB 生产源码，不缩减为 `decode_raw`，不将 MOP 或已证明工厂改为 opaque。
基于 Charon `89ac118194b978d8cf753222c19f313521377aa0` 的独立副本。

## 复现与候选

[GuardedFields.rs](GuardedFields.rs) 保留三组短路字段检查。
[GuardedOwnedError.rs](GuardedOwnedError.rs) 增加 `Result<u64, String>` 参数与 `?`。
原工具的紧凑 JSON 函数体分别为 249,455 和 47,692,683 字节；后者可以独立复现生产函数的膨胀，
不是运行时输入样本，也不是 Lean 证明。

定向 CFG 日志表明，`?` 后共用的正常清理尾段被选为外层 switch 出口；
后续短路条件的自然连接点因此无法通过出口兼容检查，产生大量代码复制。
首次尝试“首选出口不可用时选下一个安全出口”只使生产关键函数减少不到 1%，未采用。

[候选补丁](charon-cleanup-suffix.patch) 扩展现有 `duplicate_return` pass：
除裸 return 外，逐路径复制只含 `StorageDead`、Goto、Drop 且正常路径通往 return 的短尾段。
保留 Drop 本身、原操作顺序及原 unwind 目标，不放宽 CFG 出口安全检查。
只向已识别的尾段向前扩展，最多 32 层，避免引入环或无界递归。
这是局部变换的设计依据，**不是该编译 pass 的形式正确性证明**。

候选将独立复现缩小至 440,547 字节；生产 `rule_add3` 函数体从 44,936,299 字节
缩小至 481,595 字节。真实公开入口、完整 MOP 与工厂函数体的 LLBC 已生成，
前端 `has_errors=false`。生产模型没有引用本目录的手写 Rust 复现。

后续归档复核发现旧补丁遗漏了最后一行空白上下文，`git apply --check` 报 corrupt patch。
旧字节保存在 [v1 截断归档](charon-cleanup-suffix-v1-truncated.txt)，SHA-256 仍为旧报告中的
`d5c948b11c6b7d316a81acf845c5a570c93ccd7a611901fe5e55efb43c09baa6`，不能作为可应用补丁。
当前修复版只补回该行，与实际候选源码 `git diff -- charon/src` 逐字相同，SHA-256 为
`17f5c34ca63f66987498331d9712b8affb00e25867e4746b5b660893d3d6eebf`；反向应用检查通过。
实际源码、二进制、LLBC 和 Lean 模型均未因归档修复改变，旧失败/测量报告不回写。

## 旧后端失败及仍未通过的工具检查

- 配合当时的 Aeneas 工具时，完整翻译在 180 秒期限结束时退出 124。
- 当时的 60 秒顺序日志停在 `rule_add3` 的符号执行。这两项历史失败不计为通过。
  后续独立 Aeneas 候选已生成完整模型并接回 ADD，见 [公开入口实验](../full-entry/README.md)。
- `make test && make clippy` 在文档生成阶段因缺少 `odoc` 退出。
  单独 Rust 测试还遇到缺失 Miri/交叉目标；单独 clippy 缺少该 nightly 的组件。
  UI 严格金样对比为 350 通过、83 失败、2 忽略，未通过完整回归。
  差异还需要逐项审查，不能全算作环境问题；其中一个控制流金样确实改变了代码结构。
  测试框架在两个编译失败用例中仍写回了 `.out`；已归档失败输出并恢复旧期望，未批准刷新。
- 未证明候选工具的语义等价性，未迁移或刷新既有 56 条定理快照，未接入正式 proof-check。

实验目录为 `artifacts/boundary-check/charon-cfg-OYcaoK`。
其中保留未修改工具、候选工具、原始及候选 LLBC、控制流日志和测试日志。
固定候选二进制位于 `candidate-bin/`；`OuterCleanupChecked.llbc` 由该副本重新提取。
[测量报告](../../../../../artifacts/boundary-check/charon-cfg-OYcaoK/cleanup-report.json)
记录对应哈希、提取选项和检查状态，不能作为 PASS 门禁报告。

后端的符号执行开销已由 [分支实验](../branch-experimental/README.md) 继续处理，
公开入口的 Lean 定义、最终 ADD 连接和精确依赖审计已在新隔离模型中完成。
下一步仍须审查本候选的清理尾段变换及全量回归差异；旧测量报告不改写为 PASS，工具尚未采纳。
