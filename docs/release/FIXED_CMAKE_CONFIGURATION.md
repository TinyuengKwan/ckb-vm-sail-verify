# 固定下载输入的真实冷配置验证

2026-09-13。**本机全新 CMake 配置与 GMP 构建已完成，并通过独立验收。**
它证明[四项下载补充输入](FIXED_CMAKE_DOWNLOADS.md)已有一条实际可用的本地配置连接；
不是完整模拟器构建、生成物重提取、证明链或新环境 clean-room 验收。

## 实跑与身份

08:34:36–08:36:32 UTC 的[执行报告](../../artifacts/boundary-check/fixed-cmake-configure-XufcccXE/report.json)
退出 0，SHA-256：`dbd2f6e7e348c56af3c26294b87bd08f6be88eebbf34a72188793b42d80b46f7`。
[执行代码和原始日志](../../artifacts/boundary-check/fixed-cmake-configure-XufcccXE/run.py)同目录保存。

共 9 阶段：独立 Sail-RISC-V clone、固定 HEAD checkout、仓库根核对、fsck、
下载输入暂存、恢复副本的 Sail `--dir`、CMake 版本、实际全新配置、实际 GMP 构建。
源码仍为 `8f91355eee63a85738723603e23d32eecdd763dc` 的 859 文件清洁子树，
与冻结快照 `810b71aa…` 中的 Sail-RISC-V 完全一致；Git 对象没有硬链接或 alternates。

没有复制旧 `CMakeCache.txt`、目标文件、生成模型或模拟器。
新构建目录起初只有 `gmp-prefix/src/gmp-6.3.0.tar.xz` 一份已校验源码归档。
CMake 明确选择恢复副本中的受审 Sail 二进制，不调用正式工具解析器：
`SAIL_DIR`、`SAIL_PLUGIN_DIR` 指向该副本，实际 `sail --dir` 输出与此一致。
本机 C/C++、Make、CMake 等工具被复用并核对文件身份，不是重建宿主工具链。

## 四项输入如何接入

| 输入 | 实际连接 | 证据范围 |
| --- | --- | --- |
| CLI11 | `FETCHCONTENT_SOURCE_DIR_CLI11_HPP` 指向新复制的头文件目录 | 真实模拟器目标的 include 参数引用该目录；未编译模拟器 |
| jsoncons | `FETCHCONTENT_SOURCE_DIR_JSONCONS` 指向从固定归档新解出的源码 | CMake 配置及真实目标 include 路径一致 |
| asio | `FETCHCONTENT_SOURCE_DIR_ASIO` 指向从固定归档新解出的源码 | CMake 配置及真实目标 include 路径一致 |
| GMP | 在新构建目录的原下载缓存位置预置精确归档，保持上游 URL/哈希声明不变 | 日志明确确认已有文件哈希匹配、跳过下载，然后完成提取、配置、编译与安装 |

新的 `gmp/lib/libgmp.a` 为 1,549,430 字节，SHA-256
`9f925eaac8503fa7b983d1f4f7ac0545a76187837be0891ece8402ad3a1d18c5`。
这只是本次本机 GMP 构建产物的身份，不是其跨环境可复现性或算术正确性证明。

两个 `FETCHCONTENT_*DISCONNECTED` 开关虽然记录在配置中，CMake 本次明确警告它们
未被项目使用；原日志完整保留。不能把开关值当作网络隔离证据。本次证据是三个明确的
本地源码覆盖路径和 GMP 的哈希跳过下载日志，没有操作系统级网络隔离或原目录访问排除。

## 暂存接口与限制

[输入暂存器](../../scripts/stage_fixed_cmake_inputs.py) SHA-256：
`f7119c0a44acecdf17ff2de2905dcc5f4830e760d3d30492e0f7e689bf500815`。
它固定校验补充包及外部清单，只接受新输出目录：

```bash
python3 -O scripts/stage_fixed_cmake_inputs.py \
  --archive artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/cmake-downloads.tar.gz \
  --manifest artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/manifest.json \
  --out artifacts/boundary-check/fixed-cmake-inputs-new
```

此命令**只暂存数据**，输出 `downloads/`、`sources/`、预置归档的 `build/` 和配置选项清单；
不执行 CMake 或编译器。实际冷配置与构建是上面另行记录的执行过程，不能混同。
暂存失败可能保留部分新输出；换新目录重试，不覆盖旧报告。
内层归档只允许指定上游根下的普通文件与目录，拒绝链接、特殊文件、越界、重复项及
特殊权限；明确记录空目录、字节和模式。

配置选项记录的是本次新暂存目录的绝对路径，构建位置为暂存目录下的 `build/`。
尚未接入正式固定路径所需的 `deps/sail-riscv/build` 部署流程，不能直接把本次缓存
复制到正式位置或改写路径后称作新环境验收。
本辅助代码和此记录均在冻结候选之外，没有修改 handoff v1、原 CMake 源码或证明政策。

## 独立验收与剩余义务

08:39:08–08:39:21 UTC 的[独立验收](../../artifacts/boundary-check/fixed-cmake-acceptance-I9vHO5hV/report.json)
退出 0，SHA-256：`7f701d633722bbb6813f26bbdeaf366b6bebf35400331ba53ea651c1a3bc30d0`。
另一个 Python `-O` 进程核对 9 个精确命令及原始日志、输入包与配置身份，逐一将
7,824 个解出的源码文件与原始两份上游归档比对，并核对全部目录及 CLI11 头文件。
还检查实际目标 include 参数、GMP 缓存消费日志和库产物，重新运行源码根目录/fsck，
确认新源码、恢复副本源码及 v10 正式审计所覆盖的源码身份未变。

两项真实 CLI 负测确认：已有输出拒绝覆盖；清单即使只增加空白也因固定身份变化被拒绝，
且不创建输出。[17 项回归](../../scripts/tests/test_stage_fixed_cmake_inputs.py)在普通 Python
和 `-O` 模式均通过，[测试日志](../../artifacts/boundary-check/fixed-cmake-acceptance-I9vHO5hV/test-report.json)保留。

仍须在获准的新环境中完成固定路径部署、宿主兼容检查、完整模拟器及生成物构建、
Lean/Rocq/native 验收链；还要完成最终差异/公开结论审计、CI 下载重放、实际发布与独立
第三方复现。本次本机冷配置不关闭这些义务，也不消除 [LXD 事件](LXD_WRAPPER_SIDE_EFFECT.md)
所需的用户决定；本轮没有进一步安装或配置宿主软件。
