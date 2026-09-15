# v2 Rust 提取输入的范围限定准入

**已新增 v2 输入准入政策并完成独立安装；主证明门禁迁移仍待完成。**
本项不是又一次候选打包：仓库中的
[准入政策](../../proof/lean/decoder/rebuilt-input-policy.json)明确接受固定的七个工具执行文件、
46 个 full-MIR 库及六组提取输入，用于现有条件性 RV64 ADD 范围。
此输入安装本身不构成新主门禁 PASS。后续已[接入 v2 公开及下层政策](REBUILT_GATE_MIGRATION.md)，
完整主门禁于 2026-09-13 启动、仍在运行；原 v1 政策和报告保留为历史基线。

## 政策与证据

配置名 `rv64-add-rebuilt-inputs-v2`，状态
`approved-inputs-main-gate-migration-pending`。
准入政策 SHA-256：`74e7a88b1413f09df12126c0020f2bb9b261043d80bc34d74b03f9bbc875cd8f`。
仓库内[独立清单](../../proof/lean/decoder/rebuilt-input-catalogue.json)与原候选清单字节一致，
SHA-256：`b9015281f8a2c4d30aabd0b91eb6993d492b87e15eb83dcf93a8a66df8daa523`。

依据是已完成的[六根实际重提取](REBUILT_INPUT_REEXTRACTION.md)、
[源码级 kernel 重建](REBUILT_PUBLIC_KERNEL.md)、下层 map 等价和原负测，以及七类
固定资格报告。准入前重新打开打包/重提取报告，核对原固定哈希、51 个阶段结果、
五个工具变体的源码清单、两个下层模型身份和包内资格/等价/负测报告。
这不重新执行这些历史测试，也不将有限回归升级为一般编译器正确性证明。

CKB 基线仍是 `ckb-vm-1ffba3977da9-runtime-container-v1`，不是未经补丁的原始 commit。
VERSION2、IMC+B、MOP-off、fresh decoder 及 `OuterAdd.cold_public_add_step` 的
显式取指、内存和状态准备合同不变；没有关闭物理内存、平台复位、完整 VM 或 MOP-on。

政策明确保留：

- UI 共 435 项，2 项忽略；433 项双侧退出码相同，423 项选定输出相同、10 项不同。
  候选为 379 golden-pass、28 mismatch、24 command-failed、1 missing-golden、1 unchecked。
  不刷新金样，不声称上游全量 PASS。
- 24 对失败诊断分为 12 完全一致、4 仅行序不同、8 首个失败目标及行序不同；仍是失败。
- visitors `20250212` 低于上游声明的 `>=20260520`，**约束未满足**。接受固定产物的
  限定回归证据不是宣称声明约束已满足，也不批准任意版本替换。
- 历史诊断分类脚本的完整源码身份未建立，只保留固定历史输入的行为复验。
- FactoryScoped / MiniComplete 两处 `Option.map` 定义变化以显式等价和负测证据接受为
  新输入身份，不能伪装为源码路径规范化；原 raw 证明政策尚未切换。

## 实际安装与加载

以下两条命令已实际执行，均退出 0：

```sh
python3 scripts/decoder_rebuilt_inputs.py \
  --install artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/rebuilt-decoder-candidate.tar.gz \
  --destination artifacts/decoder-inputs/rebuilt-v2
python3 scripts/decoder_rebuilt_inputs.py --verify artifacts/decoder-inputs/rebuilt-v2
```

安装于 2026-09-12 23:56:06 UTC 完成。
[安装报告](../../artifacts/decoder-inputs/rebuilt-v2/install-report.json)
SHA-256：`2fb63ac03b39a188bc2a4e162df0f1e5f4066910c27a949ea02210137a762df3`。
入口源码 SHA-256：`b481513fb706be0ef62d93a527c17ffb351dcd034c00ab31a9c1e598bc8251df`。

安装实际解包 92 个叶子文件、1,848,169,195 字节（另有 manifest），并完成 27 个
Git clone / checkout / fsck / patch 步骤，恢复八个独立源码树。
每个步骤记录参数、工作目录、退出码及 **stdout** 哈希；这不是完整 stderr 归档。
后续只读复核按原重提取报告重开所有源码，核对清单和补丁，并核对全部 27 个
安装命令和 stdout 记录，再调用新加载器重验整个输入。

加载器以仓库政策和固定清单为准，而不是安装回执：

- 校验归档、原 manifest、全文件清单、哈希、大小和权限；不接受额外文件、缺项、
  链接替换、目录穿越或覆盖已有安装目录。
- 核对八个源码树的固定提交、逐文件清单、补丁及 Git 对象独立性；禁止暂存区和
  未跟踪源码变化。即使 `assume-unchanged` 使 Git diff 不显示变化，文件哈希仍会拒绝。
- 不执行旧工具回退，不接收 v1 格式作为 v2，也不读安装回执作为加载依据。
- 保留包内原候选 manifest 和报告的字节及历史状态。`scoped_inputs_admitted=true`
  来自独立准入政策，不是把旧报告改成已准入。

新增 15 项测试，相关 `test_decoder*.py` 共 89 项，普通 Python 和 `-O` 下全部通过。
原 v1 输入仍在，原四份证明政策、主/公开源码清单、主证明报告及原始验收计划均未改动。

## 尚需完成

后续已迁移正式门禁的输入选择、公共提取/clean-build/验收器及下层模型身份检查，
精确定理、合同和公理清单及负测保留；完整新门禁仍在运行，等待真实结果及复核。
不能只把旧报告路径换成新目录。
Sail 工具准入、全环境最终 clean-room 和七类发布证据也未因此关闭。

安装和加载只需要归档及仓库中的政策/清单，不读取清单 `provenance` 中的历史本机路径。
但执行编译器仍需要包外 Rust/OPAM 等固定环境，复核完整历史资格仍需要未全部包含在
归档中的原始日志和来源。这不是自包含工具环境、完整历史证据闭包或第三方复现记录。
