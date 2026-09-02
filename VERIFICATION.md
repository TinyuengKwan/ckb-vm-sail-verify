# Verification Guide

本文区分“当前可运行基线”和“六周 MVP 将交付的验收接口”。不存在的命令不会被描述成已经完成。

## 1. 当前版本基线

- CKB-VM：`1ffba3977da9dcdef8092e9ab1fd2516b27ec939`
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

**为什么 Sail 是源码构建而不是发布版**：sail-riscv 的 Lean target 需要比任何已发布
Sail 都新的编译器。在上一版基线（sail-riscv `27224cc` + 发布版 0.20.2）下，生成的
Lean 模型在第 10/131 个目标失败于 `unknown namespace LeanRV64D.Defs`。上游本身就把
两个 target 跑在两个不同的 Sail 上（`compile-lean.yml` 用 `sail-version: "latest"`，
而 `cmake/sail_required_version.txt` 为 C 模拟器钉 0.20.2），因此从未测过我们钉的那
个组合。本项目改为**一个** Sail 同时服务两个 target 并按 commit 钉死，两个 pin 必须
一起移动。

这次移动的实测结果：**物化配置 SHA-256、ISA 串、RVFI-DII 线格式与全部差分结果均未
改变**——32/32 语料、395 提交步、188 次 mutation、10 个端到端测试（含 packet fixture
与实时模拟器的一致性检查）在新基线上全部通过。改变的只是模拟器二进制与 Sail 构建。

证明轨工具链已固定（Rust 侧定义已生成，见 §2）：

- Charon：`0.1.247 (89ac118194b978d8cf753222c19f313521377aa0)`
- Aeneas：`aeneas nightly-2026.09.01-379890b`
- Lean（Sail 侧模型）：`leanprover/lean4:v4.29.0`
- Lean（Rust 侧模型 / Aeneas 库）：`leanprover/lean4:v4.31.0`，依赖 mathlib4

`scripts/generate_rust_model.sh` 在生成前核对 Charon/Aeneas 的完整版本串，不符即失败。
两侧 Lean 工具链版本**不同**，因此 Week 5 的精化定理无法直接放进任一现有工程，
需要先解决工具链统一或跨工程引用；这是已知的下一个结构性问题。

Rocq/OPAM 尚未进入门禁。

## 2. 当前可运行基线

