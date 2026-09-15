# 公开 decoder 正式输入布局迁移

2026-09-11。实现、政策差异审计及完整 `make proof-check BACKEND=lean` 已通过。
进程实际退出 0，完成后独立复核了来源、报告、日志与完整公开验收。
**这关闭正式输入布局迁移的证明门禁，不是完整环境 clean-room 或 Week6 关闭。**

## 正式入口

公开政策固定 `input_layout=public-decoder-inputs-v1`，输入目录为
`artifacts/decoder-inputs/public-v1`。该目录已通过输入包安装器实际安装；不是将旧
实验目录改名，也不依赖其 symlink 或 Git alternates。

```bash
# 首次安装：目标必须不存在，归档需先由维护者提供并核验来源。
python3 scripts/decoder_input_bundle.py install \
  --archive artifacts/boundary-check/public-inputs-package-v3/public-decoder-inputs.tar.gz \
  --sha256 e69b2d11f9161b0baa9fcb177acb046a09b1409eb489c3512b2bde708cdda8bc \
  --output artifacts/decoder-inputs/public-v1
make proof-check BACKEND=lean
```

归档当前仍是本地产物，不是可公开下载的发行版。其内容、许可证通知审计和完整工具
环境的边界见[输入包记录](DECODER_INPUTS.md)。安装报告 SHA-256：
`27c30740f9da44136d29b4316883caf60b88415caccdf27f6a296dc8622d95c7`。

## 迁移内容与不变量

- 父门禁强制使用独立安装布局，无缺包后回退旧工具目录的分支。
- Rust 提取创建新 harness 和 Cargo target；所有库文件身份先核验，才允许 sysroot
  元数据位置变化。提取选项、两个 Rust 根和依赖锁仍固定。
- 干净 Lean 构建从包内读取三个下层生成**源文件**，仍以零旧编译模块开始。
- 模型比对只处理先前实测确认的来源注释位置；Linked 模型必须恰好是在公开输出中
  增加一次 `CkbVmProduction` import。函数体、公理及其他代码不能被路径比对忽略。
- 验收器重新读取安装输入、harness、两份新 LLBC、模型、日志和内核审计。
  报告中的哈希或 PASS 字段不能自行批准新的输入。
- 新输入包/harness/身份测试加入主门禁；主门禁测试由原 9 组扩为 14 组。
  已实跑的 130 项相关测试在普通 Python 与 `-O` 下通过；完整门禁仍须实际执行。

旧主政策固定为
`079f22a9e9f04868d42c337a9eb02c083e5e6e1f3cb7a1b6cc1eaa8eba1e54c0`。
新主政策：`c8315684cf73d118703f98982e79303943d8c52d49e72d99117de25301b3a1af`；
新公开政策：`e2643499ef13d20ed1797dca4d2e6192851fdad0b0e6e53ffc41247ce85fd0b4`。

[迁移审计器](../../scripts/probes/review_public_input_migration.py) 核对：主政策只有 5 个
源码哈希改变；公开政策更新 8 个源码哈希、增加 10 个输入/检查器哈希并切换布局。
所有定理、合同、工具版本、模型批准值、资格证据及其他政策内容保持不变。
Week5/6 原验收文档字节和生产 baseline 再次核验不变。

[迁移报告](../../artifacts/boundary-check/public-input-migration-dK3ucjFP/migration-review.json)
SHA-256：`94e0c573566883e3d6bef57dede6a405d875442ca685c27c6fd7287fb30e7e76`。
其状态为 `MIGRATION_REVIEW_PASS_MAIN_RUN_PENDING`，今后主运行通过也不修改这个历史状态。
旧政策、受修改的脚本和旧主报告/顶层日志保存在同一归档目录。
归档时停止了不必要的旧编译目录递归复制；残留的部分编译副本不作为完整归档或新运行输入。

## 完整运行及独立复核

`make proof-check BACKEND=lean` 于 09:16:03–09:49:41 UTC 执行，实际退出 0。
21 个主阶段、14 组共 185 项测试和 47 个公开子阶段全部通过。新 Lean 依赖树以
0 个编译模块开始；原生产根 / 公开根依赖仍为 137 / 158 项，68 条公开定理及精确
定义、合同快照保持不变。此次仓库根位置未变，两份生成模型甚至保持原始字节哈希相同；
移动位置的来源注释处理另有先前独立 checkout 实测证据。

- [主报告归档](../../artifacts/boundary-check/public-input-migration-dK3ucjFP/after/artifacts/proof-check/report.json)：
  SHA-256 `66fb26d92860e6dde6198d1657a9aaf85b3d18f2c608033cb0340d69628a0dab`。
- [公开子报告](../../artifacts/boundary-check/public-check-pats4t00/report.json)：
  SHA-256 `e187cb8320c0564e81236c486b6653186af403f7b726c441799d2b96655f462d`。
- [完成复核记录](../../artifacts/boundary-check/public-input-migration-dK3ucjFP/completion-audit.json)：
  独立重新执行公开证据验收器、政策检查、主源码集合检查，重读 21 个主日志哈希和
  14 组测试的实际数量及 `OK`。主报告、审计、引用日志及两份政策已按原字节归档。

旧迁移审计的 `MAIN_RUN_PENDING` 状态保持原样，由上述新运行及新复核记录补充，
没有把历史审计修改成一次它未执行的证明检查。

## Week6 仍待证据

完整环境安装、递归 clean-room、runtime/mutation/重放聚合验收、
CI 下载、演示、第三方复现及发布仍按 [Week6 原条款](../plan/week6.md) 保留。
