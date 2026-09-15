# Week6 CI 来源差距核验

2026-09-13 05:12:08–05:12:14 UTC，仅执行 GitHub REST 只读查询。
[本机原始查询报告](../../artifacts/boundary-check/ci-readonly-review-y257a8t_/report.json)
SHA-256：`424aacea266ccdfcb734e29e3c53cbb3e88b73139b328ee3f03e0440e6706380`。
报告保留四次查询的命令、原始 JSON、stderr、退出码及哈希；没有推送、触发 workflow 或发布。

## 实际结果

- 本地 HEAD：`872d225dc4e16c449be37d92761b20c6aefe853c`，另有未提交的正式迁移工作树。
  按该 HEAD 查询的 workflow run 数为 **0**；即使之后该 HEAD 有 CI，也不自动覆盖工作树增量。
- 最近五次成功运行均为旧提交 `1ef21d7818029356e991dc3ed8a31b26859559e8`。
- 最近一轮 [run 34682081028](https://github.com/TinyuengKwan/ckb-vm-sail-verify/actions/runs/34682081028)
  的两个成功 job 分别是 `fmt, clippy, unit tests` 和
  `RVFI-DII differential and mutation matrix`。没有本轮 Lean/Rocq 或完整发布聚合 job。
- 该运行列出尚未过期的 `differential-artifacts-34682081028`，artifact ID
  `10294780653`，大小 59,332 字节，服务端 digest 为
  `sha256:93ed879a9851896f29a0f505f0b4de8a2c9c06c5927a54a84336078e265fcecd`。
  本次只查询元数据，**未下载、未重放**，不能把服务端 digest 当作本机已验收的下载文件。

## 对 Week6 的影响

旧 CI 绿灯和旧 artifact 不能关闭当前候选的 `ci_download` 条款。
当前 [CI 源码](../../.github/workflows/ci.yml)具有上传后下载一个 runtime 案例的逻辑，
但不含新正式主工具安装、完整 Lean、Rocq 和 release 聚合链。
脚本中存在下载步骤，也不等于本轮已实际执行并验收了该步骤。

所需后续工作：先完成当前正式主执行并冻结交付源码/工具输入，再补齐同一候选的完整 CI
执行入口；经确认提交/推送和触发后，记录实际 run、job、上传/下载的文件身份及真实重放。
独立第三方复现和实际发布仍是另外两项，不能用助手的只读查询或本机第二目录代替。
