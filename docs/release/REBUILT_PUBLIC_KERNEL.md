# 新工具候选输出的公开 ADD 源码级 kernel 重建

2026-09-12。入口：

```sh
python3 -O scripts/probes/probe_rebuilt_public_kernel.py
```

本项将新工具实际生成的六份 Rust 模型、候选 Sail Lean 模型接入原公开 ADD 证明链。
复用的是固定报告中已生成的**源码**，不伪称本次重新提取 Rust 或 Sail。
正式主/字段/raw/公开政策均不修改；本项也不是完整 `proof-check`、工具准入或 Week6
clean-room / 发布 PASS。新 Sail C++ 差异及工具资格缺口仍独立保留。

## 来源与候选准入边界

- [新工具联合提取](REBUILT_EXTRACTION_CHAIN.md)提供实际主生产、公开 decoder 和 iterator
  模型；全文件身份沿用原规则，不新设代码规范化规则。
- [下层实际重提取](LOWER_MODEL_REGENERATION.md)提供 LocalFields / FactoryScoped /
  MiniComplete；不从原批准分发包取旧下层模型来冒充新候选。
- [map kernel 等价](LOWER_MAP_EQUIVALENCE.md)及
  [原有负测](LOWER_ORIGINAL_NEGATIVES.md)作为固定候选证据；本次还会从源码重新证明
  四条 map 等价并重建字段/raw 定理。原 raw 政策必须继续拒绝两处 map 定义变化。
  候选 raw 完整审计必须等于已固定的候选审计，并与本次实际 map 定义对应；不允许仅按
  函数名接受任意新定义。
- 候选 Sail 的原始 Lean 全文件必须等于原比较报告中的完整输出，才在新目录应用原兼容
  补丁。适配后的 162 项 `.lean` / `lean-toolchain` 必须与正式政策完整清单一致。
  这不把原来因 C++ 差异而失败的三后端比较改判为成功。
- 旧 Sail 生成报告中的历史主政策/检查器只能通过已审计的精确安装迁移归档核对；
  其余来源不得用任意旧副本替代。重新核对候选生成物、工具安装和源码快照。

## 编译隔离

只复用私有 Lean 4.31.0 安装及其标准库。项目、Aeneas、Sail 支持库、Mathlib 和 decoder
证明不复制旧编译缓存，也不下载 Lake 构建缓存。初始目录必须没有 `.olean`、`.ilean`
或 `.olean.*`；所有 Lean 搜索路径必须位于本次输出树或私有编译器标准库中。

十个 Git 支持依赖从固定 revision 独立 clone，不共享 Git 对象或 alternates。
新 clone 的完整源码/配置必须等于 Git 跟踪清单及原依赖的跟踪内容；旧目录中的被忽略
元数据不复制，另行记录。Git 跟踪的内部相对符号链接保留，绑定目标内容及 Git 身份，
外部目标、悬空链接和越界路径必须拒绝。
aesop 的历史 `lean_packages/std` gitlink 固定为 `c2130e653bc1057f8f21196a9b89987d84fe247b`，
在原目录与新 clone 中都未初始化，也不在当前 Lake 依赖配置中。单独记录该 commit 并要求
目录不存在或为空，不下载、不把缺失内容当作已核验源码；当前真正使用的 batteries 仍独立
clone 并核验。除此之外不允许跳过跟踪路径。

主 Rust 的 Lake 配置仅允许一处 Aeneas 依赖路径搬迁；公开生成模型沿用原门禁的一处
`import CkbVmProduction` 连接。旧 map 归档副本只改既有两行 namespace，供等价证明导入。
全部源文件/配置在编译前后再次核对。

检查目标为原主根、字段/raw、map 等价，以及 full-MIR/general/public 三组公开快照。
公开定理类型、公理、定义及合同必须与原快照完全相同；错误公开结论与额外 False 前提
负测仍需正确拒绝。未满足任一检查则失败，不能宣称公开候选根已完成。

## 当前执行

