# audit-release readiness（正式主工具已验收，发布未完成）

2026-09-12 已实现可执行的证据聚合入口；2026-09-14 扩展为 v8，但
**完整发布验收仍未完成，Week6 未关闭**。检查器重新验收已有 runtime、Lean、
Rocq、完整 Rust 默认测试、mismatch、维护者演示及公开结论；并已为
clean-room、CI 下载、发布包和签名第三方记录接入 fail-closed 验收器。
当前外部报告、发布版本/profile 批准和受信签名者仍缺失，不因“有了验收器”变成通过。
当前版本已有严格的 release 成功路径，但只有十二个槽全部由真实验收器确认，且完成事实
齐全时才可退出 0；缺少任一外部记录、信任根或明确批准均保持非零，不能作为允许发布的
CI 绿灯。

**后续来源修正：** [Week6 每族至少 10 案例](WEEK6_RUNTIME_FLOOR.md)现已实测满足
（33 项，13/10/10；旧 BEQ 9 项不满足）。主政策只更新 corpus 来源，现为 `b5bdc401…`。
下文 v10 是历史记录，当前入口会因旧 `main_policy` pin 拒绝它；旧 Lean/Rocq 证据不能
归入这个新政策。[本轮正式生成和 kernel/Rocq 独立验收](FORMAL_FINAL_EXECUTION.md)已于
22:21:00 UTC 完成；[当前负测/演示及新聚合清单](FINAL_SUPPORT_REFRESH.md)于 22:35 UTC
实际完成六项验收，整体仍 `incomplete`、退出 2。
[本轮 46,651 项正式差异说明](FORMAL_DELTA_REVIEW.md)已独立复验，并已
[接入工作树部分验收器及新清单](WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)：
23:26:44 UTC 完成 314 次回归及真实聚合，六项接受、工作树部分未完成、五项缺失，退出 2。
后续[同轮最终执行连接](WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)于 23:42:59 UTC
完成 370 次回归与实际聚合，严格对应 Lean/Rocq 已验收引用；仅移除执行连接这一项待办。
后续增量、最终范围及六类发布义务未关闭，既有聚合报告不回写。
20:15:54 UTC [新 native 专用聚合](../../artifacts/boundary-check/week6-family-floor-cZSVQA4D/native-audit/report.json)
已完成：runtime/Rust 两项被接受，其他十项明确缺失，整体退出 2、`incomplete`。

**后续实现更新：** [工作树源码部分验收器](WORKTREE_SOURCE_VALIDATOR.md)已接入；
有报告时不再一律返回 `unimplemented`，而是实际校验完整源码及差异审查记录。
通过也仅为 `incomplete`，不关闭整个工作树条款；“其余五类无完整验收器”
是该历史实现阶段的状态，不是当前 v8 入口的结论。
真实候选报告尚缺，v10 仍保留六项 `null`。此次改变聚合器来源，下面 v10 执行记录
属于修改前身份，不代表当前入口已重新完整实跑或旧来源快照仍相同。

**公开结论验收更新：** [全量公开结论复核](PUBLIC_CLAIMS_FINAL.md)新增生产检查器，
以当前完整源码清单枚举全部项目 Markdown，固定保证性段落摘要、文档/结论类别和本地链接，
并重新验收八类当前证据。提供合格报告后 `public_claims` 可成为
`verified_existing_evidence`；这不会关闭 worktree、clean-room、CI、release package
或第三方条款，也不会把 Codex 审查冒充独立第三方。

2026-09-13 06:34 UTC 历史状态：[正式主工具迁移](FORMAL_MAIN_INTEGRATION.md)已切换到
`rebuilt-main-v1`，主政策为 `7ced9f42…`，完整正式执行于 06:26 UTC 退出 0，
06:29 UTC 独立验收通过（28/287/48/68）。
release/Rocq 检查器源码也已更新；**v8 是历史清单，当前入口应拒绝它的过期 pin**。
当前 [v10 清单](local-readiness-20260913-v10.json)接入独立验收后的完整 Lean 归档及
同来源的五项配套证据；[v9 清单](local-readiness-20260913-v9.json)保留当时 Lean 缺项。
完整本地组件不等于 Week6 PASS。不得只替换 v8 哈希并沿用其六份旧证据，
也不得把主门禁的阶段性成功计为完整通过。

