# Verification Guide

本文区分“当前可运行基线”和“六周 MVP 将交付的验收接口”。不存在的命令不会被描述成已经完成。

2026-09-13 22:21 UTC 状态：[当前 `b5bdc401…` 政策的完整正式链](docs/release/FORMAL_FINAL_EXECUTION.md)
已完成实跑及独立验收：主门禁 28 阶段/287 测试、公开子链 48 阶段/68 定理，
Rocq 含新 Sail 生成的 11 阶段 NO-GO（无额外证明）。[配套负测/演示及新六项聚合](docs/release/FINAL_SUPPORT_REFRESH.md)
已于 22:35 UTC 完成，整体仍 incomplete。
[46,651 项正式输出差异说明及复验](docs/release/FORMAL_DELTA_REVIEW.md)已完成，
并已[接入新工作树部分验收聚合](docs/release/WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)。
六项证据接受、工作树部分未完成、五项缺失；后续增量、最终范围及六类发布义务仍未完成。
后续 `43218a71…` 候选已实际关闭当时的 `public_claims` 槽；外部验收器的新源码修订
又使该报告只保留为已实跑历史身份，待新最终源码冻结后重验。`audit-release` v8
已为 clean-room、CI 外部下载、发布包和签名第三方报告接入 fail-closed 检查；
真实外部报告和版本/profile/签名者批准仍缺失，因此 Week6 状态仍为未关闭。
确定性 CI 归档、受限下载重放、GitHub Actions 只读收集及发布包 build/record 已有生产辅助
入口；这些命令不创建 release、不签名、不触发 workflow，也不替代尚缺的 clean-room 运行。
source-review policy/materializer 也已加入，但它只记录最终干净候选加两项受审 CKB 差异；
仓库所有者/发布维护者的 profile-A 明示批准仍须在 current-output 五件套生成后另行完成，
且 approval 必须绑定该五件套，不能只绑定源码后被另一组输出记录复用。
正式 Lean/Rocq 前后输出记录已有 tracked CLI；该记录器只生成待逐节点审查的执行记录，
其配套 tracked reviewer 会逐项分类完整 delta 并再次调用现有 validator。fresh native
runtime/Rust、当前输出扩展观察、additional 节点三分区审核及同根精确重扫也已有受限 tracked
入口；重扫生产器会调用完整输出组合 validator。固定 16 阶段 clean-room 编排器也已接入：
只接受固定仓库/canonical path/三项输入哈希，下载 URL 仅从环境读取，先生成未批准 v3
worktree envelope，并由最终 external validator 复验；它尚未在临时 runner 上实跑。
这些入口均未在未冻结候选上重跑，也不会自行
声称 clean-room、输出语义审批或发布完成。
下文旧报告及 v8/v10 仅代表各自历史来源，不能作为新政策的通过记录；完整 Week6 尚未关闭。

## 1. 当前版本基线

- CKB-VM 生产源码：`ckb-vm-1ffba3977da9-runtime-container-v1`，即上游
  `1ffba3977da9dcdef8092e9ab1fd2516b27ec939` 加受审容器化补丁；不是未修改的该 commit。
  固定补丁、完整源码树哈希、提取配置和验收边界见[基线审查](proof/lean/extraction/ADOPTION.md)。
- CKB-VM crate：0.24.0
- Rust：MSRV 1.95；当前 foundation 验证版本 1.97.1
- Sail compiler：**从源码构建**，commit `8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1`
  （2026-08-17）。版本号仍自称 0.20.2，与发布版**同号不同物**，因此
  `scripts/verify_environment.sh` 钉的是完整版本串
  `Sail 0.20.2 (HEAD @ 8eb1fb6b…)`，发布版会被拒绝。用 `make sail-compiler`
  构建。为什么不能用发布版见下方与 `proof/lean/expected_build_status.txt`
- sail-riscv：0.13.1，commit `8f91355eee63a85738723603e23d32eecdd763dc`（2026-08-14）
- RVFI-DII 线格式：v1，88 字节；`crates/sail-runner/tests/fixtures/sail-rvfi-dii-v1.hex`
  是从该 commit 捕获的实包，默认测试套件解析它，端到端测试再核对它没有过期
- ISA：`rv64imcb_zca_zba_zbb_zbc_zbs`
- 合并配置 SHA-256：`41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024`

依赖或配置变化属于证据变化，必须重新运行运行时差分、mutation、Lean 4 证明与 Rocq/Coq spike。

**为什么这里锁定 Sail 源码构建**：本项目验收的是所列 Sail 源码 commit 与固定
sail-riscv 的组合，不是同版本号的一般发行版。在上一版基线（sail-riscv `27224cc` + 发布版 0.20.2）下，生成的
Lean 模型在第 10/131 个目标失败于 `unknown namespace LeanRV64D.Defs`。上游本身就把
两个 target 跑在两个不同的 Sail 上（`compile-lean.yml` 用 `sail-version: "latest"`，
而 `cmake/sail_required_version.txt` 为 C 模拟器钉 0.20.2）；这些配置本身不能证明我们测试的
那个组合已被上游同时验收，也不能据此断言上游从未测试过它。本项目改为**一个** Sail
同时服务两个 target 并按 commit 钉死，两个 pin 必须
一起移动。

这次移动的实测结果：**物化配置 SHA-256、ISA 串、RVFI-DII 线格式与全部差分结果均未
改变**——32/32 语料、395 提交步、188 次 mutation、10 个端到端测试（含 packet fixture
与实时模拟器的一致性检查）在新基线上全部通过。改变的只是模拟器二进制与 Sail 构建。

当前正式主 profile 为 `rebuilt-main-v1`，工具身份由政策固定（迁移实跑见页首）：

