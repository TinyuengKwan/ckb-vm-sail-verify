# 下层模型重生成来源核验

2026-09-12。已重新核对当前字段/raw 政策、提取源码、批准输入包及三份下层模型。
它们的现有身份有效，但最近的[三根联合提取](REBUILT_EXTRACTION_CHAIN.md)不覆盖这三份输入。
从旧包复制源码后重新编译，不能算作它们已经用新工具重新提取。
随后已完成下述实际重提取：字段模型原始字节一致，工厂与共享闭包模型有真实函数体差异，
仍待审查；不是三份身份检查全部通过。

| 输入 | 现有真实来源 | 重生成所需工具 |
| --- | --- | --- |
| `LocalFields.lean` | CKB 生产 crate 的 `instructions::utils::{rd,rs1,rs2,opcode,funct3,funct7}` 六个根；命名空间 `RawDecodeExtract` | 新 base Charon + 新 base Aeneas |
| `FactoryScoped.lean` | `FactoryRoot.rs` 调用实际 `i::factory`；根 `raw_add_decoder_connection::decode`，命名空间 `RawDecodeFactory` | 新 base Charon + **仅 join-recovery 补丁**的 Aeneas |
| `MiniComplete.lean` | `decoder_shared_closure.rs`，包含真实 `core::option::_`；还有 `-strict-joins` 拒绝检查 | 新 base Charon + 同一仅 join-recovery 版本 |

字段政策 SHA-256：`2fd824db64328972468ddb76fd7cdfb4d0cfbf86e8614ab88ee10169b9b40673`。
raw 政策 SHA-256：`407909ee4584c3d1a45dcbf123fa2019d70b2eaac4f22b962caf3dea37596951`。
原始模型在批准包中的 SHA-256：

- LocalFields：`3657ae25ac3b2c690e27a8e520663d64d7996bf7397eb1f182f905a4183f6868`。
- FactoryScoped：`c5fe992b8979f1cffea74d733f06b7441311aadf2ff224306184e434a2dd3dbf`。
- MiniComplete：`d83df99cd1ec4617c9738e03405acde8158756251ab74dfe689d210ce12aad3d`。

字段原始哈希及 raw 两模型的现有规范化哈希均通过当前政策校验；政策源码清单也未漂移。
最初的来源核验未运行新提取或新增 kernel；后续实际运行见下。

## 本项原定工作与边界

先从同一 Aeneas commit `379890b54b4961dc7729e314c6eefdc09fe50981` 独立构建第三种工具：
只应用现有四文件 [join-recovery 补丁](../../proof/lean/decoder/toolchain/aeneas-join-recovery.patch)，
SHA-256 `5a924e2a6e38696eae8211f6e01b1b181bc85b1c5ce0cbf5fb44766e915f0dd9`。
当前已重建的 base 和 public 两版本不能冒充它；public 还包含函数指针、命名与分支处理补丁。
旧批准 raw 二进制 `0f757f5e…` 继续保留，不自动替换。

然后在同一受验源码候选、全新 Cargo target 中，保持原根、include / opaque、namespace、
检查选项和锁定依赖，实际重提取三个 LLBC 并翻译；差异必须保留并审查，不能覆盖旧模型、
更新金样或直接刷新 raw 政策。完整来源链还需连接九条字段、十五条 raw 定理的精确
类型/定义/依赖审计，以及错误位域、错误 Rust 位移、严格合流和 False 前提等原有负测。

已有入口 `check_raw_add_fields.py` / `check_raw_add.py` 固定原工具和本机位置，
不能通过环境变量伪装新二进制版本来绕过。新候选入口和其验收应独立实现、验证后再审查采纳。

## 新候选入口与首次失败记录

新增独立入口：

```sh
python3 -O scripts/probes/probe_rebuilt_lower_models.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_lower_models.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_lower_models.py
```