[第六轮报告](../../artifacts/boundary-check/rebuilt-public-kernel-kahdzauc/report.json)已完整结束：
2026-09-12 21:14:15–21:37:12 UTC，66 阶段，其中 65 项退出 0、错误公开结论负测退出 1。
外层退出 2，状态为 `rebuilt_public_kernel_checked_admission_pending`。
报告 SHA-256：`e94b2e9f59e41fffb2e4d2c525cef42e6bc7a786393e842879e053f89d01bf08`。

| 检查 | 实际结果 |
| --- | --- |
| 从空项目/支持编译缓存构建 | 1,865 个主构建任务完成；初始编译文件为零，结束时共 1,842 个 `.olean`，未复用第五轮缓存 |
| 主根 | 原政策审计通过，137 项精确公理依赖 |
| 下层连接 | 4 条 map 等价、9 条字段及 15 条 raw 定理通过；原 raw 政策仍拒绝两处 map 新身份 |
| full-MIR / general / public | 32 / 24 / 12 条定理、16 / 9 / 20 个定义及 general 的 3 个合同，类型/公理/定义/合同均符合原完整快照 |
| 错误公开结论 | 真正的 `Type mismatch`，退出 1；普通数据 `Error.panic` 不再被误分类 |
| 增加 False 前提 | 变异源码及审计器均退出 0，但精确类型哈希不同，因此拒绝；不把“可编译”当作正确 |
| 结束时复核 | 源码/配置、十个依赖的 revision/内容/独立性、工具/私有 Lean 安装、固定输入及正式生成物均未漂移 |

新增 False 前提后的类型 SHA-256 为
`6f58e59b97eebfcaa6711b672625f738b1c02706570df33ed99b4afbd91ff59d`，不等于原快照。
三组公开审计 JSON SHA-256：

- full-MIR：`ef551fab9189f990c88c07a653c8b9fe3ce0dd2a291317655dcf638dcda4e976`；
- general：`2a229bcd5d2e545586e89bab89cfc9fc2bc56465ad2afa89f2bbdf5eb692ac71`；
- public：`1db018082ad8186af62edbff5853753dd2d80013881abc063af0d201d50ad90b`。

此项关闭新候选输出接回原公开 ADD kernel 链的检查，不是完整 `proof-check` 新 PASS、
工具准入或 Week6 发布。25 项本入口测试普通 Python / `-O` 通过；加上新循环入口后，
相关 rebuilt / lower 测试合计 128 项通过。

完成后另以 `-O` 独立核对全部 66 个阶段的精确命令/cwd/LEAN_PATH、退出码与日志哈希，
完整源码/配置/模型/证明清单、十个依赖身份、实际候选生成来源、工具与私有 Lean 安装、
正式生成物，以及唯一 False 变异及其类型拒绝；全部通过。
随后实际重新执行主根、map、字段、raw、full-MIR、general、public 七个 Lean 审计器，
输出均与固定报告 JSON 一致，原政策/快照检查再次通过，独立复核退出 0。
这是本机完成后复核，不是独立第三方执行或又一次全依赖源码重建。

在第四轮真实构建仍运行时，另以 `-O` 独立复核前 23 个准备阶段日志、全部输入哈希、十个
依赖的 revision / 跟踪内容 / 无共享对象、干净源码配置、六份实际 Rust 模型的复制或
限定连接、旧 map 归档改名、候选 Sail 适配清单、私有 Lean 身份与搜索路径边界，退出 0。
这份复核只确认构建准备，不把正在执行的 `clean-main-build` 记成完成。

## 保留的失败

前三次未进入 Lean 模型编译；第四、五次在诊断分类时失败。报告和运行时脚本原样保留。

1. [首轮](../../artifacts/boundary-check/rebuilt-public-kernel-57ornhcm/report.json)在
   `proofwidgets` 来源比较失败：旧目录多出被 Git 忽略的
   `widget/package-lock.json.hash`，新 clone 正确地没有它。修正为比较完整跟踪源码，
   并单独记录旧目录未复制的非跟踪元数据，不复制旧缓存来凑齐清单。
   报告 SHA-256：`48ad21b7194beb4aa5e066e975f70a32254b07ee671fe36887a26a2bac525a86`；
   原 `probe-source.py`：`96fcd161c438d5bee34aecd2e0210b1acd2c0e12260c9becbaf108810bf68992`。
