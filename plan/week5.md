# Week 5: Control Flow & Memory Instruction Proofs

## Task 5.1: Prove BEQ (taken + not-taken)

```coq
Theorem ckb_beq_taken : forall rs1 rs2 offset st,
    get_reg st rs1 = get_reg st rs2 ->
    pc (ckb_beq rs1 rs2 offset st) = truncate_64 (pc st + sign_extend 13 offset).
Proof.
    intros. unfold ckb_beq. rewrite H. rewrite Z.eqb_refl.
    unfold set_pc. simpl. reflexivity.
Qed.

Theorem ckb_beq_not_taken : forall rs1 rs2 offset st,
    get_reg st rs1 <> get_reg st rs2 ->
    pc (ckb_beq rs1 rs2 offset st) = truncate_64 (pc st + 4).
Proof.
    intros. unfold ckb_beq.
    destruct (Z.eqb _ _) eqn:E.
    - apply Z.eqb_eq in E. contradiction.
    - unfold next_pc, set_pc. simpl. reflexivity.
Qed.

Theorem ckb_beq_regs_unchanged : forall rs1 rs2 offset st r,
    get_reg (ckb_beq rs1 rs2 offset st) r = get_reg st r.
Proof.
    intros. unfold ckb_beq. destruct (Z.eqb _ _);
    unfold set_pc, next_pc; simpl; reflexivity.
Qed.
```

## Task 5.2: Prove JAL

```coq
Theorem ckb_jal_link : forall rd offset st,
    rd <> 0%nat ->
    get_reg (ckb_jal rd offset st) rd = truncate_64 (pc st + 4).
Proof.
    intros. unfold ckb_jal, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.

Theorem ckb_jal_target : forall rd offset st,
    pc (ckb_jal rd offset st) = truncate_64 (pc st + sign_extend 21 offset).
Proof. intros. unfold ckb_jal, set_pc. simpl. reflexivity. Qed.
```

## Task 5.3: Build Memory Lemmas

Create `coq/MemoryBridge.v`:

```coq
Require Import Coq.ZArith.ZArith.
Require Import CkbVmVerify.MachineState.
Open Scope Z_scope.

Lemma store_load_byte_same : forall st addr v,
    0 <= v < 256 -> load_byte (store_byte st addr v) addr = v.
Proof.
    intros. unfold load_byte, store_byte. simpl.
    rewrite Z.eqb_refl.
    rewrite Z.land_ones by lia. rewrite Z.mod_small by lia.
    rewrite Z.land_ones by lia. rewrite Z.mod_small by lia.
    reflexivity.
Qed.

Lemma store_load_byte_diff : forall st a1 a2 v,
    a1 <> a2 -> load_byte (store_byte st a1 v) a2 = load_byte st a2.
Proof.
    intros. unfold load_byte, store_byte. simpl.
    destruct (Z.eqb a2 a1) eqn:E.
    - apply Z.eqb_eq in E. contradiction.
    - reflexivity.
Qed.
```

## Task 5.4: Prove LW

```coq
Theorem ckb_lw_semantics : forall rd rs1 offset st,
    rd <> 0%nat ->
    let addr := truncate_64 (get_reg st rs1 + sign_extend 12 offset) in
    get_reg (ckb_lw rd rs1 offset st) rd = sign_extend 32 (load_word32 st addr).
Proof.
    intros. unfold ckb_lw, next_pc, set_pc. simpl.
    rewrite get_set_reg_same; [|assumption].
    rewrite get_set_reg_same; [|assumption].
    unfold truncate_64. rewrite Z.mod_mod; [reflexivity|lia].
Qed.
```

## Task 5.5: Prove SW (partial)

SW modifies memory — the roundtrip proof (store then load back) is harder:

```coq
(** After SW, reading the same address returns the stored value *)
Theorem ckb_sw_roundtrip : forall rs1 rs2 offset st,
    let addr := truncate_64 (get_reg st rs1 + sign_extend 12 offset) in
    let st' := ckb_sw rs1 rs2 offset st in
    load_word32 st' addr = Z.land (get_reg st rs2) (2^32 - 1).
Proof.
    (* Requires chaining 4x store_load_byte_same/diff lemmas *)
    (* Complex but mechanical — may Admit for PoC if time-constrained *)
Admitted.
```

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/MemoryBridge.v` | Memory byte-ordering lemmas |
| Modify | `coq/InstructionEquiv.v` | BEQ(3), JAL(2), LW(1), SW(1) |
| Modify | `coq/_CoqProject` | Add MemoryBridge.v |

---

# 第五周：控制流与内存指令证明

## 任务 5.1：证明 BEQ

分 taken/not-taken 两个定理 + 寄存器不变定理。用 `destruct (Z.eqb _ _) eqn:E` 做 case analysis。

## 任务 5.2：证明 JAL

link 地址（rd = pc+4）和跳转目标两个属性。

## 任务 5.3：构建内存引理

`coq/MemoryBridge.v` 中证明 store-then-load roundtrip（同地址返回原值，不同地址不受影响）。

## 任务 5.4-5.5：证明 LW 和 SW

LW 比较直接。SW 的 roundtrip 需要链式 4 次 byte store/load 引理，较复杂，可在 PoC 阶段 Admitted。