06:30:05–06:34:14 UTC 的 [v10 实际聚合](../../artifacts/release-audit/run-37dt_nkr/report.json)
退出 2，`status=incomplete`：runtime、Lean、Rocq NO-GO、Rust tests、mismatches 和
maintainer demo 六项全部为 `verified_existing_evidence`；
`clean_room`、`worktree_audit`、`ci_download`、`release_package`、`third_party`、
`public_claims` 六项仍为 `missing`。没有 release 成功路径。
报告 SHA-256：`42b69c79233763a09c6cc3636da4ae11e7d859e60ff56082e6dc60559ede4fe3`；
清单 SHA-256：`819d730def58d9b2618cae34e91d0be38833ca4f4a1d1727c47ffef384f0743f`。
结束后在独立 Python `-O` 进程核对精确六项通过/六项缺失集合、清单哈希及
`inputs_before == inputs_after == 当时受审源码快照`，均通过。
该快照是检查器明列的证明/政策/来源范围，不是文档修改后的整个工作树审计。
本次完整 Lean 运行期间的 [LXD 安装事件](LXD_WRAPPER_SIDE_EFFECT.md)仍明确保留，
不以代码/工具身份检查替代宿主环境审计或 clean-room。

05:10:26–05:10:27 UTC 已用当前 `python -O` 入口实际提交原 v8 清单，退出 1，
精确拒绝原因 `stale pin: main_policy`；未执行或重写任何组件证据。
[拒绝报告](../../artifacts/release-audit/run-bi9l4gvi/report.json) SHA-256：
`6bdef85604f756c401966a39908f3a9affe1eaf8e1e8c2350c9aaba05f5a47df`。
这是旧证据防混用的负测，不是新来源的 readiness PASS。

以下为 01:15–02:08 UTC 历史更新：首次 v2 主门禁失败后已[修正审计迁移](REBUILT_AUDIT_CORRECTION.md)。
当时主政策为 `ca6e062b…`；v6 清单及实跑报告保留历史身份，后续入口会因旧 pin
拒绝该清单，不能直接替它改哈希。新政策配套证据已[实际补跑并独立验收](AUDIT_FIX_EVIDENCE_REFRESH.md)，
随后 Lean 新完整门禁[于 02:03:45 UTC 完成并独立验收通过](REBUILT_GATE_ACCEPTANCE.md)。
当时 v8 清单的六项受支持证据全部验收通过；六类发布义务仍缺失。

2026-09-13 已跟随 rebuilt-v2 正式政策更新验收要求和支持证据。
当时 Lean 全门禁尚在运行，v6 清单将 `lean` 留空；其余五项受支持证据已提供。
旧 v4/v5 清单和报告保留历史状态；v6 新增[实际录制的维护者演示](MAINTAINER_DEMO.md)。

## 使用

在仓库根执行；这是 readiness 检查，不是发布绿灯。
v10 在其原来源下的结果为 `incomplete`、退出 2；当前新政策会拒绝其旧 pin、退出 1。
以下命令要求选择报告所绑定的 native Rust 环境；不是任意登录 shell 的可移植验收：

```bash
make -f scripts/release.mk audit-release MANIFEST=docs/release/local-readiness-20260913-v10.json
```

或直接调用 Python，保留更精确的退出码：

```bash
python3 -O scripts/audit_release.py --manifest docs/release/local-readiness-20260913-v10.json
```

本机 v10 实跑使用 `formal-native-gWE5WMRA/report.json` 中的 `native_environment`：
先核对该报告 SHA-256 为 `51082206cf375ddab5d20bd32d3a5957c59813b536333d1b08feeefeaf577895`，
仅向子进程环境覆盖 `PATH`、`RUSTUP_HOME`、`RUSTUP_TOOLCHAIN`、`CARGO_HOME` 四项。
验收器随后重新核对实际工具和来源；不因环境来自报告就跳过身份检查。
这四项及完整私有安装仍是本机输入，不是全新机器的安装方案。

