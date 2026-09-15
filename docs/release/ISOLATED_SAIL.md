# Sail 独立源码重建与身份核验

本项只核验固定 Sail 编译器及其 OPAM 依赖能否在新目录源码重建。
**不是完整 clean-room、第三方复现、新 ADD 证明或证明政策迁移。**

## 输入与运行方式

```sh
python3 scripts/probes/probe_isolated_sail.py
python3 -m unittest discover -s scripts/tests -p test_isolated_sail.py
python3 -O -m unittest discover -s scripts/tests -p test_isolated_sail.py
```

入口默认读取本机 `/home/clair/.local/src/sail` 的 Git 历史，以及
`/home/clair/.local/share/sail-src` 的旧安装作为只读比较对象；可用
`--source`、`--baseline` 指定其他位置。它不是面向空宿主的全部工具安装器。
每次自动创建新的 `artifacts/boundary-check/isolated-sail-*`，指定的 `--out` 若已存在会拒绝。

- 源码固定在 `8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1`，3,123 个源码文件。
  独立 Git clone 不使用对象硬链接或 alternates，detached checkout 后核对文件字节和权限；
  不复制原 `_build` 或未跟踪内容。该 clone 来自本机历史，不是第三方远程复现。
- [完整 OPAM 冻结导出](sail-switch.export) 来自旧 `5.4.1` switch 的
  `opam switch export --switch=5.4.1 --freeze --full -`，含 56 个固定版本包的完整元数据。
  SHA-256：`caca2799b1c6e6a79c9d9d03d6843f195ebcbdbf0521caebfbf31631ed576948`。
  这是本机依赖快照，不是上游签名或整个宿主系统的锁。
- 新根只配置空本地 OPAM repository，导入内嵌包定义，并强制来源校验和；
  不从实时 repository 重新选版本，不复制旧安装或构建缓存。
  日志中的同次下载 `cached` 可表示多个包共用刚下载的同一源码归档，不代表复制旧根缓存。
- 56 包中包含旧依赖 switch 原有的 Sail 0.20.2 **发布版**包，也会重新构建；
  它们不是本项最终选择的 Sail。另在干净源码 clone 中执行
  `dune build @install -j 4`、`dune install --prefix=<新目录>/sail-install`。
  不使用现有 `build_sail.sh` 的默认全局安装路径，也不修改全局 OPAM switch。
- 实际 compiler invariant 必须为 `["ocaml-base-compiler" {= "5.4.1"}]`；
  导出只允许 OPAM 已知的顶层 compiler 清单行缺失，其余元数据必须与锁一致。
  原旧 switch 允许 `ocaml-system` 的备选公式不被当作新根可接受的约束。
- C / Lean 生成 smoke 明确选择新前缀中的 `bin/sail`、`share/libsail/plugins` 和
  `share/sail`，并验证完整版本字符串及 `--dir`。固定小程序为
  [tool_install_smoke.sail](../../scripts/fixtures/tool_install_smoke.sail)，不使用 VM 模型，
  不编译所生成的 C / Lean，也不计入 ADD 定理证明。

## 隔离及失败处理边界

复用宿主 `/usr/bin`、`/bin` 中的 OPAM、Git、C 工具链、Z3 等以及系统库/网络。
清除外来 OPAM、Sail、Dune、OCaml 和 Git 路径覆盖，关闭 Dune 缓存。
宿主不支持当前用户的 bwrap user namespace；新 OPAM 根使用 `--disable-sandboxing`。
这只隔离安装目录，**没有 OS 文件系统/进程沙箱，也没有锁住整个宿主构建环境**。

报告绑定原/新源码清单、原安装和新安装文件清单、OPAM 库清单、阶段日志及输入哈希；
最终检查原安装、原源码、入口文件与两份证明政策没有变化。OPAM 设置
`OPAMKEEPLOGS=true` 请求保留日志，但实测仍会清理成功包的部分命令日志。
本报告逐条绑定的是外层阶段日志，不声称内部编译日志完整归档或全部独立验收。

版本不符、构建/生成失败、依赖或源码漂移返回 1。构建及 smoke 成功但新 Sail
执行文件与既有主证明政策的哈希不同，返回 2，状态为
`isolated_sail_rebuild_identity_review_required`；不会自动刷新政策或旧工具。
即便主执行文件哈希相同，也不表示完整安装闭包已经被旧证明政策覆盖。

## 本轮预检与中止记录

预检发现 C 后端需要 `-c` 而非 `--c`，prelude 之前须声明默认位序，且 Lean
输出父目录须先创建。修正后在旧固定编译器上 C / Lean 生成均退出 0；
这只是新入口预检，不是新工具重建结果。

