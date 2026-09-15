# CKB-VM Sail Verification

当前生产源码已采用 `ckb-vm-1ffba3977da9-runtime-container-v1`：上游 commit 加固定
容器化补丁，**不是原始 CKB-VM commit 本身**。见[正式源码基线与审计清单](proof/lean/extraction/ADOPTION.md)。
正式 wrapper 合同、最终定理和 137 项审计 policy 已迁移；
`proof-check` 还强制从零编译模型/证明及 Lean 依赖。实际验收证据见 [Week 5 报告](proof/lean/reports/WEEK5_EXIT.md)。

公开 ADD decoder 已通过 47 阶段独立干净复验，并按[限定工具政策](proof/lean/decoder/ADOPTION.md)
接入主门禁，首次集成实跑已通过。它从同一个原始 ADD 字连接双方执行，保留取指/初态边界，
不扩展到 MOP-on 或所有 ISA/configuration。

2026-09-13 更新：上述首次集成属于历史基线；[新正式主工具迁移](docs/release/FORMAL_MAIN_INTEGRATION.md)
已于 06:26 UTC 完成正式门禁，并于 06:29 UTC 通过独立验收：28 个主阶段、287 项测试、
48 个公开阶段和 68 个公开定理。[v10 本地聚合](docs/release/AUDIT_RELEASE.md)于 06:34 UTC 完成，
Lean、runtime、Rust tests、Rocq NO-GO、负测与演示六项验收通过，六类发布义务仍缺失；
这不是 Week6 发布完成，也不扩大指令覆盖。

后续[Week6 案例门槛修正](docs/release/WEEK6_RUNTIME_FLOOR.md)：旧 BEQ 仅 9 项，未满足
每族至少 10 项要求。已补第十个 BEQ 并加强门禁；33 项新 corpus 的完整实跑及独立验收已通过。
主政策仅更新 corpus 来源为 `b5bdc401…`，旧完整 Lean/Rocq 验收保留历史身份。
[该政策下的完整正式链及独立验收](docs/release/FORMAL_FINAL_EXECUTION.md)已于 22:21 UTC 完成：
Lean 28/287/48/68、Rocq 11 阶段 NO-GO；[当前负测/演示及新聚合](docs/release/FINAL_SUPPORT_REFRESH.md)
于 22:35 UTC 完成六项验收、整体仍 incomplete。
[46,651 项正式输出差异说明及复验](docs/release/FORMAL_DELTA_REVIEW.md)已完成；
[新工作树部分验收聚合](docs/release/WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)也已完成：
六项证据接受、工作树部分未完成、五项缺失。后续增量、最终范围及发布义务仍待完成。

用官方 Sail RISC-V 模型验证 CKB-VM 指令语义的工程化项目。项目采用两条相互校验、但不混淆结论的链路：

- 运行时差分：CKB-VM 与 Sail 模拟器输出统一的 RVFI 风格 `CommitEvent`，逐条比较 PC、指令、寄存器写回、内存访问、trap 和终止原因。
- 形式化证明：从生产执行路径抽取可验证的纯 Rust 语义内核，以 Charon/Aeneas → Lean 4 和 Sail → Lean 4 为主证明路径；Rocq/Coq 保留为同后端兼容性 spike。

## 当前状态

运行时差分闭环已经建立并接入 CI（Week 3）。`crates/sail-runner/src/dii.rs`
实现了二进制 RVFI-DII 客户端，`crates/ckb-runner/src/injection.rs` 用同一条指令
流驱动真实 VERSION2 解释器。注入测试采用约定初态（整数寄存器全零、
PC = `0x80000000`），不经过 ELF loader 与平台栈；这不是一般平台 reset 可达性证明。
当前实测的 33 个注入语料案例（ADD 13 / ADDI 10 / BEQ 10）、398 个提交步在两端
逐字段一致，每个案例都可以从自己的 artifact 重放；33 个复制输入也已实际重新执行。

差分本身也被验证过会失败：`crates/diff-test/src/mutation.rs` 把 6 类 mutation
注入真实记录的 trace，共 194 次适用，每一次都必须被检测到并定位到被注入的那个
字段，任何一类在整个语料中没有被覆盖都算失败。仓库中的 CI 配置为两层：快速检查与
差分层均由 PR 触发，差分层依赖快速检查成功；模拟器缓存未命中时安排冷构建而不跳过。
这是工作流定义，不是当前候选的 CI 完成证据；本轮 CI 缺口见
[带时间戳的来源核验](docs/release/CI_READINESS.md)。

