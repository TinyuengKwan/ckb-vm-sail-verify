import AddPremises
import LeanRV64D.Regs
import Mathlib.Tactic.FinCases

/-! Register-only architectural relation. Missing Sail keys are not accepted.
The projection is still a parameter because the production wrapper is opaque.
No correspondence of PC, decoder, memory contents or retirement is asserted.
-/
namespace AddRegister
open Aeneas.Std
open LeanRV64D

noncomputable section
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000

abbrev Reg := Fin 32
abbrev SailState := Sail.ConcurrencyInterfaceV1.SequentialState
  RegisterType Sail.ConcurrencyInterfaceV1.trivialChoiceSource

-- Index zero is a sentinel, never read or written as a GPR.
def key (i : Reg) : {r : Register // RegisterType r = BitVec 64} :=
  match i.val with
  | 1 => ⟨.x1, rfl⟩
  | 2 => ⟨.x2, rfl⟩
  | 3 => ⟨.x3, rfl⟩
  | 4 => ⟨.x4, rfl⟩
  | 5 => ⟨.x5, rfl⟩
  | 6 => ⟨.x6, rfl⟩
  | 7 => ⟨.x7, rfl⟩
  | 8 => ⟨.x8, rfl⟩
  | 9 => ⟨.x9, rfl⟩
  | 10 => ⟨.x10, rfl⟩
  | 11 => ⟨.x11, rfl⟩
  | 12 => ⟨.x12, rfl⟩
  | 13 => ⟨.x13, rfl⟩
  | 14 => ⟨.x14, rfl⟩
  | 15 => ⟨.x15, rfl⟩
  | 16 => ⟨.x16, rfl⟩
  | 17 => ⟨.x17, rfl⟩
  | 18 => ⟨.x18, rfl⟩
  | 19 => ⟨.x19, rfl⟩
  | 20 => ⟨.x20, rfl⟩
  | 21 => ⟨.x21, rfl⟩
  | 22 => ⟨.x22, rfl⟩
  | 23 => ⟨.x23, rfl⟩
  | 24 => ⟨.x24, rfl⟩
  | 25 => ⟨.x25, rfl⟩
  | 26 => ⟨.x26, rfl⟩
  | 27 => ⟨.x27, rfl⟩
  | 28 => ⟨.x28, rfl⟩
  | 29 => ⟨.x29, rfl⟩
  | 30 => ⟨.x30, rfl⟩
  | 31 => ⟨.x31, rfl⟩
  | _ => ⟨.PC, rfl⟩

private def keyNumber : Register → Nat
  | .x1 => 1
  | .x2 => 2
  | .x3 => 3
  | .x4 => 4
  | .x5 => 5
  | .x6 => 6
  | .x7 => 7
  | .x8 => 8
  | .x9 => 9
  | .x10 => 10
  | .x11 => 11
  | .x12 => 12
  | .x13 => 13
  | .x14 => 14
  | .x15 => 15
  | .x16 => 16
  | .x17 => 17
  | .x18 => 18
  | .x19 => 19
  | .x20 => 20
  | .x21 => 21
  | .x22 => 22
  | .x23 => 23
  | .x24 => 24
  | .x25 => 25
  | .x26 => 26
  | .x27 => 27
  | .x28 => 28
  | .x29 => 29
  | .x30 => 30
  | .x31 => 31
  | _ => 0

private theorem key_number (i : Reg) : keyNumber (key i).val = i.val := by
  fin_cases i <;> rfl

theorem key_injective : Function.Injective (fun i => (key i).val) := by
  intro i j h
  apply Fin.ext
  simpa only [key_number] using congrArg keyNumber h

def sailReg (i : Reg) : regidx := .Regidx (BitVec.ofNat 5 i.val)
def rustReg (i : Reg) : Usize := Usize.ofNat i.val (by have := i.isLt; scalar_tac)
def gpr (c : AddBoundary.Core) (i : Reg) : U64 := c.registers.val[i.val]!

def sailGpr (s : SailState) (i : Reg) : Option (BitVec 64) :=
  if i = 0 then some 0 else
    (s.regs.get? (key i).val).map (cast (key i).property)

def putGpr (s : SailState) (i : Reg) (v : BitVec 64) : SailState :=
  if i = 0 then s else
    { s with regs := s.regs.insert (key i).val (cast (key i).property.symm v) }

/-- All 32 values correspond; for nonzero indices this requires the map key to
exist. The zero equation forces the Rust x0 value to be zero. -/
def state_rel (view : AddBoundary.Machine → AddBoundary.Core)
    (m : AddBoundary.Machine) (s : SailState) : Prop :=
  ∀ i : Reg, sailGpr s i = some (gpr (view m) i).bv

theorem sailGpr_put (s : SailState) (i j : Reg) (v : BitVec 64) :
    sailGpr (putGpr s i v) j =
      if i ≠ 0 ∧ j = i then some v else sailGpr s j := by
  by_cases hi : i = 0
  · simp [putGpr, hi]
  by_cases hj : j = 0
  · simp [sailGpr, hj, hi, Ne.symm hi]
  by_cases hji : j = i
  · subst j
    simp [sailGpr, putGpr, hi]
  · have hk : (key i).val ≠ (key j).val := by
      intro h
      exact hji (key_injective h).symm
    simp [sailGpr, putGpr, hi, hj, hji, Std.ExtDHashMap.get?_insert, hk]

end
end AddRegister