- Charon：`0.1.247 (89ac118194b978d8cf753222c19f313521377aa0)`
- Aeneas：`aeneas 379890b5`（已重建的 base 编译器；不是原 nightly bundle 的二进制）
- Lean（Rust / Sail / 双侧导入工程）：`leanprover/lean4:v4.31.0`
- Aeneas Lean 库同为 4.31.0；共同工程锁定 mathlib4 及传递 Git 依赖

正式主入口使用 `scripts/generate_rebuilt_rust.py`，核验源码、安装闭包、二进制哈希与版本，
在新副本中实际提取后安装模型/LLBC 对。历史 `scripts/generate_rust_model.sh` 仍保留并
要求旧 `aeneas nightly-2026.09.01-379890b`；它不是新 profile 的正式生成入口，
不要用其单独生成结果替代新政策的来源记录。
共同版本由 `proof/lean/theorems/lean-toolchain` 唯一指定，生成与构建脚本均应用它。
Sail 原生成模板使用 4.29.0；在 4.31.0 下还需要一处自动化的 `Defs.lean` 作用域
兼容补丁。不能只改版本后将 Lake 的 `Built` 当成成功：未修正的枚举派生曾触发
退出码为 0 的 compiler panic。复现、补丁边界与验收记录见
[共同 Lean 兼容性报告](proof/lean/compat/README.md)。

Rocq/OPAM 的兼容性检查由 `make proof-spike` 单独执行，当前记录为 NO-GO，
不是 Rocq 证明门禁通过。

## 2. 当前可运行基线

```bash
git submodule update --init --recursive
make ckb-baseline-apply
make check
make test
make verify-env
make verify-smoke
make verify-negative
make proof-gen BACKEND=lean
make proof-gen BACKEND=rocq
make proof-build BACKEND=lean
make proof-gen-rust
make proof-imports
make proof-spike
```

当前基线可以构建 Rust workspace、运行单元测试、构建 Sail 模拟器、验证固定环境、
通过 RVFI-DII 完成 CKB-VM 与 Sail 的端到端注入差分，并生成固定配置下的 Sail
Lean/Rocq 模型。模型生成不等于 kernel 编译或等价证明。

`make proof-gen-rust` 生成 **Rust 侧**定义：Charon 从 `crates/proof-extract` 的
根出发提取生产调用图，Aeneas 译成 Lean 4。那个 crate 是普通 Rust，一行调用
`ckb_vm::instructions::execute`，机器类型直接 import 自 `ckb-runner` 的
`InjectedMachine` 而不是重新拼写 —— 差分驱动的机器和证明提取的机器因此不可能
漂移。`ckb_vm::instructions::common::add` 出现在生成物里是因为生产**到达**它，
不是脚本点名它。

**Week 4 历史结论：不改源码也能提取，但 wrapper 当时为 opaque。**
Week 5 为取得真实 wrapper 定义已正式采用受审容器化补丁；现在的源码身份必须为
上游 commit + 补丁，不得把修改版的证明归到原始 commit。早期那个手写的
`crates/ckb-runner/src/semantics.rs` 原型已删除：它是第二份手写 RISC-V 语义，
按 §5 不能计入证明证据，留在树里只会被误当成提取目标。生成物同样要过编译检查（记录在
`proof/lean/expected_rust_build_status.txt`），当前状态 **ok**：285 个 `def`、
51 个 `axiom`。寄存器总数和 RA 已通过精确 `--include` 从原来的 axiom 补为纯定义。
exit gate 要求的"重新生成不需要编辑生成文件"已实测——连跑两次逐
字节相同。

`make proof-gen` 在生成之后调用 `scripts/check_proof_model.sh` 编译生成物，并把
结果与 `proof/lean/expected_build_status.txt` 的记录对照。这个检查**双向失败**：
出现记录之外的失败是回归；编译突然成功而记录仍写着 blocked 也判失败，因为那意味
着记录和引用它的文档都过期了 —— 陈旧的“已阻塞”会低报已证明的内容，和高报一样是
错的。四个方向都实测过。

当前记录的状态是 **ok**：Lean 模型编译通过，产出 125 个 `.olean`，24 核冷构建约
十分钟。这个状态是在把两个 pin 一起前移之后达到的（见 §1）；之前它是 blocked，
历史与原因保留在 `proof/lean/expected_build_status.txt` 里，因为那正是这两个 pin
现在是这个取值的理由。

`make proof-imports` 在同一个锁定依赖的 Lean 工程中构建双方完整库和
`SmokeImports.lean`，检查真实编译器版本、依赖 checkout、锁文件不变及无 compiler
panic；失败或超时必定非零退出。它不沿用“符合已知 blocked 也返回 0”的判定。
详细用法见 [导入工程](proof/lean/theorems/README.md)。

模型能编译**不等于**完成精化。`make proof-registers` 进一步检查寄存器 `state_rel`、
直接引用两侧生成 ADD 叶函数的条件性定理、精确公理依赖守卫及边界回归。
已证内容见 [寄存器证明](proof/lean/reports/ADD_REGISTERS.md)。`make proof-step` 进一步
连接 `execute_production` 和 `try_step`，检查 GPR/PC/next-PC、正常退休及所选内存
frame 的条件性定理；[一步边界](proof/lean/reports/ADD_STEP.md) 列出通用定理的剩余条件、固定
RVFI=false 配置与 137 项传递公理依赖。wrapper 两个合同已证明，其余条件仍显式。
两个入口都不替代最终 `proof-check`。