上述数字是运行时证据。证明轨已有 Rust/Sail 两侧 Lean 生成物；共同工具链固定为
Lean 4.31.0，双侧导入入口为 `make proof-imports`，实测记录见
[兼容性报告](proof/lean/compat/README.md)。`state_rel` 与 ADD 寄存器层条件性定理
现已实现并由 `make proof-registers` 检查，详见 [证明边界](proof/lean/reports/ADD_REGISTERS.md)。
`make proof-step` 进一步检查 [dispatch/PC 条件性一步精化](proof/lean/reports/ADD_STEP.md)，
直接连接 `execute_production` 与 `try_step`。
`make proof-check BACKEND=lean` 已串联重新生成、来源/公理/显式前提审计及负向测试，
输出条件性验收报告，详见 [proof-check 门禁](proof/lean/reports/PROOF_CHECK.md)。
这不消除剩余合同，也不等于 `audit-release`。

固定配置下的 Sail→Lean 4 与 Sail→Rocq 模型生成入口均已验证可重现，且 **Lean 模型
现在编译通过**(125 个 `.olean`)。`make proof-gen` 在生成之后会真正编译它生成的
Lean 模型并与 `proof/lean/expected_build_status.txt` 的记录双向核对 —— 生成可重现不等于
生成物可用,这两件事在这里是分开检查的。

这一步需要**所列固定 commit 的 Sail 源码构建**(`make sail-compiler`)：这里验收的是
该编译器与固定 sail-riscv 的组合，不是仅凭版本号选取一般发行版。该源码版本与
0.20.2 发行版同号，所以环境检查钉完整版本串，正式门禁另钉二进制与来源身份。Rocq 的双侧
生成/导入 spike 已记录 NO-GO，由 `make proof-spike` 复现；它不提供证明覆盖。

**Rust 侧生成也已建立**(Week 4):`crates/proof-extract` 用普通 Rust 命名生产
提取根 —— 一行调用 `ckb_vm::instructions::execute`,机器类型 import 自 ckb-runner
的 `InjectedMachine`,和差分驱动的是同一个类型。Charon 从这个根提取生产调用图,
Aeneas 译成 Lean 4,`make proof-gen-rust` 生成并编译。新基线的生成结果与已检查的
隔离模型逐字一致；`ckb_vm::instructions::common::add` 出现在生成物里是因为
生产**到达**它。

模型能编译不等于完成精化：现有定理已连接 GPR、PC/dispatch 与正常退休路径，
生产 wrapper 委托已证明；原内部定理保留 decoded-input 前提，新公开入口定理则在指定配置下
从原始 ADD 字推出两侧解码。Sail 前缀、取指和初态关系仍有明确边界。
双方导入和定理工程位于
`proof/lean/theorems/`；生成脚本统一工具链并自动应用已记录的 Sail 类型作用域
兼容补丁，不修改指令函数体。被显式设为 opaque
的部分(内存、`MachineRuntime` 动态字段容器、四个 `bool -> u64` 比较辅助)逐条
记录在 `proof/lean/expected_rust_build_status.txt`。寄存器数量 32 与 RA 1 已补齐真实
定义并检查值；已证 wrapper 委托及剩余状态/解码合同见 [ADD 剩余前提](proof/lean/reports/ADD_PREMISES.md)。完整边界见
[ADD 依赖与定理审计](proof/lean/reports/ADD_AUDIT.md)。

生成物位于忽略目录，包含 Rust/Sail 翻译；统一物理内存及平台初始化尚未关闭，
不能将其计作完整指令的 `proved` 覆盖。
已新增 [具体联合前提见证](proof/lean/reports/ADD_NONVACUITY.md)：Sail 合同在同一状态链上成立，
双侧实例以 Rust seed 为输入；该见证本身不证明 reset 可达性或 `Nonempty Machine`。
同码 ADD 解码对应另见[公开入口定理](proof/lean/decoder/toolchain/full-entry/OuterPublicStep.lean)。

只有同时满足下列条件，某条指令才能标记为 `proved`：

1. 生产 CKB-VM 路径调用被翻译的纯 Rust 语义函数，或另有机器检查的连接证明。
2. 定理直接引用 Sail 生成定义，而不是手写的第二份 RISC-V 规范。
3. Lean 4 定理使用明确的状态关系与适用前提，且没有未说明的 `sorry`/`axiom`。
4. 对应运行时差分包含可失败的负面注入测试。

