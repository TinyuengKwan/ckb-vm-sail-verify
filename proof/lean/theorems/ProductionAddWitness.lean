import SailContractWitness

/-! A concrete ADD instance with no decoded/path-contract proof arguments.
The seed supplies opaque Rust objects. This does not assert Machine is inhabited,
prove platform-reset reachability, or connect the raw Rust decoder.
-/
namespace AddWitness
open Aeneas.Std AddBoundary AddRegister AddStep ProductionWrapper
open ckb_vm_sail_extract LeanRV64D Functions
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 16000000

def rustRegs : Aeneas.Std.Array U64 32#usize :=
  ⟨[0#u64, 5#u64, 7#u64] ++ List.replicate 29 0#u64, by decide⟩

def rustInitial (seed : Machine) : Machine :=
  { seed with inner := { seed.inner with
      registers := rustRegs
      pc := 0x80000000#u64
      next_pc := 0x80000000#u64
      version := 2#u32 } }

/-- CKB's internal instruction representation, not the original 32-bit word. -/
def internalAdd : U64 := 0x020102000301#u64

theorem internal_decoded : DecodedAdd internalAdd (rustReg 3) (rustReg 1) (rustReg 2) := by
  constructor
  · decide
  · decide
  · decide
  · rfl
  · rfl
  · change Result.ok (UScalar.cast .Usize 3#u8) = Result.ok (rustReg 3)
    apply congrArg Result.ok
    apply UScalar.eq_of_val_eq
    simp
  · change Result.ok (UScalar.cast .Usize 1#u8) = Result.ok (rustReg 1)
    apply congrArg Result.ok
    apply UScalar.eq_of_val_eq
    simp
  · change Result.ok (UScalar.cast .Usize 2#u8) = Result.ok (rustReg 2)
    apply congrArg Result.ok
    apply UScalar.eq_of_val_eq
    simp

theorem initial_related (seed : Machine) : state_rel_pc view (rustInitial seed) initial := by
  constructor
  · intro i
    fin_cases i <;>
      simp [sailGpr, key, initial_regs, initialRegs,
        Std.ExtDHashMap.get?_insert, view, rustInitial, gpr, rustRegs]
  · simp [view, rustInitial, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]

/-- Invokes the existing production theorem with the proved joint witnesses.
All 32 GPRs correspond afterwards; the observed destination is 5 + 7 = 12.
-/
theorem paired_step (seed : Machine) :
    ∃ m' s',
      execute_production internalAdd (rustInitial seed) = .ok (.Ok (), m') ∧
      try_step 0 false initial = .ok false s' ∧
      state_rel_pc view m' s' ∧
      (gpr (view m') 3).bv = 12 ∧
      (view m').pc.bv = 0x80000004 ∧
      (view m').next_pc.bv = 0x80000004 ∧
      s'.regs.get? .nextPC = some 0x80000004 ∧
      (view m').memory = (view (rustInitial seed)).memory ∧ s'.mem = initial.mem := by
  obtain ⟨m', s', hr, hs, hrel, hp, hn, hsn, hg, hm, hsm⟩ :=
    ProductionAdd.decoded_add_step (rustInitial seed) initial (initial_related seed)
      internalAdd 0x002081b3 3 1 2 internal_decoded entry path ready active 0 false
  refine ⟨m', s', hr, hs, hrel, ?_, hp, hn, hsn, hm, hsm⟩
  simpa [view, rustInitial, rustRegs, gpr] using hg 3

end
end AddWitness
