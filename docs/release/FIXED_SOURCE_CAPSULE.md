# 同快照离线源码交付

2026-09-13。**源码已归档并完成本机离线递归复原与独立复核；不是第三方或 clean-room。**
它补齐 [固定安装补充包](FIXED_INSTALL_BUNDLE.md)之外的源码素材，不执行 Lean/Rocq/native 链。
后续[统一恢复入口](UNIFIED_FIXED_RESTORE.md)已实现并从归档完成本机非规范路径暂存；
空机器 bootstrap、固定绝对路径部署及全链仍未验收，不能据此说第三方已仅按文档完整复现。

## 固定身份

主项目 HEAD 为 `872d225dc4e16c449be37d92761b20c6aefe853c` **加精确工作树覆盖层**，不是该裸 commit。
本次 `source-snapshot.json` SHA-256 为
`810b71aa1d4002acce1ad0fc52ef1f37019a6e57550d1c5e381c06b68c5b9999`，
与第三轮安装包清单绑定的文件完全相同。

| 仓库 | 源文件数 | 相对 HEAD 的差异项 |
| --- | ---: | ---: |
| 主项目 | 435 | 237 |
| CKB-VM | 489 | 2 |
| sail-riscv | 859 | 0 |

CKB 的两项差异仍是已采纳 runtime-container 基线；所有差异都有字节、模式和增改删清单。
这些计数及哈希不代表已经逐项完成语义审批。本文及交付准备清单是之后追加的记录，
不属于这个冻结快照，不能把当前更晚的工作树说成同一归档身份。

## 实际递归复原

07:21:07–07:21:31 UTC 的 [执行报告](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/report.json)
退出 0，SHA-256：`5c1105a72d39e433ba12f77a8cabb9737e93cce98fbba0b8c16b25d89faae0cb`。
[执行代码及日志](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/build.py)保留在同目录。
共 17 个 Git 阶段：制作并检查三个 HEAD bundle、独立主项目 clone/checkout、配置两个本地
bundle URL、实际 `submodule update --init --recursive`、三个仓库的根目录及完整 fsck 检查。

只允许本地 file transport，关闭交互式认证及全局 Git 配置；没有远端网络 clone。
随后使用 [既有快照恢复器](../../scripts/source_snapshot.py)在新的干净 checkout 中恢复所有
工作树差异，重新核对两个子模块、CKB 补丁、所有文件字节/权限和 Git 对象独立性。
原工作区和复原副本均等于同一快照，未提交、暂存或重置原工作区。

另一个 Python `-O` 进程重新验收 17 阶段日志、三份 bundle、所有素材、精确源码快照，
并再次执行三个复原仓库的完整 fsck 和根目录核验，均通过。
整个素材目录另检查无 symlink 或特殊文件。这不是第二次生成模型或第三方复现。

## 可交付素材

素材清单列出 1,787 个文件、99,233,945 字节，包括三个 bundle、1,783 个源文件及快照；
这个统计不含清单自身。保存在同目录的 [内部素材清单](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/capsule/manifest.json)
SHA-256：`e8024a053ce895a603d5984280f293611b4078a06087ecb2d7776f2b05b53238`。

07:28:37–07:28:43 UTC 又封装成单个归档，随后由独立进程重新逐成员读取验证：

- [source-capsule.tar.gz](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/source-capsule.tar.gz)：
  86,154,011 字节，SHA-256 `782747aa8b8275575e4cfccd5dc7e19020eb4a00dfff3ff335bfdaf80ba90429`。
- [传输清单](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/transfer-manifest.json)：
  共 1,956 项（含目录及内部清单），SHA-256 `59010a3dfbff4782125ca37c600606926881322d081def4bbb6488ee4c8bc8e4`。
- [传输验证报告](../../artifacts/boundary-check/fixed-source-capsule-vra4CmWQ/transfer-report.json)：
  SHA-256 `2e45a0d81c0adc3709ad7d048ff5d53d3300399d625acf2cf88efee612a7a1ab`。

递归复原使用的是 `capsule/` 中的 bundle 和覆盖层；此后压缩包经过逐成员校验，
不能把它写成又一次从压缩包开始的完整安装实跑。
源码传输清单的 kind 与安装包不同，不应把它直接传给只接受安装包 schema 的 CLI。

[交付准备清单](fixed-input-handoff-20260913-v1.json)将源码、安装补充包、既有批准 decoder
包及证据身份连接起来。它只是本机交付素材清单，不是已发布版本、正式准入政策或完整 release 包。
清单 SHA-256：`7a88d4eaa88c83a2317401ac64d9b8dc1c74e6125d40a539645e75f5f103a015`。
已逐一复核九个文件引用及源码快照、主政策和 decoder 准入的交叉哈希；
约 449 MB 的既有 decoder 压缩包仍匹配原批准归档哈希，未重写。
后续统一恢复实跑另有报告，不改写上述早期源码复原的范围。
仍须宿主依赖、固定绝对路径的新环境全链、差异/公开结论审计、CI 下载、实际发布与第三方记录。