Rocq/Coq spike 的 GO/NO-GO 结果本身只表示工具链兼容性；只有 Rocq
kernel 检查通过且满足上述生产连接要求的定理，才能额外计入 `proved`。

## 架构

```text
CKB-VM interpreter ──► CommitEvent ◄── Sail --trace-rvfi / RVFI-DII
                              │
                       diff + fuzz + replay

production Rust execution path ─────────► Charon/Aeneas ──► Lean 4
Sail RISC-V subset ─────────────────────── Sail Lean ──────► Lean 4
                                                        │
                                                 refinement theorem

Rust/Sail generated definitions ──► Rocq/Coq compatibility GO/NO-GO
```

详细设计见：

- `docs/architecture.md`
- `docs/methodology.md`
- `VERIFICATION.md`
- `docs/plan/overview.md`

## 快速开始

```bash
# 初始化固定版本的 CKB-VM 与 Sail RISC-V 源码
git submodule update --init --recursive
make ckb-baseline-apply  # 只在精确、干净的上游源码上应用受审补丁；不提交 Git commit

# 从源码构建固定 commit 的 Sail 编译器（同版本号的发行版不能代替受审身份）
make sail-compiler
export PATH="$HOME/.local/share/sail-src/bin:$PATH"

# Rust foundation
make check
make test

# 构建模拟器、合并配置并核对当前 foundation 工具链
make verify-env

# 运行 RVFI-DII 注入语料并写出可重放 artifact
make verify-smoke

# mutation 矩阵 + 负向端到端测试（证明比较器仍然会失败）
make verify-negative

# 两者的合并入口，也是 CI 调用的单条命令
make verify-dii

# 单个案例、指定 seed、JSON 报告
cargo run -p ckb-vm-sail-diff -- --corpus --case add-signed-overflow --json

# 只用 artifact 重放，不依赖语料生成器
cargo run -p ckb-vm-sail-diff -- --replay artifacts/corpus/add-signed-overflow.json

# 对单个 ELF 做运行时差分（上游锁定版本在直接 ELF 模式下不产生 RVFI，
# 因此这条路径当前必然明确失败，而不是返回空 PASS）
cargo run -p ckb-vm-sail-diff -- \
  --elf path/to/test.elf \
  --sail-bin deps/sail-riscv/build/c_emulator/sail_riscv_sim \
  --sail-config sail-model/build/ckb_vm_config.json

# 历史单独生成/构建入口：使用各自固定工具，不代替当前正式主门禁。
# 它们会写共享生成目录；不要与 proof-check/proof-spike 并发运行。
# 生成成功不等于证明通过。
make proof-gen BACKEND=lean
make proof-gen BACKEND=rocq

# Rust 侧生产调用图生成与 Lean 编译检查
make proof-gen-rust

# 复现 Rocq 双侧路线的 NO-GO（不是证明通过）
make proof-spike

# 只跑编译检查（对照 proof/lean/expected_build_status.txt 的双向核对）
make proof-build BACKEND=lean

# 共同 Lean 4.31.0 下构建双方库并完成双侧 import（不是 ADD 定理门禁）
make proof-imports

# 条件性 ADD 一步定理、依赖守卫和边界回归
make proof-step
```

当前正式 `make proof-check BACKEND=lean` 选择 `rebuilt-main-v1`，不是上面的历史 Rust
生成脚本。它需要已准入的 v2 输入包及包外私有 Rust/Lean、Aeneas OPAM、Sail 安装；
这些安装与报告位于 Git 忽略目录，**普通 clone 不会带来这些前提**。
新 clone 的完整工具分发/安装和文档复现仍属 Week6 未关闭条款，不能靠更改政策哈希跳过。
具体已实跑范围与当前安装身份见 [正式迁移记录](docs/release/FORMAL_MAIN_INTEGRATION.md)
和 [Verification Guide](VERIFICATION.md)。

Rust 工具链由 `rust-toolchain.toml` 固定为 1.97.1（`Cargo.toml` 声明的 MSRV
仍是 1.95）；每份 artifact 记录 `rustc`、`cargo` 与 Sail 编译器版本，因此一份
证据可以说出是哪套工具链产生的。

当前生产实现以上游 `deps/ckb-vm` submodule 的
`1ffba3977da9dcdef8092e9ab1fd2516b27ec939` 为锚点，另含受审 runtime-container 补丁，
不是该原始 commit 本身。Rust MSRV 为 1.95，当前 foundation 基线在 Rust 1.97.1
复核通过。更新 submodule 属于证据变更，必须重新运行差分测试并生成证明产物。

