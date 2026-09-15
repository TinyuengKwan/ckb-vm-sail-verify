import FactoryScoped
import MiniComplete
import ArchivedFactoryScoped
import ArchivedMiniComplete

namespace LowerMapEquivalence
open Aeneas Aeneas.Std Result ControlFlow

-- Both sides refer to complete, actually generated modules. The archived
-- copies differ from the approved files only in their enclosing namespace.
theorem factory_map {T U F : Type} (ops : core.ops.function.FnOnce F T U)
    (value : Option T) (f : F) :
    RawDecodeFactory.core.option.Option.map ops value f =
      ArchivedRawDecodeFactory.core.option.Option.map ops value f := by
  cases value with
  | none => rfl
  | some x =>
    unfold RawDecodeFactory.core.option.Option.map
      ArchivedRawDecodeFactory.core.option.Option.map
    cases h : ops.call_once f x <;> simp [h]

theorem mini_map {T U F : Type} (ops : core.ops.function.FnOnce F T U)
    (value : Option T) (f : F) :
    decoder_shared_closure.core.option.Option.map ops value f =
      archived_decoder_shared_closure.core.option.Option.map ops value f := by
  cases value with
  | none => rfl
  | some x =>
    unfold decoder_shared_closure.core.option.Option.map
      archived_decoder_shared_closure.core.option.Option.map
    cases h : ops.call_once f x <;> simp [h]

theorem factory_map_function {T U F : Type} (ops : core.ops.function.FnOnce F T U) :
    (@RawDecodeFactory.core.option.Option.map T U F ops) =
      (@ArchivedRawDecodeFactory.core.option.Option.map T U F ops) := by
  funext value f
  exact factory_map ops value f

theorem mini_map_function {T U F : Type} (ops : core.ops.function.FnOnce F T U) :
    (@decoder_shared_closure.core.option.Option.map T U F ops) =
      (@archived_decoder_shared_closure.core.option.Option.map T U F ops) := by
  funext value f
  exact mini_map ops value f

end LowerMapEquivalence
