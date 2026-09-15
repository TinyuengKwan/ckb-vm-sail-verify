# 新主工具链的候选接入（未正式采纳）

后续状态：[正式入口迁移](FORMAL_MAIN_INTEGRATION.md)已开始并切换源码/政策/CMake，
新正式完整执行待完成。本文的候选与 v8 观察按当时身份保留，不代表当前正式来源验收。

正式 v8 验收与归档见[完整门禁记录](REBUILT_GATE_ACCEPTANCE.md)。本项在另一个全新
源码副本验证后续主工具链接入；不替换现有正式政策，不将原 PASS 归给新工具。

**当前结论（2026-09-13 04:08 UTC）：候选完整主门禁及独立验收已通过，
同候选 native/Rust 和新输入 Rocq NO-GO 复验亦通过；正式主工具尚未采纳。**
下文保留各阶段的运行中观察和首轮失败，最终证据见文末；不把候选成功当作 Week6 发布。

## 实现边界

- [`rebuilt_main_tools.py`](../../scripts/rebuilt_main_tools.py)只接受显式 `rebuilt-main-v1`
  工具配置；核对四份二进制、版本、支持库、私有 Rust/OPAM/Lean 完整安装闭包及新 Sail
  安装/源码，显式选择私有 Lake、Sail 编译器和插件。CMake cache 与编译器身份必须一致。
  普通和优化模式的 12 项测试通过。
- [`generate_rebuilt_rust.py`](../../scripts/generate_rebuilt_rust.py)执行新副本/缓存中的
  真实生产提取，绑定完整暂存报告与日志，然后一并安装 Lean 模型、LLBC 和来源元数据。
  原输出保存在新备份目录，失败恢复原模型和 LLBC，不递归删除任何用户目录。
  10 项测试在普通/优化模式通过，含四个更新步骤分别失败后的恢复检查，以及旧政策、
  另一源码副本报告的拒绝检查；暂存报告必须绑定本次副本的候选政策。
- 基线绑定的 `generate_rust_model.sh`、`ckb-vm.json`、CKB 源码补丁和所有原定理、合同、
  公理不变。候选仅修改 `check_proof.py`、其编排测试和候选 step 政策，明确增加新工具
  来源/测试约束；不修改正式目录中的这三个文件。
- 主入口不依赖历史探针模块；生产生成路径的 Python 来源清单明确列在 `SOURCES` 中。
  候选仍使用已安装的私有编译器及准入包，不声称重新编译工具或完成全环境 clean-room。

## 候选准备

```sh
python3 -O scripts/probes/prepare_rebuilt_main_candidate.py
```

准备器导出当前 HEAD＋工作树覆盖、独立克隆三个仓库、在新副本安装准入输入包、
从固定 Git 对象恢复全部 Lean 依赖源码而不复制项目缓存，再做精确候选适配与测试。
它还配置新 Sail CMake 并实际调用候选工具解析/来源检查。
原正式目录、原验收报告和正式政策须保持不变。

准备成功**不等于执行了完整门禁**。后续需在该候选中冷构建模拟器，使用解析器给出的
环境运行完整 `make proof-check BACKEND=lean`，独立审查新结果与精确政策差异后，
再决定正式接入。候选计划为 28 个主阶段、287 项测试与原 48 个公开阶段；
这些数字在真实运行终态前不能视为通过结果。

已有准入包中下层模型仍是受审生成源码输入。完整 clean-room、全部所需重生成、Rocq、
runtime、CI 下载、最终工作树、第三方和发布条款仍需单独闭合，不由候选准备替代。

首次准备目录 `rebuilt-main-candidate-s2chukf5` 在复制源码并开始输入安装后被主动中断，
以先补齐上述报告政策绑定检查；[报告](../../artifacts/boundary-check/rebuilt-main-candidate-s2chukf5/report.json)
保留 `failed / KeyboardInterrupt`，原源码 payload 和修改前脚本亦保留。未进入 C++ 或
Lean 构建，不计为准备成功或证明失败；后续从新目录重新准备。

## 实际准备、失败保留与独立复核

