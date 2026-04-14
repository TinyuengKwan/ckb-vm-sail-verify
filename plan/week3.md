# Week 3: Coq Infrastructure & Sail Interface Study

## Objectives

- Understand the generated Coq code structure (types, monads, instruction semantics)
- Design the bridging layer between Sail-generated Coq and hand-written CKB-VM model
- Prove first trivial lemma connecting the two sides

## Tasks

1. **Study generated Coq output**
   - Read `coq/generated/CkbVmSpec_types.v` — understand Sail's type representations
   - Read `coq/generated/CkbVmSpec.v` — find the function for each target instruction
   - Document how Sail represents: registers, memory, PC updates, bitvectors

2. **Identify the Sail execution interface**
   - How does Sail model a single instruction step?
   - What monad does it use (state monad with nondeterminism)?
   - How to extract a pure function from the monadic Sail code?

3. **Design state equivalence relation**
   - Define a Coq relation `state_equiv : machine_state -> sail_state -> Prop`
   - Map our `MachineState.v` fields to Sail's generated types
   - Handle type mismatches (Z vs bitvector, nat vs enum)

4. **Prove first bridging lemma**
   - Pick the simplest instruction (ADD)
   - Write a `Theorem add_bridge` connecting `ckb_add` to the Sail ADD function
   - Even a partial/admitted proof is fine — the goal is to validate the approach

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/SailInterface.v` | Sail state ↔ machine_state equivalence relation |
| Modify | `coq/InstructionEquiv.v` | First real bridging proof (ADD) |
| Modify | `coq/_CoqProject` | Add SailInterface.v, add generated/ dependency |
| Add | `doc/sail_coq_notes.md` | Notes on Sail Coq output structure |

## Verification Criteria

- [ ] Can explain how Sail represents ADD in Coq (function name, type signature, monad)
- [ ] `state_equiv` relation compiles in Coq
- [ ] At least one bridging lemma stated (even if `Admitted`)

---

# 第三周：Coq 基础设施与 Sail 接口研究

## 目标

- 理解生成的 Coq 代码结构（类型、monad、指令语义）
- 设计 Sail 生成代码与手写 CKB-VM 模型之间的桥接层
- 证明第一个连接两侧的引理

## 任务

1. 研读生成的 Coq 代码，理解 Sail 如何表示寄存器、内存、PC 更新、bitvector 等
2. 找到 Sail 单步执行接口（用了什么 monad？如何提取纯函数？）
3. 设计状态等价关系 `state_equiv`，映射 `MachineState.v` 到 Sail 生成类型
4. 为 ADD 指令写第一个桥接定理（即使 `Admitted` 也行，目标是验证方法可行）

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `coq/SailInterface.v` | Sail 状态 ↔ machine_state 等价关系 |
| 修改 | `coq/InstructionEquiv.v` | 第一个真正的桥接证明（ADD） |
| 修改 | `coq/_CoqProject` | 加入新文件和 generated/ 依赖 |
| 新增 | `doc/sail_coq_notes.md` | Sail Coq 输出结构笔记 |

## 验收标准

- 能解释 Sail 在 Coq 中如何表示 ADD（函数名、类型签名、monad）
- `state_equiv` 关系在 Coq 中编译通过
- 至少一个桥接引理被陈述（可以 `Admitted`）
