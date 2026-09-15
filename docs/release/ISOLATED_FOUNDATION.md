# 隔离源码快照与基础重建

2026-09-12 已完成独立 Git 副本中的 Sail 模拟器/配置冷重建、Rust 测试及
runtime/mutation/复制重放。**这不是完整 clean-room、第三方复现或发布验收。**
没有安装全新工具环境，也没有在此副本运行 Lean/Rocq 证明链。

## 入口与来源

在当前已配置好固定 Sail 编译器的原工作区执行：

```bash
python3 scripts/probes/probe_isolated_foundation.py
```

也可用 `--out` 指定一个尚不存在的新目录。入口读取原工作区 Sail CMake 缓存中的
编译器位置，因此不是空机器 bootstrap 命令。不会提交、暂存、重置原仓库或覆盖旧运行目录。

[源码快照实现](../../scripts/source_snapshot.py) 枚举 HEAD、工作树中受跟踪及非忽略的
新增文件，记录逐文件字节哈希、大小、执行权限及相对 HEAD 的增改删。
固定两个子模块 commit，拒绝 Sail 未审改动，并重新核验 CKB 已采纳的生产补丁。
源码 symlink、额外/嵌套子模块、子模块 HEAD 漂移和脏目标副本均拒绝。
快照描述工作树文件，不是暂存区内容归档或差异语义审批。

[执行脚本](../../scripts/probes/probe_isolated_foundation.py) 从本机三个 Git 仓库分别
`clone --no-hardlinks --no-checkout`，检出精确 HEAD，然后复原全部快照文件。
检查对象库无 alternates、对象文件无硬链接。它不是从远程执行第三方递归 clone。
没有搬入既有 Cargo target、Sail build、合并配置或 Lean/Rocq 生成目录；
`artifacts` 初始只允许受版本控制的 `README.md`，不允许历史证据。

随后从空 Sail 构建目录以 `RelWithDebInfo`、`DOWNLOAD_GMP=TRUE` 和四路并行重建
`sail_riscv_sim`；GMP 下载由上游 CMake 的 SHA-256 校验。
重新合并配置、验证环境，在各自新 Cargo target 中运行 Rust 测试和差分入口，
最后在副本中调用对应验收器重读实际 trace、矩阵、测试清单和日志。

## 实跑与独立复核

运行时间：2026-09-12 06:20:14–06:42:19 UTC，13 个外层阶段全部退出 0。
[报告及同目录日志](../../artifacts/boundary-check/isolated-foundation-a3241758/report.json)
状态为 `isolated_foundation_passed_with_reused_host_tools`。

报告 SHA-256：
`8a7e2b4dbc8e92781d13f18d315805fbdaa6f4f99617f3b45f71f8922883280d`。

本次源码身份是主仓库 `872d225dc4e16c449be37d92761b20c6aefe853c` **加明确工作树快照**，
不是该裸 commit，也不是新发布版本。快照 SHA-256：
`e2b251dbd97f675addd01ec0a680905a7d39b28ef08b7077420176f193c48c66`。

| 仓库 | 文件数 | 相对 HEAD 的差异 |
| --- | ---: | --- |
| 主仓库 | 269 | 15 修改、49 新增 |
| CKB-VM | 489 | 1 修改、1 新增；精确匹配已采纳的 runtime-container 基线 |
| sail-riscv | 859 | 无 |

完整逐文件清单及前后身份在报告的 `source_snapshot.repositories` 中；
`source-payload/` 保存这 1,617 个文件，`checkout/` 保存独立复原及构建结果。
运行结束后，副本与原工作区源码均等于该快照，原工作区 Git status 不变。
独立只读复核再次检查全部 payload 字节/权限/清单、13 个日志哈希、生成文件和报告哈希、
三个对象库独立性，并在副本用 `python3 -O` 再次运行 Rust/runtime 验收器，结果一致。

**本文及本轮状态文档是在运行后写入的，不属于上述已验证快照。**
不能将之后的工作树或未来候选版本自动视为已完成同一次重建；最终候选仍需重新绑定身份、
审查全部差异并完成全链验收。枚举差异不等于批准其语义。

- Rust：7 个测试二进制，78 项通过，包括全部 10 项真实引擎测试；无忽略、无过滤。
  5 个 doctest 目标共 0 个实际用例，不声称证明了 5 个 doctest。
- runtime：32 个案例（ADD/ADDI/BEQ 为 13/10/9），32 个复制产物全部重放通过。
- mutation：192 项矩阵中 188 项适用且正确定位，4 项无 GPR 写入而不可应用。
- 生成配置 SHA-256 仍为
  `41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024`。
- 新模拟器 SHA-256：
  `08a59651bfdc3db264a84e1a5d3cec6a5e104a27a320a273dd636662018baabf`。
- Rust 报告 SHA-256：
  `18aa8e86bf17e6ec9b2bf2d80d7dbd544b76afd2cfc9909557e03ae2dc35d538`。
- runtime 报告 SHA-256：
  `d69eeac7bff95b0d6169f399636d33bcd9be1a84d75b6be91edff6b7c5b0b7ff`。

首次 [isolated-foundation-91ofuk89](../../artifacts/boundary-check/isolated-foundation-91ofuk89/report.json)
在构建前失败：检查器将受版本控制的 `artifacts/README.md` 当成了历史构建产物。
修正仅放行这一文档，仍拒绝其他初始 artifact；失败记录未覆盖或改成通过。
[17 项快照/隔离回归测试](../../scripts/tests/test_source_snapshot.py) 在普通 Python 和 `-O`
下均通过；连同已有 release 检查器，本轮共复跑 145 项，两个模式均通过。

## 尚未关闭的门槛

报告明确记录复用本机固定 Sail 编译器及其支持库、Rust/Cargo、系统工具和依赖缓存。
工具及缓存未隔离安装，宿主机供应链闭包未在本轮验证。
本轮未重新提取双方 Lean/Rocq 输入或运行新 kernel proof；不能拼接原目录证明报告，
就声称这个副本已通过全链 clean-room。

06:33:16–06:33:36 UTC 的 [readiness v3 复核](../../artifacts/release-audit/run-crunixl3/report.json)
仍是五项已有证据有效、七项缺失，退出 2；报告 SHA-256：
`85e92aaa661daf9b042401983b6bdfbc207ff9ae40deb9b33d35d76ce7d87132`。
它不把本次基础重建计入 `clean_room` 或 `worktree_audit` 完成。
下一步是锁定工具环境的独立安装、双方生成物重提取及 Lean/Rocq 全链运行，
之后完成最终候选差异审计、CI 下载、发布包、维护者演示、公开结论与第三方复现。

后续进展：[Rust/Lean 的独立安装与 smoke](ISOLATED_RUST_LEAN.md) 已另行实跑通过；
该安装不是本页基础重建当时使用的工具环境，也不追溯改变本页报告的复用边界。
