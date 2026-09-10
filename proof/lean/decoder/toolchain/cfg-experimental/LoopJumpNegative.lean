import LoopJumpProof
open Aeneas.Std

-- Expected semantic type rejection, not a missing instance or dependency.
example : CandidateCfg.f = .fail .panic := by
  exact CleanupRegression.entry_returns