新增 [联合前提见证](proof/lean/reports/ADD_NONVACUITY.md) 已在 Lean 中构造同一具体 Sail 状态链的
全部路径合同，并以 Rust seed 为输入应用最终定理。这不证明 raw decoder 对应、
平台 reset 可达性或 Rust opaque 类型的无条件非空性。
同码 ADD 解码已由另一个[公开入口定理](proof/lean/decoder/ADOPTION.md)证明；
其独立干净复验及首次集成主门禁实跑均已通过，限定采纳身份与实际报告见上述记录。

Lean 支持库（`rems-project/lean-sail`）在生成的 lakefile 里是按**分支**引用的，同一
个 session 内实测解析到过两个不同 revision（`79b4d085` 与 `07946313`）。检查脚本因此
在解析前把 lakefile 钉到记录的 revision，并在 manifest 不符时失败。

Rocq 侧的结论是 **NO-GO**，两半各自卡在不同的、实测到的地方：Aeneas 的 Rocq
`Primitives.v` 定义的 `result A` 被 Rocq 9.1 prelude 的 `result A E` 遮蔽，生成物
在第 17 行第一个 trait 声明就失败（最小复现 `proof/rocq/spike/result_shadowing.v`）；
Sail 侧 `rv64d.v` 需要 `e_div`，而发布版 `rocq-sail-stdpp 0.20.2` 不提供它 ——
和 Lean 那次逼着移 pin 的问题同一形状。完整证据、信任假设与"什么会改变结论"见
`proof/rocq/SPIKE.md`，`make proof-spike` 重现它，且任一半开始成功也会判失败。

按计划，NO-GO **不替代** Lean 主线；Lean 两侧都已生成并编译通过。

`make verify-smoke` 当前源码运行 33 个注入案例（ADD 13、ADDI 10、BEQ 10），并把每个
案例的 artifact 写到 `artifacts/corpus/`。此前 32 项 / 395 步的历史实跑中 BEQ 只有 9 项，
未满足 Week6 逐族最低数；[新案例与来源修正](docs/release/WEEK6_RUNTIME_FLOOR.md)的完整实跑
及独立验收现已通过：33 项 / 398 步、194 次适用 mutation、33 次复制输入重放。

`make verify-negative` 的语义：

- `cargo test -p ckb-vm-sail-diff -- --ignored` 运行 10 个需要真实模拟器的端到端
  测试，其中 6 个是负向的：指令流分歧、末尾事件缺失、trap 分歧、引擎失败、空
  mutation 矩阵不通过，以及完整 mutation 矩阵必须逐类被定位；另有压缩指令宽度
  规范化、packet fixture 与实时模拟器输出的一致性检查，以及 16 个并发会话不会
  因为 RVFI-DII 端口竞态而失败 —— flaky 的差分在 CI 里与“真实差异时隐时现”
  无法区分；
- `cargo run -p ckb-vm-sail-diff -- --corpus --mutate` 运行 §4 的 mutation 矩阵，
  把完整 mutation 矩阵应用到真实记录的 trace 上（当前 33 案例为 194 次适用），并把结果写到
  `artifacts/corpus/mutations.json`。

`make verify-dii` 是两者的合并入口，也是 CI 调用的单条命令。

当前尚未完成：

- 通用初态/取指/Sail 就绪条件、物理内存对应及平台 reset 可达性；已有具体 Sail 联合
  前提见证及公开 ADD 同码解码证明，不能再把这两项列为未完成；
- `audit-release` 的全环境 clean-room、完整覆盖与发布证据验收（Week 6）；
  已接入的条件性 `proof-check` 不替代这些工作。

Week6 的逐项缺口和本轮实测状态见 [关闭清单](docs/WEEK6_STATUS.md)。

以下是按推进顺序保留的阶段性记录；其中“尚未采纳/尚待执行”指对应报告产生时的状态，
不覆盖后文 2026-09-13 新正式主门禁、native、Rocq 及 v10 聚合的完成记录。
旧报告的成功或失败范围不因后续进展而改写。

新增[本地 runtime 证据入口](docs/release/RUNTIME_EVIDENCE.md)：
`python3 scripts/probes/probe_release_runtime.py` 检查环境，在新 Cargo target 中构建
CLI，重跑 corpus/mutation 并从字节相同的复制产物逐案重放；独立重算 trace 和矩阵。
本轮 32 个案例及全部复制重放通过，但此入口不重建 Sail emulator，不替代完整
clean-room、CI 下载、第三方复现或完整 `audit-release` 验收。

另有[隔离基础重建入口与实测记录](docs/release/ISOLATED_FOUNDATION.md)：
`python3 scripts/probes/probe_isolated_foundation.py` 将明确的 HEAD＋工作树快照复原到
三个独立 Git 副本，冷构建 Sail 模拟器/配置，再运行 Rust 测试及差分/mutation/复制重放。
本轮 13 阶段通过且源码前后无漂移；它复用本机工具和缓存，未执行新 Lean/Rocq 链，
不是全环境 clean-room。完整发布门槛仍见 Week6 清单。

随后已完成 [Rust/Lean 独立安装](docs/release/ISOLATED_RUST_LEAN.md)：
`python3 scripts/probes/probe_isolated_rust_lean.py` 在全新工具目录下载固定版本，
核验工具身份及编译 smoke。20 阶段通过；它复用安装器/宿主系统，不安装其余翻译器，
也不执行新 ADD 证明，不能替代同一候选下的完整环境与证明链验收。

另已完成 [Rocq/OPAM 独立源码重建](docs/release/ISOLATED_ROCQ.md)：
`python3 scripts/probes/probe_isolated_rocq.py` 在空 OPAM 根重建 21 个固定包，审计实际
编译器约束和包元数据，再用新 Rocq 复跑原 spike。13 个外层阶段与十阶段 NO-GO 复验通过；
仍复用宿主工具、Aeneas 和既有 LLBC/Sail 输入，不是完整 clean-room 或额外 Rocq 证明。

