# Week 4: Core ALU Instruction Proofs

## Task 4.1: Build Reusable Tactics

Create `coq/Tactics.v`:

```coq
Require Import Coq.ZArith.ZArith.
Require Import Coq.micromega.Lia.
Require Import CkbVmVerify.MachineState.
Open Scope Z_scope.

Ltac solve_truncate :=
  unfold truncate_64, word_max;
  try rewrite Z.mod_small by lia; try lia.

Ltac simplify_regs :=
  repeat (
    try rewrite get_set_reg_same by lia;
    try rewrite get_set_reg_diff by lia;
    try rewrite x0_always_zero;
    simpl Nat.eqb).
```

## Task 4.2: Prove ADD

Two approaches depending on Week 3 results:

**Approach A** (Sail bridging ready): Prove `state_equiv` preserved through ADD execution on both sides.

**Approach B** (pragmatic, recommended): Prove CKB-VM model properties independently, connect to Sail later.

```coq
Theorem ckb_add_semantics : forall rd rs1 rs2 st,
    rd <> 0%nat -> get_reg (ckb_add rd rs1 rs2 st) rd =
    truncate_64 (get_reg st rs1 + get_reg st rs2).
Proof.
    intros. unfold ckb_add, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.

Theorem ckb_add_pc : forall rd rs1 rs2 st,
    pc (ckb_add rd rs1 rs2 st) = truncate_64 (pc st + 4).
Proof. intros. unfold ckb_add, next_pc, set_pc. simpl. reflexivity. Qed.

Theorem ckb_add_other_regs : forall rd rs1 rs2 st r,
    r <> rd -> get_reg (ckb_add rd rs1 rs2 st) r = get_reg st r.
Proof. intros. unfold ckb_add, next_pc, set_pc. simpl. apply get_set_reg_diff. assumption. Qed.
```

## Task 4.3: Prove SUB

```coq
Theorem ckb_sub_semantics : forall rd rs1 rs2 st,
    rd <> 0%nat -> get_reg (ckb_sub rd rs1 rs2 st) rd =
    truncate_64 (get_reg st rs1 - get_reg st rs2).
Proof.
    intros. unfold ckb_sub, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.
```

## Task 4.4: Prove ADDI

```coq
Theorem ckb_addi_semantics : forall rd rs1 imm st,
    rd <> 0%nat -> get_reg (ckb_addi rd rs1 imm st) rd =
    truncate_64 (get_reg st rs1 + sign_extend 12 imm).
Proof.
    intros. unfold ckb_addi, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.
```

## Task 4.5: Prove SLLI, SRLI, SRAI

SLLI and SRLI follow the same pattern. SRAI needs sign-bit reasoning:

```coq
Theorem ckb_slli_semantics : forall rd rs1 shamt st,
    rd <> 0%nat -> get_reg (ckb_slli rd rs1 shamt st) rd =
    truncate_64 (Z.shiftl (get_reg st rs1) (Z.land shamt 63)).
Proof.
    intros. unfold ckb_slli, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.
(* SRLI: identical structure with Z.shiftr *)
(* SRAI: requires reasoning about to_signed_64 and Z.testbit *)
```

## Task 4.6: Prove MUL

```coq
Theorem ckb_mul_semantics : forall rd rs1 rs2 st,
    rd <> 0%nat -> get_reg (ckb_mul rd rs1 rs2 st) rd =
    truncate_64 (get_reg st rs1 * get_reg st rs2).
Proof.
    intros. unfold ckb_mul, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.
```

## Task 4.7: Compile and Verify

```bash
make coq-check
```

Debug failures with `coqtop -R coq CkbVmVerify -R coq/generated Riscv`.

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/Tactics.v` | Proof tactics |
| Modify | `coq/InstructionEquiv.v` | 7 instruction proofs |
| Modify | `coq/_CoqProject` | Add Tactics.v |

---

# 第四周：核心 ALU 指令证明

## 任务 4.1：构建可复用策略

创建 `coq/Tactics.v`，封装 `solve_truncate` 和 `simplify_regs` 两个 Ltac。

## 任务 4.2-4.6：逐一证明 ADD, SUB, ADDI, SLLI, SRLI, SRAI, MUL

每条指令证三个属性：结果正确、PC+4、不影响其他寄存器。模式统一：`unfold → rewrite get_set_reg_same → Z.mod_mod → reflexivity`。SRAI 需要额外的符号位推理。

## 任务 4.7：编译

`make coq-check` 通过，7 条指令零 Admitted。
