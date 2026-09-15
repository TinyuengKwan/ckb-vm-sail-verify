# 正式安装输入分发核验

2026-09-13。**安装清单核验和 Sail 前缀搬迁 smoke 已通过；完整分发与 clean-room 未完成。**
本次不改变 `rebuilt-main-v1` 政策、原安装报告或任何旧证明证据，不操作 LXD。

## 实跑与范围

[入口](../../scripts/install_distribution_review.py) 在仓库根运行：

```bash
python3 -O scripts/install_distribution_review.py
```

它依赖现有固定安装，不是新机器 bootstrap 命令。每次只创建新的
`artifacts/boundary-check/install-distribution-*` 目录；不覆盖或删除原安装。
本次 06:40:59–06:42:08 UTC 退出 0，
[报告](../../artifacts/boundary-check/install-distribution-cggb3kep/report.json) SHA-256：
`77780ebf43842ed0cabc7afabba2a05e6d497a332b6a369e6a1a58f42e965122`。
完成后另一个 Python `-O` 进程独立复核六组安装、三组控制数据、复制前缀、
四条精确命令及日志、五份输出和源码/报告哈希，全部通过；这不是第二次生成执行。

先核对四份固定安装报告，再逐文件重新核对六组安装的哈希、大小、权限及链接身份。
下列统计是文件的逻辑字节数，不是压缩包大小或整个运行环境大小。

| 安装范围 | 清单项数 | 常规文件字节数 | 符号链接 |
| --- | ---: | ---: | ---: |
| Rust 两套 toolchain | 7,189 | 2,245,256,894 | 0 |
| Lean toolchain | 14,632 | 2,897,076,306 | 12 |
| Aeneas OPAM switch 安装目录 | 11,469 | 1,509,887,604 | 5 |
| Sail OPAM switch 安装目录 | 6,791 | 620,993,957 | 5 |
| Sail 安装前缀 | 1,099 | 126,946,381 | 0 |
| Rocq OPAM switch 安装目录 | 8,659 | 870,946,752 | 5 |

合计 **8,271,107,894 字节**。所有记录到的链接都是相对链接且解析在对应前缀内；
这不证明脚本、二进制、OPAM 配置或报告内部没有绝对路径。
这六组清单也不包括 v2 输入 payload、编译器源码 Git 树、系统工具/动态库与完整 OPAM 根状态。

## 确认的分发缺口

1. 正式入口从固定报告读取原绝对路径：
   [Rust/OPAM 解析](../../scripts/decoder_rebuilt_locations.py)、
   [Lean/Sail 解析](../../scripts/rebuilt_main_tools.py)及
   [Rocq 解析](../../scripts/rocq_context.py)均不会自动把路径重定位到新 checkout。
   报告哈希又被输入证据和正式源码绑定；直接修改报告中的路径会改变受审身份。
2. 已有安装闭包仅枚举 `toolchains` 或九个安装子目录，不包含 OPAM 根 `config`、
   `repo/repos-config` 与 `.opam-switch` 控制数据。本次另外枚举了 Aeneas/Sail/Rocq
   各 **346/160/57** 个控制文件，所有选定路径均存在，并核对执行前后哈希一致。
   这只是额外依赖观察，不是证明这些文件已经充分覆盖 `opam exec/list` 的全部需要。
   锁、日志、下载缓存、构建树、源码及其他仓库状态明确未计入该观察。
3. 原安装报告记录本机 bootstrap 和构建历史，且 Git 忽略的安装树不在普通 clone 中。
   打包安装文件不等于锁定工具从源码独立重建，也不等于独立第三方已完成复现。

不能据此宣布“把六组目录压缩即可复现”。完整分发方案仍须明确哪些内容是源码、
固定安装输入、OPAM 控制状态与宿主依赖；生成独立可校验清单，并在无原安装依赖的环境中实跑。

## 实际 Sail 搬迁测试

只把约 127 MB 的 Sail 前缀复制到本次新目录 `sail-prefix/`。逐文件核对身份相同，
常规文件与原目录 inode 不同且无硬链接复用。原前缀保持不动。
子进程不继承整个宿主环境，仅设置 `/usr/bin:/bin`、locale、临时目录及指向新前缀的
`SAIL_DIR` / `SAIL_PLUGIN_DIR`。

四个实际命令均退出 0：版本检查、`--dir` 检查、既有小 fixture 的 C 生成、Lean 生成。
`--dir` 返回新前缀的支持目录。生成的一份 C 和四份 Lean 文件与原安装 smoke 报告绑定的
对应文件 SHA-256 全部相同；未进行归一化。未编译这些输出，也未重新运行 ADD kernel 或
完整 RISC-V 生成。结束后重新检查六组原安装、复制前缀、选定 OPAM 控制数据及审计源码无漂移。

**这不是 OS 隔离测试。** 原目录仍在宿主可见，没有系统调用追踪或访问隔离证据；
不得把显式选择新支持目录扩大为“未访问任何原目录/宿主动态库”。
Sail 小模型生成成功也不证明 Rust、Lean、OPAM、Rocq 整套安装已可搬迁。

[11 项回归测试](../../scripts/tests/test_install_distribution_review.py)在普通 Python 和 `-O`
下均通过，覆盖路径越界/别名、目标保护、复制前源漂移、外链、控制数据变化和环境注入隔离。
该辅助入口没有加入正式证明政策，不增加定理或发布保证。

## 后续准入要求

后续 [固定路径补充包实现](FIXED_INSTALL_BUNDLE.md)已增加独立包校验与新目录暂存，
前两次完整尝试分别发现链接链和 Git 空目录问题；修正后第三轮完整打包、暂存和独立验收
已通过。另有 [同快照源码归档及离线递归复原](FIXED_SOURCE_CAPSULE.md)。这些材料仍不关闭 clean-room。

- 固定路径部署与可搬迁部署必须明确区分；不能重写旧安装报告来冒充同一次安装。
- 若采用路径映射，须另立带来源映射的新安装描述、验证 OPAM 控制数据和实际二进制路径行为，
  经审查后再变更正式解析层/政策；当前解析层保持原身份。
- 完整工具环境的独立安装、双方重生成与全链执行、源码差异审计、CI 下载、发布及第三方复现
  仍按 [Week6 原条款](../plan/week6.md)验收。本报告不填入 `clean_room` 的完成 slot。