v10 必须保留全部十二个 slot；没有证据的项写 `null`，不能删除或填写虚构 PASS。
完整 Lean 只引用已退出 0 且独立验收通过的归档。原 v8 调用在新政策下预期
为 `invalid`；v9 当时的 `lean: null` 不回写。

主 Makefile 本身在 Lean 冻结源码中，因此本轮使用独立 `scripts/release.mk`，
没有修改主 Makefile 或自动更新证明政策。裸 `make audit-release` 仍未接入。

每次建立新的 `artifacts/release-audit/run-*` 目录，输出 JSON 报告；`--out` 只能指定
不存在的新目录。记录清单与检查器哈希、政策/计划哈希、源码身份和检查前后快照、
当前 Git HEAD 与 dirty 状态。不会执行 artifact 内记录的命令，不会重跑 kernel、
发布内容或改写原证据。

| 结果 | Python 退出码 | 含义 |
| --- | --- | --- |
| `invalid` | 1 | 清单或证据无效、身份过期、文件变化、检查失败 |
| `incomplete` | 2 | 已提供的受支持证据有效，但必需报告、批准或条款仍缺失 |
| `passed` | 0 | 十二个槽全部验证，且 clean-room、CI、包发布、第三方、公开结论和工作树完成事实齐全 |

GNU make 对子命令非零退出也会报错；应读取 JSON 中的状态，不能把 Error 2 当作
可以忽略的成功。不要加 `|| true` 或据此放行发布。

## 清单与检查范围

[当前 v10 清单](local-readiness-20260913-v10.json) 绑定当前主/公开/下层政策、v2 输入准入与目录、
原 Week5/Week6/总览计划共八项哈希，以及每份报告的相对路径和 SHA-256。
证据路径必须在仓库内且不能跨越
symlink；未知字段、遗漏必需 slot、裸 PASS/布尔值和旧哈希都拒绝。
`null` 明确表示缺项。清单中的 candidate 只是本地标签，不是已发布版本。

- `runtime`：检查现有报告的环境、源码/工具哈希、35 个阶段的命令与日志；重算
  双端 trace、完整 mutation 矩阵，复核所有复制产物及重放 trace。没有重新执行引擎。
- `lean`：核对当前生产政策、工具、源码、生成模型与基线；按 profile 要求完整清单。
  当前 `rebuilt-main-v1` 必须有 28 个主阶段及 21 组 287 项测试完成记录；
  旧 profile 的 24/236 只适用于其历史政策。未知 profile 或缺少新增阶段均拒绝。
  核对主定理完整依赖/边界、合同和联合前提见证；调用公开解码验收器
  重查生成物、提取输入、48 个公开阶段及 clean-build 证据。聚合验收不执行新 kernel；
  这些是必需数量，不表示当前运行已经完成。
- `rocq`：拒绝旧主政策报告；当前 profile 要求含本次 Sail 生成的 11 个阶段，
  显式双 OPAM 根及其安装闭包、精确命令/cwd、完整包清单、生成事务、模型与最小复现。
  Rust LLBC 必须先满足本政策的生成来源，支持库只能来自受审源码。
  复核具体错误及退出码，不能用资源失败、缺文件或不相关错误冒充 NO-GO。
  旧 profile 的十阶段检查仍保留，但不能满足新 profile；两者都不增加 Rocq 证明覆盖。

- `rust_tests`：核验 [7 个测试二进制、78 项测试和全部 doctest 目标](RUST_TESTS.md)，
  逐个对照列举与执行结果，全部 10 项真实引擎测试必须执行，不能忽略或过滤。
- `mismatches`：绑定清单中相同的 runtime / Rust 报告，拒绝漏列三种语义负测；
  重算 [trap 最小化](MISMATCH_MINIMIZATION.md) 的真实 trace 首差异及全部搜索步骤。
  两类 [配对输入负测](PAIRED_NEGATIVES.md) 已具备独立程序、trace、有限搜索和复制重放证据；
  三项均检查完成才接受本轮清单。不以测试断言通过代替 artifact 验收，也不扩展至所有历史失败。

- `maintainer_demo`：检查[实际录制与回放](MAINTAINER_DEMO.md)，重算三步执行、trace/mutation、
  预期 mismatch、完整字幕与时间字节对应；要求引用同一清单的 runtime 和 trap 报告。
  演示不替代 Lean、clean-room 或第三方复现。

