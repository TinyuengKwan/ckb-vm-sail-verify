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

CKB-VM 适配器必须包住真实 VERSION2 Rust interpreter。Sail 适配器消费 RVFI-DII 二进制包（v1，88 字节）；文本 `--trace-rvfi` parser 保留给专用 exporter，并有固定 fixture 测试。

比较器遵循以下规则：

- 比较完整长度，不能只比较公共前缀。
- execution error、step limit、正常退出是不同终止状态。
- x0 写回统一规范化为无写回。
- memory 观察缺失不能自动视为相等。
- mismatch 保存 seed、ELF、双方事件和工具版本，允许重放。
- RVFI-DII 会话必须从架构复位态开始：首个执行包的 `rvfi_order` 为 0、`pc_rdata` 为 `0x80000000`，否则直接报错。上游模拟器只 `accept` 一次就关闭监听套接字，两个客户端争抢同一端口时，输的一方可能连到别人已经推进过的模拟器；这个检查使那种情况成为错误，而不是一条看起来合理的错误 trace。

比较器的检出能力本身要有证据，否则“全部一致”与“比较器失效”无法区分。
`crates/diff-test/src/mutation.rs` 因此在真实记录的 trace 上注入 6 类 mutation，
并要求每一类都被检测到、且第一个不一致字段正是被注入的字段；baseline 未通过、
某一类在整个语料中从未被覆盖、以及注入后未被检出，都判定失败。规格见
`VERIFICATION.md` §4。

CI 按成本分层：不需要模拟器的检查每次都跑，需要固定版本 Sail 模拟器的差分层跑
在缓存命中的 job 与每日定时任务上，见 `VERIFICATION.md` §8。

### 2.2 形式化证明轨

证明目标不是直接翻译整个 CKB-VM，而是**直接翻译生产代码本身**，不为证明改写它。

原设计是先从生产路径抽出一个无 I/O、无 trait object 的纯函数层，再让生产解释器
调用它。Week 4 实测推翻了这个前提：Charon/Aeneas 能直接吃下生产形状 ——
`ckb_vm::instructions::execute`（trait 泛型 + `&mut Mac`）提取只用 25 秒，
`DefaultCoreMachine` 的寄存器方法带真实 body。因此不需要重构 `deps/ckb-vm`，
也就不存在"重构是否改变了被验证对象"这个问题。

提取根写在 `crates/proof-extract` 里，是普通 Rust：

```rust
pub fn execute_production(inst: Instruction, machine: &mut InjectedMachine) -> Result<(), Error> {
    execute(inst, machine)   // ckb_vm::instructions::execute
}
```

`InjectedMachine` 由 `ckb-runner` 导出并被差分实际驱动，这里 import 而不是重新
拼写，两者因此不可能漂移。Charon 从这个根提取调用图，
`ckb_vm::instructions::common::add` 出现在生成物里是因为生产**到达**它。

提取显式将三组对象设为 opaque，每一组都有实测原因（内存的 `Iterator::skip`、
`DefaultMachine` 的 `dyn` 字段、四个 `bool -> u64` 转换），逐条记录在
`proof/lean/expected_rust_build_status.txt`。其中 `DefaultMachine` 到
`DefaultCoreMachine` 的委托是 axiom 而非翻译出的 body，必须补连接证明或明确的
方法规律前提。生成物还有其他外部声明：ADD 写回直接依赖的
`RISCV_GENERAL_REGISTER_NUMBER` 也被生成为 axiom，不能宣称 wrapper 是唯一缺口。
实际依赖、输入合法性和寄存器/PC 两层证明合同见
[ADD 审计](../proof/lean/reports/ADD_AUDIT.md)。

这条路线不引入"Rust 一份、手写证明模型一份"的双重实现，因为被翻译的就是生产
那一份。

## 3. 后端选择

当前六周 MVP 的强制主路线：

```text
production Rust path ─Charon/Aeneas─► Lean 4
Sail model ───────────Sail Lean───► Lean 4
```

理由是 Aeneas 的 Lean 支持比直接 Coq/Rocq 提取成熟，同时 sail-riscv 已维护 Lean 生成目标。`ADD` 的生产关联精化定理必须在 Lean 4 中由 kernel 检查通过。

Rocq/Coq 保留为兼容性与原 Issue #190 路线的可行性 spike：

