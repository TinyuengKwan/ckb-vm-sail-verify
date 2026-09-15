# 新 Charon UI 失败诊断的独立报告

本项将[新 UI 对照](REBUILT_CHARON_UI.md)中的失败诊断审查落为单独的可重算证据。
它不重新执行测试，不刷新金样，不把共同失败改成 PASS，也不自动采纳新工具。

```sh
python3 scripts/probes/probe_rebuilt_charon_diagnostics.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_charon_diagnostics.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_charon_diagnostics.py
```

## 实际结果

[完成报告](../../artifacts/boundary-check/rebuilt-charon-diagnostics-9mde362w/report.json)
SHA-256：`066d19a38522d3cef48d33be73c6c74dbb6660207403ea6f2f50e75dd3ec63f4`。
2026-09-12 22:51:52–22:52:54 UTC，外层退出 2，状态
`rebuilt_diagnostics_classified_tests_still_failed_admission_pending`。
入口源码 SHA-256：`96a1f29a83ca9c67ce62c758e65e33726a5a3a398183d3857fa3e0b30aadf0ad`。

| 24 对共同失败的完整 stderr | 对数 |
| --- | ---: |
| 按既有规范化规则相同 | 12 |
| 仅行顺序不同 | 4 |
| 仅首次失败目标汇总及行顺序不同 | 8 |

规范化限于既有 ANSI SGR、CRLF、panic thread 数字 ID 规则。第三类还要求被汇总的
目标确有缺少标准库的诊断，不能随意删除错误行。新日志的 rustc `error…` 行只含
E0463 缺少 `std` / `core` 及对应中止汇总；另外存在未安装 Miri 的工具警告，不能将
完整 stderr 描述成“仅包含 E0463”。两侧总计 80 次缺少 `std`、2 次缺少 `core`
诊断；这是诊断出现次数，不是 82 个测试。

入口重读全部 435 项 UI fixture/golden、433 项实际执行的两个输出流，复核原分类和
汇总；再重新核验新工具源码/补丁、实际构建二进制、Rust/OPAM 安装及 full-MIR 库。
多目标驱动源码与固定 Charon commit 的 Git blob 完全相同，SHA-256
`4ea2d4194fa72657ac1284ce7b483a5b185ec56267d2b96c1d69ba325d4d6d1a`。
前后工具闭包、日志、源码和政策检查无漂移。

后续独立只读复核未调用分类函数，重算全部 24 对日志哈希、行多重集合、目标汇总及
缺库出现次数，与报告逐项一致；另重算报告绑定的输入哈希。它没有再次运行 UI 或
再次读取完整工具安装闭包，后者属于本入口的前后核验证据。
5 项新守卫测试及原分类器 7 项测试在普通 Python 和 `-O` 下通过。

## 历史脚本身份边界

旧诊断报告绑定的脚本 SHA-256 为
`c841d005c15cbf4a9f2af3a9947595c4c55b41d506a350ae01c4d0ab29684dc5`，
但固定主仓库 commit `872d225dc4e16c449be37d92761b20c6aefe853c` 中已提交的分类脚本
SHA-256 为 `774557fed888a31f730f497d97c449de04584397a8ad85db6010b42cab5e301f`。
本次绑定并使用后者，**不声称历史整份脚本身份相同**，也未建立旧脚本全文对应。

为检查继承的分类行为，入口重读旧报告的全部 26 对日志，逐个核验日志哈希并重新分类，
每项结果与原报告一致：9 对相同、10 对仅行序变化、7 对首次失败目标及行序变化。
这证明当前脚本在这组历史输入上复现原分类，不是一般函数等价或历史源码身份证明。

首轮[失败记录](../../artifacts/boundary-check/rebuilt-charon-diagnostics-2ifcm4pd/report.json)
SHA-256：`45deb9468bba1db74fdfe7fb83674841081c2763e428fd4583c6975f63aa5745`，
止于上述脚本身份预检，尚未进行 UI 审计。已保留该次 `probe-source.py`
（SHA-256 `1df4a896d0be81d4ed78f4fe2fa7015212a5b3f2fa10fa3f35b8ad32791c2ccf`）。
未改写旧报告或将此预检错误解释为编译器语义错误。

## 未关闭的范围

本项提供新的 `charon_diagnostics` 候选资格证据，但未接入正式输入包/政策。
缺失交叉目标、UI 金样不符及完整工具准入仍需明确处置；没有上游全量测试 PASS。
其他借用、fnptr、循环、guard 与公开根证明的完成记录各有范围，不能拼成一般编译器
正确性或 Week6 发布完成。
