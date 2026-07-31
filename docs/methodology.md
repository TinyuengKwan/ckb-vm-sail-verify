# Verification Methodology

## 1. 覆盖单位

覆盖矩阵以“指令 × 版本 × ISA 配置 × 证据等级”为单位。每个条目只能处于：

- `unsupported`
- `runtime-only`
- `kernel-extracted`
- `proof-in-progress`
- `proved`

`proved` 不能由测试数量推导。

## 2. 运行时差分方法

### 输入层次

1. 手写边界样例：零、全一、符号边界、最大 shift、溢出。
2. 基于指令格式的随机单步状态。
3. riscv-tests / ACT / ckb-vm ELF。
4. 历史 mismatch 回归语料。

随机测试必须输出 seed，并提供 shrink 后的最小 state/instruction。

### 观察规范

每条 retire 指令比较：

- `order`
- `instruction`
- `pc_before` / `pc_after`
- `rd` / `rd_value`
- `memory address/rmask/wmask/rdata/wdata`
- `trap` / `halt`

完整 trace 还比较终止类别与长度。双方只有在终止类别兼容且所有事件一致时才能 PASS。

### 负面测试

比较器必须有以下故障注入：

- 修改 `pc_after`；
- 修改写回寄存器编号；
- 修改写回值；
- 修改 trap 状态；
- 删除最后一个事件或修改终止状态。

每个故障必须被检测并定位到确定字段。

## 3. 纯 Rust 内核方法

纯内核遵守便于 Aeneas/Charon 的子集：

- 使用具体 `u64`，避免复杂关联类型。
- 不使用 unsafe、线程、trait object、闭包回调。
- 状态为拥有所有权的值类型。
- wrapping、符号扩展和 shift mask 显式编码。
- 失败使用封闭枚举，不 panic。

在纯内核接入生产 CKB-VM 前，其测试只能证明骨架自身；接入后必须增加 production adapter 一致性测试。

## 4. 形式化证明方法

### 当前六周 MVP 承诺

- Lean 4 是强制主证明后端：生产调用的纯 Rust `ADD` 经 Charon/Aeneas 生成，Sail `ADD` 经 Sail Lean backend 生成，并完成一条 kernel 检查的精化定理。
- Rocq/Coq 是兼容性 spike：对同一内核和配置报告双侧生成、导入、状态桥接的 GO/NO-GO；只有 kernel 检查通过的定理才计入额外覆盖。
- `ADDI`、`BEQ` 是强制运行时差分范围，不是本轮强制定理；`MUL` 是运行时 stretch goal。
- 以下阶段 B–E 是 post-MVP 扩展顺序，不属于当前六周成功标准。

### 阶段 A：算术效果

当前只强制证明 ADD 的寄存器写回、x0 行为与 PC；SUB、ADDI、逻辑指令、shift 和 MUL 在后续按相同模板扩展。

### 阶段 B：控制流

BEQ/BNE/BLT/BGE/JAL/JALR，分别证明 taken/not-taken、link 地址与目标地址。

### 阶段 C：抽象内存效果

将 load/store 拆为地址计算、内存请求和结果写回。先证明效果等价，再证明 CKB memory adapter 实现该效果。

### 阶段 D：组合指令

MOP 的定理目标是其观察效果等于标准指令序列的组合，不修改 Sail 标准模型来“加入”CKB 私有指令。

### 阶段 E：原子与异常

加入 reservation、trap 和访问错误后，才开始 A 扩展证明。

## 5. 定理验收模板

每条指令必须记录：

```text
instruction:
ckb source function:
pure kernel function:
sail generated function:
preconditions:
state relation:
theorem file/name:
runtime corpus:
known exclusions:
tool commits:
```

证明文件不能只引用手写 CKB 模型；必须能追溯到翻译生成物和 Sail 生成物。

## 6. 可重现性

- CKB-VM、sail-riscv、Sail、Aeneas/Charon、Lean 4 与 Rocq/OPAM spike 固定 commit/version。
- Cargo.lock 纳入版本控制。
- 配置 override 与合并后的完整配置都保存 hash。
- mismatch artifact 使用 JSON，不依赖终端文本。
- CI 在干净环境重建生成物。

## 7. 报告规则

报告同时给出：

- 已证明指令数；
- 仅有运行时差分证据的指令数；
- unsupported 与 known exclusion 数量；
- 测试总数、随机 seed、语料与工具版本；
- 每条 theorem 的文件/名称、Rust source、Sail generated function；
- Rocq/Coq spike 的 GO/NO-GO、最小复现和可信假设；
- 未观察字段、允许差异与可信计算基。

不得把 property test 数量加到 proved 数量，也不得把纯内核单元测试标记为 CKB 生产实现的 runtime evidence。

## 8. 门禁与失败策略

以下情况均为失败或 unsupported，不得降级成 PASS：

- 一端事件为空、提前结束或执行报错；
- trace 只有公共前缀相同；
- memory 指令的一端缺少 memory observation；
- parser 遇到不完整 RVFI record；
- 生成配置与运行配置 hash 不同；
- 定理只引用手写替代模型；
- Rust 翻译目标没有生产调用或连接证明。

Lean 4 主路径遇到翻译问题时，必须缩小纯内核或修复状态桥接，不能把 Rocq NO-GO 当作主证明的替代。Rocq/Coq spike 失败时记录 NO-GO 和最小复现。

不得用 `Admitted`、`sorry`、未解释 `Axiom` 或过滤 mismatch 保持里程碑表面完成。