六类发布义务仍是必需项。`worktree_audit` 的
[源码部分](WORKTREE_SOURCE_VALIDATOR.md)和
[历史生成记录组合](WORKTREE_GENERATION_VALIDATOR.md)在 v3 及以前实际校验后最多为
`incomplete`；只有 v4 携带仓库所有者/发布维护者对 profile A 精确范围的显式批准，且与
同一清单的 Lean/Rocq 最终执行连接后无剩余义务，才可验证该槽。
`public_claims` 现有[全量验收器](PUBLIC_CLAIMS_FINAL.md)，但只有来源一致的实际报告才能
通过。v8 已为 `clean_room`、`ci_download`、`release_package`、`third_party`
接入真实验收器：分别检查递归 checkout/安装/重生成/全链阶段，GitHub 临时 runner
与外部下载重放及离线 Sigstore bundle，已批准版本/profile 的不可变发布与下载，
以及仓库固定 allowed-signers 下的 SSH 签名第三方复现。CI 必须引用同一 clean-room
报告，第三方必须引用同一 release package。当前固定政策中版本/profile/签名者为空，
对应报告也未产生，且政策固定的 `.github/workflows/week6-release.yml` 尚不存在，因此仍为
`missing`；现有 `ci.yml` 不能冒充五作业 clean-room 流程。裸 PASS、自带信任键或只有哈希
均不能通过。发布包检查还会执行固定只读 GitHub API 查询，要求 immutable release 的唯一
uploaded 归档资产大小和 `sha256:` 摘要一致，再核对独立下载字节；签名文件必须是同一
immutable release 上另一个唯一 uploaded asset，大小与摘要也须与本地实际验签文件一致。
仓库现已有确定性 CI 归档、下载重放 gate、只读 CI collector 和发布包 build/record
生产辅助入口，并纳入检查器源码快照；它们不创建上述外部事实。source-inventoried source-review
policy/materializer 已落实并要求最终候选根仓库干净、只保留两项逐路径允许的 CKB 差异；
它也可将独立给出的 source/generation/output/approval 记录组成 v4 envelope，但强制保留
正式 Lean/Rocq 聚合连接义务。approval 现还必须绑定同一 envelope 的完整 output-identity
五件套，不能只凭源码身份批准可替换输出；因此 profile-A 批准必须在输出观察/审核/重扫后产生。
profile-A 批准和 workflow 本体尚未落地；固定 16 阶段 clean-room 编排器已实现并双模式测试，
但尚未在经批准的临时 runner/container 上实跑，
政策中的版本/profile/签名者也仍为空。
`public_claims` 的运行期 evidence manifest 现必须与 release manifest 的真实 candidate 相同；
跟踪的文档审查标签不再被误当成可自引用的 Git commit 身份。
正式 Lean/Rocq 执行及前后输出清单的 one-off recorder 已生产化为受限新目录入口；配套
formal-delta reviewer 也已对历史 46,651 项记录完成生产入口预演并由现有 validator 接受。
fresh native runtime/Rust 入口和 current-output 的观察、三分区审核、精确重扫生产链亦已纳入
源码 pin；精确重扫会进入既有严格组合 validator。260 项相关 producer/validator 回归在普通
与 `-O` 模式均通过。这证明入口兼容，不是当前未冻结源码的 fresh formal/native 执行或
current-output 身份。
clean-room decoder 阶段现调用正式 admitted installer，而非仅解包 payload；真实临时安装已完成
27 个源码恢复阶段并由 loader 核对五个源码变体。只读远端核验同时确认当前为个人账户仓库，
GitHub larger runner 不可直接配置；标准 Linux runner 的官方 14 GB SSD 规格也尚未证明能容纳
固定工具闭包、decoder 安装及并存构建输出。因此 runner 组织归属/容量仍是执行前硬门槛。
缺项不表示仓库从未做过相关测试，
而是本轮发布候选的完整、来源一致的验收证据尚未接入。

## v9 当前实跑

