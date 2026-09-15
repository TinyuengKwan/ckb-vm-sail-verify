(* Minimal reproduction of the Sail-side NO-GO, using the generated model's
   support imports. Expected failure: e_div is absent in rocq-sail-stdpp 0.20.2.
   The full generated rv64d.v is compiled separately to confirm this same error.
   This fixture is not a replacement model or a theorem. *)
Require Import SailStdpp.Base.
Require Import SailStdpp.Real.
Require Import SailStdpp.ConcurrencyInterfaceTypes.
Require Import SailStdpp.ConcurrencyInterface.
Require Import SailStdpp.ConcurrencyInterfaceBuiltins.

Definition missing_division := e_div 4 2.
