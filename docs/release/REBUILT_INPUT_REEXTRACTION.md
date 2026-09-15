# 候选包内工具的六根实际重提取

[候选输入包](REBUILT_INPUT_CANDIDATE.md)中的工具与 full-MIR 库已用于实际重提取，
并从包内 Git bundle 恢复和核验工具源码。**本项完成可用性核验，不批准新工具，
不更新正式政策，不重新执行 Lean kernel，也不声明完整 clean-room 或发布通过。**

```sh
python3 scripts/probes/probe_rebuilt_input_reextraction.py
python3 -m unittest discover -s scripts/tests -p 'test_rebuilt_input*.py'
python3 -O -m unittest discover -s scripts/tests -p 'test_rebuilt_input*.py'
```

## 本轮记录

2026-09-12 23:35:00–23:41:58 UTC 完成，外层退出 2，状态
`candidate_payload_six_roots_reextracted_sources_restored_admission_pending`。
[报告](../../artifacts/boundary-check/rebuilt-input-reextraction-bjlcd5ip/report.json)
SHA-256：`e3784350a6232f44e56f49b3668df75ef933b73dbec0020ac4760edfb02ee668`。
入口源码 SHA-256：`9d16bb6510ef64c538c115e835a8f1fac5ccd5070d16b8e851286f58e842de56`。

共 51 个实际阶段：27 个源码恢复/检查/补丁阶段、7 个版本检查、4 个固定锁文件
依赖下载、12 个提取/翻译阶段，以及 1 个原严格模式负测。前 50 个退出 0；最后一个
退出 2，诊断仍为 `Context collapse does not support concrete shared borrows`，
不是把任意执行失败算作负测通过。外层退出 2 表示候选待准入，不是正式门禁 PASS。

使用已实际解包的 `rebuilt-input-candidate-z2k9y4hg/unpacked/payload`，没有另外复制
一套载荷。工具源码从其两个 bundle 独立 clone、固定 commit checkout 并执行
`git fsck --full --strict`，恢复 base/public Charon、base/public/join-only Aeneas
五个变体，应用三份精确补丁。三个 Aeneas 各自再恢复一份 Charon ML；共八个独立
Git 源码树。检查源码文件/权限、补丁字节、提交和已提交的源码链接；无对象硬链接
或 alternates。**恢复源码不等于本轮重新编译工具**；本轮执行的是包内已有执行文件。

## 模型结果

| 模型 | 本轮与包内参考的比较 |
| --- | --- |
| CkbVmProduction | 全文件字节一致 |
| OuterClosedDepsV3 | 仅既有整行 `Source:` checkout 前缀规则；373 处，固定 canonical hash 匹配 |
| FnPtrFullMir | 仅既有 fixture 源码位置规则；20 处，固定 canonical hash 匹配 |
| LocalFields | 全文件字节一致 |
| FactoryScoped | 既有路径规则检查通过；后续独立复核还确认全文件字节一致 |
| MiniComplete | 既有路径规则检查通过；后续独立复核还确认全文件字节一致 |

六份 LLBC 都是本轮 Charon 新生成，六次 Aeneas 都只翻译相应新文件。
原 LLBC 仅用于提取元数据对照：格式、crate、target 和全部选项保持一致，只允许
已核验 sysroot 位置及输出位置变化。**没有证明两个 LLBC AST 一般等价**。
模型原始哈希、LLBC 哈希和每次命令/工作目录/日志哈希均见报告；不改写生成模型。

公开根只在 public/iterator 两组启用原有两个 Aeneas 开关，每组切换时清除旧开关，
不向 fields/factory/mini 泄漏。六组都显式使用包内 46 库的 full-MIR sysroot。
新建 Cargo home、target、Charon cache 和两个 harness；四次 `cargo fetch --locked`
完成后，提取阶段设置 `CARGO_NET_OFFLINE=true`。没有复制旧 Cargo/Charon 缓存。

## 复核和保留边界

生产脚本前后核对候选载荷、完整固定工具安装及相关源码、47 个脚本/配置/政策等
输入、CKB 快照和两个 harness。本轮另行只读复核：

- 重新构造并逐项核对全部 51 个命令、工作目录、公开开关、退出码、时间顺序和日志哈希；
- 重算六份 LLBC/模型哈希和提取元数据，检查上述四份全文件一致及两份既有身份规则；
- 重开八个 Git 源码树，核对文件/权限、提交、补丁及对象独立性；
- 重算包内全部文件、47 个绑定输入、固定 CKB 快照和 harness，无漂移。

只读复核没有再次提取、再次执行 kernel 或重新核对整个私有工具安装闭包；完整
工具闭包的前后检查属于本轮生产脚本。新增 10 项回归测试；连同包校验为 20 项，
全部 `test_rebuilt_*.py` 为 138 项，普通 Python 与 `-O` 均通过。

CKB 源码复用 `/tmp/rebuilt-lower-source-feuenccl/checkout` 固定快照，SHA-256 为
`99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12`，
不是本轮重新 clone 的项目源码。主/下层提取配置、factory 的原固定 Cargo.lock、
Rust nightly 和 OPAM 安装仍为明确核验的包外输入。不能据此宣称仅凭该归档即可在
任意主机独立重建，亦不是全部历史资格日志的分发闭包。

后续 [v2 输入准入及独立安装](REBUILT_INPUT_ADMISSION.md)已明确新工具、标准库和下层
模型身份及资格处置。接下来接入主门禁和下层证明政策，再重跑相应正式门禁。
两处下层 `Option.map` 定义的旧政策差异没有因本次字节匹配而
消失；它们仍须依据既有等价证明单独处置。UI 失败、visitors 约束差异及历史诊断源码
身份限制仍保留，不自动豁免。原四份正式政策、原 `proof-check` 报告和验收定义未改动。
