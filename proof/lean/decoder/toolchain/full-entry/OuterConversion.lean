import OuterRawLinked

namespace OuterConversion
open Aeneas.Std OuterDecodeCandidate
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000

/-- Kernel-evaluated boundary checks on the extracted standard-library body,
    including its actual error constructor. No handwritten replacement. -/
theorem convert_zero :
    I32.Insts.CoreConvertTryFromU64TryFromIntError.try_from 0#u64 =
      .ok (.Ok 0#i32) := by rfl

theorem convert_max_signed :
    I32.Insts.CoreConvertTryFromU64TryFromIntError.try_from 2147483647#u64 =
      .ok (.Ok 2147483647#i32) := by rfl

theorem reject_first_overflow :
    I32.Insts.CoreConvertTryFromU64TryFromIntError.try_from 2147483648#u64 =
      .ok (.Err core.num.error.IntErrorKind.PosOverflow) := by rfl

theorem reject_max_unsigned :
    I32.Insts.CoreConvertTryFromU64TryFromIntError.try_from 18446744073709551615#u64 =
      .ok (.Err core.num.error.IntErrorKind.PosOverflow) := by rfl

#print axioms convert_zero
#print axioms convert_max_signed
#print axioms reject_first_overflow
#print axioms reject_max_unsigned
end OuterConversion