第二个候选位于
`artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/checkout`。
40 个准备子阶段全部退出 0，包含准入包安装、10 个 Lean Git 依赖的独立恢复、
普通/优化模式各 **69 项**测试以及真实工具/来源核验。但最后的准备器把混有 Sail 配置
警告的输出当成纯 JSON，发生 `JSONDecodeError`；
[失败报告](../../artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/report.json)
SHA-256 `10d5b747cc5a0facc7082888ccea9235445e685feeda3ccfedfe7f79de2a9742` 保留失败状态。
不能将子进程完成当作整个准备器通过。

后续准备器改为唯一标记的结构化输出，版本预检清除尚未物化的 runtime 配置变量。
已测试正常记录及缺失、重复、错误结构、无效 JSON 的拒绝。
未修改上述候选源码或失败报告，而是在 **02:43:13–02:44:09 UTC** 另行实际执行
[`review_rebuilt_main_candidate.py`](../../scripts/probes/review_rebuilt_main_candidate.py)。
它核对全部原日志/测试、原始源码 payload、精确三文件适配、候选政策/源码快照、
无旧项目模型/Lean 编译缓存，并重新运行候选工具解析和来源检查，退出 0。

- [独立复核报告](../../artifacts/boundary-check/rebuilt-main-candidate-review-u34780fb/report.json)：
  `7c2819ab1766ebb0580cedc5142d2aec3c6723c5e7ee7e3f35bf6abcb4d1df25`。
- 候选 step 政策 SHA-256：
  `697883be2675b6997910690011c5d30b45d07987a80006c7811da517ac9c5000`。
- 候选 HEAD＋工作树覆盖内容身份：
  `ad3c2d8fdbc9482f6cf30f869edfd8f885faf93b105c716c331b46377dbfc1b4`；
  [快照文件](../../artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/candidate-source-snapshot.json)
  SHA-256 `71c87fea71324295bcce8e4a9e1c6433b6cc0d1e0134d5d99537855aa1911931`。

## 完整候选运行

**2026-09-13 02:44:49 UTC** 已在该副本实际启动：

```sh
make proof-check BACKEND=lean
```

[候选主报告](../../artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/checkout/artifacts/proof-check/report.json)
是这次独立运行的记录，已于 **04:05:47 UTC** 终态通过。`sail-config` 阶段从空构建产物
开始编译新模拟器，随后执行双方生成、kernel、所有测试和公开层无项目缓存重建。
当前正式政策仍为 `ca6e062b…`，原 v8 成功证据与六类未关闭义务不变。

截至 **03:15 UTC**，同一次运行的 `sail-config`、`environment`、`generate-rust`
已通过，`generate-sail` 仍在运行。主生产提取在 **03:06:20–03:09:17 UTC**
实际完成 13 个阶段，并将新模型与 LLBC 安装到该候选；
[本次暂存报告](../../artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/checkout/artifacts/boundary-check/rebuilt-production-rust-w072wv3j/report.json)
SHA-256 `4be89d5969082f8ef16a32d31e49a0e3fbc5e568e685c327ef4fc0f9c9c9a7c2`。
候选生成日志记录 `policy_changed=false`；这不表示正式目录中的主工具已采纳，
也不能将这三个已完成阶段计为完整 kernel 验收。

## 候选独立验收器

[`rebuilt_main_acceptance.py`](../../scripts/rebuilt_main_acceptance.py)已于 **04:08:32 UTC**
实际验收成功，且只接受完整运行终态通过的候选。它先要求原独立检查器的 17 组 / 236 项测试及阶段序列
精确不变，再在内存中强制加入四组新测试，形成 28 阶段 / 287 项要求；不改写检查器文件，
不移除原生成、kernel、日志、依赖、公理、合同或公开负测检查。
同时重新约束候选源码快照、已导入的检查器源码、精确工具/入口政策差异和准备复核身份。

```sh
python3 -O scripts/rebuilt_main_acceptance.py
```

8 项检查器测试在普通和优化模式通过。**02:58:23 UTC** 在主进程仍运行时实际调用，
按预期退出 1，拒绝把 `running` 报告当作通过；
[拒绝记录](../../artifacts/boundary-check/rebuilt-main-acceptance-6d6ddm21/report.json)
SHA-256 为 `a8805a70f687ce6bd7d64b3aa917629dd8b56b4825ec8c647cef12a5dff2c99d`。
其中绑定观察到的主报告哈希及 `running` 状态。这是防提前验收的负测，
不是候选 kernel 失败；也不代表独立完整验收已经通过。

