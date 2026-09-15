# 固定路径安装补充包（字节往返与独立验收完成）

2026-09-13。目标是把 [安装分发核验](INSTALL_DISTRIBUTION_REVIEW.md)确认的包外安装输入
整理为可逐项校验的压缩包。**第三轮完整打包及独立验收已通过；不关闭 clean-room 或发布。**
不修改正式政策、原报告中的绝对路径、原安装或 LXD 配置。

07:13:23–07:23:44 UTC 的 [第三轮报告](../../artifacts/boundary-check/fixed-install-package-o7qy39ke/report.json)
退出 0，SHA-256：`90232f24ae4d39a78301368ba7b67355c2cfe7263fb3373b872dfb8838304de7`。
共 **56,702 项**：53,556 个普通文件、27 条链接、3,119 个目录，普通文件共
8,404,146,606 字节；压缩包为 **3,177,313,112 字节**。
完整解到新目录并逐项复核，暂存 Sail 的 Git 根、固定 HEAD、源码及对象独立性均通过。

07:26:37–07:29:36 UTC 的 [独立验收](../../artifacts/boundary-check/fixed-install-acceptance-W9Da1PEm/report.json)
另以 Python `-O` 重新读取整个压缩包和暂存目录，核对六组安装、四份报告、
Sail Git 根/对象/源码及来源前后快照，退出 0。
报告 SHA-256：`48a9424c266db35c225b87448dd85a54545e2fb06a94101a4fd438c92c79e352`。

包文件：[extra-installations.tar.gz](../../artifacts/boundary-check/fixed-install-package-o7qy39ke/extra-installations.tar.gz)，
SHA-256 `d128c9e7a4755fa01b8f54640bae3276c4c0a5ff968ee62b88ed01ca4240cd3c`；
[外部清单](../../artifacts/boundary-check/fixed-install-package-o7qy39ke/manifest.json) SHA-256
`d6c28ebc2fc9f6010aec478763a4f792bd18c5ec17b5fafc50fc3675cc5266b2`。

## 实现与范围

[制作入口](../../scripts/build_fixed_install_bundle.py)：

```bash
python3 -O scripts/build_fixed_install_bundle.py
```

每次建立新目录，包含 `manifest.json`、`extra-installations.tar.gz`、
独立 Sail Git 源码副本、`staged/` 暂存结果、源码快照、阶段日志及 `report.json`。
不覆盖任何已有目录，也不将包解压到当前生产安装位置。
生产者只有在完整暂存、原输入复核和暂存 Sail 仓库根/源码身份核验都通过后才返回 0。

包内包括六组固定安装目录、四份原始安装报告、选定 OPAM 控制文件及 repo/opam-init 状态，
以及没有对象硬链接/alternates 的 Sail 编译器源码 Git 副本。源码构建缓存不复制。
目录（包括空目录）、普通文件权限/字节和相对符号链接分别记录。

以下仍明确是外部输入，不能将“补充包”说成完整 release 包或任意机器安装方案：

- 主项目精确 HEAD、工作树覆盖层及固定子模块；源码快照清单本身不是源码归档。
- 已批准 rebuilt-v2 decoder 输入包及其既有安装入口。
- 固定 bootstrap 可执行文件、兼容系统工具与动态库；未声称宿主闭包完整。
- 当前正式报告所要求的原绝对 checkout 布局；暂存不代表路径重映射获准。
- 原历史报告引用的完整日志/输出树；本包仅保存选定安装输入和报告。

包内 Git/OPAM 元数据包含本机路径；对外分发前还须审查隐私元数据、许可证及再分发条件。
尚未上传、发布或触发外部 CI。

## 校验与暂存接口

[独立入口](../../scripts/fixed_install_bundle.py)使用 `--archive`、`--manifest` 和必需的
`--manifest-sha256` 校验包；可加 `--stage` 指定一个尚不存在的新目录，完成字节暂存。
清单哈希必须来自另外可信的来源，不能把从未知包内现算出的哈希当作信任依据。

校验拒绝额外/缺失/重复条目、路径越界、文件或链接作为父目录、硬链接与特殊文件、
错误字节/权限/类型、重复 JSON 键，以及保证字段升级。
相对符号链接允许有限链，但必须无环、不越界，并最终落到清单中的普通文件。
暂存不调用 `tar.extract`，不覆盖文件，完整核对目录和文件清单。
其 `operational_installation_claimed=false`；通用包校验不替代完整生产者的 Git/来源验收。

在当前仓库校验本次包，不解包也不部署：

```bash
python3 -O scripts/fixed_install_bundle.py \
  --archive artifacts/boundary-check/fixed-install-package-o7qy39ke/extra-installations.tar.gz \
  --manifest artifacts/boundary-check/fixed-install-package-o7qy39ke/manifest.json \
  --manifest-sha256 d6c28ebc2fc9f6010aec478763a4f792bd18c5ec17b5fafc50fc3675cc5266b2
```