另已完成 [Sail 独立源码重建及身份核验](docs/release/ISOLATED_SAIL.md)：
`python3 scripts/probes/probe_isolated_sail.py` 在新 OPAM 根重建 56 包，再独立编译
固定 commit 的 Sail。18 阶段及 C / Lean 小型生成检查通过，但新执行文件哈希与
现有证明政策不同，整体退出 2、要求身份审查，未自动采纳。小型生成物与旧工具一致
不代表完整模型等价；该结果也不替代新工具下的完整提取/证明链或 clean-room。

另已完成 [full-MIR 标准库独立重建](docs/release/ISOLATED_FULL_MIR.md)：
`python3 scripts/probes/probe_isolated_full_mir.py` 使用独立安装的 nightly 和空 Cargo
缓存构建，46 个库已物化为无外链 sysroot；因全部哈希不同于原批准库，外层返回 2，
随后[真实公开 decoder / iterator 重提取](docs/release/FULL_MIR_REEXTRACTION.md) 的
11 个阶段通过，两份生成 Lean 模型按既有源位置注释映射匹配原身份。外层仍返回 2，
等待正式资格采纳，未替换正式输入、独立重建翻译器或执行新 ADD 证明。

完整 Sail 重生成另发现[历史文件残留](docs/release/SAIL_STALE_GENERATED_FILE.md)：
旧固定编译器的干净输出不含政策中已有的 `Specialization.lean`，其余 162 项一致。
原比较入口因此失败；隔离清理后的主 kernel / 导入环境审计已通过，原主根 137 项依赖不变。
候选工具的 Lean / Rocq 原始输出相同，但 C++ 两文件不同，整项比较仍失败，未采纳新工具。
后续[受限 C++ 标记对应审查](docs/release/SAIL_CPP_CORRESPONDENCE.md)已将 642 个字段
建立全局一一映射，对应类型和头文件顺序一致，所有方法区域及间隙均有覆盖。
这不改写原始比较失败，也不替代宏/名称绑定审查、实际候选 C++ 编译和运行差分。
后续[候选完整模拟器冷构建](docs/release/REBUILT_SAIL_CPP.md)已完成 10 阶段：新目录中
实际生成及编译完整 C++ 模型，新物化配置与原绑定配置相同。
[新模拟器的实际双端差分](docs/release/REBUILT_SAIL_RUNTIME.md)随后完成 38 阶段，
32 个案例、188 项适用 mutation、32 个复制输入实际重放通过并独立复核。
原始生成字节差异和工具准入边界保持明确，未替换正式政策或原批准门禁报告。
不得把旧文件补回新模型或直接刷新哈希来掩盖这个复现缺口。
随后已按隔离 kernel 证据接入[精确安装及单文件政策迁移](docs/release/SAIL_INSTALL_MIGRATION.md)，
在该次运行中保留原批准工具和公开政策，完整主/公开 proof-check 已通过并独立复核：
22 个主阶段、206 项回归及 47 个公开子阶段通过；这不采纳候选 Sail 工具。

另已完成 [Charon 双版本独立源码重建](docs/release/ISOLATED_CHARON.md)：分别以原提交和
已批准公开补丁，在独立源码、空 Cargo 缓存及 target 中构建，18 阶段和两侧提取 smoke 通过。
四个新二进制哈希不同于批准工具，外层返回 2；尚未采纳或用于完整生产资格/证明链。
[Aeneas 的锁定 OPAM 依赖环境](docs/release/AENEAS_OPAM_DEPENDENCIES.md) 已完成 116 包源码重建
及元数据收尾审计；[Aeneas 双版本源码／模型核验](docs/release/ISOLATED_AENEAS.md) 的
20 个阶段通过，三份完整 Lean 生成物匹配。但复用原 LLBC，尚未将新工具连接为完整提取链，
外层返回 2、未正式采纳；既有 visitors 版本与上游声明约束的差异继续显式记录。

后续 [新工具联合生产提取](docs/release/REBUILT_EXTRACTION_CHAIN.md) 已实际连接新 Charon、
Aeneas 和 full-MIR，在同一源码快照中重提取并翻译三份模型，20 阶段通过。
主模型原始字节相同，公开 decoder / iterator 按既有来源注释映射匹配，未复译旧 LLBC。
完整资格回归、下层模型准入和新 kernel 链仍待完成；此结果不自动采纳新工具。

新工具的 [435 项 Charon UI 对照](docs/release/REBUILT_CHARON_UI.md)随后完成；433 项
实际执行的两侧退出码相同，但仍有金样不符和各 24 项命令失败，不能记作全量通过。
后续[独立诊断报告](docs/release/REBUILT_CHARON_DIAGNOSTICS.md)已逐项复核 24 对失败并
重放历史 26 对分类；明确披露旧报告脚本哈希与当前 Git 版本不同，不据此假定历史源码
身份相同，也不将缺失标准库或 Miri 的环境失败改为 PASS。
[下层模型重生成](docs/release/LOWER_MODEL_REGENERATION.md)已补建仅含 join-recovery
补丁的第三种 Aeneas，并完成三份实际提取及严格合流负测。字段模型原始字节一致，
工厂/最小模型的 `Option.map` 函数体不同，既有身份检查不符，不能作为纯路径差异放行。
后续[显式 sysroot 对照](docs/release/LOWER_SYSROOT_DIFFERENCE.md)已重现该最小模型差异，
[map 等价与原 raw 定理候选检查](docs/release/LOWER_MAP_EQUIVALENCE.md)也已通过：4 条等价、
9 条字段及 15 条原 raw 定理，类型/公理集合不变，仅两处 map 定义不同；两个负测正确拒绝。
随后[原字段/raw 负测与生产工厂运行检查](docs/release/LOWER_ORIGINAL_NEGATIVES.md)的 17 阶段完成：
四类错误结果、两类 False 前提和严格合流均按预期拒绝；新构建检查器通过全部 32,768 个
ADD 编码、196,608 次非 ADD 邻域及 32,768 次目标寄存器变异检查。
此项复用主模型/支持库编译缓存，原政策仍拒绝候选，未完成新公开 decoder 全链、
全套资格回归或工具采纳，不是完整 `proof-check` 新 PASS。

