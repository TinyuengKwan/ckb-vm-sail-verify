import CkbVmProduction
import LeanRV64D.Step
import ExtractedConstants
import AddPremises

/- Both generated models must elaborate in one Lean environment.
   This checks availability and names, not refinement or axiom discharge. -/
#check ckb_vm_sail_extract.execute_production
#check ckb_vm_sail_extract.ckb_vm.instructions.common.add
#check LeanRV64D.Functions.execute_RTYPE
#check LeanRV64D.Functions.run_hart_active
#check LeanRV64D.Functions.tick_pc
#check ExtractedConstants.register_count_eq
#check ExtractedConstants.ra_eq
#check AddBoundary.production_dictionary
#check AddBoundary.RegisterDelegation
#check AddBoundary.PcDelegation
#check AddBoundary.DecodedAdd
