import CkbVmProduction

/-! Kernel-checked values of constants extracted from the production dependency.
These theorems unfold generated definitions; they do not supply replacements.
The observed footprint consists of the three standard logical axioms,
not a constant-value premise. Guards reject extra dependencies, including sorryAx.
-/
namespace ExtractedConstants
open Aeneas.Std ckb_vm_sail_extract

theorem register_count_eq : ckb_vm_definitions.RISCV_GENERAL_REGISTER_NUMBER = 32#usize := by
  unfold ckb_vm_definitions.RISCV_GENERAL_REGISTER_NUMBER
  rfl

theorem ra_eq : ckb_vm_definitions.registers.RA = 1#usize := by
  unfold ckb_vm_definitions.registers.RA
  rfl

/-- info: 'ExtractedConstants.register_count_eq' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms register_count_eq

/-- info: 'ExtractedConstants.ra_eq' depends on axioms: [propext, Classical.choice, Quot.sound] -/
#guard_msgs in
#print axioms ra_eq

end ExtractedConstants
