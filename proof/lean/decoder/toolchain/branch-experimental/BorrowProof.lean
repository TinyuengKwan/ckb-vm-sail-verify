import JoinNested
import SharedLoop
open Aeneas.Std

namespace BorrowRegression
set_option maxRecDepth 10000
set_option maxHeartbeats 8000000

theorem nested_assert (b : Bool) : join_duplicate.join_nested_shared b = .ok () := by
  cases b <;> rfl

/-- The captured shared reference remains valid across arbitrarily many loop
    iterations, including the largest u32 count; no artificial fuel bound. -/
theorem count_loop (n i : U32) :
    join_duplicate.join_nested_shared_in_loop_loop0 n i = .ok () := by
  unfold join_duplicate.join_nested_shared_in_loop_loop0
  rw [loop]
  by_cases hlt : i < n
  · have hi : i.val < n.val := hlt
    have hn : n.val ≤ U32.max := by simpa only [U32.max_eq] using U32.le_max n
    have hb : i.val + (1#u32).val ≤ U32.max := by
      have hone : (1#u32).val = 1 := rfl
      rw [hone]
      omega
    obtain ⟨j, hj, hv⟩ := WP.spec_imp_exists (U32.add_spec (x := i) (y := 1#u32) hb)
    have hs : join_duplicate.join_nested_shared_in_loop_loop0.body n i = .ok (.cont j) := by
      simp [join_duplicate.join_nested_shared_in_loop_loop0.body, hlt, hj]
    rw [hs]
    exact count_loop n j
  · simp [join_duplicate.join_nested_shared_in_loop_loop0.body, hlt]
termination_by n.val - i.val
decreasing_by simp_all; omega

theorem nested_loop (b : Bool) (n : U32) :
    join_duplicate.join_nested_shared_in_loop b n = .ok (if b then 1#i32 else 2#i32) := by
  have h := count_loop n 0#u32
  have h' : join_duplicate.join_nested_shared_in_loop_loop1 n 0#u32 = .ok () := by
    exact h
  cases b <;> simp [join_duplicate.join_nested_shared_in_loop, h, h']

#print axioms nested_assert
#print axioms count_loop
#print axioms nested_loop
end BorrowRegression
