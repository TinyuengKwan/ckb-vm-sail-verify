# 新 full-MIR sysroot 的真实重提取核验

2026-09-12，承接 [46 个新库的独立重建](ISOLATED_FULL_MIR.md)。
公开 decoder 和函数指针迭代器的 Rust → LLBC → Lean 两条链已实际完成，
输出模型匹配既有批准模型；**没有据此自动采纳新库，也没有在本入口重跑 kernel**。

## 可执行入口

```sh
python3 scripts/probes/probe_full_mir_reextraction.py
python3 -m unittest discover -s scripts/tests -p test_full_mir_reextraction.py
python3 -O -m unittest discover -s scripts/tests -p test_full_mir_reextraction.py
```

入口绑定 full-MIR 构建报告 SHA-256
`13d82971a424442ea3fc4fbd4deda0672cb1725c0cda9e32817465830a618516`，
重新核验 46 个新库及独立 Rust 安装文件，不通过放宽原输入包校验器来替换 sysroot。
复用正式输入包中已批准的 Charon、Charon-driver 和 Aeneas；这些翻译器尚未在本项源码重建。

在独立主仓库与 CKB Git clone 中应用原已采纳的 runtime-container 补丁，
核对源码/字节清单，并建立原固定 Rust root 与 Cargo.lock 的相对路径 harness。
新 `CARGO_HOME` 和 target 起初为空；先按锁在线 fetch 到新缓存，实际提取仍保留
原 `--offline`。不是从旧 Cargo 缓存或旧 target 重放。

提取器的 include、opaque、start-from、目标信息和其他选项均保持原样；
对照归档 LLBC 元数据时只映射经实际文件哈希核验的新 sysroot 位置和输出文件位置。
该元数据检查不声称两个 LLBC AST 相等。最终 Lean 输出另由原严格模型身份检查器核验。

## 实测与独立复核

16:05:07–16:06:45 UTC，11 个阶段全部退出 0。
[报告](../../artifacts/boundary-check/full-mir-reextraction-fnvlb9v2/report.json) SHA-256：
`a170b3c45ce291c07f8feb8e03c56a5c06b68f09d08634932da80df06f7a9cfe`。
整体退出 2，状态 `new_sysroot_public_and_iterator_models_match_admission_pending`。

| 模型 | 经既有注释路径映射后的批准 SHA-256 | 映射行数 |
| --- | --- | --- |
| `OuterClosedDepsV3.lean` | `b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061` | 373 |
| `FnPtrFullMir.lean` | `3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3` | 20 |

这两种映射均是之前已经审查的精确 `Source:` 注释行位置映射，本项未修改检查器。
源文件名、行列范围及所有 Lean 代码字节保持在比较中；原始生成物不被改写。
公开模型原始 SHA-256：`0ec0be5a5b1b1cf15a811d14704e12dfd0f4913cfcc3d6c2cd4f7d563b86036d`；
迭代器原始 SHA-256：`c5847f862c1edadc74d8d2384cdb2699e3fce5f9cb40c474d0e8c151ee9235b1`。

结束后在 `python3 -O` 中独立复验所有阶段日志、输入哈希、实际新库、固定翻译器、
Rust 安装清单、harness、两个 clone 的源码、LLBC 选项和原始/映射后模型身份，全部通过。
正式输入包、原 CKB 基线和两份证明政策未改变。10 项新增回归测试普通及 `-O` 通过。

## 尚未关闭

新库对本项目这两条提取链的模型一致性已有实际证据，但没有证明全部标准库语义、
所有 Charon/Aeneas 用例或任意工具组合正确；也没有执行新 sysroot 下的完整资格回归和公开 ADD kernel 门禁。
后续需明确正式工具/输入采纳与生成物清理的迁移基线，在同一候选上重新运行完整门禁。
Aeneas/Charon 源码重建、完整环境/来源一致性、第三方及发布门槛仍待完成。
