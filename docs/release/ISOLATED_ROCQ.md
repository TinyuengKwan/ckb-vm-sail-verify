# Rocq / OPAM 独立重建与既有输入 NO-GO 复验

2026-09-12 已在全新 OPAM 根中按冻结元数据下载源码、重建 OCaml/Rocq 及支持库，
再用新 Rocq 复跑原有十阶段 spike。**这是局部工具重建和既有输入复验，不是完整
clean-room、双方输入重新提取、Rocq 额外证明或第三方复现。**

## 入口与冻结输入

在已有受审 Aeneas、Rust LLBC、Sail Rocq 生成物及其来源证据的仓库根执行：

```bash
python3 scripts/probes/probe_isolated_rocq.py
```

[实现](../../scripts/probes/probe_isolated_rocq.py) 默认建立新的
`artifacts/boundary-check/isolated-rocq-*`；`--out` 只能是新目录。
它先检查既有 spike 输入，因此不是空机器上的完整 bootstrap 入口。

[冻结 switch 导出](rocq-switch.export) 从此前 `rocq-spike` switch 以
`opam switch export --freeze --full` 取得，包含全部 21 个包的版本、定义、源码 URL
和校验和；SHA-256 固定为
`07f9b97b579da3d67f99d50e0815aa764b36b998e13e0b0221ce38168814691f`。
这复用了旧安装的**包元数据**，没有复制旧 switch 的编译器、库或下载缓存。
元数据来源不是独立发布者认证；摘要用于绑定字节，不证明安装历史。

新 OPAM 根只配置一个本地空仓库，通过完整导出导入包定义，不查询移动的软件包版本列表。
导入显式要求源码校验和、四路构建，并清除继承的 OPAM 假运行/旧根选项及旧 switch 路径，
禁用 Dune 缓存。核心版本为 OCaml 5.2.1、Dune 3.23.1、Rocq core/runtime 9.1.1、
stdlib 9.0.0、stdpp/bitvector 1.13.0、sail-stdpp 0.20.2。
安装后要求完整 21 包清单一致，实际编译器位于新 switch、无外部链接或共享硬链接，
且版本符合原 spike 要求。

宿主 `bwrap` 的 uid-map 创建返回 Permission denied，无法使用 OPAM 构建沙箱。
本入口只对新 OPAM 根使用 `--disable-sandboxing --no-opamrc --no-setup`；
构建不是 OS 隔离的，宿主安装器、系统编译工具及系统依赖仍复用。
`--assume-depexts` 不安装系统包，实际 conf 包仍执行其检查。
未修改原全局 switch 的包或默认选择，不声称完成宿主依赖闭包审计。

## 编译器约束与导出差异审计

首轮 [isolated-rocq-9e15tq8x](../../artifacts/boundary-check/isolated-rocq-9e15tq8x/report.json)
在 07:12:41–07:24:55 UTC 完成包构建，但完整导出比对失败；报告 SHA-256：
`008fc9ee0e47eef396405c2422768ca9b49948f55848cf8f8772937ec05ba900`。
导入后实际 invariant 只约束 `ocaml-base-compiler`，未精确到 5.2.1；
重新导出也缺少顶层 `compiler: ["ocaml-base-compiler.5.2.1"]` 一行。

随后只在该失败候选中诊断：显式设置精确公式后，实际 invariant 已是
`["ocaml-base-compiler" {= "5.2.1"}]`，但导出仍不恢复该行。
[诊断记录](../../artifacts/boundary-check/isolated-rocq-9e15tq8x/post-failure-invariant-diagnostic.txt)
说明了候选后续变化；原失败报告与原导出日志未覆盖，不把它称为未变化或通过的副本。

修正后的入口显式设置并查询**实际精确 invariant**，再比对导出：
只允许上述一行缺失，所有包定义、来源校验和、roots 和其余内容仍需一致。
宽泛或空 invariant、额外版本/字段/校验和变化均拒绝。
原始导出保留，报告 `metadata_audit` 明确写出 `exact_export_bytes=false` 和唯一差异，
不通过改写冻结导出或证明政策隐藏它。

## 第二轮实际通过与独立复核

第二轮使用另一个空 OPAM 根，重新下载和构建，不复用首轮输出。
运行时间 14:00:25–14:17:17 UTC，13 个外层阶段全部退出 0。
[完整报告](../../artifacts/boundary-check/isolated-rocq-ac54t6f8/report.json) 状态：
`isolated_rocq_rebuild_and_existing_input_nogo_passed`，SHA-256：
`3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540`。

[新 Rocq 上的十阶段 spike](../../artifacts/boundary-check/isolated-rocq-ac54t6f8/spike/report.json)
SHA-256：`713b85b344f6088fb152826380c1c8febdc81d22bfa715c75839ed509ce0e460`。
结果仍为 NO-GO：Rust 模型是原 `result bool` 的类型冲突，Sail 模型与最小复现是原
`e_div` 缺失；三个预期拒绝阶段退出 1，其余阶段退出 0。
无缺文件、资源失败或不相关诊断冒充 NO-GO，`extra_proof_coverage=false`。
Rust 部分仅重新翻译既有 LLBC；没有重新生成 LLBC 或 Sail 源码。

实际安装文件清单共 8,659 项，包括库字节、权限和内部链接；清单 SHA-256：
`e03a37b1c376dfe9305c5a991c65ef6ff104ad14bfe96bda4aa7da6fe8a13e72`。
该清单绑定本次产物，不声称新编译器与旧目录的二进制字节相同。
完成后在 `python3 -O` 下重新查询新 switch 的包、约束、导出和工具位置，
重算全部安装文件清单及阶段日志哈希，并再次运行原 Rocq 证据验收器，全部通过。
安装阶段总输出及 spike 各阶段日志均保留；OPAM 自动清理的成功构建中间日志不另称完整归档。

[16 项安装回归测试](../../scripts/tests/test_isolated_rocq.py) 和原有 16 项 spike 检查器测试
在普通 Python 与 `-O` 下通过，共 32 项。原全局 OPAM switch 列表、冻结计划、
主/公开 Lean 政策和生产证明源码未改变。

## 尚未关闭

后续 [Sail 独立源码重建](ISOLATED_SAIL.md) 已完成，二进制身份审查/采纳仍未完成。
[full-MIR 独立重建](ISOLATED_FULL_MIR.md) 也已完成，新库哈希不同，提取资格尚待核验。
Aeneas/Charon 独立安装仍待完成；后续须把全部新工具与
同一候选源码连接，重新生成双方输入并运行 runtime、Lean 主门禁和 Rocq spike。
本次安装和此前其他目录的报告不能拼接成完整 clean-room。
readiness v3 未把本报告计入缺失条款；工作树最终审计、CI 下载、发布包、演示、
公开结论和第三方复现仍未关闭。