2. [第二轮](../../artifacts/boundary-check/rebuilt-public-kernel-msce2mx7/report.json)的来源守卫
   拒绝了 Mathlib Git 跟踪的内部脚本符号链接。修正后仅允许解析到依赖目录内部现存文件
   的链接，Git revision/干净状态绑定链接本身，内容清单绑定其目标；越界及悬空链接仍拒绝。
   报告 SHA-256：`33ee40856ec3ba2bfa096ae021a8c6d671be58177c1543e57450dc0891858712`；
   原 `probe-source.py`：`0a8e0690b99c20936bb88ab29456241628c8510e6678dd7c4fadca454c3209a1`。
3. [第三轮](../../artifacts/boundary-check/rebuilt-public-kernel-34gi5152/report.json)的来源守卫
   拒绝了 aesop 历史未初始化 gitlink。核对其固定 commit、原目录为空和当前 Lake 配置后，
   增加上述单独记录和空目录守卫，没有初始化或虚构该依赖。
   报告 SHA-256：`0d5d0d8086163c9c9ad201e3341c4abb8f3156441455d86a542e2a71008c6a71`；
   原 `probe-source.py`：`bd4abd1f185e86e9fc7f21984e9a004d46b93404dbbcb367edc014aecf5f1fa7`。
4. [第四轮](../../artifacts/boundary-check/rebuilt-public-kernel-tnice9wk/report.json)实际主构建
   成功，但复用的大小写不敏感 `panic` 搜索误命中 `Built Aeneas.Std.Core.Panic`。
   新的成功阶段检查沿用原主门禁的内部错误签名，并识别实际错误诊断行；非零/信号退出、
   真实 panic、错误诊断和 `sorryAx` 仍拒绝。新回归覆盖正常模块名与这些失败情形。
   报告 SHA-256：`f4d645e339ef7ede20b4163d992d52d90f16d794cec00480c6bcf6db6594e778`；
   原 `probe-source.py`：`b2e7863e911e23c87a9d34becea02e313bac82f010d7eb5f300f533821b1f321`。
   另以 `-O` 核对原始完整日志、实际退出码和 1,865 项完成标记，新诊断检查接受该日志；
   再以原公开门禁 46 个退出 0 的阶段日志复验，均通过，日志未改写。
5. [第五轮](../../artifacts/boundary-check/rebuilt-public-kernel-ktp49cde/report.json)实际完成
   1,865 项主构建、137 项主根公理审计、4 条 map / 9 条字段 / 15 条 raw 定理审计及
   三组公开审计（68 条定理、45 个定义、3 个合同），全部符合固定快照。
   错误公开结论实际以 `Type mismatch` 退出 1，但检查器误命中其中的 `Error.panic`。
   报告 SHA-256：`9100d1463cfccdd107647abcaf74b336c01f7db6dfd676752625a94f7279342d`；
   原 `probe-source.py`：`a5d6cd0d8a9a2c6ed8ebd683c8e714093b98b53498f3f6cdc3d32870b5596fc4`。
   新负例检查要求精确退出 1 及真正的预期错误诊断行，继续拒绝导入/资源/内部错误，
   新增测试覆盖构造子数据、意外退出、仅在普通文本出现的错误名和各类基础设施失败。
   修改后以全部 64 个原阶段日志复验诊断分类通过，不改写原失败报告。
   另行核对第五轮构建后的完整源码/配置、模型/证明清单、十个依赖的 revision / 跟踪内容 /
   无共享对象、正式生成物及所有固定输入，均未漂移；这不替代尚未执行的 False 负测。
   最新相关测试共 122 项（85 项 rebuilt、37 项 lower），普通 Python / `-O` 均通过。