2026-09-13 05:57:05–05:59:00 UTC，实际聚合退出 2、`incomplete`；
runtime、Rocq、Rust tests、mismatches、maintainer_demo 五项为 `verified_existing_evidence`，
Lean 与上述六类条款为 `missing`。新 Rocq 为 11 阶段；所有组件均使用新正式来源，
不是重用 v8 PASS。聚合快照首尾一致并已另行与当前受审来源核对。
[报告](../../artifacts/release-audit/run-56ak_bgi/report.json) SHA-256：
`547ebebddbf4dfa07c9b025f7fa64b4ce198098378b448780e16e0811d49e3df`；
清单 SHA-256：`4e9f52641875d170a6c5f25834d81b129a020295e09557d8f207cb074428e500`。

该聚合早于 06:01–06:03 UTC 的 [非预期宿主安装](LXD_WRAPPER_SIDE_EFFECT.md)。
它没有完整宿主环境不变或 clean-room 声明，不能用源码快照一致掩盖宿主变化。

## v1 历史实跑记录

2026-09-12 03:37:24–03:37:37 UTC 使用 `local-readiness-20260912.json` 实际运行 make 入口，退出 2。
[报告](../../artifacts/release-audit/run-rd7hoddj/report.json) SHA-256：
`2ded3a990aeae19da75c5d4e8c5bfc50583077a2dd2fabb42172e304dcbedc22`。

runtime / Lean / Rocq 均为 `verified_existing_evidence`；其余九项为 `missing`。
`release_claimed=false`、`week6_closed=false`、`fresh_execution_claimed=false`。
21 项新聚合检查测试在普通 Python 与 `-O` 模式通过，覆盖缺项、过期政策、
报告变化、错误哈希、路径约束、伪造完成声明、未实现验收器及旧输出保护。

其中 Rocq 是本轮另外执行的新记录：`make proof-spike` 于 03:31:07–03:35:43 UTC
完成，退出 0；[报告](../../artifacts/rocq-spike/run-jf7lk0r4/report.json) SHA-256：
`f8ab9b1a080d98cac2555c6212df47d34149a95270bc5f0f3b4d7b0874cf161b`。
它绑定当时的 `c8315684…` 政策，十阶段确认原两侧 NO-GO；只重翻译既有 Rust LLBC，
没有声称重新生成全部 Sail/Rust 输入或 clean-room。旧 `run-rbx9livc` 报告保留，
聚合验收实际拒绝它的旧政策身份，没有自动改写旧报告。

## 保证边界与后续

这是本机已有证据的重新验收，不是独立执行者证明，也不是工具供应链认证。
哈希用于绑定字节，不能证明报告真实执行历史或替代可信的 CI/第三方原始记录。
既有 ADD 定理仍然是列出前提下的结果，不扩展为全部 ISA 或整个 CKB-VM 已验证。

下一项是推进全环境隔离重建、最终工作树审批、CI 下载和版本包，最后收集独立第三方
及经确认的发布记录；公开结论报告须随最终源码身份重新验收。
现有成功路径只有在实际证据、信任根和明确批准全部补齐并相互连接时才会退出 0；
不得删除缺项、只填完成标签或复用旧源码身份来制造完成。

## v2 历史实跑记录

2026-09-12 03:52:10–03:52:28 UTC，新的 make 聚合实跑仍退出 2。
[报告](../../artifacts/release-audit/run-4qi0toy2/report.json) SHA-256：
`fbc46b22fe53f5980e0df45ccbe0d84f3350151f4efce408601cf3f998cdc821`。
四项报告为 `verified_existing_evidence`；mismatch 为 `incomplete`，另七项 `missing`。
相关 71 项 Python 检查测试（聚合 23、Rust 15、mismatch 12、最小化 21）普通和 `-O`
均通过。本轮没有修改原计划、主 Makefile、Lean 定理或冻结政策。

## v3 历史实跑记录

2026-09-12 04:15:19–04:15:38 UTC 新清单聚合实跑退出 2。
[报告](../../artifacts/release-audit/run-5c92ra8k/report.json) SHA-256：
`93861f8122ac586de4514a917c5d483ffa296fd900fbed0edc8aa13fab81172a`。
runtime、Lean、Rocq、Rust tests、mismatches 五项重新验收通过；另七项仍 `missing`，
`release_claimed=false`、`week6_closed=false`。配对程序与库单独记录来源及构建证据，
不是更改原 Rust/Lean 基线。128 项相关检查器测试普通及 `-O` 通过。

