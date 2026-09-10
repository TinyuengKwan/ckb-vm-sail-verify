import FnPtrFullMir

namespace FullMirIterator
open Aeneas Aeneas.Std fnptr_cases

theorem into_iterator {T : Type} (A : Type) (v : alloc.vec.Vec T) :
    SharedAVec.Insts.CoreIterTraitsCollectIntoIteratorSharedATIter.into_iter A v =
      .ok ⟨alloc.vec.Vec.deref v, 0⟩ := rfl

def hitTable (inst : U64) : Table := ⟨⟨[fun _ _ => .ok (some inst)], by scalar_tac⟩⟩
def emptyTable : Table := ⟨⟨[], by scalar_tac⟩⟩
def missHitTable (inst : U64) : Table :=
  ⟨⟨[fun _ _ => .ok none, fun _ _ => .ok (some inst)], by scalar_tac⟩⟩

theorem actual_entry_hit (b : U32) (inst : U64) :
    through_table (hitTable inst) b = .ok (some inst) := by
  change through_table_loop ⟨alloc.vec.Vec.deref (hitTable inst).entries, 0⟩ b = _
  unfold through_table_loop
  rw [loop]
  rfl

theorem actual_entry_empty (b : U32) :
    through_table emptyTable b = .ok none := by
  change through_table_loop ⟨alloc.vec.Vec.deref emptyTable.entries, 0⟩ b = _
  unfold through_table_loop
  rw [loop]
  rfl

theorem actual_entry_order (b : U32) (inst : U64) :
    through_table (missHitTable inst) b = .ok (some inst) := by
  change through_table_loop ⟨alloc.vec.Vec.deref (missHitTable inst).entries, 0⟩ b = _
  unfold through_table_loop
  rw [loop]
  change loop (fun it => through_table_loop.body b it)
    ⟨alloc.vec.Vec.deref (missHitTable inst).entries, 1⟩ = _
  rw [loop]
  rfl

#print axioms into_iterator
#print axioms actual_entry_hit
#print axioms actual_entry_empty
#print axioms actual_entry_order
end FullMirIterator