当前 [23 项回归测试](../../scripts/tests/test_fixed_install_bundle.py)在普通 Python 和 `-O`
下通过，含真实 Git 空 refs 目录的打包/暂存/仓库根检查。新辅助代码尚未进入正式证明政策。

## 保留的两次失败

首轮 [报告](../../artifacts/boundary-check/fixed-install-package-kwbvyzfz/report.json) 在写包前
拒绝两条合法的 Lean 两级相对链接，退出 1；报告 SHA-256：
`af598ca5d3e3c28d0c36f2965ebd2457788ca94eeef068834458127c0584e02b`。
旧实现仅允许直接链接。修正加入有限链及环/悬空负测，旧实现和测试已随失败目录归档。

第二轮 [报告](../../artifacts/boundary-check/fixed-install-package-99a1qrcz/report.json) 也退出 1，
SHA-256：`1b4566b69793a2bc82de1ebf2dd0af132d72d76d482e350c8c83cf52b8338732`。
其 53,583 个文件/链接条目、8,404,146,606 字节和约 3.18 GB 压缩包通过了字节往返，
另一个 Python `-O` 进程也确认包文件字节与当时清单相符；**但完整验收仍失败**。
原因是没有记录空目录，解包后的 `.git/refs` 缺失，Git 向上发现了主项目仓库，
得到错误的 HEAD `872d225…`，而不是 Sail 的 `8eb1fb6…`。

修正后目录类型/权限及空目录纳入格式，暂存检查拒绝缺失或多余目录；
生产者还显式要求暂存源码的 `git rev-parse --show-toplevel` 等于该目录，
不能仅依赖 Git 向上发现的仓库。第二轮旧包、清单、暂存树、代码与失败报告保留，
不改写为成功。第三轮随后完整实跑及独立验收通过，不能用 23 项测试代替该实跑记录。

## 与源码交付的连接

[同快照源码归档](FIXED_SOURCE_CAPSULE.md)已经另行制作，并在本机从三个 bundle 实际递归
检出和复原。两者绑定的 `source-snapshot.json` SHA-256 均为
`810b71aa1d4002acce1ad0fc52ef1f37019a6e57550d1c5e381c06b68c5b9999`。
[交付准备清单](fixed-input-handoff-20260913-v1.json)另列已批准 decoder 归档及其政策身份。
这份清单不属于冻结源码快照，也不是新的正式输入准入或 release PASS。
本页追加后的工作树不再与归档快照相同；原完整源码身份保留在包与源码归档中。

[统一恢复入口](UNIFIED_FIXED_RESTORE.md)已从三类归档完成本机非规范路径暂存；
固定绝对路径部署、兼容宿主依赖及新环境中的同候选生成/执行仍待验收。
包内原报告不是这次新环境的运行证据，也不能据本机暂存成功关闭 `clean_room` slot。

## 2026-09-15 xz 重新封装（同成员、同清单，只换容器）

原 gzip 包 3,177,313,154 字节超过 GitHub release 单文件 2 GiB 上限。同一份 56,702 项内容用
`scripts/fixed_install_bundle.py --recompress-xz` 重新封装为 xz：先逐成员核对 gzip 包与清单，
把解压出的 tar 流交给 `/usr/bin/xz -9 -T 20 --check=sha256`，再逐成员核对 xz 包，并要求两个容器
解压后的 tar 流 SHA-256 相同。清单 `ac7b468e…` 不变；新包
`c8e8ca2797aeabcbee3935949f6ad6b622a40468d77a7f5d79a50b1854a67ff4`，1,801,059,088 字节，
低于上限约 346 MB。03:47:29–04:02:09 UTC 的
[重封装报告](../../artifacts/boundary-check/fixed-install-package-xz-20260915/recompress-report.json)
与随后另一普通模式进程的
[独立验收](../../artifacts/boundary-check/fixed-install-package-xz-20260915/independent-acceptance.json)
（完整暂存 56,702 项并核对 tar 流哈希后删除暂存目录）见同目录。

加载与暂存现在按魔数识别容器，gzip 与 xz 都接受，文件名不作依据；新建包默认 xz，
`build_fixed_install_bundle.py --compression gz` 仍可生成旧格式。clean-room 控制器与 VM launcher
固定的安装包哈希改为上述 xz 值，下载文件名改为 `extra-installations.tar.xz`；清单哈希不变。
源码归档的提取入口同样改为按魔数识别。25 项包测试与恢复入口测试在普通与 `-O` 下通过。
这只是容器更换，不是新的安装验收、clean-room 或发布证据；旧 gzip 包与其报告保留原身份。
