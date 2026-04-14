# Week 4: Core ALU Instruction Proofs

## Objectives

- Complete equivalence proofs for R-type and I-type ALU instructions
- Establish reusable proof patterns and tactics

## Target Instructions

| Instruction | Type | Key semantic point |
|-------------|------|--------------------|
| ADD | R-type | Wrapping 64-bit addition |
| SUB | R-type | Wrapping 64-bit subtraction |
| ADDI | I-type | 12-bit sign-extended immediate |
| SLLI | I-type | Left shift, 6-bit shamt |
| SRLI | I-type | Logical right shift |
| SRAI | I-type | Arithmetic right shift (sign-preserving) |
| MUL | R-type (M-ext) | Lower 64 bits of 128-bit product |

## Tasks

1. **Establish proof template**
   - Extract the common pattern: decode → read operands → compute → write-back → advance PC
   - Build Ltac tactics for: bitvector arithmetic, register read/write, x0 enforcement

2. **Prove ADD and SUB**
   - Full proof (not Admitted): `ckb_add rd rs1 rs2 st ≡ sail_ADD rd rs1 rs2 st`
   - Handle x0 corner case

3. **Prove ADDI**
   - Sign extension of 12-bit immediate
   - Verify Sail and CKB-VM agree on sign extension semantics

4. **Prove shift instructions (SLLI, SRLI, SRAI)**
   - Shift amount masking (& 63 for RV64)
   - SRAI: sign bit preservation

5. **Prove MUL**
   - Lower-half multiply semantics
   - Verify wrapping behavior matches

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/Tactics.v` | Reusable proof tactics (bitvector, register) |
| Modify | `coq/CkbVmModel.v` | Refine model if needed to match Sail interface |
| Modify | `coq/InstructionEquiv.v` | 7 completed proofs |
| Modify | `coq/_CoqProject` | Add Tactics.v |

## Verification Criteria

- [ ] `make coq` succeeds with 7 instruction proofs (no Admitted)
- [ ] Proof template documented for reuse

---

# 第四周：核心 ALU 指令证明

## 目标

- 完成 R-type 和 I-type ALU 指令的等价性证明
- 建立可复用的证明模式和策略

## 目标指令

ADD, SUB, ADDI, SLLI, SRLI, SRAI, MUL（共 7 条）

## 任务

1. 建立证明模板：解码 → 读操作数 → 计算 → 写回 → PC+4
2. 构建 Ltac 策略：bitvector 算术、寄存器读写、x0 强制清零
3. 逐一证明 7 条指令，重点关注：12 位符号扩展、移位量截断（& 63）、SRAI 的符号位保持、MUL 的低半截取

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `coq/Tactics.v` | 可复用证明策略 |
| 修改 | `coq/CkbVmModel.v` | 按需调整模型以对齐 Sail 接口 |
| 修改 | `coq/InstructionEquiv.v` | 7 条指令完整证明 |
| 修改 | `coq/_CoqProject` | 加入 Tactics.v |

## 验收标准

- `make coq` 通过，7 条指令证明无 Admitted
- 证明模板文档化
