import Lean

-- Installer smoke only, not a VM theorem or an addition to proof coverage.
theorem toolInstallSmoke (n : Nat) : n + 0 = n := Nat.add_zero n
