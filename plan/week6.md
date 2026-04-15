# Week 6: Extended Proofs & MOP Verification

## Task 6.1: Add AND/OR/XOR to Model and Prove

Add to `coq/CkbVmModel.v`:

```coq
Definition ckb_and (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  next_pc (set_reg st rd (truncate_64 (Z.land (get_reg st rs1) (get_reg st rs2)))).

Definition ckb_or (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  next_pc (set_reg st rd (truncate_64 (Z.lor (get_reg st rs1) (get_reg st rs2)))).

Definition ckb_xor (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  next_pc (set_reg st rd (truncate_64 (Z.lxor (get_reg st rs1) (get_reg st rs2)))).
```

Proofs follow the exact same pattern as ADD — just substitute the operator.

## Task 6.2: Add SLTI and Prove

```coq
Definition to_signed_64 (v : Z) : Z :=
  if Z.testbit v 63 then v - word_max else v.

Definition ckb_slti (rd rs1 : reg_index) (imm : word) (st : machine_state) : machine_state :=
  let v1 := to_signed_64 (get_reg st rs1) in
  let sext_imm := to_signed_64 (sign_extend 12 imm) in
  next_pc (set_reg st rd (if Z.ltb v1 sext_imm then 1 else 0)).

Theorem ckb_slti_binary : forall rd rs1 imm st,
    rd <> 0%nat ->
    let r := get_reg (ckb_slti rd rs1 imm st) rd in r = 0 \/ r = 1.
Proof.
    intros. unfold ckb_slti, next_pc, set_pc in *. simpl in *.
    rewrite get_set_reg_same in *; [|assumption].
    rewrite get_set_reg_same in *; [|assumption].
    destruct (Z.ltb _ _); auto.
Qed.
```

## Task 6.3: Add JALR and Prove

```coq
Definition ckb_jalr (rd rs1 : reg_index) (imm : word) (st : machine_state) : machine_state :=
  let ret := truncate_64 (pc st + 4) in
  let target := truncate_64 (Z.land (get_reg st rs1 + sign_extend 12 imm) (Z.lnot 1)) in
  set_pc (set_reg st rd ret) target.

Theorem ckb_jalr_target : forall rd rs1 imm st,
    pc (ckb_jalr rd rs1 imm st) =
    truncate_64 (Z.land (get_reg st rs1 + sign_extend 12 imm) (Z.lnot 1)).
Proof. intros. unfold ckb_jalr, set_pc. simpl. reflexivity. Qed.
```

## Task 6.4: MOP Fusion Proof

Create `coq/MopEquiv.v`. Prove WIDE_MUL = MULH then MUL:

```coq
Definition ckb_wide_mul (rd_hi rd_lo rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  let v1 := to_signed_64 (get_reg st rs1) in
  let v2 := to_signed_64 (get_reg st rs2) in
  let product := v1 * v2 in
  next_pc (set_reg (set_reg st rd_hi (truncate_64 (Z.shiftr product 64)))
                   rd_lo (truncate_64 product)).

(** When registers don't alias, WIDE_MUL = MULH then MUL *)
Theorem wide_mul_equiv : forall rd_hi rd_lo rs1 rs2 st,
    rd_hi <> rd_lo -> rd_hi <> rs1 -> rd_hi <> rs2 ->
    rd_hi <> 0%nat -> rd_lo <> 0%nat ->
    (* ... equivalence with sequential MULH + MUL ... *)
    True. (* Placeholder — fill in with actual theorem *)
Admitted.
```

## Task 6.5: Audit Admitted

```bash
grep -n "Admitted" coq/*.v
```

ALU proofs should have zero. Memory/MOP may have some — document each.

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/MopEquiv.v` | MOP fusion proofs |
| Modify | `coq/CkbVmModel.v` | AND/OR/XOR/SLTI/JALR |
| Modify | `coq/InstructionEquiv.v` | 5+ more proofs |
| Modify | `coq/_CoqProject` | Add MopEquiv.v |

---

# 第六周：扩展证明与 MOP 验证

## 任务 6.1：位运算

添加 AND/OR/XOR 模型，用 ADD 相同模式证明。

## 任务 6.2：SLTI

添加 `to_signed_64`（二补数转换），证明结果只能是 0 或 1。

## 任务 6.3：JALR

目标地址 `(rs1 + sext(imm)) & ~1`。证明目标正确。

## 任务 6.4：MOP 融合

创建 `coq/MopEquiv.v`，以 WIDE_MUL 为例证明融合 = 顺序执行。需要寄存器不别名条件。

## 任务 6.5：审计 Admitted

用 grep 找所有 Admitted，决定是证明还是记录。
