(** * MachineState: CKB-VM machine state definitions for verification.
    
    This file defines the abstract machine state used in both the
    CKB-VM model and the equivalence proofs. It mirrors the essential
    state components of CKB-VM's CoreMachine trait. *)

Require Import Coq.ZArith.ZArith.
Require Import Coq.Vectors.Vector.
Require Import Coq.Lists.List.
Import ListNotations.

Open Scope Z_scope.

(** ** Register file
    CKB-VM uses 32 64-bit general-purpose registers (RV64).
    Register x0 is hardwired to zero. *)

Definition reg_index := nat.  (* 0..31 *)
Definition word := Z.        (* 64-bit values represented as Z *)

(** 64-bit word bounds *)
Definition XLEN : nat := 64.
Definition word_max : Z := 2 ^ 64.

(** Wrap a value to 64-bit unsigned *)
Definition truncate_64 (v : Z) : Z := Z.modulo v word_max.

(** Sign-extend from bit width n to 64 bits *)
Definition sign_extend (n : nat) (v : Z) : Z :=
  let half := 2 ^ (Z.of_nat n - 1) in
  if Z.testbit v (Z.of_nat n - 1)
  then truncate_64 (v - 2 ^ Z.of_nat n)
  else truncate_64 v.

(** ** Machine state *)
Record machine_state := mk_state {
  regs : reg_index -> word;   (** Register file (x0 always returns 0) *)
  pc   : word;                (** Program counter *)
  mem  : word -> word;        (** Memory (byte-addressable, simplified) *)
}.

(** Get register value (x0 hardwired to 0) *)
Definition get_reg (st : machine_state) (r : reg_index) : word :=
  match r with
  | O => 0
  | _ => truncate_64 (regs st r)
  end.

(** Set register value (writes to x0 are discarded) *)
Definition set_reg (st : machine_state) (r : reg_index) (v : word) : machine_state :=
  mk_state
    (fun r' => if Nat.eqb r' 0 then 0
               else if Nat.eqb r' r then truncate_64 v
               else regs st r')
    (pc st)
    (mem st).

(** Update PC *)
Definition set_pc (st : machine_state) (new_pc : word) : machine_state :=
  mk_state (regs st) (truncate_64 new_pc) (mem st).

(** Advance PC by 4 (standard instruction size) *)
Definition next_pc (st : machine_state) : machine_state :=
  set_pc st (pc st + 4).

(** Advance PC by 2 (compressed instruction size) *)
Definition next_pc_c (st : machine_state) : machine_state :=
  set_pc st (pc st + 2).

(** ** Memory access (simplified, little-endian, 64-bit addressable)
    In the full verification, this would model CKB-VM's memory with
    W^X enforcement and page-based permissions. For the PoC, we use
    a simplified byte-addressable memory. *)

Definition load_byte (st : machine_state) (addr : word) : word :=
  Z.land (mem st addr) 255.

Definition store_byte (st : machine_state) (addr : word) (v : word) : machine_state :=
  mk_state
    (regs st)
    (pc st)
    (fun a => if Z.eqb a addr then Z.land v 255 else mem st a).

(** Load 32-bit word (little-endian) *)
Definition load_word32 (st : machine_state) (addr : word) : word :=
  let b0 := load_byte st addr in
  let b1 := load_byte st (addr + 1) in
  let b2 := load_byte st (addr + 2) in
  let b3 := load_byte st (addr + 3) in
  Z.lor b0 (Z.lor (Z.shiftl b1 8) (Z.lor (Z.shiftl b2 16) (Z.shiftl b3 24))).

(** Load 64-bit doubleword (little-endian) *)
Definition load_word64 (st : machine_state) (addr : word) : word :=
  let lo := load_word32 st addr in
  let hi := load_word32 st (addr + 4) in
  truncate_64 (Z.lor lo (Z.shiftl hi 32)).
