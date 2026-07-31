# Verification Guide

本文区分“当前可运行基线”和“六周 MVP 将交付的验收接口”。不存在的命令不会被描述成已经完成。

## 1. 当前版本基线

- CKB-VM：`1ffba3977da9dcdef8092e9ab1fd2516b27ec939`
- CKB-VM crate：0.24.0
- Rust：MSRV 1.95；当前 foundation 验证版本 1.97.1
- Sail compiler：0.20.2
- sail-riscv：0.13.1，commit `27224ccb2290f022e46213c05b3e72e8a9ea635e`
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
make proof-gen BACKEND=lean
make proof-gen BACKEND=rocq
```

当前基线可以构建 Rust workspace、运行比较器/parser 单元测试、构建 Sail
模拟器、验证固定环境，并生成固定配置下的 Sail Lean/Rocq 模型。模型生成不等于
kernel 编译或等价证明。

当前尚未完成：

- RVFI-DII client，因此不能把端到端 CKB/Sail 差分标记为闭环；
- 生产路径对纯 Rust `ADD` 语义的调用连接；
- Rust 侧 Lean 4 生成、双方导入和 `ADD` 定理；
- Rocq/Coq 的 Rust 侧生成、双方导入、状态桥接与 GO/NO-GO 报告。

直接 ELF 模式得到空 RVFI 流必须返回失败，不能当作空程序或 PASS。

## 3. 六周 MVP 验收接口

以下接口是计划中的稳定验收面；只有相应实现合入后才能按本节验收：

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

## 5. 证明审计

Lean 4 主定理和关键连接层不得包含未说明的 `sorry` 或 `axiom`。

Rocq/Coq spike 只有在定理由 Rocq kernel 检查通过时才计入额外证明覆盖；GO/NO-GO 报告本身不等于证明。若生成代码依赖公理或抽象接口，必须进入审计 allowlist 并解释影响。

证明还必须满足：

- Rust 定义来自生产执行路径实际调用的纯函数，或另有机器检查的连接证明；
- Sail 定义由固定 Sail 模型和同一配置生成；
- 定理直接引用双方生成物，不引用手写第三份指令语义；
- 记录状态关系、前提、源函数、生成函数、工具版本和 theorem 名称。

## 6. Artifact 与 Mismatch

每个运行至少记录：

- CKB-VM、sail-riscv 和工具链版本；
- ISA 配置哈希；
- 测试 ID、随机 seed 和初始状态；
- 双方规范化事件；
- 第一个不一致字段；
- 原始 Sail 数据或其路径；
- mismatch 分类与重放命令。

发现 mismatch 可以是有效结果；错误返回 PASS、吞掉差异或无法重放才是验收失败。差异应分类为 CKB 候选缺陷、配置/版本差异、adapter 缺陷、unsupported 或待分类。

## 7. 保证边界

运行时差分只说明固定版本和公开语料中的有限输入一致。Lean 4 定理只说明 ADD 在列出前提下满足精化关系。Rocq/Coq spike 只说明该后端路线的可行性，除非另有 kernel 检查通过的定理。

本项目不证明完整 CKB-VM，也不覆盖 ASM/JIT、VERSION0/1、load/store 完整内存语义、MOP、A、ECALL/syscall、cycle accounting、并发/原子模型或整条 CKB 链安全性。