新工具的 [borrow 资格回归](docs/release/REBUILT_BORROW_QUALIFICATION.md)随后完成：两个原
Rust 用例实际重提取、模型字节一致，九条定理及 False／错误回边负测通过，并证明变异
实际错误轨迹。[fnptr 资格回归](docs/release/REBUILT_FNPTR_QUALIFICATION.md)也已完成
22 阶段，原 16 条局部定理与七项负测通过；普通标准库模型中的 opaque 迭代入口边界不变。
[循环清理回归](docs/release/REBUILT_LOOP_QUALIFICATION.md)也已由新双版本 Charon 重提取，
原四条定理与错误结果负测通过。[guard 回归](docs/release/REBUILT_GUARD_QUALIFICATION.md)
随后完成 15 阶段，原全输入等价证明、具体反例及错误等式负测通过；四组限定回归均已
完成独立复核，但不构成一般编译器正确性证明。这四项明确复用支持编译缓存。另行启动的
[公开候选源码级 kernel 重建](docs/release/REBUILT_PUBLIC_KERNEL.md)现已完成第六轮 66 阶段：
1,865 项主构建、主/下层/公开审计及错误公开结论、False 前提负测通过，最终来源复核
无漂移。前五轮失败记录保留；本轮不复用项目/支持编译缓存，外层退出 2、待准入。
不能据此宣称新工具已采纳或完整 clean-room 已完成。

候选工具已另行整理为[待准入输入包](docs/release/REBUILT_INPUT_CANDIDATE.md)：92 个文件，
含 7 个新工具执行文件、46 个新 full-MIR 库、实际模型/LLBC 和七类资格报告。
归档、全新目录解包及包外固定清单校验已完成；10 项回归测试通过。
这不是对 `public-v1` 的覆盖，原 v1 加载器明确拒绝候选格式。
后续[包内实际重提取](docs/release/REBUILT_INPUT_REEXTRACTION.md)已完成 51 阶段：
恢复八个工具源码树，六个根全部重提取，四份模型全文件一致、两份通过既有源码位置
身份规则，原严格模式负测正确拒绝。随后 [v2 输入准入政策及安装入口](docs/release/REBUILT_INPUT_ADMISSION.md)
已接受固定新身份并保留资格限制；实际安装/加载通过，15 项新增测试及相关 89 项测试
在普通模式和 `-O` 下通过。后续[公开主调用层及下层政策迁移](docs/release/REBUILT_GATE_MIGRATION.md)
已完成代码和静态审查；00:14:51 UTC 启动的首次门禁失败记录保留，修正后
[完整重跑及独立验收](docs/release/REBUILT_GATE_ACCEPTANCE.md)于 02:03–02:08 UTC 完成。
这属于旧主政策的历史证据，不是当前发布包。

生产调用图提取和源码关联已建立；Rocq 双侧生成/导入尝试及 NO-GO 报告已存在。
Rocq 当前的构建失败意味着没有完成双侧成功导入、状态桥接或定理。

直接 ELF 模式得到空 RVFI 流必须返回失败，不能当作空程序或 PASS。

RVFI-DII 会话必须从架构复位态开始，首包不是 `rvfi_order` 0 / `pc` `0x80000000`
时直接报错：上游模拟器只 `accept` 一次，端口竞态下输的一方可能连到别人已经推进
过的模拟器，这种情况必须是错误而不是一条看起来合理的 trace。

## 3. 六周 MVP 验收接口

以下接口是稳定验收面。`verify-smoke`、`verify-negative` 与 `proof-spike` 已实现
并可直接验收；`proof-check BACKEND=lean` 已实现条件性 ADD 定理的严格生成/证明审计。
`audit-release` 已有[聚合器与历史清单说明](docs/release/AUDIT_RELEASE.md)。v10 只代表
旧 `7ced9f42…` 政策；当前 `b5bdc401…` 的本地清单和 v3 工作树记录位于 Git 忽略的
`current-output-integration-zvlwq2MM` 证据目录。完整发布验收仍未完成；缺项时退出非零：

```bash
make verify-smoke
make verify-negative
make proof-check BACKEND=lean
make proof-spike
make -f scripts/release.mk audit-release \
  MANIFEST=artifacts/boundary-check/current-output-integration-zvlwq2MM/manifest.json
```

预期语义：

- `verify-smoke`：对 ADD、ADDI、BEQ 的至少 10 个案例完成严格双端比较；
- `verify-negative`：至少 5 类 mutation 全部被检测；
- `proof-check BACKEND=lean`：重新生成两侧 Lean 4 定义，实际编译并检查生产关联的
  条件性 ADD 定理，精确审计公理、显式前提及来源；报告 `assurance=conditional`，
  另要求模型/证明/Lean 依赖从零构建，并重新提取和审计指定配置的公开 ADD decoder；
  wrapper 合同已证明，但取指/初态与 Sail 前提未全部消除，完整指令覆盖不自动成为 `proved`；
- `make proof-spike`：在新 profile 下执行 11 阶段，包括本次 Sail Rocq 生成、从已核验生产
  LLBC 重新翻译 Rust、显式双 OPAM 上下文及原具体 NO-GO/最小复现；须先完成主门禁生成阶段；
