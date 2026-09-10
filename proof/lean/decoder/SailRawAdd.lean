import RawFields

namespace RawAddDecode
open LeanRV64D Functions AddStep AddRegister
noncomputable section
set_option maxRecDepth 1000000
set_option maxHeartbeats 16000000
set_option linter.unusedSimpArgs false

def encode (rd rs1 rs2 : BitVec 5) : BitVec 32 :=
  BitVec.append (BitVec.append (BitVec.append (BitVec.append
    (BitVec.append 0#7 rs2) rs1) 0#3) rd) 0x33#7

theorem reg_matches (r : BitVec 5) : encdec_reg_backwards_matches r = true := by
  simp [encdec_reg_backwards_matches, Functions.not, Functions.base_E_enabled]

macro "bits" : tactic => `(tactic| (
  simp only [encode, Sail.BitVec.extractLsb]
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp
  all_goals repeat' (erw [BitVec.getElem_append]; simp)))

theorem op_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 6 0 = 0x33#7 := by bits
theorem f3_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 14 12 = 0#3 := by bits
theorem f7_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 31 25 = 0#7 := by bits
theorem rd_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 11 7 = rd := by bits
theorem rs1_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 19 15 = rs1 := by bits
theorem rs2_bits (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 24 20 = rs2 := by bits
theorem not_cbop (rd rs1 rs2 : BitVec 5) :
    Sail.BitVec.extractLsb (encode rd rs1 rs2) 14 0 ≠ 24595#15 := by
  intro h
  have hb := congrArg (fun v : BitVec 15 => v[5]) h
  simp [encode, Sail.BitVec.extractLsb] at hb
  erw [BitVec.getElem_append] at hb
  simp at hb

theorem no_pause : currentlyEnabled .Ext_Zihintpause = (pure false : SailM Bool) := by
  simp [currentlyEnabled, hartSupports]

theorem no_ntl : currentlyEnabled .Ext_Zihintntl = (pure false : SailM Bool) := by
  simp [currentlyEnabled, hartSupports]

theorem ntl_skip (r : BitVec 5) :
    (do let op ← encdec_ntl_backwards r
        if (← currentlyEnabled .Ext_Zihintntl) then
          pure (some (.NTL op)) else pure none : SailM (Option instruction)) =
      (if encdec_ntl_backwards_matches r then pure none else
        do let _ ← encdec_ntl_backwards r; pure none) := by
  simp only [no_ntl]
  unfold encdec_ntl_backwards encdec_ntl_backwards_matches
  split <;> simp

theorem sail_decode (rd rs1 rs2 : BitVec 5) (s : SailState)
    (hlp : currentlyEnabled .Ext_Zicfilp s = .ok false s) :
    ext_decode (encode rd rs1 rs2) s =
      .ok (.RTYPE (.Regidx rs2, .Regidx rs1, .Regidx rd, .ADD)) s := by
  unfold ext_decode encdec_backwards
  simp only [no_pause, ntl_skip]
  simp [op_bits, f3_bits, f7_bits, rd_bits, rs1_bits, rs2_bits, not_cbop, reg_matches,
    encdec_uop_backwards_matches, encdec_iop_backwards_matches,
    RawAddFields.sail_reg_decode, bind_eq, pure_eq, hlp]
  split <;> simp_all [bind_eq, map_eq, pure_eq, RawAddFields.sail_reg_decode]
  all_goals obtain ⟨ha, hs⟩ := ‹none = _ ∧ _›
  all_goals subst_vars
  all_goals simp [bind_eq, map_eq, pure_eq, hlp, RawAddFields.sail_reg_decode]

end
end RawAddDecode
