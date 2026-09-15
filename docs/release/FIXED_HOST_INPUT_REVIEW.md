# 固定输入的宿主前置条件：静态核验

2026-09-13。**静态输入记录与独立复核完成，不是环境兼容性或 clean-room 验收。**
这是[统一暂存恢复](UNIFIED_FIXED_RESTORE.md)之后的准备工作；没有执行被检查的工具、
改动宿主、配置 LXD、重写安装报告或运行 proof-check。

## 实际证据

[入口](../../scripts/review_fixed_host_inputs.py) SHA-256：
`fff03081fc0310eaffb3f1bdd7dd1feaf6ad4d686919f596bc8cda25d841494d`。
它绑定已经验收的非规范路径恢复报告、冻结源码快照、安装清单和 decoder catalogue，
在读取元数据前后复核全部声明的安装条目。它是冻结候选之外的辅助代码，未加入正式证明政策。

08:17:30–08:18:53 UTC 的[执行报告](../../artifacts/boundary-check/fixed-host-review-5HYjs2mi/run/report.json)
退出 0，终态为 `static_host_input_inventory_recorded_not_environment_acceptance`。
SHA-256：`310a437d89c47ba43dcf8d6e4a85eb8ae3b6e31b6884b7beb84355d477409860`。
退出 0 只表示输入记录完成，不是宿主可运行判定。

| 核验范围 | 实际记录 |
| --- | --- |
| 安装包＋decoder catalogue | 56,794 项，其中 53,648 个普通文件，字节/模式前后复核 |
| ELF | 673 个路径、650 份不同内容；记录类型、架构、解释器、NEEDED、SONAME、RPATH/RUNPATH |
| 脚本 | 453 个 shebang 记录，另记可执行权限位；没有运行或解析全部脚本行为 |
| 宿主库缓存 | 1,039 条缓存记录，25 个 NEEDED 名称；仅形成同名候选列表 |
| 宿主文件观察 | 27 个库/解释器路径（其中 1 个缺失），另记 31 个代表性宿主命令文件；不是完整宿主闭包 |
| 冷构建下载声明 | 冻结 Sail-RISC-V 源码中的 GMP、CLI11、jsoncons、asio URL 与 SHA256/SHA3_256 |

使用已检查为 ELF 的实际 `readelf` 程序读取文件，未使用 `ldd` 或执行被检查的二进制。
本机 `/usr/sbin/ldconfig` 是 shell 包装脚本，先阅读后未调用；只用实际
`/usr/sbin/ldconfig.real -p` 读取现有缓存，未运行缓存更新。读取程序本身也记录并复核哈希。

08:21:40–08:22:22 UTC 的[独立复核](../../artifacts/boundary-check/fixed-host-acceptance-a2yAyyrv/report.json)
退出 0，SHA-256 `11227ad873190f2ca38a0eff61f9d6b2564066994f8d2eea1fc84716f6a34475`。
重新核对全部声明输入、650 份 ELF 记录和共 651 个读取命令的原始日志；
另用 `objdump -p` 交叉检查 13 个关键文件的 NEEDED 顺序，均相符。
测试覆盖解析拒绝、库缓存计数、下载哈希算法、包装脚本不执行、符号链接身份和已有输出保护；
[18 项回归](../../scripts/tests/test_review_fixed_host_inputs.py)在普通 Python 和 `-O`
下均通过，[原始测试日志](../../artifacts/boundary-check/fixed-host-acceptance-a2yAyyrv/test-report.json)已保存。

## 不能被“同名候选齐全”掩盖的边界

25 个 NEEDED 名称均至少有一个包内名称或宿主缓存候选，但**没有证明实际装载路径、
架构/ABI/符号版本兼容性或递归动态库闭包**。例如 `libc.so.6` 在 Lean 支持目录中有同名
内容，不代表所有工具会选择它。`libgmp.so.10`、`libzstd.so.1` 本次只有宿主缓存候选，
不能把宿主库自动算入交付包。

两份 Lean 支持文件——`lib/glibc/libc.so` 与 `lib/glibc/libpthread.so`——记录了
`/nix/store/hwwqshlmazzjzj7yhrkyjydxamvvkfd3-glibc-2.26-131/lib/ld-linux-x86-64.so.2`
解释器路径，本机该路径不存在。它们位于支持库目录而不是 `bin/lean`；本轮没有执行它们，
因此既不据此宣称 Lean 主程序失败，也不删除、改写它们或创建伪兼容链接来制造通过。
实际调用路径需要在新环境完整执行中确认。

本次没有覆盖 dlopen/插件数据访问、脚本的完整解释器选择、系统头文件和静态库、
C/C++ sysroot、全部 Cargo registry 缓存或所有外部网络输入。
宿主观察发生在已披露的 [LXD 包装脚本事件](LXD_WRAPPER_SIDE_EFFECT.md)之后，不能说
此前完整证明运行期间宿主没有变化，也不能把这次观察称为新机器 clean-room。

## 使用与后续

在仍持有本次固定归档和恢复副本的工作区，可另建输出重新记录：

```bash
python3 -O scripts/review_fixed_host_inputs.py \
  --restore-report artifacts/boundary-check/unified-fixed-restore-L5xCOnDq/run/report.json \
  --install-manifest artifacts/boundary-check/fixed-install-package-o7qy39ke/manifest.json \
  --out artifacts/boundary-check/fixed-host-input-review-new
```

该命令专门核验本次固定非规范路径副本，不是通用新机器兼容性门禁。
输出必须不存在；清单哈希由入口固定，不能通过更换同名元数据接纳新身份。
四份 CMake 下载内容已另行[保存并独立校验](FIXED_CMAKE_DOWNLOADS.md)，后续
[本机冷配置与 GMP 构建](FIXED_CMAKE_CONFIGURATION.md)也已实跑和独立验收；这不是网络隔离，
亦未改动 handoff v1。下一步须在获准的新环境中完成固定绝对路径
部署、宿主准备和同候选完整执行；v10 的六类未关闭义务保持未关闭。