- `audit-release`：目标是检查版本、哈希、覆盖、重放 artifact、占位符与保证边界。
  当前本地清单引用独立验收后的完整 Lean、新 runtime/Rocq、完整 workspace 测试、
  三项语义负测、真实演示和 v3 工作树部分记录；实际聚合六项验收通过，工作树仍因
  最终交付范围/语义审批而 `incomplete`，其余五类发布义务缺失。v10 的 06:34 UTC
  六项聚合仅保留历史身份。
  两项配对输入有独立产物/有限最小化/重放证据，不声称同码 VM 缺陷。
  `incomplete` 退出 2，不是发布 PASS。独立 Makefile 保持现有 Lean 冻结源码不变，
  裸 `make audit-release` 尚未接入。

任一 runner error、空 trace、事件长度差异、字段差异或终止差异都不能返回 PASS。

`proof-check` 要求两侧实际编译及指定定理的 kernel 检查成功，具体流程与
原内部定理 137 项与公开解码步骤 158 项的审计边界见 [门禁说明](proof/lean/reports/PROOF_CHECK.md)。报告在
`artifacts/proof-check/report.json`，失败不能沿用先前 PASS。
2026-09-13 起当前主入口要求先[安装 v2 输入](docs/release/REBUILT_INPUT_ADMISSION.md)到
`artifacts/decoder-inputs/rebuilt-v2`，以及固定的包外 Rust/Lean、Aeneas OPAM 和 Sail 安装；
Rocq 还需要独立的私有 Rocq 安装。没有旧实验目录或 v1 工具回退。
原 [公开 v2 门禁迁移](docs/release/REBUILT_GATE_ACCEPTANCE.md)已经完成；
[正式主工具迁移后的完整门禁](docs/release/FORMAL_MAIN_INTEGRATION.md)也已于 06:26 UTC
退出 0，06:29 UTC 独立验收通过（28 主阶段/287 测试/48 公开阶段/68 公开定理）。
2026-09-11 的 `public-v1` [迁移记录](docs/release/PUBLIC_INPUT_MIGRATION.md)
是已归档历史基线；包安装和条件性门禁均不等于完整环境 clean-room 或 Week6 发布。

当前安装报告及其引用的私有安装树位于 `artifacts/boundary-check/`，均为 Git 忽略输入。
普通 clone 不含这些文件，不能仅凭本机已通过的记录声称新机器已可完整复现。
精确来源已可由冻结归档在本机恢复，但完整安装方案与同一候选下的 clean-room 实跑仍待完成；
同版本但身份不同的工具必须经过审查，不自动刷新政策使之通过。

[安装分发核验](docs/release/INSTALL_DISTRIBUTION_REVIEW.md)已另行确认六组安装约 8.27 GB，
固定报告仍含被正式入口直接使用的绝对路径，且安装目录哈希不覆盖全部 OPAM 控制状态。
新目录中的 Sail 前缀小模型生成通过，只是一个组件的搬迁 smoke；不能代替整套分发或 clean-room。
后续 [固定安装补充包](docs/release/FIXED_INSTALL_BUNDLE.md)已完成字节往返和独立验收，
[同快照源码归档](docs/release/FIXED_SOURCE_CAPSULE.md)也已实际离线递归复原。
[交付准备清单](docs/release/fixed-input-handoff-20260913-v1.json)连接源码、安装与批准 decoder 包；
[统一恢复入口](docs/release/UNIFIED_FIXED_RESTORE.md)已从这三类归档完成本机新目录暂存，
并由恢复副本安装及校验 decoder 输入。该入口不运行正式解析器或证明链；原安装报告的
绝对路径未重写，已有生产目录会被拒绝覆盖。仍不是完整空机器 bootstrap、固定绝对路径
的新环境全链或发布完成；恢复脚本是冻结候选之外的单独辅助代码。
[宿主前置条件静态记录](docs/release/FIXED_HOST_INPUT_REVIEW.md)另已完成 ELF/宿主文件观察，
但库名候选、文件哈希不证明实际装载或 ABI 兼容。冷构建所需的四项 CMake 下载内容已
[另行保存](docs/release/FIXED_CMAKE_DOWNLOADS.md)，并完成独立新目录的
[实际 CMake 冷配置与 GMP 构建](docs/release/FIXED_CMAKE_CONFIGURATION.md)及独立验收；
尚未接入正式构建路径或旧交付清单，不替代完整新环境生成和证明链。
`check_proof_model.sh` 是构建状态核对器，对符合记录的 `blocked` 也返回 0；
因此新门禁不调用该状态核对器，而是运行严格构建和 Lean 环境导出审计，
同时核验最终定理的传递公理、定理/合同类型和关系定义，不只用文本搜索判断信任边界。

## 4. 强制 Mutation

至少覆盖：

1. `pc_after` 差异；
2. 写回寄存器编号差异；
3. 写回值差异；
4. trap 状态差异；
5. trace 长度或终止状态差异。

每个 mutation 必须产生非零退出码，并在报告中定位第一个不一致字段。

实现见 `crates/diff-test/src/mutation.rs`。第 5 条的两种观察分属不同比较字段，
因此拆成两类单独注入，实际执行 6 类：

| mutation | 注入内容 | 必须报出的字段 |
|---|---|---|
| `pc_after` | 被测指令提交的下一个 PC 加 2 | `pc_after` |
| `register_index` | 写回换到另一个非 `x0` 寄存器 | `register_writes` |
| `register_value` | 写回值翻转最低位 | `register_writes` |
| `trap` | 反转提交的 trap 标志 | `trap` |
| `trace_length` | 丢掉最后一个提交事件 | `trace_length` |
| `termination` | 换成另一个终止类别 | `termination` |

