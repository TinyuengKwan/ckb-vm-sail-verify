# 新 Charon / Aeneas / full-MIR 的联合生产提取

2026-09-12。已经在同一个源码候选中，使用独立重建的翻译器和标准库，实际重提取并
翻译主生产路径、公开 decoder 和 iterator。**三份完整 Lean 模型匹配基线；尚未采纳
新工具，未在本项执行 kernel 或完整工具资格链，Week6 未关闭。**

## 可重复入口

```sh
python3 scripts/probes/probe_rebuilt_extraction_chain.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_extraction_chain.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_extraction_chain.py
```

入口只接受新输出目录。默认在 `artifacts/boundary-check/rebuilt-extraction-chain-*`
保存报告、日志、完整源码快照和载荷、独立 checkout、LLBC 及原始 Lean 文件。
不调用会覆盖正式生成物的生产入口，不改政策；失败保留生成物及已完成阶段。
匹配成功仍退出 2、`rebuilt_tools_three_models_match_qualification_pending`，不是发布绿灯。

## 输入和边界

- 工具来自已完成的 [Charon 双版本重建](ISOLATED_CHARON.md) 和
  [Aeneas 双版本重建](ISOLATED_AENEAS.md)。主生产模型使用 base；公开 decoder / iterator
  使用原批准补丁对应的 public 构建。逐项重验固定报告、日志、完整源码/补丁、构建产物与
  复制二进制、两侧 Charon OCaml 库和 Lean 支持源，工具版本如实保留新源码标识。
- 使用[独立安装的 Rust](ISOLATED_RUST_LEAN.md)、[独立 OPAM 依赖](AENEAS_OPAM_DEPENDENCIES.md)
  和[新 full-MIR sysroot](ISOLATED_FULL_MIR.md)，重验安装清单及全部 46 个库。
  本入口复用这些已经独立构建的产物，不声称又在本目录重编了工具。
- full-MIR 构建报告绑定旧 `c8315684…` 政策。入口先完整检查
  [精确安装迁移](SAIL_INSTALL_MIGRATION.md)，只允许它到 `9308acea…` 的限定迁移，
  从归档核对原政策；其余旧输入必须仍匹配当前字节。不能用历史报告豁免任意源码漂移。
- 从主仓库及两个子模块分别 `clone --no-hardlinks`，再恢复精确 HEAD＋dirty overlay；
  无 Git alternates / 对象硬链接。CKB 源码仍为原 upstream＋runtime-container 补丁，
  不把 overlay 归到原裸 commit，Sail 源码不作新修改。
- 使用全新 Cargo home / target，先按锁下载，实际提取时设置 `CARGO_NET_OFFLINE=true`。
  清除旧工具、Rust wrapper 和 Miri 环境；显式验证私有 Rust 路径和版本。
- 每个提取调用都显式指定新 sysroot。主模型从旧报告的自动 sysroot 选择（`null`）
  改为本次已验字节的显式目录；**这不只是旧库目录搬迁，也不批准新库**。
  比较器只豁免 sysroot 和输出路径字段，所有其他提取选项、根、include / opaque、
  Charon 格式及目标信息必须不变。原始 LLBC 不改写，不声称 AST 等价。
- Aeneas 只翻译本轮实际提取的新 LLBC；旧 LLBC 仅用于提取选项核验。
  主模型要求原始字节相同；公开两模型只允许既有 Source 注释位置映射，不新增归一化。

## 实跑结果

[报告](../../artifacts/boundary-check/rebuilt-extraction-chain-18z20fdd/report.json)：
18:00:51–18:05:33 UTC，20 个阶段全部退出 0，外层按未采纳边界退出 2。
报告 SHA-256：`db0ddb324274e9ab1fa69650eed19ea661ef5b4f68face18aa72113c96414c9e`。
源码快照身份：`99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12`。
这是运行时的明确候选身份；之后的文档更新不冒充该快照内已有内容。

| 模型 | 实际比较 |
| --- | --- |
| `CkbVmProduction.lean` | 原始字节相同；SHA-256 `9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e` |
| `OuterClosedDepsV3.lean` | 原始 SHA-256 `e76ce92a9a6fdda32fec250714139da474c8ee9fb93d0427a65efdef532347c7`；只映射 373 处来源前缀后匹配 `b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061` |
| `FnPtrFullMir.lean` | 原始 SHA-256 `c5847f862c1edadc74d8d2384cdb2699e3fce5f9cb40c474d0e8c151ee9235b1`；只映射 20 处来源位置后匹配 `3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3` |

新 LLBC SHA-256 分别为：

- main：`7a2001c11a30c227b010f0f3e4e76b2db227f5e895cbdd36dd9233a0a9b02dd9`。
- public：`539a85faef4c4b85509c8bb300763341aef8858988a16c714182d05c56f32347`。
- iterator：`a052ec7e21d68d6a618680d2df6bed7827d4f55096293563fe55de9df0cc308a`。

完成后独立用 Python `-O` 重新核对全部 20 阶段日志、提取/翻译精确 argv 与工作目录、
工具/标准库及安装清单、完整源码载荷和独立候选、全部 LLBC 选项及三份完整模型。
核对时原仓库和候选均与记录快照一致；正式生成物和政策保持原字节。
13 项新测试及相关 Charon 13、Aeneas 11、full-MIR 10 项，共 47 项普通及 `-O` 通过。

## 还需要什么

本项关闭了“新组件各自成功，但从未一起实际提取生产输入”的缺口，不是全链验收。
后续[435 项 Charon UI 对照](REBUILT_CHARON_UI.md)已实跑并保留其失败；其余已声明的
翻译器资格回归以及本轮新模型与主/公开 kernel 连接仍待完成。
[字段/工厂等下层模型](LOWER_MODEL_REGENERATION.md)随后已用第三种仅含 join-recovery
补丁的新 Aeneas 实际重提取。字段原始字节相同，另外两份的 `Option.map` 函数体变化，
既有身份检查不符；这不是只剩来源注释搬迁，也未完成新模型准入。
visitors 锁定版本与上游声明约束差异继续显式保留。
新 Sail 的 C++ 输出差异、候选 runtime 构建及全链 proof-check、正式工具身份采纳、
工作树审计与七类完整发布证据仍待完成。本项没有 OS 沙箱、第三方或新增形式证明覆盖。