## 项目结构

```text
crates/
  core/          后端无关的 CommitEvent、严格比较与注入程序支持子集
  ckb-runner/    CKB-VM VERSION2 adapter 与 DII 镜像
  sail-runner/   Sail 进程、RVFI parser 与二进制 RVFI-DII 客户端
  diff-test/     指令编码、注入语料、mutation 矩阵、可重放 artifact、CLI 与 JSON 报告
  proof-extract/ 证明轨的生产提取根（普通 Rust，一行调用生产解释器）
deps/
  ckb-vm/        被验证的生产 Rust 实现
  sail-riscv/    权威 Sail RISC-V 模型
patches/
  ckb-vm/        受审的 runtime-container 源码补丁，由 make ckb-baseline-apply 应用
proof/
  lean/          Lean 4 主证明入口：theorems/ 定理、decoder/ 解码对应层、
                 audit/ policy、extraction/ 源码基线、reports/ 各阶段历史报告
  rocq/          Rocq/Coq 生成、导入与兼容性 spike
docs/            架构、方法、覆盖、语义缺口与 Week 1–6 计划
artifacts/       失败案例格式；大体积本地生成物默认忽略
sail-model/
  ckb_vm_config.json 叠加到 sail-riscv 默认配置的 override
.github/
  workflows/ci.yml 分层 CI：每次 PR 跑快速/差分作业，另有缓存和定时回归；尚非完整发布链
scripts/
  build_*/prepare_*/verify_*   工具链与模拟器构建、环境核验
  generate_*/configure_*       两侧证明模型生成与 Lake 工程配置
  check_*/public_decoder_*     证明门禁及其子门禁（路径与哈希被 policy 固定）
  tests/                       门禁的单元与负向测试
  probes/                      被门禁引用的边界探针
  experiments/                 不被门禁引用的翻译器实验与回归审计脚本
```


证明轨翻译的是**生产代码本身**，不为证明改写指令语义：提取根在
`crates/proof-extract`，一行调用 `ckb_vm::instructions::execute`。Week 4 记录的
结论是指令函数体不需要上游 patch；Week 5 为了让 `DefaultMachine` 可提取，引入了
`patches/ckb-vm/runtime-container.patch`（只把三个 `dyn` 字段搬进私有结构体，
`CoreMachine` 实现逐字未变），其审查与等价边界见
[源码基线采用决议](proof/lean/extraction/ADOPTION.md)。
早期那个手写的 `semantics.rs` 原型已删除：它是第二份手写 RISC-V 语义，
`VERIFICATION.md` §5 明确规定这种东西不能计入证明证据，留在树里只会误导。
注意：锁定的上游 sail-riscv 只有在 RVFI-DII socket 模式下才真正产生 RVFI 包，
所以差分闭环走的是指令注入而不是 ELF；直接 ELF 模式得到的空 RVFI 流仍然被明确
拒绝。注入意味着 Sail 不从内存取指，CKB 侧镜像的做法是在每一步之前把该条指令写
到当前 PC，因此这不是对取指路径的测试。load/store、ECALL 等缺少 CKB 侧观察的指令
被 `core::program::validate_program` 拒绝，而不是与缺失字段比较。完整边界见
`docs/semantic-gaps.md`。

## 当前六周 MVP 范围

当前 Spark Validation Sprint 固定为 VERSION2、单 hart、无异步中断：

1. 运行时差分强制覆盖 `ADD`、`ADDI`、`BEQ`，至少 10 个可重放案例；
2. `MUL` 是运行时差分 stretch goal；
3. Lean 4 强制完成一条生产关联的 `ADD` 等价定理；
4. Rocq/Coq 强制交付双侧生成、导入和状态桥接的 GO/NO-GO 证据；
5. 至少 5 类故障注入必须被比较器识别。

load/store、MOP、A 扩展、ECALL、cycle accounting、页权限、VERSION0/1
和 ASM/JIT 都不在本轮成功标准中。它们保留在 post-MVP 路线图中，并且在
相应观察器、状态关系或连接证明完成前保持 `unsupported`。

## 非目标

- 不把有限测试宣传成形式化证明。
- 不把手写 Coq/Rocq 模型宣传成生产 Rust 的证明。
- 不通过截断到较短 trace、吞掉执行错误或省略内存事件来制造 PASS。
