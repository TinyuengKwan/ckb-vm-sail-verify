# 新旧 Option.map 等价与原 raw ADD 定理连接

2026-09-12。对实际重提取的 FactoryScoped / MiniComplete，已证明新旧 `Option.map`
的点态及函数级等价，并用新模型重新编译原字段/raw 定理。**原 raw 政策仍拒绝候选；
未采纳新工具，未完成新公开 decoder 全链或 clean-room。**

## 实际入口和范围

```sh
python3 -O scripts/probes/probe_lower_map_kernel.py
```

[等价证明](../../scripts/fixtures/lower-model-equivalence/LowerMapEquivalence.lean)直接导入
三份新生成模型和两份原批准模型的归档副本，不手写替代 map 定义。原模型副本只改
外层 namespace 的开始/结束两行，以便同时加载；其余字节必须与批准输入相同。
四个定理量化任意类型 `T/U/F`、任意 `FnOnce` 实例、任意 Option 值和闭包值，覆盖
`Result.ok`、`fail` 和 `div`，没有添加执行成功或 `False` 前提。

[导出器](../../scripts/fixtures/lower-model-equivalence/ExportLowerMapAudit.lean)用四个固定
预期类型再次检查接口，并导出定理类型、完整公理集合和四个实际 map 定义。
四个等价定理的依赖均仅为 `propext`、`Quot.sound`。

归档副本的 elaborated body 因复制消重而有两个内部名称变化：map 的 `match_1` 名称，
以及绑定变量中的模块名。仅对**旧归档副本**逐处要求唯一匹配、还原这两个名称后，
其完整表达式必须匹配原 raw 政策的定义哈希。这不是新模型的规范化规则，不修改任何
生成文件、Lean 表达式或正式政策；其余表达式变化必须拒绝。

所有新模型/证明 `.olean` 从空目录编译。主模型、Aeneas、Sail、Mathlib 等已有支持库
编译缓存明确复用：15 个搜索目录，70,681 个 `.olean` / `.ilean` 及附属 `.olean.*`
文件运行前后哈希一致；可选 `Cli` 构建目录不存在的状态也单独记录，实际缺失导入仍失败。
使用独立安装、完整清单核验的 Lean 4.31.0。这不是全依赖源码重建。

## 完成报告

[报告](../../artifacts/boundary-check/lower-map-kernel-0v7r0ook/report.json)：
19:24:50–19:30:46 UTC，23 阶段中 21 项退出 0，两个预期负测退出 1。
外层退出 2，`lower_map_equivalence_and_raw_kernel_checked_admission_pending`。
报告 SHA-256：`57cb243c8742513062547a8983b6cafeca689907250146e78f46cbea3d8101cd`。

| 检查 | 结果 |
| --- | --- |
| 新旧 map 点态/函数等价 | 4 条定理通过，无非标准公理 |
| 原字段定理 | 9 条通过，完整字段政策审计一致 |
| 原 raw ADD 定理（含最小闭包全输入回归） | 15 条通过，全部类型/公理集合与原政策一致 |
| raw 定义审计 | 仅两处 map 定义不同，其余定义哈希一致；原政策拒绝 |
| 错误返回值负测 | 新 MiniComplete 的 `some t` 改为 `none`，模型可编译，原等价证明被 `unsolved goals` 拒绝 |
| 额外 False 前提负测 | 加前提后的等价定理可编译，固定接口审计被 `type mismatch` 拒绝 |

三份审计 JSON 哈希：

- map：`733245c1e5ae5ac8034de1fac53b65f33e36a9c543d9bab7816122275f8549f3`。
- field：`4e9c426fef6fb23f619d74c5114cf00c121e80042e8e87e9337a40bc460369bb`。
- raw：`2d400d57ef6fc84ef77d4ff32a88b82bd49051cfc2939ac63a32a261f67dda9d`。

两个候选定义哈希分别是：

- `RawDecodeFactory.core.option.Option.map`：`a74085a72240faa6c09145a9902e139a18a39c94d1491b5eea2a0b9ee698b8c3`。
- `decoder_shared_closure.core.option.Option.map`：`168e09602a0a048c47577d912bb4482b7ef357577b46982c1fb0ec5b150e5f3f`。

它们只记录在候选报告中，原 raw / field / public / main 政策均不改变。
16 项新 kernel 检查器测试、5 项 sysroot 对照检查器测试，加已有相关 59 项，共 80 项
普通 Python 与 `-O` 测试通过。

完成后独立 `-O` 复核全部 23 阶段日志与精确命令、原样/重命名复制、两个负测的实际
变异、70,681 项复用编译文件及私有 Lean 安装清单；再次用 Lean 执行 map / field / raw
三个审计导出器，所得完整 JSON 与记录一致。原定理类型/公理、限定两处定义差异、
旧副本内部名称核对和原 raw 政策拒绝均重新验证；正式来源、生成物和原计划哈希不变。

## 保留的失败与修正

- [首轮](../../artifacts/boundary-check/lower-map-kernel-wrrhavgr/report.json)在可选 Cli
  搜索目录不存在时过早失败，尚未运行 kernel。报告 SHA-256
  `ee3dc8c9d410d49733ec395eb4568610e8bac78d31f50bea7ca1c0dd7a0bfd6c`；原脚本保存在
  `probe-source.py`，SHA-256 `97500b1e6b82ce5f50e8b5ac08c71ef8af8e25ca22f171d81f0e29657de4fbbb`。
  修正后显式记录缺失/空目录及运行后状态，不跳过真实 import 失败。
- [第二轮](../../artifacts/boundary-check/lower-map-kernel-7cezjkf8/report.json)完成模型和四条
  等价定理编译，但导出器的局部标识符语法失败。报告 SHA-256
  `2fb8fae28f7892df6eeed4007ef9a9cc6c8ee1a7b7ef5511eb500ca6fc2a9354`；原导出器保存在
  `models/ExportLowerMapAudit.lean`，SHA-256 `34ab705c059ad402914ccfe66976e45a2904d4f208d038ceb144862ed6aa4c22`。
  原入口亦保存在 `probe-source.py`。修正后使用新输出目录重新编译，失败报告未改写。

## 尚未关闭

[sysroot 对照](LOWER_SYSROOT_DIFFERENCE.md)已在固定最小模型上重现来源差异，本项补上
生成函数的实际 kernel 等价与候选 raw 连接。随后[原字段/raw 负测与工厂运行检查](LOWER_ORIGINAL_NEGATIVES.md)
已在新候选上完成。仍需候选准入的精确政策/配置审查、公开 decoder 全套负测和新工具资格
回归、全依赖重建与新模型公开根连接。
不得把本项误作完整 `proof-check` 新 PASS、正式工具采纳或 Week6 发布验收；原有条件性
执行、取指/初态/物理内存及 unsupported 边界不变。
