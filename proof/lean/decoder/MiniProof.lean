import MiniComplete

namespace DecoderRegression
open Aeneas.Std decoder_shared_closure

def expected (bits version : U32) : Result (Option U32) := do
  match (bits &&& 127#u32) with
  | 103#uscalar =>
    let f ← bits >>> 12#i32
    match (f &&& 7#u32) with
    | 0#uscalar =>
      let op := if version >= 1#u32 then 10#u32 else 20#u32
      let r ← bits >>> 7#i32
      let result ← op + (r &&& 31#u32)
      .ok (some result)
    | _ => .ok none
  | 51#uscalar =>
    let r ← bits >>> 7#i32
    .ok (some (r &&& 31#u32))
  | _ => .ok none

theorem all_inputs (bits version : U32) :
    shared_factory bits version = expected bits version := by
  unfold shared_factory shared_factory.closure.Insts.CoreOpsFunctionFnTupleOptionU32.call expected
  simp only [lift, bind_tc_ok]
  split <;> simp_all
  cases hshift : bits >>> 12#i32 <;> simp_all
  split <;> simp_all [core.option.Option.map,
    shared_factory.closure.closure.Insts.CoreOpsFunctionFnOnceTupleU32U32.call_once]
  split <;> rfl

#print axioms all_inputs
end DecoderRegression