三条使这些结果算作证据的约束：

- mutation 施加在**真实记录**的 CKB-VM trace 上，并与同一程序的**真实** Sail
  trace 比较，因此被测的是出货路径而不是一对手写 trace；
- 未被 mutation 的原始比较必须先通过；baseline 不通过的案例不产出 mutation
  结论，而是记入 `baseline_failures` 并使整轮失败；
- 报出的第一个不一致字段必须正是被注入的字段，否则记入 `mislocated` 并失败。

不适用的 mutation（例如给一条不提交任何寄存器写的 trace 注入寄存器差异）必须
带原因逐条打印，不能静默跳过；任何一类在整个语料中从未被注入并定位，都判定
失败，因为那是语料缺口而不是通过。

## 5. 证明审计

Lean 4 主定理和关键连接层不得包含未说明的 `sorry` 或 `axiom`。

**当前已知的支持库假设与未解决依赖**（不是最终定理的批准 allowlist）：

- Aeneas 的 Lean 支持库包含 4 处 `sorry`：`Aeneas/Std/Slice.lean` 中的
  `core.slice.Slice.get_unchecked` 及其 spec 定理，以及
  `Aeneas/Std/StringIter.lean` 的 `IteratorChars.next`、`IteratorChars.fold`。
  ADD 的读取使用有 body 的 `Slice.index_usize`。不能仅凭这个直接调用就预先
  排除未来证明经其他引理依赖 `sorryAx`；最终定理必须检查传递依赖。
- 旧原始源码模型含 63 个 `axiom`，包括显式 opaque 的内存、`DefaultMachine` 和
  四个 `bool -> u64` 比较辅助，以及其他外部声明。这一文件级
  数字不等于选中 ADD 的必要假设集合。理由及审计入口见
  `proof/lean/expected_rust_build_status.txt` 与 `proof/lean/reports/ADD_AUDIT.md`。
- `RISCV_GENERAL_REGISTER_NUMBER` 和 `registers.RA` 已分别生成纯定义 32 和 1，
  不再需要常量值/成功前提。`ExtractedConstants.lean` 的值引理及依赖守卫由
  `make proof-imports` 编译；实测只有三个标准逻辑公理，无 `sorryAx`。
- **以下是旧 policy 的历史边界，不是新源码的验收状态**：旧 `DefaultMachine` 到 `DefaultCoreMachine` 的委托是 axiom 而不是被翻译的
  body**。生产实例的 `registers/set_register/pc/update_pc/commit_pc` 都是 opaque。
  需补连接证明或明确读取、局部写回、PC 更新/提交的规律；“ADD 不触及 dyn 字段”
  本身不够证明这些规律。仍依赖它们的定理必须标注为相应前提下的精化。
  [ADD_PREMISES.md](proof/lean/reports/ADD_PREMISES.md) 区分了已编译的方法合同、状态/编码
  条件和 Sail 一步前缀合同；当前 `decoded_add_step` 已使用它们连接双方真实入口，
  合同本身不是其生产实例的证明。历史完整一步有 141 项依赖；当前 patched 基线的
  137 项公理清单见 `AddStepAxioms.lean`，
  不能沿用寄存器叶定理较小的依赖清单。

Rocq/Coq spike 只有在定理由 Rocq kernel 检查通过时才计入额外证明覆盖；GO/NO-GO 报告本身不等于证明。若生成代码依赖公理或抽象接口，必须进入审计 allowlist 并解释影响。

证明还必须满足：

- Rust 定义来自生产执行路径实际调用的纯函数，或另有机器检查的连接证明；
- Sail 定义由固定 Sail 模型和同一配置生成；
- 定理直接引用双方生成物，不引用手写第三份指令语义；
- 记录状态关系、前提、源函数、生成函数、工具版本和 theorem 名称。
- 对最终 theorem 执行 `#print axioms`，区分标准逻辑公理、外部声明与未证行为规律，
  同时审计 theorem 的显式参数。报告中的合法输入前提不能直接假设待证明的 ADD
  结果；应证明两侧成功及关系保持，包括 CKB 外层 Aeneas Result 与内层 VM Result。

## 6. Artifact 与 Mismatch

新运行报告和 artifact 使用 schema 3。`ckb_vm_commit` 只表示上游锚点，修改版身份须读取
`ckb_vm_source_baseline` 的 baseline ID、补丁/源码树/manifest 哈希；校验失败时该字段为 null，
CI 不接受缺失身份。该字段核验的是当前源码 checkout，不是运行中二进制的构建证明。
旧 schema 2 artifact 仍可重放输入，但不能据此补认新源码身份。新 proof-check policy
已绑定修改版来源及正式 wrapper 合同，运行状态以本次验收报告为准。

`--artifact-dir` 为每个案例写一份 JSON（`crates/diff-test/src/artifact.rs`），
包含 schema 版本、案例身份与 seed、双方 commit、模拟器版本、合并配置 SHA-256、
初始状态、双方规范化事件、比较结果与首个不一致字段、原始 88 字节 v1 RVFI-DII 包，
以及两条重放命令。`--replay <artifact>` 只依赖 artifact 本身，不依赖语料生成器；
artifact 中的十六进制程序与记录的案例不一致时直接报错，不会静默重放别的程序。

`--mutate` 另外写出 `artifacts/corpus/mutations.json`：schema 版本、环境、seed、
逐条 mutation 结果、逐类覆盖统计，以及重放整轮 mutation 的单条命令。

`--json` 在所有模式下输出同一个顶层信封（`schema_version`、`mode`、`seed`、
`terminal_policy`、`environment`、`results`、`mutations`、`summary`），CI 因此只
需要读一种形状；`summary.passed` 与进程退出码同源。