## v4 历史政策迁移后更新

精确安装政策迁移后，v3 清单不再适用；原清单和历史报告不改写。
当时入口使用 v4 清单，固定主政策 `9308acea…` 及全量 proof-check 报告。
新增必需的 21 项安装回归阶段；runtime、Rust 测试、配对负测、trap 最小化和 Rocq
都已实际补跑并独立复核，详见[本地证据更新](LOCAL_EVIDENCE_REFRESH.md)。
本次 131 项相关检查器测试普通 Python 与 `-O` 均通过；七类完整发布条款仍不可省略。

新清单于 17:52:59–17:53:18 UTC 实际聚合，退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-du7w5vuk/report.json) SHA-256：
`8d205b69efa7e60e4be53972cfb78439c8bec78736abcfa0720a49b3b9d2fcf0`。
五项受支持组件全部 `verified_existing_evidence`，七项仍 `missing`；
聚合前后快照与当前输入亦已独立核对，未刷新正式工具或原验收定义。

## v5：rebuilt-v2 支持证据接入，主门禁待完成

2026-09-13 00:34:51–00:34:59 UTC，Python `-O` 聚合实跑退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-z7f4rrrm/report.json) SHA-256：
`ffcd278b4cdd6f8fac8bc0933ef79b2210801786742d91d06c27b9f09e06076b`。
runtime、Rocq、Rust tests、mismatches 四项为 `verified_existing_evidence`；
Lean 新报告待完成，另七项发布义务仍缺失，共八项 `missing`。
聚合前后快照、清单哈希、当前主/公开来源及精确缺项集合已另行复核。
这里 Lean 缺项不是定理失败，也不能用归档 v1 PASS 填入当前 v2 清单。

## v6：实际维护者演示验收

2026-09-13 00:50:13–00:50:24 UTC 新清单实跑退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-o2fzc1g8/report.json) SHA-256：
`1737fbee3a3240165f443a420fefc577c03aef6b97bf6fe60d8944746d660f4e`。
五项已提供组件均为 `verified_existing_evidence`，Lean 新结果及其余六项仍缺失。
实际录制/回放及独立验收见[维护者演示](MAINTAINER_DEMO.md)；165 项相关检查器测试
普通 Python 与 `-O` 下通过。没有调整原计划、Lean 政策或发布成功条件。

## v7：精确 map 审计修正后补跑

2026-09-13 01:28:49–01:29:00 UTC，新政策清单实跑退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-x4uigh95/report.json) SHA-256：
`730b59bc48b56ffb522d5f14bf452d127c629511bd3e083ec41fda5efb521f2b`。
五项已有组件均重新验收通过，Lean 完整重跑及六类发布义务仍缺失。
所有报告来自[实际补跑](AUDIT_FIX_EVIDENCE_REFRESH.md)，并已独立核对聚合快照与当前来源。
首次 Rocq 并发漂移失败保留，不计入通过集合；后续十阶段 NO-GO 才是 v7 引用。

## v8：完整 Lean 验收接入

2026-09-13 **02:06:32–02:08:06 UTC**，Python `-O` 实际聚合退出 2、`incomplete`。
[报告](../../artifacts/release-audit/run-na0_m08b/report.json) SHA-256：
`506b0859dc0653b56de601a4086dd9db349de20d1fd50169af8a60d07ff40ca7`。
[清单](local-readiness-20260913-v8.json) SHA-256：
`cb7f787900af5326ad199dd102d7d26a8f6b73fcdac2a8928625351d7016b9b8`。

六项受支持组件均为 `verified_existing_evidence`；新增 Lean 证据指向不可被下一次主运行
覆盖的报告/日志归档。原 v7 保持历史状态，其他五项继续引用同一政策下的实际补跑。
另六类 clean-room、worktree 审计、CI 下载、release 包、第三方复现及公开结论审计均
仍 `missing`，`release_claimed=false`、`week6_closed=false`。
