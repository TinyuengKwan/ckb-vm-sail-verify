import ProductionAdd
import ProductionAddWitness
import Lean

open Lean Elab Command

run_cmd do
  let modules := (← getEnv).header.moduleNames
  if modules.contains `LeanRV64D.Specialization then
    throwError "stale Specialization module is imported"
  unless modules.contains `LeanRV64D.SpecializationV1 do
    throwError "expected SpecializationV1 module is missing"
  liftIO <| IO.println ("SAIL_MODULE_AUDIT=" ++ (toJson (modules.map Name.toString)).compress)
