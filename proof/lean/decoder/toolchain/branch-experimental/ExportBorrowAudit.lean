import BorrowProof
import SharedEffectProof
import Lean
open Lean Elab Command

run_cmd do
  let names := #[``BorrowRegression.nested_assert, ``BorrowRegression.count_loop,
    ``BorrowRegression.nested_loop, ``BorrowRegression.next_some,
    ``BorrowRegression.next_done, ``BorrowRegression.add_value,
    ``BorrowRegression.transform_lanes, ``BorrowRegression.empty_extract,
    ``BorrowRegression.two_updates]
  let entries ← names.mapM fun n => do
    let info ← getConstInfo n
    unless info matches .thmInfo _ do throwError "not a theorem: {n}"
    let axioms ← collectAxioms n
    pure (n.toString, Json.mkObj [("type", toJson (reprStr info.type)),
      ("axioms", toJson (axioms.map Name.toString))])
  liftIO <| IO.println ("BORROW_AUDIT_JSON=" ++ (Json.mkObj entries.toList).compress)
