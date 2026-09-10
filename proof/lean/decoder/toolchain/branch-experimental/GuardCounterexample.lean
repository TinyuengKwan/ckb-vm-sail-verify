import OwnedCleanup
import OwnedGuardMutant
open Aeneas.Std
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000

theorem original_zero :
    guarded_owned_error.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) =
      .ok (.Ok none) := by rfl

theorem mutant_zero :
    GuardedMutant.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) =
      .ok (.Ok (some 11#u8)) := by rfl

theorem wrong_guard_changes_result :
    guarded_owned_error.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) ≠
      GuardedMutant.field_alternatives 0#u64 (.Ok 0#u64) (.Ok 0#u64) := by
  rw [original_zero, mutant_zero]
  intro h
  cases h

#print axioms wrong_guard_changes_result
