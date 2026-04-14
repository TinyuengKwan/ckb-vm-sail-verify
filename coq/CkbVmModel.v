(** * CkbVmModel: Coq abstraction of CKB-VM's Rust interpreter.

    This file models the instruction execution semantics of CKB-VM's
    Rust interpreter mode (src/instructions/execute.rs). Each function
    corresponds to a handle_* function in execute.rs.

    The model focuses on functional correctness: given a machine state,
    executing an instruction produces a new machine state. Side effects
    (cycle counting, syscalls, error handling) are abstracted away.

    Reference: https://github.com/nervosnetwork/ckb-vm/blob/develop/src/instructions/execute.rs *)

Require Import Coq.ZArith.ZArith.
Require Import CkbVmVerify.MachineState.

Open Scope Z_scope.

(** ** R-type instructions (register-register) *)

(** ADD rd, rs1, rs2 -- rd = rs1 + rs2
    CKB-VM: handle_add in execute.rs
    Wrapping 64-bit addition. *)
Definition ckb_add (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let v2 := get_reg st rs2 in
  let result := truncate_64 (v1 + v2) in
  next_pc (set_reg st rd result).

(** SUB rd, rs1, rs2 -- rd = rs1 - rs2
    CKB-VM: handle_sub in execute.rs
    Wrapping 64-bit subtraction. *)
Definition ckb_sub (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let v2 := get_reg st rs2 in
  let result := truncate_64 (v1 - v2) in
  next_pc (set_reg st rd result).

(** ** I-type instructions (register-immediate) *)

(** ADDI rd, rs1, imm -- rd = rs1 + sext(imm)
    CKB-VM: handle_addi in execute.rs
    Immediate is sign-extended 12-bit value. *)
Definition ckb_addi (rd rs1 : reg_index) (imm : word) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let sext_imm := sign_extend 12 imm in
  let result := truncate_64 (v1 + sext_imm) in
  next_pc (set_reg st rd result).

(** ** Shift instructions *)

(** SLLI rd, rs1, shamt -- rd = rs1 << shamt
    CKB-VM: handle_slli in execute.rs
    Shift amount is 6-bit for RV64 (0..63). *)
Definition ckb_slli (rd rs1 : reg_index) (shamt : word) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let sh := Z.land shamt 63 in
  let result := truncate_64 (Z.shiftl v1 sh) in
  next_pc (set_reg st rd result).

(** SRLI rd, rs1, shamt -- rd = rs1 >> shamt (logical)
    CKB-VM: handle_srli in execute.rs *)
Definition ckb_srli (rd rs1 : reg_index) (shamt : word) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let sh := Z.land shamt 63 in
  let result := truncate_64 (Z.shiftr v1 sh) in
  next_pc (set_reg st rd result).

(** SRAI rd, rs1, shamt -- rd = rs1 >> shamt (arithmetic)
    CKB-VM: handle_srai in execute.rs
    Arithmetic right shift preserves sign bit. *)
Definition ckb_srai (rd rs1 : reg_index) (shamt : word) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let sh := Z.land shamt 63 in
  (* Convert to signed 64-bit, shift, convert back *)
  let signed_v1 := if Z.testbit v1 63
                   then v1 - word_max
                   else v1 in
  let result := truncate_64 (Z.shiftr signed_v1 sh) in
  next_pc (set_reg st rd result).

(** ** Branch instructions *)

(** BEQ rs1, rs2, offset -- if rs1 == rs2 then pc += sext(offset)
    CKB-VM: handle_beq in execute.rs *)
Definition ckb_beq (rs1 rs2 : reg_index) (offset : word) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let v2 := get_reg st rs2 in
  if Z.eqb v1 v2
  then set_pc st (truncate_64 (pc st + sign_extend 13 offset))
  else next_pc st.

(** ** Jump instructions *)

(** JAL rd, offset -- rd = pc + 4; pc += sext(offset)
    CKB-VM: handle_jal in execute.rs *)
Definition ckb_jal (rd : reg_index) (offset : word) (st : machine_state) : machine_state :=
  let return_addr := truncate_64 (pc st + 4) in
  let target := truncate_64 (pc st + sign_extend 21 offset) in
  set_pc (set_reg st rd return_addr) target.

(** ** Load/Store instructions (simplified) *)

(** LW rd, offset(rs1) -- rd = sext(mem[rs1 + sext(offset)][31:0])
    CKB-VM: handle_lw in execute.rs
    Loads 32-bit value and sign-extends to 64-bit. *)
Definition ckb_lw (rd rs1 : reg_index) (offset : word) (st : machine_state) : machine_state :=
  let base := get_reg st rs1 in
  let addr := truncate_64 (base + sign_extend 12 offset) in
  let value := load_word32 st addr in
  let sext_value := sign_extend 32 value in
  next_pc (set_reg st rd sext_value).

(** SW rs2, offset(rs1) -- mem[rs1 + sext(offset)] = rs2[31:0]
    CKB-VM: handle_sw in execute.rs
    Stores lower 32 bits. *)
Definition ckb_sw (rs1 rs2 : reg_index) (offset : word) (st : machine_state) : machine_state :=
  let base := get_reg st rs1 in
  let addr := truncate_64 (base + sign_extend 12 offset) in
  let value := Z.land (get_reg st rs2) (2^32 - 1) in
  let st1 := store_byte st addr (Z.land value 255) in
  let st2 := store_byte st1 (addr+1) (Z.land (Z.shiftr value 8) 255) in
  let st3 := store_byte st2 (addr+2) (Z.land (Z.shiftr value 16) 255) in
  let st4 := store_byte st3 (addr+3) (Z.land (Z.shiftr value 24) 255) in
  next_pc st4.

(** ** M-extension instructions *)

(** MUL rd, rs1, rs2 -- rd = (rs1 * rs2)[63:0]
    CKB-VM: handle_mul in execute.rs
    Lower 64 bits of full 128-bit product. *)
Definition ckb_mul (rd rs1 rs2 : reg_index) (st : machine_state) : machine_state :=
  let v1 := get_reg st rs1 in
  let v2 := get_reg st rs2 in
  let result := truncate_64 (v1 * v2) in
  next_pc (set_reg st rd result).
