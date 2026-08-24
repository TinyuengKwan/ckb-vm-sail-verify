# Verification Guide

本文区分“当前可运行基线”和“六周 MVP 将交付的验收接口”。不存在的命令不会被描述成已经完成。

## 1. 当前版本基线

- CKB-VM：`1ffba3977da9dcdef8092e9ab1fd2516b27ec939`
- CKB-VM crate：0.24.0
- Rust：MSRV 1.95；当前 foundation 验证版本 1.97.1
- Sail compiler：0.20.2
- sail-riscv：0.13.1，commit `27224ccb2290f022e46213c05b3e72e8a9ea635e`
- RVFI-DII 线格式：v1，88 字节；`crates/sail-runner/tests/fixtures/sail-rvfi-dii-v1.hex`
  是从该 commit 捕获的实包，默认测试套件解析它，端到端测试再核对它没有过期
- ISA：`rv64imcb_zca_zba_zbb_zbc_zbs`
- 合并配置 SHA-256：`41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024`

依赖或配置变化属于证据变化，必须重新运行运行时差分、mutation、Lean 4 证明与 Rocq/Coq spike。

Aeneas/Charon、Lean 4 与 Rocq/OPAM 尚未进入当前 foundation 执行门禁；
它们必须在 Week 4 首次生成 Rust 侧定义或检查定理前固定版本，不能沿用浮动最新版。

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
```

当前基线可以构建 Rust workspace、运行单元测试、构建 Sail 模拟器、验证固定环境、
通过 RVFI-DII 完成 CKB-VM 与 Sail 的端到端注入差分，并生成固定配置下的 Sail
Lean/Rocq 模型。模型生成不等于 kernel 编译或等价证明。

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
- `proof-check`、`proof-spike` 与 `audit-release`（Week 4–6）。

直接 ELF 模式得到空 RVFI 流必须返回失败，不能当作空程序或 PASS。

RVFI-DII 会话必须从架构复位态开始，首包不是 `rvfi_order` 0 / `pc` `0x80000000`
时直接报错：上游模拟器只 `accept` 一次，端口竞态下输的一方可能连到别人已经推进
过的模拟器，这种情况必须是错误而不是一条看起来合理的 trace。

## 3. 六周 MVP 验收接口

以下接口是稳定验收面。`verify-smoke` 与 `verify-negative` 已实现并可直接验收；
`proof-check`、`proof-spike` 与 `audit-release` 仍是计划中的接口，只有相应实现
合入后才能按本节验收：

```bash
make verify-smoke
make verify-negative
make proof-check BACKEND=lean
make proof-spike BACKEND=rocq
make audit-release
```

预期语义：

- `verify-smoke`：对 ADD、ADDI、BEQ 的至少 10 个案例完成严格双端比较；
- `verify-negative`：至少 5 类 mutation 全部被检测；
- `proof-check BACKEND=lean`：生成两侧 Lean 4 定义并由 kernel 检查生产关联的 ADD 定理；
- `proof-spike BACKEND=rocq`：重现双侧 Rocq 生成/导入并明确输出 GO 或 NO-GO；
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
