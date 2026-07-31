# 六周 CKB-VM Sail Validation Sprint 总览

## 目标

六周交付一个维护者可在本地和 CI 中验收的验证 MVP，而不是宣称完整 CKB-VM 已被证明：

1. 可运行、不会误报 PASS 的 RVFI 风格差分框架。
2. 被生产执行路径调用的纯 Rust 指令语义内核。
3. `ADD`、`ADDI`、`BEQ` 至少 10 个可重放差分案例，`MUL` 为 stretch。
4. 一条直接引用 Rust/Sail 生成物且生产关联的 Lean 4 `ADD` 精化定理。
5. Rocq/Coq 双侧生成、导入和状态桥接的 GO/NO-GO 证据，以及可重现发布。

## 强制里程碑

| 时间 | 里程碑 | Go/No-Go 条件 |
|---|---|---|
| Week 1 | 冻结范围与环境 | Rust tests 通过；版本、配置哈希和文档基线一致 |
| Week 2 | RVFI-DII 差分闭环 | ADD/ADDI/BEQ 可重放；空事件、长度和错误不误报 |
| Week 3 | CLI/CI 与语料 | 至少 10 个案例；5 类 mutation 全部被检测并产出 artifact |
| Week 4 | 双侧 Lean 生成与 Rocq spike | Lean 生成无需手改；Rocq 输出可复现 GO/NO-GO |
| Week 5 | 生产连接与 ADD 定理 | 生产调用可审计；Lean 4 kernel 检查通过；无未说明占位 |
| Week 6 | clean-room 发布 | `VERIFICATION.md` 可独立执行；release、报告和重放证据齐全 |

Lean 4 是强制主证明后端，不能用 Rocq NO-GO 替代。Rocq/Coq spike 无论 GO 或 NO-GO 都必须附可复现证据，不能退回手写第二份 CKB 规范冒充生产证明。

本轮交付固定为 Week 1–6，不再保留 Week 7–8 计划文件；post-MVP 范围由方法文档和语义缺口文档继续维护。

## 工作流

```text
foundation
  → RVFI runtime oracle
  → CLI/CI corpus and replay
  → production-linked Lean 4 proof + Rocq compatibility spike
  → audit and release
```

## Deliverables

- `crates/core/`：统一观察协议、严格比较与结构化错误。
- `crates/ckb-runner/`：真实 CKB-VM adapter 与临时 extraction scaffold。
- `crates/sail-runner/`：Sail 进程、RVFI parser 与 DII client。
- `crates/diff-test/`：CLI 编排、报告与退出状态。
- `proof/`：生成物入口、状态关系与真实定理。
- `docs/coverage.md`：指令证据矩阵。
- `docs/semantic-gaps.md`：允许差异与结论边界。
- `artifacts/`：失败种子、最小输入和版本元数据格式。

## Definition of Done

项目结项要求同时满足：

- `cargo fmt --check` 和 `cargo test --workspace --locked` 通过。
- 差分比较器检测 PC、寄存器编号、寄存器值、trap、trace 尾部和终止差异。
- Sail parser 有来自固定 RVFI fixture 的测试。
- ADD、ADDI、BEQ 合计至少 10 个共享初态场景在两端产出结构化事件。
- 5 类 mutation 均返回失败并定位首个差异字段。
- 一个 Lean 4 `ADD` 定理直接引用两端生成物并由 kernel 检查。
- 被证明的 Rust 函数与生产路径存在可审计连接。
- Rocq/Coq spike 产出双侧生成/导入的 GO/NO-GO、最小复现和假设清单。
- `rg 'Admitted|Axiom|sorry|axiom' proof` 无未解释结果或只有审计 allowlist。
- 所有依赖固定版本，Cargo.lock 被跟踪。
- `VERIFICATION.md` 能在干净环境重现验收。

## 非完成状态

以下任何一项存在都不能宣称“CKB-VM 已验证”：

- 只证明手写模型；
- 只比较 PC 或寄存器，未声明 memory 缺口；
- 比较公共前缀后忽略长度；
- 吞掉一端执行错误；
- 生成配置与模拟器配置不同；
- 定理未引用 Sail 生成函数；
- 生产代码未调用被翻译函数。