## 同候选的 native runtime / Rust 验收入口

[`rebuilt_main_runtime.py`](../../scripts/rebuilt_main_runtime.py)复用候选中未修改的
runtime 与完整 Rust 测试生产器，以及原独立检查器。该入口：

- 要求前四个主阶段全部通过，并核对其日志哈希；允许后续 kernel 仍运行，
  但不将主报告的 `running` 当作证明通过。
- 核对固定准备复核、候选完整源码快照、原正式政策和候选政策；首尾重新核验
  私有 Rust/OPAM/Lean/Sail 安装闭包及生成物。运行期间不编辑候选源码。
- 原生测试显式选择已核验的私有 Rust **1.97.1**，不改变生产提取的 nightly。
  使用独立 Cargo home，每个生产器各自建立全新 target。
- 实际运行 corpus/mutation/32 次复制重放及全部 Rust 测试，然后由独立子进程
  重开报告、原始 artifact、测试清单、执行日志和二进制；要求 32 案例、188 项适用
  mutation、4 项不可应用、78 项测试（含 10 项真实引擎测试），不得遗漏 ignored 测试。

```sh
python3 -O scripts/rebuilt_main_runtime.py
```

10 项回归测试在普通和优化模式通过，覆盖未完成/失败阶段、旧政策、缺失/重排阶段、
日志漂移/符号链接、错误 Rust 安装/二进制、重复检查输出和不完整测试清单。
**03:15:24 UTC** 对真实候选调用时，因 `generate-sail` 尚未完成，入口按预期退出 1，
没有启动任何测试子阶段；
[拒绝报告](../../artifacts/boundary-check/rebuilt-main-runtime-0v0142li/report.json)
SHA-256 `c0f1f658a3d119bd8e14c1679c7c142491467bef9318e6c5e6ad8b4787cd0bb6`。
此记录只验证禁止生成期间启动的守卫，**不是 runtime/Rust PASS**。
正式采纳、kernel 验收、clean-room、release、Week6 关闭标志均保持 false。

### 实际 native 验收完成

双方生成完成后，**03:17:54–03:21:08 UTC** 在同一候选中重新调用上述入口，
三个阶段 `runtime`、`rust-tests`、`independent-check` 均退出 0。
[总报告](../../artifacts/boundary-check/rebuilt-main-runtime-vxlpsoz0/report.json)
SHA-256 `65df501da4d6e3190b06d7f724c6f07bd8653898e0a6e5beb8a101bdb077cdda`，
状态为 `candidate_native_runtime_and_rust_verified_formal_adoption_pending`。

- [runtime 报告](../../artifacts/boundary-check/rebuilt-main-runtime-vxlpsoz0/runtime/report.json)：
  SHA-256 `2d3916c3a6641286f15847ce7b34ca3ec4717070ca93bfc0951061d6d8d55f4d`；
  32 案例、188 项适用 mutation、4 项不可应用、32 次复制后真实重放通过。
- [Rust 报告](../../artifacts/boundary-check/rebuilt-main-runtime-vxlpsoz0/rust-tests/report.json)：
  SHA-256 `ce377659d3dafb0d7ff30d5e9ba56944255d9dd1a71c653033a71a2af2e551b7`；
  7 个测试程序、78 项测试全部通过，含 10 项真实引擎测试；5 个 doctest target
  均实际列举和执行（0 条 doctest），0 ignored、0 filtered。
- 独立子进程重新校验原始证据成功；来源、双方生成物、工具安装闭包、子报告及
  前四个生成阶段日志首尾一致。运行时使用私有 Rust 1.97.1，不复用原生项目构建缓存。

截至 **03:21 UTC**，候选主门禁仍在 `kernel-step`，没有完整终态 PASS；本次 native
成功不代替主门禁、Rocq、新主工具正式采纳或完整 clean-room。原正式 v8 的输入快照、
政策和完整 PASS 报告已再次只读核验保持不变；之前的提前启动拒绝报告保留。

## 显式双 OPAM 根的 Rocq 连接与实测

