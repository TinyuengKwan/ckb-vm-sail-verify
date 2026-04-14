# Week 5: Control Flow & Memory Instruction Proofs

## Objectives

- Complete proofs for branch, jump, load, and store instructions
- Handle the more complex semantic areas: PC-relative addressing, sign extension, memory access

## Target Instructions

| Instruction | Type | Key semantic point |
|-------------|------|--------------------|
| BEQ | B-type | Conditional PC-relative branch, 13-bit offset |
| JAL | J-type | PC-relative jump, 21-bit offset, link register |
| LW | I-type Load | 32-bit load with sign extension to 64-bit |
| SW | S-type Store | 32-bit store, little-endian byte ordering |

## Tasks

1. **Prove BEQ**
   - Branch condition: equality comparison
   - PC offset: sign-extended 13-bit immediate
   - Fall-through vs taken path

2. **Prove JAL**
   - Return address: pc + 4 written to rd
   - Target: pc + sign-extended 21-bit offset
   - x0 link case (JAL x0 = unconditional jump, no link)

3. **Prove LW**
   - Address computation: base + sign-extended 12-bit offset
   - Memory read: 4 bytes, little-endian
   - Result: sign-extended from 32-bit to 64-bit
   - Need to bridge memory model between CKB-VM and Sail

4. **Prove SW**
   - Address computation: same as LW
   - Memory write: lower 32 bits of rs2, little-endian 4-byte store
   - Verify byte ordering matches Sail's memory model

5. **Memory model bridging**
   - Define equivalence between our simplified byte-addressable memory and Sail's memory model
   - May need helper lemmas for little-endian encode/decode

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/MemoryBridge.v` | Memory model equivalence (byte ordering, load/store) |
| Modify | `coq/MachineState.v` | Refine memory model if needed |
| Modify | `coq/InstructionEquiv.v` | 4 more proofs (total: 11) |
| Modify | `coq/_CoqProject` | Add MemoryBridge.v |

## Verification Criteria

- [ ] `make coq` succeeds with 11 instruction proofs
- [ ] Memory bridging lemmas documented
- [ ] BEQ taken/not-taken both covered

---

# 第五周：控制流与内存指令证明

## 目标

- 完成分支、跳转、加载、存储指令的等价性证明
- 处理更复杂的语义：PC 相对寻址、符号扩展、内存访问

## 目标指令

BEQ, JAL, LW, SW（共 4 条，累计 11 条）

## 任务

1. BEQ：相等比较的分支条件、13 位偏移量符号扩展、taken/not-taken 两种路径
2. JAL：返回地址 pc+4 写入 rd、21 位偏移量、x0 作为 rd 的特殊情况
3. LW：地址计算（base + sext(imm12)）、4 字节小端序读取、32→64 位符号扩展
4. SW：4 字节小端序写入、与 Sail 内存模型的字节序对齐
5. 内存模型桥接：定义简化内存模型与 Sail 内存模型之间的等价关系

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `coq/MemoryBridge.v` | 内存模型等价（字节序、load/store） |
| 修改 | `coq/MachineState.v` | 按需完善内存模型 |
| 修改 | `coq/InstructionEquiv.v` | 新增 4 条证明（累计 11 条） |

## 验收标准

- `make coq` 通过，11 条指令证明完成
- 内存桥接引理有文档
