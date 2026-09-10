import LeanRV64D.Step

/- Diagnostic queries only. Run from proof/lean/generated/sail:
     lake env lean ../../audit/SailDependencies.lean
   Or from proof/lean/theorems after make proof-imports:
     lake env lean ../audit/SailDependencies.lean
   execute_RTYPE covers all register-register operations; run_hart_active and
   try_step also cover fetch, interrupts and other instructions. -/
#check LeanRV64D.Functions.execute_RTYPE
#print axioms LeanRV64D.Functions.rX_bits
#print axioms LeanRV64D.Functions.wX_bits
#print axioms LeanRV64D.Functions.execute_RTYPE
#print axioms LeanRV64D.Functions.tick_pc
#print axioms LeanRV64D.Functions.run_hart_active
#print axioms LeanRV64D.Functions.try_step
