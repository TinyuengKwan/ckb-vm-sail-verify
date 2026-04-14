(** * InstructionEquiv: Equivalence proofs between CKB-VM and Sail spec.

    This file contains the core verification results: for each target
    instruction, we prove that CKB-VM's execution semantics (as modeled
    in CkbVmModel.v) are equivalent to the Sail RISC-V specification
    (as generated in CkbVmSpec.v).

    The proofs follow a common pattern:
    1. Unfold both the CKB-VM model function and the Sail spec function
    2. Show that the register/PC/memory updates are identical
    3. Handle edge cases (x0 hardwiring, overflow behavior, etc.)

    Status: Skeleton -- proofs will be filled in once Coq generation
    from Sail is complete and the interface is finalized. *)

Require Import Coq.ZArith.ZArith.
Require Import CkbVmVerify.MachineState.
Require Import CkbVmVerify.CkbVmModel.

Open Scope Z_scope.

(** ** Helper lemmas *)

(** truncate_64 is idempotent for values already in range *)
Lemma truncate_64_idempotent : forall v,
  0 <= v < word_max ->
  truncate_64 v = v.
Proof.
  intros v [Hlo Hhi].
  unfold truncate_64, word_max.
  apply Z.mod_small. lia.
Qed.

(** x0 is always zero after any register write *)
Lemma x0_always_zero : forall st rd v,
  get_reg (set_reg st rd v) 0 = 0.
Proof.
  intros. unfold get_reg, set_reg. simpl. reflexivity.
Qed.

(** Writing to a register and reading back gives the written value *)
Lemma get_set_reg_same : forall st rd v,
  rd <> 0%nat ->
  get_reg (set_reg st rd v) rd = truncate_64 v.
Proof.
  intros st rd v Hneq.
  unfold get_reg, set_reg. simpl.
  destruct rd; [contradiction |].
  rewrite Nat.eqb_refl.
  unfold truncate_64.
  rewrite Z.mod_mod; [reflexivity | lia].
Qed.

(** Writing to a register does not affect other registers *)
Lemma get_set_reg_diff : forall st rd r v,
  r <> rd ->
  get_reg (set_reg st rd v) r = get_reg st r.
Proof.
  intros st rd r v Hneq.
  unfold get_reg, set_reg. simpl.
  destruct r; [reflexivity |].
  destruct (Nat.eqb (S r) 0) eqn:E; [discriminate |].
  destruct (Nat.eqb (S r) rd) eqn:E2.
  - apply Nat.eqb_eq in E2. lia.
  - reflexivity.
Qed.

(** ** Equivalence proofs *)

(** *** ADD equivalence
    Theorem: CKB-VM's ADD implementation produces the same result
    as the Sail RISC-V specification for ADD.

    TODO: Complete once Sail Coq generation interface is finalized.
    The proof will unfold both definitions and show that:
    - Both read rs1 and rs2
    - Both compute wrapping 64-bit addition
    - Both write the result to rd (with x0 -> 0 enforcement)
    - Both advance PC by 4 *)

(* Placeholder -- will be replaced with actual Sail spec reference *)
(* 
Theorem add_equiv : forall rd rs1 rs2 st,
  ckb_add rd rs1 rs2 st = sail_execute_ADD rd rs1 rs2 st.
*)

(** For now, we prove internal consistency properties of the CKB-VM model. *)

(** ADD with x0 as destination is a no-op on registers *)
Theorem add_x0_noop : forall rs1 rs2 st,
  get_reg (ckb_add 0 rs1 rs2 st) 0 = 0.
Proof.
  intros. unfold ckb_add. apply x0_always_zero.
Qed.

(** ADD is commutative *)
Theorem add_comm : forall rd rs1 rs2 st,
  ckb_add rd rs1 rs2 st = ckb_add rd rs2 rs1 st.
Proof.
  intros. unfold ckb_add.
  f_equal. f_equal. f_equal.
  lia.
Qed.

(** SUB(a, a) = 0 *)
Theorem sub_self_zero : forall rd rs st,
  rd <> 0%nat ->
  get_reg (ckb_sub rd rs rs st) rd = 0.
Proof.
  intros. unfold ckb_sub.
  rewrite get_set_reg_same; [| assumption].
  (* get_reg st rs - get_reg st rs = 0 *)
  unfold truncate_64, next_pc, set_pc.
  simpl.
  rewrite get_set_reg_same; [| assumption].
  replace (get_reg st rs - get_reg st rs) with 0 by lia.
  unfold truncate_64, word_max. simpl.
  reflexivity.
Qed.

(** ADDI with imm=0 is equivalent to register move *)
Theorem addi_zero_is_move : forall rd rs1 st,
  ckb_addi rd rs1 0 st = next_pc (set_reg st rd (get_reg st rs1)).
Proof.
  intros. unfold ckb_addi, sign_extend.
  simpl. f_equal. f_equal.
  rewrite Z.add_0_r. reflexivity.
Qed.

(** BEQ with same register always branches *)
Theorem beq_same_always_branches : forall rs offset st,
  ckb_beq rs rs offset st =
  set_pc st (truncate_64 (pc st + sign_extend 13 offset)).
Proof.
  intros. unfold ckb_beq.
  rewrite Z.eqb_refl. reflexivity.
Qed.

(** JAL stores correct return address *)
Theorem jal_return_addr : forall rd offset st,
  rd <> 0%nat ->
  get_reg (ckb_jal rd offset st) rd = truncate_64 (pc st + 4).
Proof.
  intros. unfold ckb_jal, set_pc.
  simpl. rewrite get_set_reg_same; [| assumption].
  unfold truncate_64. rewrite Z.mod_mod; [reflexivity | lia].
Qed.

(** MUL with 0 yields 0 *)
Theorem mul_zero_left : forall rd rs1 rs2 st,
  get_reg st rs1 = 0 ->
  rd <> 0%nat ->
  get_reg (ckb_mul rd rs1 rs2 st) rd = 0.
Proof.
  intros rd rs1 rs2 st Hrs1 Hrd.
  unfold ckb_mul.
  rewrite get_set_reg_same; [| assumption].
  rewrite Hrs1. simpl.
  unfold truncate_64, word_max. simpl.
  reflexivity.
Qed.