新主工具环境的 `OPAMROOT/OPAMSWITCH` 指向 Aeneas 的私有安装，不能作为 Rocq 的
默认安装位置。[`rebuilt_main_rocq.py`](../../scripts/rebuilt_main_rocq.py)作为额外、单独
记录哈希的候选驱动，复用冻结源码中的 spike 阶段执行器、具体错误分类和原独立验收器，
不编辑候选或正式 `rocq_spike.py`。

- Aeneas 翻译明确使用 Aeneas 私有 root/switch；全部 Rocq 编译明确使用
  `isolated-rocq` 私有 root/switch 和已核验的 Rocq 二进制绝对路径。
- Rocq 安装报告固定为
  `3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540`；
  完整安装闭包、OPAM/OCaml/Rocq 二进制以及实际 21 包清单必须一致。
- 首先用新 Sail 真正重生成该候选的 Rocq 输入，重开生成日志、事务和安装文件；
  再用该候选主阶段新提取的生产 LLBC 生成 Rust Rocq 模型。不复用旧 Rocq 模型输出。
- 保留原十阶段及三个预期拒绝检查；独立子进程还核对每个阶段的精确命令/工作目录、
  双 OPAM 根、驱动哈希、外层生成事务及发布文件哈希。缺输入、超时、资源或其他错误
  均不能当作 NO-GO。
- 前四个主阶段须已完成；首尾核对候选源码、Lean 生成物、正式政策和相关工具身份。
  不将 Rocq 生成/NO-GO 计为额外证明覆盖，也不声称正式接入或全环境 clean-room。

```sh
python3 -O scripts/rebuilt_main_rocq.py
```

首版 11 项测试在普通和优化模式通过。**03:30:42 UTC** 首次实际启动，
**03:32:10–03:35:48 UTC** 完成 Sail Rocq 重生成与事务安装。
该次运行随后失败，详情与后续重跑见下文；不能计为完整 Rocq 验收通过。

同一次主 Lean 门禁的 `kernel-step` 已完成 **1,872 个构建任务**，定理审计通过，
随后进入回归测试。尚待所有测试、公开 decoder 阶段及完整候选独立验收；
原正式 v8 成功记录不改写，也不把这个阶段性结果算成整个候选 PASS。

### 首轮支持库定位失败及显式修正

首轮在 **03:37:30 UTC** 退出 1：Aeneas 的 `rust-generate` 子进程退出 0 并生成了
`CkbVmProduction.v`，但警告不能复制 `Primitives.v`，驱动因此报
`missing fresh Rust Rocq output`，没有进入编译或把缺输入算成 NO-GO。
[外层失败报告](../../artifacts/boundary-check/rebuilt-main-rocq-xnsz8fhl/report.json)
SHA-256 `20b54966834b1b34e357e3ca94724745c38a28d35b6b64afddbe36267805104c`；
[spike 失败报告](../../artifacts/boundary-check/rebuilt-main-rocq-xnsz8fhl/spike/report.json)
SHA-256 `b8e8acd041355a3598a1bbd1aa222210d55f78076de986938cc696bb2d9eb891`。
[修改前驱动](../../artifacts/boundary-check/rebuilt-main-rocq-xnsz8fhl/driver-before-primitives-fix.py)
和[修改前测试](../../artifacts/boundary-check/rebuilt-main-rocq-xnsz8fhl/tests-before-primitives-fix.py)
已归档，哈希分别为 `e843d8c3…`、`b0fe6f38…`，不覆盖失败记录。

核查准入包中 Aeneas `src/Translate.ml` 的复制实现后，确认它按 `argv[0]` 所在目录
寻找 `backends/coq/Primitives.v`；二进制包与源码分开放置时，该相邻目录不存在。
现在从**已由准入包完整源码清单核验的** `sources/base/aeneas/backends/coq/Primitives.v`
显式安装支持库，绑定固定 SHA-256
`45d1909de822a99f9f8685fc504d6622b86959e6e0bacaae3443b426ef977c16`。
此文件与此前正式 Rocq 复验的支持库逐字节一致；不新写或修改支持定义，不修改编译器。
若翻译器已输出不同的同名文件，入口拒绝而不覆盖；独立验收重开源文件和目标文件。
首轮实际生成的主模型亦与原正式 Rocq 模型逐字节一致（SHA-256 `369397b5…`），
但这个比对本身不替代新编译器上的实际 spike。

