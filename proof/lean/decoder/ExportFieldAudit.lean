import RawFields
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``RawAddFields.rd, ``RawAddFields.rs1, ``RawAddFields.rs2,
    ``RawAddFields.opcode, ``RawAddFields.funct3, ``RawAddFields.funct7,
    ``RawAddFields.index_val, ``RawAddFields.sail_reg_decode,
    ``RawAddFields.operands_correspond]
  let entries ← names.mapM fun declName => do
    let deps ← collectAxioms declName
    let info ← getConstInfo declName
    pure (declName.toString, Json.mkObj [
      ("axioms", toJson (deps.map Name.toString)),
      ("type", toJson (reprStr info.type))])
  let definitions := #[``RawAddFields.index,
    ``RawDecodeExtract.instructions.utils.x, ``RawDecodeExtract.instructions.utils.rd,
    ``RawDecodeExtract.instructions.utils.rs1, ``RawDecodeExtract.instructions.utils.rs2,
    ``RawDecodeExtract.instructions.utils.opcode, ``RawDecodeExtract.instructions.utils.funct3,
    ``RawDecodeExtract.instructions.utils.funct7, ``LeanRV64D.Functions.encdec_reg_backwards]
  let bodies ← definitions.mapM fun declName => do
    let info ← getConstInfo declName
    let body := match info with
      | .defnInfo d => reprStr d.value
      | _ => "NOT_A_DEFINITION"
    pure (declName.toString, toJson body)
  liftIO <| IO.println ("FIELD_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList)]).compress)