发现最后一项输出目录问题时，首个候选已经开始安装，因而主动中止该候选后修正入口，
没有在运行途中修改入口后继续当作通过。
[原中止报告](../../artifacts/boundary-check/isolated-sail-ha9z3wq1/report.json)
保留 `failed`，SHA-256：
`a3d2d3a9fbcb5993d3ccfc12553a91f9ac41a11dc717297a1560aa76f7b3ebaf`。
下一次运行使用另一个全新根，未复用该中止候选的安装物。

16 项入口回归测试在普通 Python 与 `-O` 下均通过，覆盖版本/commit、精确依赖和
约束、元数据漂移、环境清理、旧目录拒绝、二进制不匹配时不自动批准等。

## 第二轮实测结果与独立复核

2026-09-12 15:21:14–15:29:49 UTC，第二个全新根的 18 个阶段全部退出 0；
56 包安装、固定 commit 的 Sail 构建/安装、精确约束审计及 C / Lean 生成 smoke 均成功。
[完整报告](../../artifacts/boundary-check/isolated-sail-nrdi23ds/report.json) SHA-256：
`a765bc5f4cbaa9af62909ea9cd1e1d2af50a5b9f8437aaf80a7be0cf91b88739`。

**整体入口退出 2，而非证明政策验收通过**：
`status=isolated_sail_rebuild_identity_review_required`。

| 身份 | SHA-256 |
| --- | --- |
| 现有主政策中的 Sail 执行文件 | `5ea16bff5d607483d80ca03702f7af28ea0dc7048507c0b9b9c8212294eafb46` |
| 新源码构建 Sail 执行文件 | `783dd162807daafcab8f61afe29e64d7431eb8d8365cc22feb9f74f1633314cf` |
| 新 Sail 安装清单（1,099 项） | `de183d616d9134fee93ddd68866ca767fcb71ab27794d53ff48bb923e6aa00e5` |
| 新 OPAM 安装清单（6,791 项） | `a5f86c65fe8009fe94645e541f03138f4c9134bf32346c720e1b6d28f4279cc7` |

实际查询得到精确 `ocaml-base-compiler.5.4.1` 约束；OPAM 重导出仍只缺少顶层
compiler 清单行，其他完整元数据与冻结文件一致，没有放宽或更新包版本。

完成后在 `python3 -O` 中独立重读报告，重算所有安装清单、3,123 个源文件、
输入/政策与 18 份阶段日志哈希；重新查询新根包版本、invariant、完整导出以及 Sail
版本和支持库路径，全部与报告一致。旧源码与旧安装保持原样，全局 switch 列表未增加。
47 项独立工具安装相关测试在普通 Python 和 `-O` 下通过。

另与修正后的旧编译器预检产物
`artifacts/boundary-check/sail-baseline-smoke-hasyu_rf` 比较：新生成的 `smoke.c` 和
四个 `.lean` 文件均**逐字节相同**；新旧 `share/sail` 下全部 146 项文件清单
（字节/权限）也相同。这只支持小型生成 smoke 的一致性，不覆盖完整 RISC-V 模型。

两份 ELF 可观察到各自不同的安装路径和调试路径；新文件包含其新 `sail-install`
及 OPAM 前缀。**尚未证明二进制的全部差异仅来自路径**，因此未执行二进制归一化，
也未依据相同版本、相同源码或小型 smoke 自动采纳新工具。

后续 [完整模型与 ELF 身份审查](SAIL_MODEL_IDENTITY.md) 已进一步核实：主程序代码段相同，
`.data` 的全部变化仅为三个精确安装目录字段，所有 10 个原生插件也已核对。
原完整比较已在旧工具侧结束：三个后端生成成功，但发现原政策含一个历史残留文件，
因而拒绝匹配。后续新工具 Lean / Rocq 原始输出一致，但 C++ 两文件不同、整项比较失败；
隔离清理后的主 kernel / 边界审计通过，见
[残留文件记录](SAIL_STALE_GENERATED_FILE.md)；这不改变本页原重建报告的结论。

## 尚未关闭

Sail 独立源码重建与基础生成检查已完成；新工具的身份审查/正式政策采纳仍未完成。
下一步应审计完整生成物和工具闭包差异，而不是直接修改旧政策的执行文件哈希；
之后仍须与 Aeneas/Charon、full-MIR 和同一源码候选连接，重新生成双方模型并跑完整证明/执行链。
本项报告不能与其他候选的安装和证明报告拼接成完整 clean-room。
Week6 readiness 的七类未完成验收仍保持未关闭。
