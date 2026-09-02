(* Minimal reproduction of the Rust-side Rocq blocker.

   Aeneas's Rocq support library defines `Inductive result A`, but Rocq 9.1's
   prelude (Corelib.Init.Datatypes) also defines a `result A E`, and the
   prelude wins. Every Aeneas-generated signature of the form `... -> result T`
   is therefore ill-typed: `result T` is `Type -> Type`, not `Type`.

   `scripts/rocq_spike.sh` compiles this against the Primitives.v it has just
   generated, so the reproduction cannot drift from the pinned Aeneas. To run
   it by hand, put a freshly generated Primitives.v beside this file:

       aeneas -backend rocq -dest . target/CkbVmProduction.llbc
       rocq compile -Q . "" Primitives.v
       rocq compile -Q . "" result_shadowing.v

   Expected: `result : Type -> Type -> Type`, declared in
   Corelib.Init.Datatypes -- not Aeneas's one-parameter result. *)

Require Import Primitives.
Import Primitives.

About result.

(* This is the shape Aeneas emits for every fallible function. It fails with
   "The term "result bool" has type "Type -> Type" which should be Set, Prop
   or Type." *)
Fail Check (nat -> result bool).
