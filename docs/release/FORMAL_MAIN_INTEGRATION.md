# 正式主工具入口迁移

2026-09-13。本次从已独立验收的 [候选](REBUILT_MAIN_CANDIDATE.md) 接入正式目录。
**新正式完整执行及独立验收已完成；Week6 未关闭。** 06:26 UTC 主门禁退出 0，
06:29 UTC 独立验收通过，详见末节。下文按时间保留切换及各阶段记录。

## 身份与边界

- 原正式政策：`ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f`。
- 已验收候选政策：`697883be2675b6997910690011c5d30b45d07987a80006c7811da517ac9c5000`。
- 新正式政策：`7ced9f425d1fbda578a796fbc7135a15fec930b66adfbc26a3fc1ba1a177b6f5`。
  相对候选仅两份 helper 的模块说明改为已由正式 profile 选择，因此重新绑定源码哈希；
  不将候选 PASS 归到这个新政策。
- `check_proof.py` 和 `test_proof_check.py` 与已验收候选逐字节相同。
  profile 为 `rebuilt-main-v1`；94 个本地源码身份显式绑定。
- 定理、合同、前提、公理清单、配置、CKB upstream＋patch 基线及双方 Lean 模型身份不变。
  没有新增解码/执行证明，也没有降低既有公开入口或无项目缓存重建要求。

## 正式接口

`release_evidence.py` 根据政策选取完整清单：旧 profile 为 24 阶段、236 测试；
新 profile 为 28 阶段、21 组 287 测试。未知 profile、遗漏新增阶段或错误测试数均拒绝。
新验收器已在独立进程中实际复核候选完整报告，接受 28/287/68；这是证据重验，
不是在正式目录重新运行 kernel。

`rocq_context.py` 与 `rocq_spike.py` 接入显式双 OPAM 根。新 profile 要求在本次执行中
先生成 Sail Rocq 输入，再从本政策绑定的生产 LLBC 重新翻译 Rust；共 11 阶段。
支持库只能从已核验源码复制，已存在但身份不同的文件不能覆盖。
独立验收检查安装闭包、精确命令及 cwd、完整包清单、生成事务和文件哈希。
旧 profile 的十阶段路径仍保留。Rocq 的目标仍是具体 NO-GO 和最小复现，
`extra_proof_coverage=false`，不是双侧 Rocq 证明。

新增及扩展的三组接口测试共 69 项，普通 Python 和 `python -O` 均通过。
连同正式主工具四组与核心测试，最终政策下八组共 138 项在普通/优化模式均通过。

05:02:52–05:06:05 UTC 的 [正式切换预检报告](../../artifacts/boundary-check/formal-main-cutover-wmgdvto7/report.json)
退出 0，SHA-256：`f67970e3030dc8aa99727772d5c1cac69086c92e4057308f6448eb3f9d7b291d`。
实际解析并核验了主工具/支持源码和私有安装闭包、当前 94 项政策来源、独立 Rocq 上下文；
对比确认候选 helper 仅模块说明改变，执行 AST 相同。报告保存 16 组执行日志及哈希，
这仍是预检，不是 kernel 或完整正式验收。

## 保留与重跑

切换前源码/政策保存在
`artifacts/boundary-check/before-formal-main-integration-fjfGvSKC/`。
旧 Sail 构建目录保留为其中的 `previous-sail-build/`，不删除；正式位置重新配置，
显式指向 `isolated-sail-nrdi23ds/sail-install/bin/sail`，不能复用旧模拟器作新工具输出。
新 Rust/Sail 安装器另保留生成物事务和旧文件。

旧正式主证据在 `approved-rebuilt-proof-YQTKZPMC/`；候选主证据在
`approved-rebuilt-main-ajOS4Y08/`（均位于 `artifacts/boundary-check/`）。
v8 聚合报告及所有历史失败保持原样。由于政策/检查器源码已改，v8 不再是当前来源验收。

预检通过后已启动 `make proof-check BACKEND=lean`，状态为运行中，
尚无新正式 PASS；进度写入 `artifacts/proof-check/report.json`。新 Sail 模拟器将从
空构建目录产生，Rust/Sail 生成与完整 kernel 链继续按正式入口执行。

## 正式实跑的阶段性结果

