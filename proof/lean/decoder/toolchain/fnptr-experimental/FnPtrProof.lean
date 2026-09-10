import FnPtrCases

namespace FnPtrRegression
open Aeneas Aeneas.Std fnptr_cases

theorem unknown_call (f : U32 → U32 → Result (Option U64)) (b v : U32) :
    invoke f b v = f b v := rfl

theorem select_first (b : U32) : select true b = first b 2#u32 := rfl
theorem select_second (b : U32) : select false b = second b 2#u32 := rfl
theorem callback_panic (b : U32) :
    invoke_failure b = .fail .panic := rfl
theorem arbitrary_failure (e : Error) (b v : U32) :
    invoke (fun _ _ => .fail e) b v = .fail e := rfl
theorem arbitrary_divergence (b v : U32) :
    invoke (fun _ _ => .div) b v = .div := rfl

def table : Table := ⟨⟨[first, second], by scalar_tac⟩⟩
theorem table_initialized : make_table = .ok table := rfl
theorem table_first (b : U32) : from_table table 0#usize b = first b 2#u32 := rfl
theorem table_second (b : U32) : from_table table 1#usize b = second b 2#u32 := rfl
theorem table_out_of_bounds (b : U32) :
    from_table table 2#usize b = .fail .arrayOutOfBounds := rfl

theorem named_map_one (x : U64) :
    map_one (some x) = (do let y ← plus_one x; .ok (some y)) := rfl
theorem named_map_two (x : U64) :
    map_two (some x) = (do let y ← plus_two x; .ok (some y)) := rfl
theorem named_items_distinct :
    map_one (some 0#u64) ≠ map_two (some 0#u64) := by
  change (Result.ok (some 1#u64) : Result (Option U64)) ≠ .ok (some 2#u64)
  intro h
  have hv := congrArg UScalar.val (Option.some.inj (Result.ok.inj h))
  norm_num at hv

def hitIter (inst : U64) : core.slice.iter.Iter (U32 → U32 → Result (Option U64)) :=
  ⟨⟨[fun _ _ => .ok (some inst)], by scalar_tac⟩, 0⟩
theorem loop_hit (b : U32) (inst : U64) :
    through_table_loop (hitIter inst) b = .ok (some inst) := by
  unfold through_table_loop
  rw [loop]
  rfl

def noneIter : core.slice.iter.Iter (U32 → U32 → Result (Option U64)) :=
  ⟨⟨[fun _ _ => .ok none], by scalar_tac⟩, 0⟩
theorem loop_miss_step (b : U32) :
    through_table_loop.body b noneIter = .ok (.cont { noneIter with i := 1 }) := rfl
theorem loop_end (b : U32) :
    through_table_loop { noneIter with i := 1 } b = .ok none := by
  unfold through_table_loop
  rw [loop]
  rfl

#print axioms unknown_call
#print axioms select_first
#print axioms select_second
#print axioms callback_panic
#print axioms arbitrary_failure
#print axioms arbitrary_divergence
#print axioms table_initialized
#print axioms table_first
#print axioms table_second
#print axioms table_out_of_bounds
#print axioms named_map_one
#print axioms named_map_two
#print axioms named_items_distinct
#print axioms loop_hit
#print axioms loop_miss_step
#print axioms loop_end
end FnPtrRegression
