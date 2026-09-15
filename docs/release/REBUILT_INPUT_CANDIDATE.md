# 独立重建工具的待准入输入包

本项将新工具、实际提取输入和已完成的候选资格报告整理成独立包，供后续正式准入。
**没有覆盖原 `public-v1`，没有更新正式政策，没有将候选包伪装成已批准输入。**
原 v1 加载器明确拒绝该候选包格式，这一行为已有回归测试。
后续已有独立的 [v2 范围限定准入政策及安装入口](REBUILT_INPUT_ADMISSION.md)；
它保留本包原始候选状态，主证明门禁尚未切换。

```sh
python3 scripts/rebuilt_input_candidate.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_input_candidate.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_input_candidate.py
```

## 实际生成与解包

2026-09-12 23:15:48–23:18:51 UTC 完成，外层退出 2，状态
`rebuilt_candidate_inputs_packaged_unpacked_admission_pending`。
[报告](../../artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/report.json)
SHA-256：`326ae28c839496192a98e411fb03f1c00b09a9f77ad357b6c88070267b4a25e1`。
入口源码 SHA-256：`8622b6cfc29ca735c7f3f2e2261e0293a60592bfe99c787ec6793a05c26ccbce`。

| 产物 | 身份 |
| --- | --- |
| [归档](../../artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/rebuilt-decoder-candidate.tar.gz) | 448,901,251 字节；SHA-256 `1a81921b12215a87106ac2080c05de3f2bf9d51b9bb14bdb80a90ac8c05c58d5` |
| [包外校验清单](../../artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/catalogue.json) | SHA-256 `b9015281f8a2c4d30aabd0b91eb6993d492b87e15eb83dcf93a8a66df8daa523` |
| 包内 `package.json` | SHA-256 `afa859f41166f9a1ebc412d3096603cc6005c4c679e23399e9a67f75af55799f` |

原始载荷为 92 个文件、1,848,169,195 字节（不含 `package.json`）。归档已实际解包到
全新的 `unpacked/payload`，逐文件核验哈希、大小、权限及无链接属性。
拒绝未知文件、目录穿越、symlink/hardlink 成员及覆盖已有输出。
包外清单是显式哈希绑定的校验依据，不能由包内 manifest 自行更换批准的文件哈希。

已另行执行以下命令，退出 0，结果为 92 项、1,848,169,195 字节：

```sh
python3 scripts/rebuilt_input_candidate.py \
  --verify-payload artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/unpacked/payload \
  --catalogue artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/catalogue.json \
  --catalogue-sha256 b9015281f8a2c4d30aabd0b91eb6993d492b87e15eb83dcf93a8a66df8daa523
```

后续只读复核还重算了每个原始叶子输入、七类资格报告、配置差异及报告前后输入，
全部匹配。工具完整源码/补丁、Rust/OPAM 安装、full-MIR 及原批准包的核验属于打包入口
执行的前后检查；独立解包校验没有重新执行这些工具或 kernel。
10 项入口测试在普通 Python 和 `-O` 下通过。

## 包含内容

| 类别 | 数量及范围 |
| --- | --- |
| 执行文件 | 7：public/base 的 Charon、driver、Aeneas，以及 join-only Aeneas |
| 原始模型与 LLBC | 各 6：主生产、公开 decoder、full-MIR iterator、LocalFields、FactoryScoped、MiniComplete |
| 资格报告 | 7 类 public_clean、borrow、fnptr、charon_ui、charon_diagnostics、guard_equivalence、loop_equivalence，加 1 份 full-MIR 报告 |
| 补充证据报告 | 6：联合/下层提取、map 等价、原负测、新 Sail C++、新 runtime |
| 工具源码历史与补丁 | 2 份既有固定 commit 的完整 Git bundle、3 份精确补丁 |
| Rust harness | 原 `lib.rs` 和依赖锁，各 1 份 |
| 物化 full-MIR | 全部 46 个新库，未保留外部链接 |
| 原批准配置/政策参考 | 5 份，明确放在 `reference/`，不是候选的新批准政策 |
| 候选提取配置 | 1 份，状态 `candidate-rv64-add-public-rebuilt-v2` |

执行文件和模型直接来自已绑定的实际重建/提取报告，不用旧 LLBC 重新翻译以凑身份。
源码 bundle 复用已核验的原固定历史，工具补丁未改变；本打包项只核对 bundle HEAD。
后续[包内工具重提取](REBUILT_INPUT_REEXTRACTION.md)已恢复八个独立源码树并应用补丁，
用包内工具/标准库实际完成六个根的提取与模型身份检查；这是后续独立运行的证据，
不回写为打包入口曾经执行过提取。

候选提取配置与原文件恰有 11 个字段变化：状态、三个工具哈希、公开 LLBC 哈希，
四项包内路径、sysroot 位置占位及待准入状态说明。其余字段逐项保持原值，包括
roots、include/opaque、翻译选项及两个 public 环境开关；没有扩大提取面或
增加 opaque，VERSION2/MOP-off 证明边界未变。原配置全文以参考输入保留。两处下层 `Option.map` 模型变化仍明确存在，
仅附上已完成的等价/负测证据，不把它们当成路径差异更新原 raw 政策。

## 不包含的声明与下一步

这是可分发的候选叶子输入，不是完整发布包或全部历史证据闭包。资格报告中的原路径
不改写，相关全部日志、源码副本和编译缓存没有递归打包；不能凭这些报告 JSON 宣称
可脱离原记录独立重审整个历史执行。Sail、Rust、Lean、Rocq 完整安装及主机动态库仍在包外。

在新目录恢复工具源码、用包内工具和标准库重提取并核验模型已完成，见上述后续报告。
后续 v2 输入政策已明确固定工具、标准库/模型身份和资格处置，独立安装/加载已完成。
尚需将这些身份接入主证明门禁及下层模型政策，并重新执行对应正式检查。
UI 金样/交叉目标、visitors 声明约束差异及历史诊断脚本身份限制均未被隐藏或自动豁免。

原批准的四份证明政策、主/公开源码清单、既有 `proof-check` 报告和 Week5/Week6
验收定义不变。七类发布门槛仍未关闭；本项不是第三方复现、CI 下载、维护者演示或发布。
