# Aeneas 双版本独立源码重建

2026-09-12。入口：

```sh
python3 scripts/probes/probe_isolated_aeneas.py
```

使用[独立重建并完成元数据核验的 116 包 OPAM 环境](AENEAS_OPAM_DEPENDENCIES.md)，
不复制旧 Aeneas/Charon OCaml 编译缓存。每侧从批准输入包的独立 Git bundle 恢复：

- Aeneas commit `379890b54b4961dc7729e314c6eefdc09fe50981`；`base` 无补丁，
  `public` 仅应用原批准的 17 文件补丁，SHA-256
  `956a3b1b895c9ffee8376d7cc8f2440efcedba8592908bac8b58c4a07b7c387d`。
- Charon commit `89ac118194b978d8cf753222c19f313521377aa0` 的 OCaml 库，
  两侧各自独立 clone 到新 Aeneas 目录，`src/charon` 必须指向这一副本。
- 由该私有 switch 的 Dune 3.24.2 / OCaml 5.2.1 构建 `main.exe`，使用 `dev` profile、
  四个 job、新的 `src/_build`。未调用会格式化源码或修改源码 pin 的安装入口。

完整 Aeneas Git 清单包含 824 项；提交中的链接只核对精确链接文本，不遍历文档或技能目标。
拒绝未跟踪源码、链接变更、路径逃逸及批准补丁以外的源码改动。
每侧独立核验 Charon 的 1,225 项源码和 Git 对象独立性。
十一项入口测试在普通 Python 与 `-O` 下通过。

## 模型核验范围

本项复用已验证的现存 LLBC，**不重新提取 Rust，不执行新的 Lean kernel**：

- base 重生成 `CkbVmProduction.lean`，必须匹配正式模型的完整原始字节。
- public 使用原固定选项和环境，重生成公开 decoder 与 iterator 模型；
  只能使用现有 `decoder_model_identity` 的精确 Source 注释位置映射，不能新增代码归一化。

新工具版本直接来自新源码的 Git 标识，不伪装成原发布二进制。
二进制哈希、实际版本、模型和日志均记录；即使模型匹配，整体也返回 2，
保持 `new_tools_approved=false`，等待完整资格及正式采纳。
原 visitors 版本与上游声明之间的差异仍保留，不以“编译成功”代替全部依赖资格。

## 本次执行记录

首轮 `isolated-aeneas-l5kh04gi` 完成环境核验和源码恢复，但 Dune 不接受 `--jobs=4`，
在实际编译前停止。原报告 SHA-256：
`56f6719684063e04d128b7a2a2c6bf8d031837b8e50a676b1d6cbcc49d6ca04b`。
原源码副本 `probe-source.py` SHA-256：
`c56c5a1cb0d944f1200c5325b3c811750ec7aeed044823d742895bf980b03c0d`。
已改用实际 CLI 支持的 `-j 4`，增加精确 argv 测试；旧报告和失败目录保留。

第二轮：[isolated-aeneas-hksgq6ho](../../artifacts/boundary-check/isolated-aeneas-hksgq6ho/report.json)。
17:27:36–17:35:09 UTC 的 20 个阶段全部退出 0，使用新的源码副本和空 Dune build。
报告 SHA-256：`6e9bdc1e7f98691ad0d1953f68bb9f57a1a5ea9b60afd49d5f847cd22d98b1a5`。
外层退出 2，状态为 `base_and_public_aeneas_rebuilt_models_match_qualification_pending`。

- base 版本 `aeneas 379890b5`，二进制 SHA-256
  `98b7f9727b6296a41d2732bdb5a054937869fb1f9f776d6f2de47be17247953d`。
- public 版本 `aeneas 379890b5-dirty`，二进制 SHA-256
  `dfa656486c7edc719c6e3314fa873e3a8e66b6654f4ea27b948d6a93d519db17`。
- 主模型完整原始字节匹配：`9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e`。
- 公开 decoder 完整模型匹配：`b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061`。
- iterator 完整模型匹配：`3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3`。

此次复用原 LLBC 的来源路径，公开两模型的原始哈希与既有规范化身份也相同，未改写生成物。
独立 `-O` 复核已检查全部 20 阶段日志、输入、OPAM 完整安装清单、两侧精确源码及补丁、
真实 Dune 产物与复制二进制、三份完整模型；两侧 `backends/lean` 支持源亦匹配原主政策。
两个新二进制均不同于批准工具，尚未采纳。后续已与新 Charon / full-MIR 在同一候选中
[实际重提取三份模型](REBUILT_EXTRACTION_CHAIN.md)，20 阶段通过且完整模型匹配；
完整资格及 kernel 链仍待完成。该后续执行与本项复译旧 LLBC 分别记录，不拼接成全链证明。

本机宿主工具被复用，无 OS 沙箱，未采纳新编译器；本项不是完整 clean-room、
第三方复现或 Week6 发布通过。