新增三项支持库拒绝/复制测试后，共 **14 项**测试在普通和优化模式通过。
**03:40:27 UTC** 从新目录再次启动完整重生成、翻译、编译及独立验收：
[重跑报告](../../artifacts/boundary-check/rebuilt-main-rocq-3voqu0iu/report.json)。
该次重跑于 **03:53:53 UTC** 完成，结果见下文；首轮失败保持原状态。

截至 **03:41 UTC**，同一次主候选的 **27 个阶段和全部 287 项测试已通过**，
最后的 `public-decoder` 阶段仍运行。完整候选独立验收与正式主工具采纳仍未完成。

### 修正后 Rocq 全链与独立验收通过

**03:40:27–03:53:53 UTC** 的重跑终态为
`candidate_fresh_rocq_inputs_and_specific_nogo_verified_adoption_pending`，退出 0。
外层报告 SHA-256
`7d487c02576232455208b7005771f4be949f102a3700bdffc2dfab8500f8c6ff`；
[十阶段 spike 报告](../../artifacts/boundary-check/rebuilt-main-rocq-3voqu0iu/spike/report.json)
SHA-256 `87218706b489b0177cda0f77e7df649b3b93f27a1272c03106fd79cd44b9c1d3`。

- 新 Sail 在 **03:41:21–03:44:53 UTC** 实际重新生成并安装该候选的 Rocq 文件，
  没有复用首轮模型作为本次生成结果。生成事务 SHA-256
  `303ec366adcae823ba78d971a96305d853ec56aad61784833057b9cb167911c0`。
- 使用该候选主阶段新提取的生产 LLBC，再次执行 Aeneas Rocq 翻译；支持库从已核验
  源码显式复制并记录来源。`Primitives.v` 编译成功，主 Rust 模型准确重现既有
  result 类型冲突，最小复现通过。
- Sail support/types 编译成功；完整 Sail 模型及最小复现准确重现既有 `e_div` 缺失。
  十阶段为七项正常退出 0、三项预期编译拒绝退出 1，不将拒绝当作 kernel 证明。
- **03:50:48–03:53:52 UTC**，独立子进程重新核对全部阶段、命令/工作目录、双 OPAM
  上下文、具体诊断、模型及支持库哈希、生成日志/事务/文件和固定工具安装身份，通过。
  外层入口随后确认候选完整源码、Lean 生成物、原主生成阶段日志和驱动输入没有漂移。

结论仍是**具体 Rocq NO-GO，额外证明覆盖为 false**。这次补齐了同候选的新 Rocq
输入与真实复验，不替代完整主 Lean 验收、正式工具采纳或整个环境 clean-room。
截至 **03:54 UTC**，主门禁仍在公开 decoder 的无项目缓存依赖构建。

## 完整主门禁及独立验收终态

同一次候选主进程在 **02:44:49–04:05:47 UTC** 实际运行，最终退出 0，
主报告状态 `passed`，SHA-256
`851aeeb7586ad2c8bc27a26b69221ca4dd631816a9bdbd85437d0a63ebeabb7e`。

- 全部 **28 主阶段 / 21 组 287 项测试**完成；主 kernel 冷构建 1,872 项任务。
- [公开子报告](../../artifacts/boundary-check/rebuilt-main-candidate-ljhriv2y/checkout/artifacts/boundary-check/public-check-sc10rpmq/report.json)
  SHA-256 `097fdd8d7265e359d43fcd0e9d467ffe5df0431ff22de9f3137d6313df13d8bb`；
  全部 **48 阶段、68 项公开定理**完成，含真实 Rust 重提取、公开/iterator 翻译、
  1,865 项无项目缓存依赖构建、原始编码到 ADD 执行连接、精确审计以及两类公开负测。
- 错误公开结果被正确拒绝，弱化为 `False` 的可编译定理被审计拦住；未跳过负测。
  最终主定理仍为原 137 项依赖，wrapper 合同操作的未关闭公理为 0；
  原公共根的配置、取指、内存/初态关系和 Sail 就绪前提仍明确保留。