复用三根联合提取的明确源码候选（快照 `99127abf…`），从固定 Git bundle 独立克隆
Aeneas 和 Charon ML，只恢复原四文件 join-recovery 补丁，使用已重建的 OPAM 依赖、
新 Cargo home / target 和显式 full-MIR。原 LLBC 只用于核对选项，不供翻译；三个新模型
逐份按现有字段/raw 身份规则比较，不因首份不符而省略后续比较。入口不执行 kernel、
不替换原工具/模型/政策；完成提取仍返回 2，保留待身份审查或待资格/kernel 的状态。

首次运行[报告](../../artifacts/boundary-check/rebuilt-lower-models-6wppjgbl/report.json)
SHA-256 `6727ed8570c07965e2d60240d13ddb46c179801c605ea5a09e6d512a31a93508`。
11 个构建/版本阶段完成，join-only Aeneas 编译成功，但 18:38:12 UTC 在提取前因
候选缺少 `deps/ckb-vm/Cargo.lock` 失败。该锁被 Git 忽略，不在源码快照中。
首轮原脚本保存在 `probe-source.py`，SHA-256
`30bfb333784f55fda6229aad6fdf8a9c45b7b811b00e3dc3ce6e9820c67ee215`；
报告、日志、源码和二进制已独立复核，失败记录未改写，也未声称产出模型。

修正入口显式物化原字段政策锁定的 CKB 锁（`b10b35cb…`），不运行新的依赖解析；
已有不同文件或符号链接必须拒绝，不能覆盖。此文件作为 Git 快照之外的独立输入记录，
提取后再次检查。工厂 harness 同样复制原锁 `d45baf8a…`，不重新生成版本。
第二次运行[报告](../../artifacts/boundary-check/rebuilt-lower-models-wrf1aw3s/report.json)
SHA-256 `b47cad8e0c3eb239ffbf879217efb6335439f7c2e11aad1d4274e68ea9e0dac9`。
独立构建成功，但 `fetch-fields` 退出 101：嵌套副本的 CKB crate 被外层原仓库的 Cargo
workspace 发现。此轮也未产出模型，12 阶段及实际诊断已独立复核；保留脚本 SHA-256
为 `72840d2f486caaf9d1041495d15f99d9d9353f155fb2296303c4bf3c0240a8c0`。

因此新入口先在 `/tmp/rebuilt-lower-source-*` 中从三个独立 clone 恢复**同一源码快照**，
核验上层没有 Cargo manifest，再物化锁。不是同一物理目录，也不是修改生产
`Cargo.toml` 的 workspace 定义。新目录保留并在报告绑定绝对路径，旧候选和失败产物不删。
入口 20 项测试，加联合提取 13、Aeneas 11、full-MIR 10 项，共 54 项普通和 `-O` 通过。

## 实际重提取完成，但两个模型身份不匹配

[第三轮报告](../../artifacts/boundary-check/rebuilt-lower-models-tt2j7xeu/report.json)：
18:44:07–18:48:33 UTC，SHA-256
`5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35`。
26 阶段中 25 项退出 0，严格合流负测按原原因退出 2；外层退出 2，状态为
`lower_models_reextracted_identity_review_required`。新工具版本为 `aeneas 379890b5-dirty`，
二进制 SHA-256 `af9a5ec84ff951fe4a92ffc0c2a49579e6d761e6f863e889eed758802d72483c`，
不替换原批准 raw 二进制。

| 模型 | 实际结果 |
| --- | --- |
| LocalFields | 原始字节与政策一致，SHA-256 `3657ae25ac3b2c690e27a8e520663d64d7996bf7397eb1f182f905a4183f6868` |
| FactoryScoped | 原始 SHA-256 `5a3ac950964416f148ae417e78dfa42b2d3899db5b0f54c241a705b3d4a7068b`；既有规范化哈希不符 |
| MiniComplete | 原始 SHA-256 `6f65774afd345abc9b3e058f9c47db450057984d4e054838986fb65ae863fd4b`；既有规范化哈希不符 |

