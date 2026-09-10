-- Regression probe for the computable type-definition scope used by the adapter.
-- Putting this declaration in a `noncomputable section` panics on Lean 4.31.0.
import Sail

section
namespace SailCompatProbe

inductive AtomicSupport where
  | AMONone | AMOSwap | AMOLogical | AMOArithmetic | AMOCASW | AMOCASD | AMOCASQ
  deriving BEq, Inhabited, Repr

example : (AtomicSupport.AMONone == AtomicSupport.AMONone) = true := rfl
example : (AtomicSupport.AMONone == AtomicSupport.AMOCASQ) = false := rfl

end SailCompatProbe
end
