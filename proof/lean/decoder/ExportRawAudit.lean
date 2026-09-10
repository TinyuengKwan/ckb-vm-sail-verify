import RawAddWitness
import MiniProof
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``RawAddDecode.sail_decode, ``RawAddDecode.split_word,
    ``RawAddDecode.raw_add_iff, ``RawAddDecode.reconstruct,
    ``RawAddDecode.factory_dispatch, ``RawAddDecode.index_u64,
    ``RawAddDecode.assemble_value, ``RawAddDecode.rust_decode,
    ``RawAddDecode.internal_decoded, ``RawAddDecode.raw_decoders_correspond,
    ``RawAddDecode.raw_add_step, ``RawAddDecode.decode_context_machine,
    ``RawAddDecode.raw_premises_inhabited, ``RawAddDecode.raw_paired_step,
    ``DecoderRegression.all_inputs]
  let entries ← names.mapM fun declName => do
    let deps ← collectAxioms declName
    let info ← getConstInfo declName
    pure (declName.toString, Json.mkObj [
      ("axioms", toJson (deps.map Name.toString)),
      ("type", toJson (reprStr info.type))])
  let definitions := #[``RawDecodeFactory.decode,
    ``RawDecodeFactory.ckb_vm.instructions.i.factory,
    ``RawDecodeFactory.ckb_vm.instructions.i.factory.closure.Insts.CoreOpsFunctionFnTupleOptionU64.call,
    ``RawDecodeFactory.ckb_vm.instructions.i.factory.closure.closure_6.Insts.CoreOpsFunctionFnOnceTupleU16U64.call_once,
    ``RawDecodeFactory.core.option.Option.map,
    ``RawDecodeFactory.ckb_vm.instructions.Rtype.new,
    ``RawDecodeFactory.ckb_vm.instructions.set_instruction_length_4,
    ``RawDecodeFactory.ckb_vm_definitions.instructions.OP_ADD,
    ``RawDecodeFactory.ckb_vm.machine.VERSION2,
    ``RawDecodeFactory.U64.Insts.Ckb_vmInstructionsRegisterRegister.BITS,
    ``RawAddDecode.encode, ``RawAddDecode.internal, ``RawAddDecode.RawFetchPath.toActive,
    ``RawAddDecode.rawPath, ``DecoderRegression.expected,
    ``decoder_shared_closure.shared_factory,
    ``decoder_shared_closure.core.option.Option.map,
    ``LeanRV64D.Functions.ext_decode]
  let bodies ← definitions.mapM fun declName => do
    let info ← getConstInfo declName
    let body := match info with
      | .defnInfo d => reprStr d.value
      | _ => "NOT_A_DEFINITION"
    pure (declName.toString, toJson body)
  liftIO <| IO.println ("RAW_ADD_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList)]).compress)
