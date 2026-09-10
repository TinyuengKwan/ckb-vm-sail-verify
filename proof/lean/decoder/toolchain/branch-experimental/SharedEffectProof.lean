import SharedLoop
open Aeneas.Std loop_shared_loan_in_join

namespace BorrowRegression
set_option maxRecDepth 10000
set_option maxHeartbeats 8000000

def lanes (a b c d : U64) : Array U64 4#usize := ⟨[a,b,c,d], by simp⟩
def output (a b : U64) : Slice U64 := ⟨[a,b], by simp; scalar_tac⟩
def start : State := ⟨lanes 10#u64 20#u64 30#u64 40#u64, 1#u32, 1#u32, 7#u8, true⟩
def finish : State := ⟨lanes 12#u64 22#u64 32#u64 42#u64, 1#u32, 1#u32, 7#u8, true⟩

theorem next_some (i j n : Usize) (hi : i < n) (hj : i.val + 1 = j.val) :
    core.iter.range.IteratorRange.next core.iter.range.StepUsize ⟨i,n⟩ = .ok (some i, ⟨j,n⟩) := by
  have hb : i.val + (1#usize).val ≤ UScalar.max .Usize := by scalar_tac
  simp only [core.iter.range.IteratorRange.next, core.iter.range.StepUsize,
    core.iter.range.UScalarStep, core.cmp.PartialOrdUsize, core.cmp.impls.PartialOrdUsize.lt,
    core.clone.CloneUsize, core.clone.impls.CloneUsize.clone,
    core.iter.range.UScalarStep.forward_checked, bind_tc_ok]
  simp only [show i.val < n.val from hi, decide_true, ↓reduceIte, hb, ↓reduceDIte,
    bind_tc_ok]
  congr 3
  apply UScalar.eq_of_val_eq
  simpa using hj

theorem next_done (n : Usize) :
    core.iter.range.IteratorRange.next core.iter.range.StepUsize ⟨n,n⟩ = .ok (none, ⟨n,n⟩) := by
  simp [core.iter.range.IteratorRange.next, core.iter.range.StepUsize,
    core.iter.range.UScalarStep, core.cmp.PartialOrdUsize, core.cmp.impls.PartialOrdUsize.lt]

theorem add_value {ty : UScalarTy} (x y z : UScalar ty) (h : x.val + y.val = z.val) :
    (x + y : Result (UScalar ty)) = Result.ok z := by
  have hb : x.val + y.val ≤ UScalar.max ty := by scalar_tac
  obtain ⟨v,hv,hval⟩ := WP.spec_imp_exists (UScalar.add_spec hb)
  have heq : v = z := UScalar.eq_of_val_eq (hval.trans h)
  simpa only [heq] using hv

theorem transform_lanes (a b c d : U64) : transform (lanes a b c d) =
    .ok (lanes (core.num.U64.wrapping_add a 1#u64) (core.num.U64.wrapping_add b 1#u64)
      (core.num.U64.wrapping_add c 1#u64) (core.num.U64.wrapping_add d 1#u64)) := by
  have h0 := next_some 0#usize 1#usize 4#usize (by decide) (by simp)
  have h1 := next_some 1#usize 2#usize 4#usize (by decide) (by simp)
  have h2 := next_some 2#usize 3#usize 4#usize (by decide) (by simp)
  have h3 := next_some 3#usize 4#usize 4#usize (by decide) (by simp)
  unfold transform transform_loop
  iterate 5
    rw [loop]
    simp only [transform_loop.body, h0, h1, h2, h3, next_done, bind_tc_ok,
      lift, Array.index_usize, Array.update, lanes]
    simp

theorem empty_extract (s : State) (r : Slice U64) :
    State.extract s r 0#usize = .ok (s,r) := by
  unfold State.extract State.extract_loop
  simp only [lift, bind_tc_ok]
  rw [loop]
  simp [State.extract_loop.body, core.iter.range.IteratorRange.next,
    core.iter.range.StepUsize, core.iter.range.UScalarStep,
    core.cmp.PartialOrdUsize, core.cmp.impls.PartialOrdUsize.lt]

/-- Two transforming iterations: reading the old data at the back edge would
    incorrectly yield 11 twice. The actual result must contain 11 then 12. -/
theorem two_updates : State.extract start (output 0#u64 0#u64) 2#usize =
    .ok (finish, output 11#u64 12#u64) := by
  have h0 := next_some 0#usize 1#usize 2#usize (by decide) (by simp)
  have h1 := next_some 1#usize 2#usize 2#usize (by decide) (by simp)
  have h32 := add_value 0#u32 1#u32 1#u32 (by rfl)
  have hs := add_value 0#usize 1#usize 1#usize (by simp)
  have ht1 : transform ⟨[10#u64,20#u64,30#u64,40#u64], by simp⟩ =
      .ok ⟨[11#u64,21#u64,31#u64,41#u64], by simp⟩ := by
    exact transform_lanes 10#u64 20#u64 30#u64 40#u64
  have ht2 : transform ⟨[11#u64,21#u64,31#u64,41#u64], by simp⟩ =
      .ok ⟨[12#u64,22#u64,32#u64,42#u64], by simp⟩ := by
    exact transform_lanes 11#u64 21#u64 31#u64 41#u64
  unfold State.extract State.extract_loop
  simp only [lift, bind_tc_ok]
  iterate 3
    rw [loop]
    simp [State.extract_loop.body, start, finish, h0, h1, next_done,
      ht1, ht2, h32, hs, lift, Array.index_usize, Slice.update,
      core.num.U64.wrapping_add, lanes, output]

#print axioms empty_extract
#print axioms two_updates
end BorrowRegression