自动分类只产出 `match`、`unclassified_mismatch`、`runner_error` 与 `unsupported`。
把 mismatch 判成 CKB 候选缺陷、配置差异还是 adapter 缺陷仍然是人工判断。
本轮新增[最小化工具与真实 trap 差异记录](docs/release/MISMATCH_MINIMIZATION.md)：
按长度穷举原输入的非空有序子序列，重新执行两端并保留观察特征；预算耗尽或执行错误
不报告最小化成功。它不自动确认根因，不将 unsupported 差异转为 PASS。

每个运行至少记录：

- CKB-VM commit、sail-riscv commit、sail-riscv 模型版本；
- 构建工具链：`rustc`、`cargo` 与 Sail 编译器版本。注意 `sail_model_version` 是
  模拟器报告的 sail-riscv 模型发布号，与 `sail_compiler` 是两个不同的版本与两个
  不同的 pin；
- ISA 配置哈希；
- 测试 ID、随机 seed 和初始状态；
- 双方规范化事件；
- 第一个不一致字段；
- 原始 Sail 数据或其路径；
- mismatch 分类与重放命令。

发现 mismatch 可以是有效结果；错误返回 PASS、吞掉差异或无法重放才是验收失败。差异应分类为 CKB 候选缺陷、配置/版本差异、adapter 缺陷、unsupported 或待分类。

注入路径的 CKB-VM ISA 为 `ISA_IMC | ISA_B`，与 Sail 配置的
`rv64imcb_zca_zba_zbb_zbc_zbs` 对齐。**不包含 `ISA_MOP`**：开启它会让
`DefaultDecoder` 转而使用 `decode_mop`，向前读取 `pc + 4`、`pc + 8`、`pc + 12`
以融合多条指令。位置式注入下这些地址上是上一步残留或从未写入的字节，即解码器会
读到不属于当前注入流的内容；一旦融合命中，CKB 侧一步会退休多条指令，而 Sail 侧
一步只退休一条。这不是"少一个扩展"的记录差异，而是两侧对"一步"的定义会不一致。

## 7. 保证边界

运行时差分只说明固定版本和当前语料中的有限输入一致。注入差分另有三条边界：
两端只比较提交效果，因此“写回寄存器已有值”这类不改变架构状态的写在两端都不可
观察；RVFI-DII 不从内存取指，CKB 侧镜像在每步前把指令写到当前 PC，所以这不是对
取指路径的测试；缺少 CKB 侧观察的指令（load/store/AMO/SYSTEM）被拒绝执行而不是
被比较。Lean 4 定理只说明 ADD 在列出前提下满足精化关系。Rocq/Coq spike 只说明该后端路线的可行性，除非另有 kernel 检查通过的定理。

本项目不证明完整 CKB-VM，也不覆盖 ASM/JIT、VERSION0/1、load/store 完整内存语义、MOP、A、ECALL/syscall、cycle accounting、并发/原子模型或整条 CKB 链安全性。

## 8. 持续集成

以下描述当前工作树中的 `.github/workflows/ci.yml` 配置，不是本候选的远端执行凭证。
配置分两层：

- `fast`：在 `main` 分支 push、pull request、schedule 或手动触发时安排运行。只初始化 `deps/ckb-vm`（Rust workspace
  的 path 依赖），执行 `make check` 与 `make test`，不需要 Sail 模拟器。
- `differential`：在相同触发下安排运行，但依赖 `fast` 成功，需要固定版本的 Sail 模拟器。
  模拟器构建按 sail-riscv 的 submodule commit 缓存；未命中时冷构建，不跳过。
  缓存 key 由 submodule commit、Sail 版本和构建脚本哈希组成。

差分层不能因为缓存未命中而跳过：改动比较器或 mutation 逻辑的 PR 如果只跑快速
检查就变绿，那是一个假信号；定时任务也顶替不了，因为 `schedule` 事件运行的永远
是默认分支，不会验证 PR 的 head commit。定时任务的作用只是捕捉没有 commit 触发
的漂移（上游发布移动、缓存过期、runner 镜像变化）。

Rust 工具链由 `rust-toolchain.toml` 固定；Sail 编译器按固定 commit 从源码构建。
CI 在编译器缓存未命中时安装 OPAM、创建 switch 并运行 `build_sail.sh`，不是安装
同版本号的发布二进制；后者不能替代本项目固定的源码版本。

`differential` 依次执行 `make verify-env`、`make verify-dii`，再产出一份
`artifacts/report.json` 并用 `jq` 重新校验：`summary.passed`、`summary.failures`、
每一类 mutation 的 `located` 计数，以及 `environment` 中的 rustc、cargo、Sail
编译器、双方 commit 与配置哈希是否都存在 —— 命令本身已经用退出码表达成败，这
一步是为了让将来改动退出码也无法把失败变成绿灯，也让一份说不出自己工具链的报告
不能充当证据。

工作流定义了 artifact 上传（每案例 JSON、mutation 报告、总报告）和后续下载/检查步骤；
正常执行到检查步骤时，比对总报告字节一致，并用下载到的一个案例 artifact 执行重放。
“CI artifact 能在本地用一条命令重放”是关于上传出去的字节的断言，所以要用那些
字节验证。步骤存在不表示某次运行已执行到该步，更不代表 32 个案例均从下载包重放。
最近保存的[只读来源核验](docs/release/CI_READINESS.md)发生于 2026-09-13 05:12 UTC：
当时本地 HEAD 的运行数为 0，查询到的成功运行属于旧提交；该次核验未下载 artifact。
未查询此后远端状态，不能把该历史观察写成当前远端仍然没有新运行。当前候选的完整
Lean/Rocq/release CI 和真实下载重放证据仍未提供。
