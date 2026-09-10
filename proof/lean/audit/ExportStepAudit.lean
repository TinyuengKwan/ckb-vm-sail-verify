import ProductionAdd
import ProductionAddWitness
import Lean

/-! Machine-readable evidence from the elaborated environment, not a source grep.
The policy separately pins source contents, so changing a referenced definition
without changing its name also requires review. This file adds no proof axioms. -/
open Lean Elab Command

run_cmd do
  let theoremName := ``ProductionAdd.decoded_add_step
  let axioms ← collectAxioms theoremName
  let contracts := #[``ProductionWrapper.registerDelegation, ``ProductionWrapper.pcDelegation]
  let contractEntries ← contracts.mapM fun declName => do
    let deps ← collectAxioms declName
    pure (declName.toString, toJson (deps.map Name.toString))
  let witnesses := #[``AddWitness.sail_contracts_jointly_inhabited,
      ``AddWitness.paired_step, ``AddWitness.internal_decoded,
      ``AddWitness.initial_related, ``AddWitness.decode_add]
  let witnessEntries ← witnesses.mapM fun declName => do
    let deps ← collectAxioms declName
    pure (declName.toString, toJson (deps.map Name.toString))
  let names := #[theoremName, ``AddStep.decoded_add_step,
      ``ProductionWrapper.view, ``ProductionWrapper.valid,
      ``ProductionWrapper.valid_all, ``ProductionWrapper.valid_iff,
      ``ProductionWrapper.registerDelegation, ``ProductionWrapper.pcDelegation,
      ``AddBoundary.RegisterDelegation.mk, ``AddBoundary.PcDelegation.mk,
      ``AddBoundary.DecodedAdd.mk, ``AddStep.ArchFrame.mk,
      ``AddStep.StepEntry.mk, ``AddStep.ActiveAddPath.mk, ``AddStep.RetireReady.mk,
      ``AddStep.state_rel_pc, ``AddRegister.state_rel, ``AddStep.StepEntry.prepared,
      ``AddWitness.sail_contracts_jointly_inhabited, ``AddWitness.paired_step,
      ``AddWitness.initial_related, ``AddWitness.internal_decoded,
      ``AddWitness.initial, ``AddWitness.initialRegs, ``AddWitness.ram,
      ``AddWitness.rustInitial, ``AddWitness.rustRegs, ``AddWitness.internalAdd,
      ``AddWitness.entry, ``AddWitness.path, ``AddWitness.ready]
  let boundaryEntries ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let body := match info with
      | .defnInfo value => reprStr value.value
      | _ => ""
    pure (declName.toString, Json.mkObj [
      ("type", toJson (reprStr info.type)), ("definition", toJson body)])
  let evidence := Json.mkObj [
    ("theorem", toJson theoremName.toString),
    ("axioms", toJson (axioms.map Name.toString)),
    ("boundary", Json.mkObj boundaryEntries.toList),
    ("contract_axioms", Json.mkObj contractEntries.toList),
    ("witness_axioms", Json.mkObj witnessEntries.toList)]
  liftIO <| IO.println ("PROOF_AUDIT_JSON=" ++ evidence.compress)
