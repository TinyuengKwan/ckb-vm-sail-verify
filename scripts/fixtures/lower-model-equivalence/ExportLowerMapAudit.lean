import LowerMapEquivalence
import Lean
open Aeneas Aeneas.Std Lean Elab Command

-- These fixed types reject an extra premise even if its proof compiles.
example {T U F : Type} (ops : core.ops.function.FnOnce F T U)
    (value : Option T) (f : F) :
    RawDecodeFactory.core.option.Option.map ops value f =
      ArchivedRawDecodeFactory.core.option.Option.map ops value f :=
  LowerMapEquivalence.factory_map ops value f

example {T U F : Type} (ops : core.ops.function.FnOnce F T U)
    (value : Option T) (f : F) :
    decoder_shared_closure.core.option.Option.map ops value f =
      archived_decoder_shared_closure.core.option.Option.map ops value f :=
  LowerMapEquivalence.mini_map ops value f

example {T U F : Type} (ops : core.ops.function.FnOnce F T U) :
    (@RawDecodeFactory.core.option.Option.map T U F ops) =
      (@ArchivedRawDecodeFactory.core.option.Option.map T U F ops) :=
  LowerMapEquivalence.factory_map_function ops

example {T U F : Type} (ops : core.ops.function.FnOnce F T U) :
    (@decoder_shared_closure.core.option.Option.map T U F ops) =
      (@archived_decoder_shared_closure.core.option.Option.map T U F ops) :=
  LowerMapEquivalence.mini_map_function ops

run_cmd do
  let names := #[``LowerMapEquivalence.factory_map, ``LowerMapEquivalence.mini_map,
    ``LowerMapEquivalence.factory_map_function, ``LowerMapEquivalence.mini_map_function]
  let entries ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let axioms ← collectAxioms declName
    pure (declName.toString, Json.mkObj [("type", toJson (reprStr info.type)),
      ("axioms", toJson (axioms.map Name.toString))])
  let names := #[``RawDecodeFactory.core.option.Option.map,
    ``ArchivedRawDecodeFactory.core.option.Option.map,
    ``decoder_shared_closure.core.option.Option.map,
    ``archived_decoder_shared_closure.core.option.Option.map]
  let bodies ← names.mapM fun declName => do
    let info ← getConstInfo declName
    let body := match info with
      | .defnInfo d => reprStr d.value
      | _ => "NOT_A_DEFINITION"
    pure (declName.toString, toJson body)
  liftIO <| IO.println ("LOWER_MAP_AUDIT_JSON=" ++
    (Json.mkObj [("theorems", Json.mkObj entries.toList),
      ("definitions", Json.mkObj bodies.toList)]).compress)
