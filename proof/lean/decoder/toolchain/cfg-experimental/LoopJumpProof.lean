import LoopJumpBaseline
import LoopJumpCandidate
open Aeneas.Std

namespace CleanupRegression

/-- The changed upstream golden still yields identical loop semantics for
    every initial iterator, not just the fixture's concrete 0..1 range. -/
theorem loop_body_equal (iter : core.ops.range.Range I32) :
    BaselineCfg.f_loop.body iter = CandidateCfg.f_loop.body iter := by rfl

theorem loop_equal (iter : core.ops.range.Range I32) :
    BaselineCfg.f_loop iter = CandidateCfg.f_loop iter := by rfl

theorem entry_equal : BaselineCfg.f = CandidateCfg.f := by rfl

theorem entry_returns : CandidateCfg.f = .ok () := by
  have hbound : (1 : Int) ≤ I32.max := by rw [I32.max_eq]; decide
  have h : CandidateCfg.f_loop.body { start := 0#i32, «end» := 1#i32 } =
      .ok (.done ()) := by
    simp [CandidateCfg.f_loop.body, core.iter.range.IteratorRange.next,
      core.iter.range.StepI32, core.iter.range.IScalarStep,
      core.iter.range.IScalarStep.forward_checked, core.cmp.PartialOrdI32,
      core.clone.CloneI32, core.cmp.impls.PartialOrdI32.lt, hbound]
  unfold CandidateCfg.f CandidateCfg.f_loop
  rw [loop, h]

#print axioms loop_body_equal
#print axioms loop_equal
#print axioms entry_equal
#print axioms entry_returns
end CleanupRegression
