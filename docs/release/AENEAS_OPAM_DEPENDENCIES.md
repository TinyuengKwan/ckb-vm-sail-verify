# Aeneas 独立依赖环境重建

2026-09-12。本项准备独立构建 Aeneas 的 OCaml 环境，**不代表已经重建 Aeneas 编译器**。

## 锁来源

从原候选 Aeneas 的 Dune trace 定位到实际使用的本机 switch：
`artifacts/boundary-check/decoder-toolchain-VBwba1/ocaml-switch`。
原 `decoder-toolchain.export` 含全部 116 个包的完整元数据；实际重新查询该 switch，
确认 installed 包集合和版本完全匹配。OCaml 5.2.1 的 compiler invariant 是精确等式。

已将原导出逐字节固化为 [aeneas-switch.export](aeneas-switch.export)，SHA-256：
`bfa3265986b21625b49f8dec3713c078db1c3cd327da64ea9e775a70f6a46237`。
没有重新求解浮动依赖，也没有修改原 switch。

## 独立入口及完成结果

```sh
python3 scripts/probes/probe_aeneas_opam_dependencies.py
```

入口创建全新 OPAM root，从空仓库描述导入完整锁并源码构建，不复制旧安装、
构建缓存或 Dune 缓存。要求源码下载 checksum 校验，复用宿主编译工具，四个构建 job。
使用与此前隔离 OPAM 重建一致的无 OS 沙箱方式，不安装全局工具。

完成后必须核对 116 个实际包、精确 compiler invariant、完整导出元数据和实际私有
`ocamlopt` 路径／版本／哈希，并记录安装文件清单。已知 OPAM 导出仅可能缺少顶层
compiler 清单行，除此之外的差异都会拒绝。十项回归测试普通 Python 与 `-O` 通过。

原运行：[aeneas-opam-qhtaephh](../../artifacts/boundary-check/aeneas-opam-qhtaephh/report.json)，
116 包源码构建和包集合核验均成功，随后因 `opam switch set-invariant` 参数缺少
`--formula=` 而失败。原报告 SHA-256：
`62fdda2673d42c2775ede24910439bcb13f1d41a543e04872d0b1aae8bc9539d`。
当时的入口源码另存为 `probe-source.py`，SHA-256：
`8e24b506d646b8d9882bef087659ebab04760d00d5c3ddb064348d25449cb467`。
入口参数现已修正并增加精确 argv 回归测试；不覆盖原失败记录。

`scripts/probes/finalize_aeneas_opam_dependencies.py` 显式复用上述已完成的全新包构建，
仅修复 compiler invariant 并收尾审计，不重新下载/编译或复制包缓存。
[收尾报告](../../artifacts/boundary-check/aeneas-opam-finalize-mj9dgb4h/report.json)
于 17:20:00–17:20:30 UTC 完成，七阶段全成功，返回 2，状态为
`aeneas_dependencies_rebuilt_metadata_finalized_compiler_pending`。
SHA-256：`64f4b5dfff7dbfe3d08d3a935de0e3942805d46fe277e2738ba654b6bb757b6e`。

实际 compiler invariant 为精确 OCaml 5.2.1；导出仅缺少已知顶层 compiler 清单行，
其他完整元数据与锁一致。11,469 项安装文件在修复前后完全相同，清单身份：
`b322f614e5b446fc7582cc5f86bb61605159b99de569771f8cf791492e43201e`。
实际私有 `ocamlopt.opt` SHA-256：
`0eecb51332c371ea62a344f492a2ed4c36a3935e7f594fe8b2998ea373320b08`。

已以 `python3 -O` 独立复核原失败阶段、保留的原脚本、七个新阶段、全部输入／日志／导出、
116 个包、完整安装清单与 compiler/bootstrap 哈希。后续编译器构建见
[Aeneas 双版本重建](ISOLATED_AENEAS.md)；本页只证明依赖环境已复原和审计。

## 必须保留的依赖边界

原实际构建锁是 `visitors 20250212`，但固定 Charon 源码的 `dune-project` 声明
`visitors >= 20260520`。这是既有环境与声明约束之间的差异，不通过静默升级掩盖。
复原旧环境不能据此宣布满足全部上游依赖资格；后续 Aeneas/Charon OCaml 源码构建、
工具测试与正式采纳必须继续审查这一点。

剩余工作包括固定源码及已采纳补丁的 Aeneas 双版本构建、Charon OCaml 库连接、
新工具上的生产提取与资格/证明链，以及同一候选的完整 Week6 验收。
