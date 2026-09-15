# 当前正式政策的负测、演示与六项聚合

2026-09-13 22:29:37–22:35:53 UTC，使用原负测、最小化、演示和聚合入口实际完成。
[执行报告](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/report.json)退出 0、无错误，
SHA-256：`b31193831432de6287161235803dc7ed5bd9520832b90d554e142f2468cb3b95`。
这是本地配套证据更新，不是发布、clean-room、第三方复现或新的 kernel 执行。

## 实际执行及独立验收

- 使用经核验的 Rust 1.97.1 工具、新 Cargo home 和独立 target，重新构建双程序负测 runner。
  [两类负测](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/paired/report.json)
  分别执行 37 / 12 个最小化试验，最小总指令数为 4 / 3，并将复制输入送入双方实际重放。
  最小性仅限保持所定义差异的非空保序子序列，不是一般根因证明。
- 旧 trap artifact 只提供固定输入 `[0x00500093, 0x0000107b, 0x00700113]`；
  用[本轮 33 案例 runtime](WEEK6_RUNTIME_FLOOR.md)的二进制重新执行两侧，再做 4 次最小化试验。
  [最小报告](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/trap-minimized/report.json)
  保留单字 `0x0000107b`，首差异为 `pc_after`，分类为 `unsupported`，正常重放退出 1。
  这不是 trap 正确性证明；旧报告和旧二进制身份未修改。
- [新演示](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/demo/report.json)
  实际录制并回放 corpus/mutation、ADD 重放及已知 trap 重放：33 案例（13/10/10）、
  194 项适用 mutation、4 项不适用。终端记录约 6.95 秒，不录制输入。
  演示报告 SHA-256：`122a3fe73295b221d869ff7a76268139627e5606e653e7abd51e0567693bc2dd`。
- [独立子进程检查](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/independent-support.log)
  重验三类负测的输入、原始 trace、最小化和重放，以及演示内容、时间记录和实际播放结果。
  源码首尾一致；运行前只比正式链冻结快照多六份明确的文档更新，记录于同目录源码差异文件。
  终态后核对了全部 33 个绑定的顶层记录文件哈希，无不符。

## 当前聚合结果

[新清单](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/manifest.json)使用
`week6-b5bdc401-formal-final-records-not-approved-release` 标签；这不是用户批准的 release 版本。
清单 SHA-256：`2936c96f65f36999b92a8a5a28b3521e355ea6ed070993881c841b58a0d26764`。
原 `audit_release.py` 实际运行后，runtime、Rust tests、Lean、Rocq、mismatches、maintainer_demo
六项均为 `verified_existing_evidence`；Lean/Rocq 引用[本轮完整正式链](FORMAL_FINAL_EXECUTION.md)。
[聚合报告](../../artifacts/boundary-check/final-support-refresh-tRaviJ98/audit/report.json)
SHA-256：`e857cae85f1c42f76e351b4a0cbaf0a380a84a0407bd6c76f12418217438ef03`，
整体 `incomplete`，退出 2。录制器忠实保留该非零退出，不把它重写为聚合成功。

clean_room、worktree_audit、ci_download、release_package、third_party、public_claims
仍全部缺失；当前聚合器没有 release 成功路径。
后续[46,651 项正式输出差异说明及复验](FORMAL_DELTA_REVIEW.md)已完成，
并已由[新清单实际接入工作树部分验收](WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)；
本次新负测/演示产物及运行后的文档更新也须进入最终交付范围审查。
本页在执行终态后追加，不回填源码快照，也不将旧 v10 或旧 10,021 项差异审查归给本轮。