新 LLBC 哈希依次为 `e305faa73952f471e597ce674a96ab6bf4b87e2e1bf93addac64b6cd9b8a5105`、
`aa93ce7233fecd65372c268704ecf44a0191218f2853bc8ebeb61e167fb29494`、
`a2cf38656b9f45c4d0ea6e3ae401aaa66893c6883f331fee66609d7807d5e265`。
独立 `-O` 审计重验了全部日志、精确提取/翻译命令与 cwd、源码快照及显式锁、
工具源码/补丁/构建产物、安装闭包、三个 LLBC 选项与完整模型，正式来源和生成物不变。

只读完整差异检查将工厂的 195 处、最小模型的 11 处已知 Source 路径搬迁单独列出后，
剩余代码差异各只有 `core.option.Option.map`：新输出多了携带 `(o, b)` 的结果及
`if b then ok o else ok o`。此比较未改写生成文件，也未加入新的身份规范化规则。
**两个 map 的定义都在 `ExportRawAudit.lean` / raw 政策中锁定，不能只修改模型哈希放行。**
随后[显式 sysroot 对照](LOWER_SYSROOT_DIFFERENCE.md)和
[实际 map kernel 等价/原 raw 定理连接](LOWER_MAP_EQUIVALENCE.md)已完成。
其后[原字段/raw 负测及生产工厂运行核验](LOWER_ORIGINAL_NEGATIVES.md)也已完成。
精确审计准入迁移、公开 decoder 完整负测/工具资格与全依赖公开根重建仍待完成。

## 新旧工具 × 新旧 LLBC 的交叉翻译

诊断入口 `python3 -O scripts/probes/probe_lower_translation_matrix.py` 只翻译已有 LLBC，
明确不声称又重提取 Rust，也不构建或批准旧工具。[实际报告](../../artifacts/boundary-check/lower-translation-matrix-wr5nvm89/report.json)
记录 18:54:15–18:56:42 UTC 的 10 阶段（两次版本检查、八次翻译），全部退出 0，
外层仍为 2、`translation_matrix_complete_no_adoption`。SHA-256：
`cd956d4300e19b0b29492dbc84cf9cd015c67d88d05168f4449d9164faaf900c`。

工厂与最小模型各自完整执行以下四格：

| LLBC 输入 | 原批准 join-only Aeneas | 新构建 join-only Aeneas |
| --- | --- | --- |
| 原 LLBC | 完整原模型；匹配原政策 | 与左侧原始字节完全相同 |
| 新 LLBC | 新模型；不匹配原政策 | 与左侧原始字节完全相同 |

四对同输入输出逐字节一致。因此**本次差异随 LLBC 输入改变出现，不随 Aeneas 二进制
切换出现**。这不能进一步区分新 Charon 与 full-MIR 标准库的影响，也不是一般的
翻译器等价证明或 `Option.map` 的 Lean 等价证明。
后续[显式 sysroot 四格对照](LOWER_SYSROOT_DIFFERENCE.md)在固定最小模型上进一步确认：
同一套库下新旧 Charon 输出相同，已安装 std 重现原模型，full-MIR 重现新模型。
它仍不追认旧报告未记录的隐式库身份；函数体的后续独立 kernel 证据见上。
完成后独立 `-O` 复核全部十阶段日志、八次精确 argv/cwd、输入/工具/源码与安装闭包、
八份完整模型和四对比较结果通过；正式生成物和政策保持原身份。

最初交叉预检因旧工具目录含两份历史未跟踪 Rust 测试而拒绝，没有执行翻译；
[失败报告](../../artifacts/boundary-check/lower-translation-matrix-ob3egqp9/report.json)
SHA-256 `63082a31a3f26299162ddc2848d7fd0a4d33b64757db97da880468a3447c084d`，原脚本
SHA-256 `ac5dc3b6b571575ece0172938099a76f1c0b90d6510bb4fe181429cfdc6d766a`，均保留。
随后只读审查并固定 `tests/src/decoder_fn_pointer.rs` 与 `decoder_shared_closure.rs`
的精确集合/哈希，同时要求旧目录全部受跟踪差异恰为原 join 补丁；未删除测试或放宽新
源码构建检查。这两份历史文件没有作为本矩阵输入。新增五项守卫测试，与前述测试共
59 项普通和 `-O` 通过。
