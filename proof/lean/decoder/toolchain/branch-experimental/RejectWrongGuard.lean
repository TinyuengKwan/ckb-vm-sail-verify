import OwnedCleanup
import OwnedGuardMutant
open Aeneas.Std
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000

example : guarded_owned_error.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) =
    GuardedMutant.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) := by
  rfl