随后 **04:06:12–04:08:32 UTC**，另一个进程在 `python3 -O` 下实际执行完整独立验收，
退出 0；[验收报告](../../artifacts/boundary-check/rebuilt-main-acceptance-b7f_p_zm/report.json)
SHA-256 `d478e39edbf43b6c540d58565c0d923fe445fbcec407211f6662e4cdc902e51d`，
状态 `candidate_full_main_evidence_verified_formal_adoption_pending`。
它重开全部主/公开证据、工具和生成来源，核对精确政策差异，要求 23 个实际导入的
候选检查模块与冻结源码快照一致，首尾输入未变化；没有重跑 kernel 或声称正式接入。

[成功主报告归档](../../artifacts/boundary-check/approved-rebuilt-main-ajOS4Y08/report.json)
包含主报告、`lean-audit.json` 和全部 28 个阶段日志，共 **30 个文件**。
逐个核对与已验收原件的字节哈希一致，且均为独立常规文件，没有复制项目构建缓存。
唯一公开子报告、完整候选及冻结源码快照继续保留，不能删除其依赖树后仍声称可复核。

**候选验收后的下一项是正式主工具/入口基线接入审查，结果见下节。**
现有正式政策 `ca6e062b…`、原 v8 主报告 `4385aea4…` 和 v8 输入快照均保持不变。
正式接入需另行记录来源/工具/配置、可恢复的旧输出与新执行证据；不能把本候选 PASS
归给未实际运行的新正式目录。完整 clean-room、最终工作树审计、CI 下载重放、release、
独立第三方及发布结论审计仍须按原验收定义分别关闭。

## 正式接入只读审查：已确认实际集成缺口

[`review_rebuilt_main_adoption.py`](../../scripts/probes/review_rebuilt_main_adoption.py)
在 **04:21:43–04:27:55 UTC** 实际执行并退出 0。
[审查报告](../../artifacts/boundary-check/rebuilt-main-adoption-review-odocvhco/report.json)
SHA-256 `326d97bd28251fb4c18f4ef6edd3a4a615e21faec3acbfcc07470121e21be2ee`，
状态 `accepted_candidate_revalidated_formal_integration_gaps_confirmed`。
5 项审查器测试在普通和优化模式通过。

两个独立进程分别重验原正式 v8 和完整新候选，两者均退出 0；没有混用两个目录的
Python 模块。候选对应的 94 项本地源码清单与正式目录的拟变更清单精确对应，
核心仍是 `check_proof.py`、其编排测试及 step 政策三个文件，未混入证明/合同变更。
审查期间正式 HEAD＋工作树内容身份首尾均为
`924c0e13e76286ff2905add52f7b0e18469dff3db1c67bff132f593876575e24`，
v8 验收快照、正式政策、原输出和审查输入均未变化。这是审查时点的来源记录，
不是一次新正式运行或新的 Git commit。

实际接入缺口已确认，不能只复制上述三个文件就宣称完成：

1. 正式 `release_evidence.py` 仍固定要求 **24 阶段 / 236 测试**；须显式支持
   新 profile 的 **28 阶段 / 287 测试**，保留所有旧检查和四组新增强制检查。
2. 对正式目录实际调用新工具解析器，准确得到 `Sail CMake compiler differs`。
   现有 CMake 指向旧 Sail；须先保留旧构建/模型/证据，再显式配置并冷构建新 Sail，
   不能复用旧缓存伪装为新编译器产物。
3. 实际查询 Aeneas 私有 OPAM 根，只存在 `isolated-aeneas` switch，且该 switch 没有
   `rocq-core`。正式 spike 的默认选择不能工作；须把候选验证过的双 OPAM 上下文、
   受审 `Primitives.v` 来源绑定及对应的独立检查接入正式入口。

后续工作顺序：落实正式 release/Rocq 入口与测试，审查最终源码/政策哈希及辅助代码说明；
保留旧基线，统一切换核心入口、政策和构建环境；在正式目录真实重生成并重跑
Lean/native/Rocq，再刷新依赖该身份的 mismatch、演示及 readiness 证据。
本报告没有切换政策、写入正式生成物或采纳主工具，也未关闭其余 Week6 发布义务。