```text
production Rust path ──Aeneas/Rocq-of-Rust──► Rocq
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

上式是一般关系示意，具体 ADD 定理还应从合法输入和外围条件推出两侧成功，避免
只假设双方已成功而漏掉失败行为。初版范围是对应的已解码 ADD；取指/解码与 cycle
不在提取根内。`common.add` 和 Sail `execute_RTYPE` 都不推进 PC，包含 PC 的结论
必须另外连接生成的 CKB `execute` 与 Sail `run_hart_active` / `tick_pc`。
Sail 的寄存器映射必须具有所需键；全零复位态不是通用 ADD 引理的必要限制。

## 5. 信任边界

需要明确记录的可信组件：

- Rust compiler/Charon/Aeneas 的翻译正确性假设；
- Sail compiler 对 Lean 4/Rocq 后端的翻译；
- 强制证明使用的 Lean 4 kernel，以及兼容性 spike 使用的 Rocq kernel；
- `DefaultMachine` 到 `DefaultCoreMachine` 的委托：它因 `dyn` 字段无法翻译，在生成物里是 axiom；
- 实际定理可达的外部声明与显式前提；寄存器总数和 RA 已提取并检查值，wrapper 合同仍未实例化。见 ADD 审计，不能只扫描占位符；
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
crates/proof-extract/
  使用共享 InjectedMachine 类型调用生产 instructions::execute 的提取根
crates/ckb-runner/src/lib.rs
  只读 CKB-VM 观察 adapter，不属于被证明语义
crates/sail-runner/
  Sail 进程、RVFI parser 与 DII client
crates/diff-test/
  外部 oracle 的 CLI 编排、重放与报告
proof/{lean,rocq}/generated/
  工具生成物，不手工修改
proof/lean/audit/
  可执行的依赖查询，不是精化定理
proof/lean/theorems/
  共同 Lean 4.31.0 双侧 import 工程；state relation 与精化定理待实现
proof/lean/compat/
  Sail 类型作用域兼容补丁、回归探针与实测报告
proof/rocq/theorems/（计划目录）
  兼容性 NO-GO 尚未解除
```

旧 `coq/CkbVmModel.v` 等手写状态/语义文件不继续作为证明入口。Rocq 路线迁移到 `proof/rocq/`，只有同时引用 Rust 与 Sail 生成物的关系定理才计入覆盖。

## 8. 当前的硬限制

- sail-riscv 的 `--trace-rvfi` 只有在 RVFI-DII socket 模式下才产生包；直接 ELF 空输出必须报错。差分闭环因此建立在指令注入而不是 ELF 上。
- RVFI-DII 不从内存取指：第 k 条注入字就是第 k 步执行的指令。CKB 侧镜像在每步之前把该字写到当前 PC 并让解码缓存失效，所以两端跑的是同一条指令流，但这不是对取指路径的测试。
- CKB runner 已采集 PC、raw instruction 与 GPR delta，但尚无 committed data-memory observer；load/store/AMO/SYSTEM 因此被支持子集拒绝。
- 寄存器观察的分辨率是架构状态变化：写回寄存器已有值在两端都不可观察。
- 注入路径的 CKB ISA 已收敛到 `ISA_IMC | ISA_B`。开启 `ISA_MOP` 会让解码器走 `decode_mop` 并向前读取注入流之外的字节，融合命中时一步退休多条指令；两侧对"一步"的定义必须一致，因此宏操作融合不在范围内。
- 双侧工程使用共同 Lean 4.31.0，生成流程包含已记录的 Sail 类型作用域补丁；`make proof-step` 检查条件性 dispatch/PC 定理，wrapper 委托已证明，原内部定理审计 137 项依赖。新增公开 ADD decoder 定理审计 158 项，在既定配置和取指条件下推出同码解码；其独立干净复验及集成主门禁实跑均通过。Sail 前缀、物理内存对应与 reset 可达性仍有边界，不能据此标记无条件完整指令 `proved`。
- 提取不需要修改 `deps/ckb-vm`，因此本轮不需要上游 patch/PR。
- 寄存器总数与 RA 已从 axiom 补为真实定义；生产 wrapper 方法仍是 axiom，其五个委托合同虽已编译，尚无实例/连接证明。

- mutation 矩阵证明的是**比较器**会失败，不是语料覆盖了 CKB-VM 的输入空间；两者是不同的命题。

因此当前结论是“运行时差分闭环 + 可构建的证明骨架”，不是形式化验证完成。
