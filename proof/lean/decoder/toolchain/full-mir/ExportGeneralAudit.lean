import OuterStepWitness
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``OuterAdd.cache_key_val, ``OuterAdd.cache_key_bound,
    ``OuterAdd.key_in_cache, ``OuterAdd.key_remainder, ``OuterAdd.decode_raw_key,
    ``OuterAdd.decode_cache_hit, ``OuterAdd.decode_cache_miss, ``OuterAdd.pc_not_sentinel,
    ``OuterAdd.decode_cold_fast, ``OuterAdd.half_low_mask, ``OuterAdd.halves_rejoin,
    ``OuterAdd.pc_add_two, ``OuterAdd.fetch_add16, ``OuterAdd.fetch_encoded,
    ``OuterAdd.fetch_word, ``OuterAdd.decode_cold_word, ``OuterAdd.decode_written_hit,
    ``OuterAdd.fast_word_witness, ``OuterAdd.edge_word_witness,
    ``OuterAdd.fast_decoder_witness, ``OuterAdd.edge_decoder_witness,
    ``OuterAdd.cold_raw_add_step, ``OuterAdd.paired_fetch, ``OuterAdd.cold_paired_step]
  let entries ← names.mapM fun declName => do
    let deps ← collectAxioms declName
    let info ← getConstInfo declName
    unless info matches .thmInfo _ do throwError "not a theorem: {declName}"
    pure (declName.toString, Json.mkObj [
      ("axioms", toJson (deps.map Name.toString)), ("type", toJson (reprStr info.type))])
  let names := #[``OuterAdd.foldedPc, ``OuterAdd.cacheKey, ``OuterAdd.withCache,
    ``OuterAdd.lowHalf, ``OuterAdd.highHalf, ``OuterAdd.nextHalfPc,
    ``OuterAdd.sailActive, ``OuterAdd.wordMemory, ``OuterAdd.pairedMemory]
  let bodies ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let body ← match info with
      | .defnInfo d => pure (reprStr d.value)
      | _ => throwError "not a definition: {declName}"
    pure (declName.toString, toJson body)
  let contracts ← #[``OuterAdd.WordFetch, ``OuterAdd.WordFetch.fast,
    ``OuterAdd.WordFetch.edge].mapM fun declName => do
    let info ← getConstInfo declName
    let kind ← match info with
      | .inductInfo _ => pure "inductive"
      | .ctorInfo _ => pure "constructor"
      | _ => throwError "not a contract declaration: {declName}"
    pure (declName.toString, toJson (kind ++ ":" ++ reprStr info.type))
  liftIO <| IO.println ("GENERAL_DECODER_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList),
      ("contracts", Json.mkObj contracts.toList)]).compress)
