import OuterInit

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

abbrev Cache := Array (U64 × U64) 4096#usize
abbrev Factory := U32 → U32 → Result (Option U64)
def factoryIter (i : Nat) : core.slice.iter.Iter Factory :=
  ⟨alloc.vec.Vec.deref (initial 2#u32).factories, i⟩

abbrev LoopResult := Result (ControlFlow (core.slice.iter.Iter Factory)
  (core.result.Result U64 ckb_vm.error.Error × Cache))

theorem iterator_entry :
    SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter
      Global (initial 2#u32).factories = .ok (factoryIter 0) := rfl

theorem next_zero : core.slice.iter.IteratorSliceIter.next (factoryIter 0) =
    .ok (some compressedFactory, factoryIter 1) := rfl
theorem next_one : core.slice.iter.IteratorSliceIter.next (factoryIter 1) =
    .ok (some addFactory, factoryIter 2) := rfl

theorem cache_update (a : Cache) (k : Usize) (pair : U64 × U64)
    (hk : k.val < a.val.length) :
    Array.update a k pair = .ok (a.set k pair) := by
  simp only [Array.update, Array.getElem?_Usize_eq, List.getElem?_eq_getElem hk]
  rfl

theorem cache_write_visible (a : Cache) (k : Usize) (pair : U64 × U64)
    (hk : k.val < a.val.length) :
    Array.index_usize (a.set k pair) k = .ok pair := by
  simp only [Array.index_usize, Array.getElem?_Usize_eq, Array.set_val_eq,
    List.getElem?_set_self hk]

theorem cache_other_unchanged (a : Cache) (k j : Usize) (pair : U64 × U64)
    (hne : j ≠ k) :
    Array.index_usize (a.set k pair) j = Array.index_usize a j := by
  have hv : j.val ≠ k.val := fun h => hne (UScalar.eq_of_val_eq h)
  simp [Array.index_usize, Array.set, hv]

theorem first_factory_skips (a : Cache) (pc : U64) (k : Usize)
    (rd rs1 rs2 : BitVec 5) :
    ckb_vm.decoder.DefaultDecoder.decode_raw_loop.body 2#u32 a pc k
      (⟨encode rd rs1 rs2⟩ : U32) (factoryIter 0) = .ok (.cont (factoryIter 1)) := by
  let continuation (out : Result (Option U64)) : LoopResult := do
    let o ← out
    match o with
    | none => .ok (.cont (factoryIter 1))
    | some inst =>
      let a' ← Array.update a k (pc, inst)
      .ok (.done (.Ok inst, a'))
  exact congrArg continuation (compressed_rejects_add rd rs1 rs2 2#u32)

theorem second_factory_writes (a : Cache) (pc : U64) (k : Usize)
    (hk : k.val < a.val.length) (rd rs1 rs2 : BitVec 5) :
    ckb_vm.decoder.DefaultDecoder.decode_raw_loop.body 2#u32 a pc k
      (⟨encode rd rs1 rs2⟩ : U32) (factoryIter 1) =
      .ok (.done (.Ok (internal rd rs1 rs2), a.set k (pc, internal rd rs1 rs2))) := by
  let continuation (out : Result (Option U64)) : LoopResult := do
    let o ← out
    match o with
    | none => .ok (.cont (factoryIter 2))
    | some inst =>
      let a' ← Array.update a k (pc, inst)
      .ok (.done (.Ok inst, a'))
  have hc := congrArg continuation (add_decode rd rs1 rs2)
  have hu := congrArg (fun (out : Result Cache) => do
    let a' ← out
    (Result.ok (.done (.Ok (internal rd rs1 rs2), a')) : LoopResult))
    (cache_update a k (pc, internal rd rs1 rs2) hk)
  exact hc.trans hu

theorem factory_loop_add (a : Cache) (pc : U64) (k : Usize)
    (hk : k.val < a.val.length) (rd rs1 rs2 : BitVec 5) :
    ckb_vm.decoder.DefaultDecoder.decode_raw_loop (factoryIter 0) 2#u32 a pc k
      (⟨encode rd rs1 rs2⟩ : U32) =
      .ok (.Ok (internal rd rs1 rs2), a.set k (pc, internal rd rs1 rs2)) := by
  unfold ckb_vm.decoder.DefaultDecoder.decode_raw_loop
  rw [loop, first_factory_skips]
  change loop _ (factoryIter 1) = _
  rw [loop, second_factory_writes a pc k hk]

#print axioms iterator_entry
#print axioms factory_loop_add
#print axioms cache_write_visible
#print axioms cache_other_unchanged
end
end OuterAdd