Sail 模拟器冷构建与环境检查已通过，新模拟器 SHA-256 为
`958e9d958a490fd495e496bd7620e19fb7901291349844ffa8f80c151547ef44`。
本次生成的 C++/header 与先前候选并非逐字节相同。
05:26:29–05:27:35 UTC 的 [受限对应检查](../../artifacts/boundary-check/formal-sail-cpp-correspondence-qz_uwbjv/report.json)
通过：3,675 个方法、642 个字段、3,676 个间隔均检查，176 个字段名对应改变；
头文件中的顺序、对应类型和初始化保持，许可的生成标识符及对应注释之外的文本须精确一致。
报告 SHA-256：`6c85ec90c5bfc3bcdfe95d02465cbda9a08226dabbcad30e589a5928da4b8e13`。
这不是完整 C++ 解析、ABI 或执行等价证明，不能代替本次 native 实跑。

05:29:39–05:32:50 UTC 的 [正式 Rust 暂存报告](../../artifacts/boundary-check/rebuilt-production-rust-tscvsc_j/report.json)
完成 13 阶段，SHA-256：`4ea7d62f0e3f84014fb3a596323a39b9f6e723a75fad7f0123582ac1c6c56356`。
新 Lean 模型全文件 SHA-256 仍为 `9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e`，
未归一化；新 LLBC 与模型已由正式生成器一并安装并绑定当前政策。
主门禁随后完成 `generate-sail`，前四个生成阶段均通过，已进入 `kernel-step`。
输入稳定后接续独立的正式 native 和新 11 阶段 Rocq 执行；
仍不能把阶段性成功当作完整主门禁或本次 Rocq PASS。

## 正式 native 验收完成

05:40:00–05:46:13 UTC 的 [native 完整执行报告](../../artifacts/boundary-check/formal-native-gWE5WMRA/report.json)
退出 0，SHA-256：`51082206cf375ddab5d20bd32d3a5957c59813b536333d1b08feeefeaf577895`。
驱动只在前四个正式生成阶段完成且日志身份一致时启动；6 项守卫测试普通/优化模式通过。
使用经完整安装闭包核验的私有 Rust 1.97.1，初始不存在的 Cargo home，两个独立新 target；
生产者完成后在另一个 Python `-O` 进程中重新验收，最终再核对源码、模型、工具和四阶段来源。

- [runtime 报告](../../artifacts/boundary-check/formal-native-gWE5WMRA/runtime/report.json)：
  32 案例、188 项适用 mutation、4 项不适用及 32 次复制重放；
  SHA-256 `ed6571bba185848283578ff50d64b67fed28d071950b2a2b9e74769b31f59a24`。
- [Rust tests 报告](../../artifacts/boundary-check/formal-native-gWE5WMRA/rust-tests/report.json)：
  7 个二进制、78 项测试（含 10 项真实引擎）、5 个 doctest 目标/0 项 doctest，
  无 ignored 或 filtered-out；SHA-256 `69787d4132013cbe291627c6f9ba4de93e2df2e37f4f065e80b19f19844df892`。

执行期间完整源码快照为 `d8c7b0c2ce1be4bdf30b3af515afb0c4b733f091442d0039fd3657acb6002493`；
本节是执行结束后追加的文档记录，不能宣称文档追加后的完整快照仍为这个身份。
这两项正式 native 证据不替代完整 Lean 主门禁、独立 Rocq 验收或完整 clean-room。

## 正式 Rocq 与配套证据完成

05:40:01–05:51:07 UTC 的 [新正式 Rocq 实跑](../../artifacts/rocq-spike/run-iu08clul/report.json)
完成全部 11 阶段，退出 0；报告 SHA-256 为
`ed404517e8ae909b119897b90141b0dbdb3fbdd19d9e095f885e8e39b20967a0`。
本次实际生成 Sail Rocq 输入，并由当前政策绑定的生产 LLBC 重新翻译 Rust。
三次预期拒绝（Rust 模型、Sail 模型及 Sail 最小复现）均为精确诊断/退出 1，
其余八个阶段退出 0。结论仍为 NO-GO，额外证明覆盖为 false。

05:52:59–05:54:49 UTC 又通过 [当前正式验收器的独立复核](../../artifacts/boundary-check/formal-rocq-acceptance-v5euf2jh/report.json)，
重新核对完整来源、工具闭包、双 OPAM 上下文、命令/cwd、事务与模型；
报告 SHA-256：`e9deddf5cb46edcfa348af6884a6096a9b5a12189e06019b7358969a57d6ceb7`。

两类 [配对负测](../../artifacts/boundary-check/paired-negatives-hwewjiop/report.json) 使用新独立 target
重跑，37/12 次搜索与两次复制重放通过；最小总长度为 4/3 条指令。
新 CLI 的 [trap 重执行及最小化](../../artifacts/boundary-check/formal-trap-9yz9q90l/report.json)
于 05:51:19–05:51:26 UTC 完成，4 次实测后单条 `0x0000107b` 保留 `pc_after` 差异，
分类仍为已知 unsupported，最小性仅限非空、保持顺序的子序列，不是根因等价证明。

