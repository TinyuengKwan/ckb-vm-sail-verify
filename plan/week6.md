# Week 6: Extended Proofs & MOP Verification

## Objectives

- Add proofs for a few more instructions to strengthen coverage
- Prove MOP fusion correctness as compositions of standard instructions
- Complete the formal verification portion

## Additional Instruction Proofs

| Instruction | Extension | Key point |
|-------------|-----------|-----------|
| AND / OR / XOR | RV64I | Bitwise operations |
| SLTI | RV64I | Signed comparison with immediate |
| JALR | RV64I | Register-indirect jump |

## Tasks

1. **Prove bitwise operations (AND, OR, XOR)**
   - Straightforward bitvector operations
   - Should follow directly from the proof template established in Week 4

2. **Prove SLTI**
   - Signed comparison: requires modeling two's complement interpretation
   - Result is 0 or 1

3. **Prove JALR**
   - Target: (rs1 + sext(imm)) & ~1
   - Link: rd = pc + 4
   - Lowest bit clearing

4. **MOP fusion correctness**
   - Pick 1-2 MOP instructions (e.g., WIDE_MUL = MULH + MUL)
   - Prove: executing the fused MOP produces the same register state as executing the two constituent instructions sequentially
   - This is a CKB-VM internal proof, no Sail involvement needed

5. **Review and harden all proofs**
   - Ensure no Admitted remains
   - Check all proofs are robust (no `omega` on fragile goals)

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/MopEquiv.v` | MOP fusion = sequential execution proofs |
| Modify | `coq/CkbVmModel.v` | Add AND/OR/XOR/SLTI/JALR models |
| Modify | `coq/InstructionEquiv.v` | 5 more proofs (total: ~16) |
| Modify | `coq/_CoqProject` | Add MopEquiv.v |

## Verification Criteria

- [ ] `make coq` succeeds with ~16 proofs, zero Admitted
- [ ] At least 1 MOP fusion proof complete
- [ ] All proofs compile cleanly on a fresh environment

---

# 第六周：扩展证明与 MOP 验证

## 目标

- 新增若干指令证明增强覆盖面
- 证明 MOP 融合指令的正确性（作为标准指令序列的等价组合）
- 完成形式化验证部分

## 额外指令

AND, OR, XOR（位运算），SLTI（有符号比较），JALR（间接跳转），共 5 条（累计约 16 条）

## 任务

1. 位运算指令遵循 Week 4 模板，应能快速完成
2. SLTI 需要建模二补数有符号解释
3. JALR：目标地址 (rs1 + sext(imm)) & ~1，最低位清零
4. MOP 融合正确性：证明 WIDE_MUL = MULH 后跟 MUL 的效果等价。这是 CKB-VM 内部证明，不需要 Sail
5. 审查所有证明，确保零 Admitted

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `coq/MopEquiv.v` | MOP 融合 = 顺序执行等价证明 |
| 修改 | `coq/CkbVmModel.v` | 新增 AND/OR/XOR/SLTI/JALR 模型 |
| 修改 | `coq/InstructionEquiv.v` | 新增 5 条证明 |

## 验收标准

- `make coq` 通过，约 16 条证明，零 Admitted
- 至少 1 个 MOP 融合证明完成