```bash
git submodule update --init --recursive
make check
make test
make verify-env
make verify-smoke
make verify-negative
make proof-gen BACKEND=lean
make proof-gen BACKEND=rocq
make proof-build BACKEND=lean
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

**Week 4 要求记录的结论:提取不需要修改 `deps/ckb-vm`，因此本轮不需要上游
patch 或 PR。** 原计划设想的是先重构生产代码去调用抽出的纯内核；实测表明
Charon/Aeneas 直接吃得下生产形状，那次重构因此没有发生 —— 被翻译的就是跑差分
的那份代码，不存在"重构是否改变了被验证对象"的问题。早期那个手写的
`crates/ckb-runner/src/semantics.rs` 原型已删除：它是第二份手写 RISC-V 语义，
按 §5 不能计入证明证据，留在树里只会被误当成提取目标。生成物同样要过编译检查（记录在
`proof/lean/expected_rust_build_status.txt`），当前状态 **ok**：279 个 `def`、
65 个 `axiom`。exit gate 要求的"重新生成不需要编辑生成文件"已实测——连跑两次逐
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

模型能编译**不等于**存在定理。Rust 侧生成、状态桥接与 ADD 精化定理都还没有。

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

`make verify-smoke` 运行 32 个注入案例（ADD 13、ADDI 10、BEQ 9，共 395 个提交
步），并把每个案例的 artifact 写到 `artifacts/corpus/`。

`make verify-negative` 的语义：

- `cargo test -p ckb-vm-sail-diff -- --ignored` 运行 10 个需要真实模拟器的端到端
  测试，其中 6 个是负向的：指令流分歧、末尾事件缺失、trap 分歧、引擎失败、空
  mutation 矩阵不通过，以及完整 mutation 矩阵必须逐类被定位；另有压缩指令宽度
  规范化、packet fixture 与实时模拟器输出的一致性检查，以及 16 个并发会话不会
  因为 RVFI-DII 端口竞态而失败 —— flaky 的差分在 CI 里与“真实差异时隐时现”
  无法区分；
- `cargo run -p ckb-vm-sail-diff -- --corpus --mutate` 运行 §4 的 mutation 矩阵，
  把 188 个 mutation 应用到真实记录的 trace 上，并把结果写到
  `artifacts/corpus/mutations.json`。

`make verify-dii` 是两者的合并入口，也是 CI 调用的单条命令。

当前尚未完成：

- 生产路径对纯 Rust `ADD` 语义的调用连接；
- Rust 侧 Lean 4 生成、双方导入和 `ADD` 定理；
- Rocq/Coq 的 Rust 侧生成、双方导入、状态桥接与 GO/NO-GO 报告；
- `proof-check` 与 `audit-release`（Week 5–6）。

直接 ELF 模式得到空 RVFI 流必须返回失败，不能当作空程序或 PASS。

RVFI-DII 会话必须从架构复位态开始，首包不是 `rvfi_order` 0 / `pc` `0x80000000`
时直接报错：上游模拟器只 `accept` 一次，端口竞态下输的一方可能连到别人已经推进
过的模拟器，这种情况必须是错误而不是一条看起来合理的 trace。

## 3. 六周 MVP 验收接口

以下接口是稳定验收面。`verify-smoke`、`verify-negative` 与 `proof-spike` 已实现
并可直接验收；`proof-check` 与 `audit-release` 仍是计划中的接口，只有相应实现
合入后才能按本节验收：

```bash
make verify-smoke
make verify-negative
make proof-check BACKEND=lean
make proof-spike
make audit-release
```

预期语义：

- `verify-smoke`：对 ADD、ADDI、BEQ 的至少 10 个案例完成严格双端比较；
- `verify-negative`：至少 5 类 mutation 全部被检测；
- `proof-check BACKEND=lean`：生成两侧 Lean 4 定义并由 kernel 检查生产关联的 ADD 定理；
- `make proof-spike`：重现双侧 Rocq 生成/导入并核对已记录的 GO/NO-GO；
- `audit-release`：检查版本、哈希、覆盖、重放 artifact、占位符与保证边界。

任一 runner error、空 trace、事件长度差异、字段差异或终止差异都不能返回 PASS。

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

**当前已知的信任基与 allowlist**（实测，非推断）：

- Aeneas 的 Lean 支持库在构建中报告 4 处 `sorry`：`Aeneas/Std/Slice.lean:359`
  （`core.slice.Slice.get_unchecked`）、同文件 615（其 spec 定理），以及
  `Aeneas/Std/StringIter.lean:12,15`。ADD 路径用的是 `Slice.index_usize`，
  它与其 spec **不含** `sorry`。这四处在信任基里但不在 ADD 定理会走的路径上；
  任何触及它们的定理必须显式声明。
- Rust 侧生成物含 65 个 `axiom`，全部来自被显式设为 opaque 的部分：内存实现、
  `DefaultMachine`（因 `dyn` 无法翻译）、以及四个 `bool -> u64` 比较辅助函数。
  理由逐条记录在 `proof/lean/expected_rust_build_status.txt`。
- **`DefaultMachine` 到 `DefaultCoreMachine` 的委托是 axiom 而不是被翻译的
  body**，这是生产机器与被提取定义之间唯一未被提取覆盖的一环。ADD 不触及它承载
  的 `dyn` 字段，但这一点必须作为前提写进定理，不能默认成立。

Rocq/Coq spike 只有在定理由 Rocq kernel 检查通过时才计入额外证明覆盖；GO/NO-GO 报告本身不等于证明。若生成代码依赖公理或抽象接口，必须进入审计 allowlist 并解释影响。

证明还必须满足：

- Rust 定义来自生产执行路径实际调用的纯函数，或另有机器检查的连接证明；
- Sail 定义由固定 Sail 模型和同一配置生成；
- 定理直接引用双方生成物，不引用手写第三份指令语义；
- 记录状态关系、前提、源函数、生成函数、工具版本和 theorem 名称。

## 6. Artifact 与 Mismatch

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

`.github/workflows/ci.yml` 分两层，因为两层的成本差三个数量级：

- `fast`：每个 push 和 pull request 都跑。只初始化 `deps/ckb-vm`（Rust workspace
  的 path 依赖），执行 `make check` 与 `make test`，不需要 Sail 模拟器。
- `differential`：需要固定版本的 Sail 模拟器，**同样每个 pull request 都跑**。
  模拟器构建按 sail-riscv 的 submodule commit 缓存；未命中时冷构建，不跳过。
  缓存 key 由 submodule commit、Sail 版本和构建脚本哈希组成。

差分层不能因为缓存未命中而跳过：改动比较器或 mutation 逻辑的 PR 如果只跑快速
检查就变绿，那是一个假信号；定时任务也顶替不了，因为 `schedule` 事件运行的永远
是默认分支，不会验证 PR 的 head commit。定时任务的作用只是捕捉没有 commit 触发
的漂移（上游发布移动、缓存过期、runner 镜像变化）。

Rust 工具链由 `rust-toolchain.toml` 固定；Sail 编译器按上游做法安装固定版本的
二进制发布，不在 CI 里构建 opam switch。

`differential` 依次执行 `make verify-env`、`make verify-dii`，再产出一份
`artifacts/report.json` 并用 `jq` 重新校验：`summary.passed`、`summary.failures`、
每一类 mutation 的 `located` 计数，以及 `environment` 中的 rustc、cargo、Sail
编译器、双方 commit 与配置哈希是否都存在 —— 命令本身已经用退出码表达成败，这
一步是为了让将来改动退出码也无法把失败变成绿灯，也让一份说不出自己工具链的报告
不能充当证据。

所有 artifact（每案例 JSON、mutation 报告、总报告）都会上传，然后**从上传结果
下载回来**：比对总报告字节一致，并用下载到的那份案例 artifact 执行一次重放。
“CI artifact 能在本地用一条命令重放”是关于上传出去的字节的断言，所以要用那些
字节验证。
