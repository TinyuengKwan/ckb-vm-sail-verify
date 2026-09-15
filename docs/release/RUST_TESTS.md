# 完整 workspace 默认测试与真实引擎负测

精确审计修正后的当前执行见[本地证据更新](AUDIT_FIX_EVIDENCE_REFRESH.md)；
下述早期报告保留为历史记录，不再作为新政策证据。

在仓库根运行 `python3 scripts/release_rust_tests.py`。必须已准备好固定 Sail emulator
与合并配置；这不是安装全工具环境的入口。默认创建独立目录，`--out` 只接受新目录。

先校验环境、记录源码与工具身份，在空 Cargo target 中执行
`cargo test --workspace --locked --no-run --message-format=json`。结合 Cargo metadata
要求所有启用的 lib/bin/integration test 目标都有测试二进制；逐个读取 `--list` 后以
`--include-ignored --test-threads=1` 执行。再为全部 doctest 目标分别列举并运行。
检查器比较完整用例名字和汇总，而不是只检查进程退出 0；ignored、filtered-out、
重复、漏跑、测试失败、缺少末尾汇总和缺失二进制均不能通过。

## 2026-09-12 实跑

[报告](../../artifacts/boundary-check/release-rust-tests-kxnsufbz/report.json) SHA-256：
`da0dde728e1f80ddc26752db8eac0d8f6f0773f7b56d7acc1bfef2a529aa6e6c`。
时间 03:48:23–03:48:45 UTC，19 个阶段退出 0。

- 7 个测试二进制，78 项测试通过；ignored / filtered-out 均为 0。
- 包含通常需要显式启用的全部 10 项真实引擎测试：完整 corpus、mutation、真实差异、
  缺失末尾事件、trap、引擎错误、压缩宽度、实时 packet、空矩阵和并发会话。
- 5 个 doctest 目标全部列举和执行；目前共有 0 项 doctest，不能写成“5 项 doctest 通过”。
- 15 项新测试检查用例在普通 Python 与 `-O` 模式均通过。

早先的 `release-rust-tests-pwpminmt` 也曾实跑通过；随后增加测试二进制路径的 symlink
检查并再次全量执行，新报告才匹配当前脚本身份。旧报告不改写。

`audit-release` 的 `rust_tests` slot 已接入此验收器，并重新读取全部记录、二进制与日志。
这里只覆盖 workspace 的**默认 feature/target 配置**及测试中引用的依赖行为，不是
`--all-features`、所有平台或 CKB-VM 上游自己的全部测试。使用已有依赖缓存、本机工具
和既有 Sail emulator；源码身份明确为已采纳的 upstream + runtime-container patch。
没有重新生成 Sail 模型、执行全环境 clean-room、独立第三方或发布。
