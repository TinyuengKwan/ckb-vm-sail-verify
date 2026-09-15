# 新 Charon 的全量 UI 对照（非全量通过）

2026-09-12。已使用独立重建的 base/public Charon，在新测试目录重跑原资格证据中的
435 个 UI 用例。不更新金样、不改 Charon 实现，不把两侧共同失败计为通过。

```sh
python3 scripts/probes/probe_rebuilt_charon_ui.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_charon_ui.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_charon_ui.py
```

## 实测记录

[外层报告](../../artifacts/boundary-check/rebuilt-charon-ui-jtet5h5k/report.json)：
18:14:39–18:16:58 UTC，四个编排阶段退出 0，外层退出 2、资格待完成。
SHA-256：`325e6f340bd365dcea0992309d38a6635b264a198ce70afd8999c9cd8b563e00`。
[435 项原始子报告](../../artifacts/boundary-check/cleanup-regression-yq4zi5ka/report.json)
SHA-256：`31d604fa0cb7154c16bfb5f746f19ac3e60d4a4b106903a853f873630c0adc76`。

| 结果 | 新 base | 新 public |
| --- | ---: | ---: |
| 精确金样通过 | 386 | 379 |
| 金样不符 | 21 | 28 |
| 命令失败 | 24 | 24 |
| 无金样 | 1 | 1 |
| 按用例指令不检查输出 | 1 | 1 |
| 忽略 | 2 | 2 |

433 个实际执行用例的两侧退出码全部相同；423 项选定输出相同、10 项不同，
无超时或缺失执行。正常用例比较 stdout，known-failure/known-panic 比较 stderr；
两个流的完整日志都保留并核对哈希，不能把“选定输出一致”扩大为全部诊断一致。

原资格报告为 422 项输出一致、11 项不同；现在 `slice_index_range` 变为两侧一致。
剩余 10 项均属于原差异集合，无新增差异用例。分别为 `mem-discriminant-from-derive`、
`closures`、`issue-1051-missing-loop-jump`、`guarded-owned-error`、
`issue-120-bare-discriminant-read`、`issue-70-override-provided-method.3`、
`issue-708-from-str-mismatched-generics`、`invalid-reconstruct-assert`、`traits`、
`vec-reconstruct-move-values`。这不是这些变换的通用语义证明。

相较旧记录，两侧各有 28 项 golden-mismatch 和两项 command-failed 变为 golden-pass，
没有其他用例状态变化。**不能把改善全部归因于新二进制**：本次标准库/安装环境也变化了，
下述输入边界是显式记录的一部分。

## 环境和来源

入口先重新校验[联合提取所用组件](REBUILT_EXTRACTION_CHAIN.md)：完整工具源码/补丁、
构建产物、Rust/OPAM 安装清单及 full-MIR 库。两个工具均复制至本轮新目录，
实际子报告的二进制哈希必须与重建报告一致。

测试源码从批准 Git bundle 独立恢复至固定 Charon commit，应用原已批准的 cleanup-suffix
补丁；三个额外 fixture/golden 文件从原实验读取，并按固定旧资格报告逐字校验。
完整测试文件清单和金样前后保持不变。
继续调用未修改的 `probe_charon_cleanup_regressions.py`，不更改上游 UI 包装器或测试选项。

使用私有 nightly-2026-08-18，Cargo 离线，`CHARON_CACHE_DIR` 指向本轮新目录。
`CHARON_MIRI_SYSROOTS` 为已独立构建的 native full-MIR sysroot；只对其具备的目标生效，
用例自己的显式 sysroot / 多目标要求不被改写。没有安装缺失的交叉目标或 Miri，
没有复用全局 Charon cache，也没有声称全工具环境或全部跨目标已准备齐全。

## 失败诊断与复核

24 项命令失败均出现跨目标库缺失的 E0463。完整错误行检查只发现缺失 `std` 或 `core`，
以及对应的中止汇总，不将 `core` 缺失错误误写成全部缺失 `std`。
在原已审查诊断分类函数下，两侧完整 stderr 为：12 对完全相同，4 对仅行顺序变化，
8 对仅最先失败目标汇总及行顺序变化。它们仍是失败，不改为通过；原分类 CLI 仍固定旧报告，
本轮只读复核使用其分类函数，并未改写旧资格记录。

另以 Python `-O` 独立重读所有 fixture/golden、两个输出流、选定输出及汇总；
重新核对外层日志、输入前后清单、实际工具来源和完整安装文件，结果一致。
10 项新守卫测试和原诊断分类 7 项测试在普通及 `-O` 下通过。

后续[单独的诊断资格报告](REBUILT_CHARON_DIAGNOSTICS.md)已完成，保存 24 对分类及原始
日志关联，并披露历史脚本哈希与当前 Git 版本不同：当前脚本已逐项重放旧 26 对分类，
但未证明历史整份脚本身份相同。

本项只是新工具下的一类资格证据。后续[借用](REBUILT_BORROW_QUALIFICATION.md)、
[函数指针](REBUILT_FNPTR_QUALIFICATION.md)、[循环](REBUILT_LOOP_QUALIFICATION.md)、
[守卫](REBUILT_GUARD_QUALIFICATION.md)及[公开根 kernel 链](REBUILT_PUBLIC_KERNEL.md)已
分别完成限定范围验证。金样不符和缺失目标继续披露，不声称全上游测试、一般编译器正确性、
正式工具采纳或 Week6 发布完成。
