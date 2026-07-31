# Verification Architecture

## 1. 设计原则

项目必须区分三种不同强度的证据：

| 证据 | 能说明什么 | 不能说明什么 |
|---|---|---|
| 单元测试 | 本地函数在给定样例上工作 | 两个 VM 等价 |
| 差分测试 | 两个独立实现对已执行输入一致 | 所有输入一致 |
| 精化证明 | 在明确前提下，所有输入保持关系 | 前提之外的行为 |

所有报告必须使用这三个名称，不使用笼统的“verified”覆盖不同证据。

## 2. 双轨架构

### 2.1 运行时差分轨

双方输出统一的提交事件：

```rust
CommitEvent {
    order,
    instruction,
    pc_before,
    pc_after,
    register_writes,
    memory,
    trap,
    halt,
}
```

CKB-VM 适配器必须包住真实 VERSION2 Rust interpreter。Sail 适配器优先消费 RVFI-DII 二进制包；foundation 阶段允许解析 `--trace-rvfi`，但 parser 必须有固定 fixture 测试。

比较器遵循以下规则：

- 比较完整长度，不能只比较公共前缀。
- execution error、step limit、正常退出是不同终止状态。
- x0 写回统一规范化为无写回。
- memory 观察缺失不能自动视为相等。
- mismatch 保存 seed、ELF、双方事件和工具版本，允许重放。

### 2.2 形式化证明轨

证明目标不是直接翻译整个 CKB-VM。首先从生产路径抽取一个无 I/O、无 trait object、无全局状态的纯函数层：

```rust
fn execute_pure(
    instruction: DecodedInstruction,
    state: ArchitecturalState,
) -> Result<ArchitecturalState, SemanticsError>;
```

内存指令扩展为显式效果：

```rust
StepEffect {
    register_write,
    next_pc,
    memory_request,
}
```

生产解释器执行这个效果；证明器翻译同一个函数。这样消除“Rust 一份、手写证明模型一份”的双重实现。

## 3. 后端选择

当前六周 MVP 的强制主路线：

```text
Rust pure kernel ──Charon/Aeneas──► Lean 4
Sail model ───────────Sail Lean───► Lean 4
```

理由是 Aeneas 的 Lean 支持比直接 Coq/Rocq 提取成熟，同时 sail-riscv 已维护 Lean 生成目标。`ADD` 的生产关联精化定理必须在 Lean 4 中由 kernel 检查通过。

Rocq/Coq 保留为兼容性与原 Issue #190 路线的可行性 spike：

```text
Rust pure kernel ──Aeneas/Rocq-of-Rust──► Rocq
Sail model ─────────────Sail Coq backend► Rocq
```

Rocq spike 必须对同一个 `ADD` 纯 Rust 内核和 Sail 配置给出双侧生成、导入、状态桥接的 GO/NO-GO 证据。GO 后完成的 Rocq 定理只有经 kernel 检查才能计入额外证明覆盖；NO-GO 必须附最小复现，不能冒充证明完成。

当前运行时 MVP 强制覆盖 `ADD`、`ADDI`、`BEQ` 的至少 10 个可重放案例，`MUL` 为 stretch goal。load/store、MOP、A、ECALL、cycle、VERSION0/1 与 ASM/JIT 是 post-MVP 范围。

## 4. 精化关系

不同来源的状态类型不应强行相等，而应建立关系：

```text
state_rel(ckb, sail) :=
  同一 XLEN
  ∧ 32 个 GPR 对应（x0 = 0）
  ∧ PC 对应
  ∧ 当前指令可访问的内存 footprint 对应
  ∧ reservation/trap 状态在指令需要时对应
```

核心定理形态：

```text
state_rel ckb sail
→ allowed instruction config version2
→ ckb_step instruction ckb = Ok ckb'
→ sail_step instruction sail ⇓ sail'
→ state_rel ckb' sail'
  ∧ observe ckb ckb' = observe sail sail'
```

适用前提必须包含 ISA 开关、特权级、对齐策略、内存范围、异常环境和版本。

## 5. 信任边界

需要明确记录的可信组件：

- Rust compiler/Charon/Aeneas 的翻译正确性假设；
- Sail compiler 对 Lean 4/Rocq 后端的翻译；
- 强制证明使用的 Lean 4 kernel，以及兼容性 spike 使用的 Rocq kernel；
- CKB-VM 生产路径确实调用纯语义内核的代码连接；
- RVFI 适配器只影响测试观察，不影响 VM 行为。

翻译器生成代码应固定 commit，CI 重新生成后必须保持 clean diff。

## 6. 语义差异策略

| 差异 | 处理方式 |
|---|---|
| ECALL/退出 | 独立终止关系，不与普通 RISC-V trap 混证 |
| cycle accounting | 不属于架构状态，但错误终止必须比较 |
| 4MB 内存与 W^X | 在地址/权限前提中表达，另证 adapter |
| 非对齐访问 | 按 CKB VERSION2 行为分情况证明和测试 |
| MOP | post-MVP：证明为标准指令序列的组合等价 |
| A 扩展 | post-MVP；当前 ckb-vm 0.24.0 无公开 decoder，保持 unsupported |
| VERSION0/1 | 不在当前六周 MVP 结论中 |
| ASM mode | 需另建 Rust interpreter 与 ASM 的等价层 |

## 7. 仓库边界

```text
crates/core/
  后端无关的事件协议与严格比较器
crates/ckb-runner/src/semantics.rs
  临时证明翻译目标；最终必须移入生产调用边界或由生产路径调用
crates/ckb-runner/src/lib.rs
  只读 CKB-VM 观察 adapter，不属于被证明语义
crates/sail-runner/
  Sail 进程、RVFI parser 与 DII client
crates/diff-test/
  外部 oracle 的 CLI 编排、重放与报告
proof/{lean,rocq}/generated/
  工具生成物，不手工修改
proof/{lean,rocq}/theorems/
  state relation、adapter lemmas 与精化定理
```

旧 `coq/CkbVmModel.v` 等手写状态/语义文件不继续作为证明入口。Rocq 路线迁移到 `proof/rocq/`，只有同时引用 Rust 与 Sail 生成物的关系定理才计入覆盖。

## 8. 当前 foundation 的硬限制

- sail-riscv 的 `--trace-rvfi` 只有在 RVFI-DII socket 模式下才产生包；直接 ELF 空输出必须报错。
- CKB runner 已采集 PC、raw instruction 与 GPR delta，但尚无 committed data-memory observer。
- `crates/ckb-runner/src/semantics.rs` 目前是临时 extraction target，尚未接入生产 CKB-VM 调用图。
- proof 目录目前没有定理或 Rust 翻译生成物。

因此当前结论是“可构建的验证骨架”，不是 runtime differential closed loop，也不是形式化验证完成。