05:54:22–05:54:44 UTC 的 [配套独立验收及演示](../../artifacts/boundary-check/formal-support-refresh-bk5s659j/report.json)
绑定本次相同 runtime/Rust/三类负测，并完成真实录制和独立回放验收；
报告 SHA-256：`bd679110c4c71408feead112b2de1d988650eae1258bd7cd1cd50e0a94be430a`。
[演示报告](../../artifacts/boundary-check/formal-support-refresh-bk5s659j/demo/report.json)
SHA-256：`832195bb4c98d712552cdfd94f902ba63272b7de66bab13f8ea14050d40fc507`。

## v9 聚合与剩余工作

[新 v9 清单](local-readiness-20260913-v9.json)引用这些新报告，`lean` 明确留空。
05:57:05–05:59:00 UTC 实际聚合退出 2、`incomplete`，五项已有组件全部验收通过，
完整 Lean 及六类发布义务仍缺失。
[聚合报告](../../artifacts/release-audit/run-56ak_bgi/report.json) SHA-256：
`547ebebddbf4dfa07c9b025f7fa64b4ce198098378b448780e16e0811d49e3df`。
完成后已独立核对聚合前后快照与当前受审源码，以及精确的五项通过/七项缺失集合。

主门禁的 kernel、主定理审计及 21 组 287 项测试已通过，原主根 137 项依赖不变；
当前仍在最后的公开 decoder/无项目缓存构建阶段，尚无完整主门禁 PASS。
06:01–06:03 UTC 另发生 [非预期 LXD 包装脚本安装](LXD_WRAPPER_SIDE_EFFECT.md)，
晚于上述五项组件及 v9 聚合结束，但发生于主门禁公开阶段期间。
它必须列入最终宿主环境审计，不宣称该段宿主环境完全未变；进一步 LXD 操作等待用户决定。

上述是 v9 时点的阶段性状态；完整主门禁和独立验收随后完成，见下节。
完整 clean-room、最终 worktree 审计、
CI 下载重放、实际发布、第三方复现和公开结论审计不能由本次迁移替代。

## 完整正式主门禁与独立验收完成

`make proof-check BACKEND=lean` 于 05:06:23–06:26:00 UTC 实际运行并退出 0。
28 个主阶段、21 组 287 项测试全部通过；必需公开子流程完成 48 阶段、68 个公开定理，
从零项目编译缓存重建 1,865 个任务，错误结论与削弱前提两类负测均符合预期。
主根依赖仍为 137 项，公开执行根为 158 项；没有扩大到物理内存耦合、真实平台初态可达性
或一般编译器正确性。

完整主报告保存于 [30 文件归档](../../artifacts/boundary-check/formal-main-acceptance-hnOBopcM/main/report.json)，
SHA-256 为 `1371a5b84ea1d460bbd19af36cbd32696aad9a53ef2e742fc511d5ba880a1996`。
[本次公开报告](../../artifacts/boundary-check/public-check-mqyhbzhy/report.json) SHA-256 为
`77b2f35b3e23767d93e996dfea35199c7593601be98682bd69ad846426fda9ff`。
归档包括 28 份阶段日志、主报告与 `lean-audit.json`，公开子目录及生成事务保留原位置。

06:26:15–06:29:06 UTC 在另一个 Python `-O` 进程中，用当前正式
`release_evidence.check_lean` 直接验收归档，未修改全局计数或借用候选检查器。
[独立验收报告](../../artifacts/boundary-check/formal-main-acceptance-hnOBopcM/report.json)
退出 0，SHA-256 为 `d9eda4930f3ab566cd771ea66094a1f77a89e2571722b69bd62e12ded0925c55`。
归档与原日志逐文件相同，受审输入及完整源码快照在该独立检查前后一致。
其 `source-snapshot.json` 只代表该次验收时的 HEAD 加工作树，不是随后文档修改后的身份，
也不是全部 dirty 差异已完成语义审计。

新 [v10 清单](local-readiness-20260913-v10.json) 接入上述完整归档；v9 保留 `lean: null`。
本次证明运行期间发生的 LXD 安装仍须列入宿主审计，不能把源码/工具哈希一致说成
整段宿主环境未变或 clean-room 通过。聚合结果见 [readiness 记录](AUDIT_RELEASE.md)。
