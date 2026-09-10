import OuterPublicWitness
import OuterConversion
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``OuterAdd.public_mop_off, ``OuterAdd.decode_cold_public_word,
    ``OuterAdd.sparse_public_mop_off, ``OuterAdd.fresh_public_word,
    ``OuterAdd.cold_public_add_step, ``OuterAdd.fast_public_witness,
    ``OuterAdd.edge_public_witness, ``OuterAdd.cold_public_paired_step,
    ``OuterConversion.convert_zero, ``OuterConversion.convert_max_signed,
    ``OuterConversion.reject_first_overflow, ``OuterConversion.reject_max_unsigned]
  let entries ← names.mapM fun declName => do
    let deps ← collectAxioms declName
    let info ← getConstInfo declName
    unless info matches .thmInfo _ do throwError "not a theorem: {declName}"
    pure (declName.toString, Json.mkObj [
      ("axioms", toJson (deps.map Name.toString)), ("type", toJson (reprStr info.type))])
  let names := #[
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_1,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_2,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_3,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_4,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_5,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure.Insts.CoreOpsFunctionFnPairMutDefaultDecoderMutMResultOptionU64Error.call,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_1.Insts.CoreOpsFunctionFnPairMutDefaultDecoderMutMResultOptionU64Error.call,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_2.Insts.CoreOpsFunctionFnPairMutDefaultDecoderMutMResultOptionU64Error.call,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_3.Insts.CoreOpsFunctionFnPairMutDefaultDecoderMutMResultOptionU64Error.call,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_4.Insts.CoreOpsFunctionFnPairMutDefaultDecoderMutMResultOptionU64Error.call,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_mop.closure_5.Insts.CoreOpsFunctionFnOnceTupleI32OptionI32.call_once,
    ``OuterDecodeCandidate.ckb_vm.machine.VERSION3,
    ``OuterDecodeCandidate.core.num.error.TryFromIntError,
    ``OuterDecodeCandidate.I32.Insts.CoreConvertTryFromU64TryFromIntError.try_from,
    ``OuterDecodeCandidate.ckb_vm.instructions.m.factory,
    ``OuterDecodeCandidate.ckb_vm.instructions.b.factory,
    ``OuterDecodeCandidate.decode]
  let bodies ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let body ← match info with
      | .defnInfo d => pure (reprStr d.value)
      | _ => throwError "not a definition: {declName}"
    pure (declName.toString, toJson body)
  liftIO <| IO.println ("PUBLIC_DECODER_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList)]).compress)
