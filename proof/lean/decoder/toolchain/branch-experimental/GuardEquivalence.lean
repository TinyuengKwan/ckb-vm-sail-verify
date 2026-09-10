import OwnedCleanup
import GuardedFactored
open Aeneas.Std
set_option maxHeartbeats 4000000
set_option maxRecDepth 10000

theorem bool_result (b : Bool) :
    (if b then (Result.ok true : Result Bool) else Result.ok false) = .ok b := by
  cases b <;> rfl

theorem bind_pointwise {α β : Type} (x : Result α) (f g : α → Result β)
    (h : ∀ a, f a = g a) : (x >>= f) = (x >>= g) := by
  exact congrArg (fun k => x >>= k) (funext h)

theorem bind_cond {α β : Type} (p : Prop) [Decidable p]
    (x y : Result α) (f : α → Result β) :
    ((if p then x else y) >>= f) =
      (if p then x >>= f else y >>= f) := by
  by_cases h : p <;> simp [h]

theorem guarded_equivalence (head : U64)
    (next tail : core.result.Result U64 String) :
    guarded_owned_error.field_alternatives head next tail =
      GuardedFactored.field_alternatives head next tail := by
  simp only [guarded_owned_error.field_alternatives, GuardedFactored.field_alternatives,
    guarded_owned_error.Word.rd, GuardedFactored.Word.rd,
    guarded_owned_error.Word.rs1, GuardedFactored.Word.rs1,
    guarded_owned_error.Word.rs2, GuardedFactored.Word.rs2,
    bool_result]
  repeat' first
    | rfl
    | (apply bind_pointwise; intro value)
    | (split <;> simp_all only [if_pos, if_neg, bind_tc_ok, bool_result])
    | (simp only [bind_cond, bind_assoc_eq, bind_tc_ok, bool_result])

#print axioms guarded_equivalence
