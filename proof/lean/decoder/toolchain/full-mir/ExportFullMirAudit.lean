import IteratorProof
import OuterEntry
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``FullMirIterator.into_iterator, ``FullMirIterator.actual_entry_hit,
    ``FullMirIterator.actual_entry_empty, ``FullMirIterator.actual_entry_order,
    ``OuterAdd.factory_rd, ``OuterAdd.factory_rs1, ``OuterAdd.factory_rs2,
    ``OuterAdd.factory_op, ``OuterAdd.factory_f3, ``OuterAdd.factory_f7,
    ``OuterAdd.add_dispatch, ``OuterAdd.add_decode, ``OuterAdd.compressed_mask,
    ``OuterAdd.compressed_rejects_add, ``OuterAdd.initial_new,
    ``OuterAdd.initial_factories, ``OuterAdd.initial_mop_off, ``OuterAdd.initial_cache,
    ``OuterAdd.iterator_entry, ``OuterAdd.next_zero, ``OuterAdd.next_one,
    ``OuterAdd.cache_update, ``OuterAdd.cache_write_visible, ``OuterAdd.cache_other_unchanged,
    ``OuterAdd.first_factory_skips, ``OuterAdd.second_factory_writes, ``OuterAdd.factory_loop_add,
    ``OuterAdd.page_mask, ``OuterAdd.add_low_two, ``OuterAdd.fetch_add32,
    ``OuterAdd.fresh_initial, ``OuterAdd.decode_raw_zero]
  let entries ← names.mapM fun declName => do
    let axioms ← collectAxioms declName
    let info ← getConstInfo declName
    unless info matches .thmInfo _ do throwError "not a theorem: {declName}"
    pure (declName.toString, Json.mkObj [
      ("axioms", toJson (axioms.map Name.toString)), ("type", toJson (reprStr info.type))])
  let names := #[
    ``fnptr_cases.SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter,
    ``OuterDecodeCandidate.SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.empty,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.add_instruction_factory,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.new,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_bits,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_raw,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_raw_loop,
    ``OuterDecodeCandidate.ckb_vm.decoder.DefaultDecoder.decode_raw_loop.body,
    ``OuterDecodeCandidate.ckb_vm.instructions.i.factory,
    ``OuterDecodeCandidate.ckb_vm.instructions.rvc.factory,
    ``OuterDecodeCandidate.ckb_vm.instructions.Rtype.new,
    ``OuterDecodeCandidate.ckb_vm.instructions.set_instruction_length_4,
    ``OuterDecodeCandidate.fresh_decoder,
    ``OuterAdd.initial, ``OuterAdd.factoryIter]
  let bodies ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let body ← match info with
      | .defnInfo d => pure (reprStr d.value)
      | _ => throwError "not a definition: {declName}"
    pure (declName.toString, toJson body)
  liftIO <| IO.println ("FULL_MIR_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList)]).compress)
