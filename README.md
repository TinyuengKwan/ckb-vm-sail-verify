# CKB-VM Sail Verification

用官方 Sail RISC-V 模型验证 CKB-VM 指令语义的工程化项目。项目采用两条相互校验、但不混淆结论的链路：

- 运行时差分：CKB-VM 与 Sail 模拟器输出统一的 RVFI 风格 `CommitEvent`，逐条比较 PC、指令、寄存器写回、内存访问、trap 和终止原因。
- 形式化证明：从生产执行路径抽取可验证的纯 Rust 语义内核，以 Charon/Aeneas → Lean 4 和 Sail → Lean 4 为主证明路径；Rocq/Coq 保留为同后端兼容性 spike。

## 当前状态

运行时差分闭环已经建立（Week 2）。`crates/sail-runner/src/dii.rs` 实现了二进制
RVFI-DII 客户端，`crates/ckb-runner/src/injection.rs` 用同一条指令流驱动真实
VERSION2 解释器，双方都从架构复位态（整数寄存器全零、PC = `0x80000000`）出发，
因此比较不再经过 ELF loader 与平台栈。当前 32 个注入语料案例、395 个提交步在
两端逐字段一致，每个案例都可以从自己的 artifact 重放。

这只是运行时证据，不是形式化验证：证明轨仍然停在 Sail 侧模型生成，没有 Rust
侧生成、状态桥接或等价定理。

固定配置下的 Sail→Lean 4 与 Sail→Rocq 模型生成入口均已验证可重现；
生成物位于忽略目录，仍不包含 Rust 翻译、状态桥接或等价定理，不能计入
形式化证明覆盖。

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

production-called pure Rust semantics ──► Charon/Aeneas ──► Lean 4
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

# Rust foundation
make check
make test

# 构建模拟器、合并配置并核对当前 foundation 工具链
make verify-env

# 运行 RVFI-DII 注入语料并写出可重放 artifact
make diff-corpus

# 语料 + 负向端到端测试（证明比较器仍然会失败）
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

# 生成 Sail 侧证明后端模型；这一步本身不建立等价定理
make proof-gen BACKEND=lean
make proof-gen BACKEND=rocq
```

当前生产实现固定为 `deps/ckb-vm` submodule 的
`1ffba3977da9dcdef8092e9ab1fd2516b27ec939`（拉取时为远程 `develop`
最新 HEAD），Rust MSRV 为 1.95，当前 foundation 基线在 Rust 1.97.1
复核通过。更新 submodule 属于证据变更，必须重新运行差分测试并生成证明产物。

## 项目结构

```text
crates/
  core/          后端无关的 CommitEvent、严格比较与注入程序支持子集
  ckb-runner/    CKB-VM VERSION2 adapter 与 DII 镜像；含临时 extraction scaffold
  sail-runner/   Sail 进程、RVFI parser 与二进制 RVFI-DII 客户端
  diff-test/     指令编码、注入语料、可重放 artifact、CLI 与 JSON 报告
deps/
  ckb-vm/        被验证的生产 Rust 实现
  sail-riscv/    权威 Sail RISC-V 模型
proof/
  lean/          必须完成的 Lean 4 主证明入口
  rocq/          Rocq/Coq 生成、导入与兼容性 spike
docs/            架构、方法、覆盖、语义缺口与 Week 1–6 计划
artifacts/       失败案例格式；大体积本地生成物默认忽略
sail-model/
  ckb_vm_config.json 叠加到 sail-riscv 默认配置的 override
scripts/
  prepare_sail_config.sh
  generate_proof_model.sh
  verify_environment.sh
```


`crates/ckb-runner/src/semantics.rs` 仍是临时翻译原型。只有在生产
CKB-VM 路径实际调用同一函数，或存在机器检查的连接证明后，它才可能成为
证明证据；最终生产语义位置由 CKB-VM 上游 patch/PR 决定。
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
