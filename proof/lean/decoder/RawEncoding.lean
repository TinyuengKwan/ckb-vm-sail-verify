import SailRawAdd

namespace RawAddDecode
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

structure IsRawAdd (w : BitVec 32) : Prop where
  opcode : Sail.BitVec.extractLsb w 6 0 = 0x33#7
  funct3 : Sail.BitVec.extractLsb w 14 12 = 0#3
  funct7 : Sail.BitVec.extractLsb w 31 25 = 0#7

theorem encode_is_add (rd rs1 rs2 : BitVec 5) : IsRawAdd (encode rd rs1 rs2) :=
  ⟨op_bits rd rs1 rs2, f3_bits rd rs1 rs2, f7_bits rd rs1 rs2⟩

theorem split_word (w : BitVec 32) :
    BitVec.append (BitVec.append (BitVec.append (BitVec.append
      (BitVec.append (Sail.BitVec.extractLsb w 31 25) (Sail.BitVec.extractLsb w 24 20))
        (Sail.BitVec.extractLsb w 19 15)) (Sail.BitVec.extractLsb w 14 12))
          (Sail.BitVec.extractLsb w 11 7)) (Sail.BitVec.extractLsb w 6 0) = w := by
  apply BitVec.eq_of_getElem_eq
  intro i hi
  interval_cases i <;> simp [Sail.BitVec.extractLsb]
  all_goals repeat' (erw [BitVec.getElem_append]; simp [Sail.BitVec.extractLsb])

theorem reconstruct (w : BitVec 32) (h : IsRawAdd w) :
    encode (Sail.BitVec.extractLsb w 11 7) (Sail.BitVec.extractLsb w 19 15)
      (Sail.BitVec.extractLsb w 24 20) = w := by
  have hs := split_word w
  rw [h.opcode, h.funct3, h.funct7] at hs
  exact hs

theorem raw_add_iff (w : BitVec 32) :
    IsRawAdd w ↔ ∃ rd rs1 rs2, w = encode rd rs1 rs2 := by
  constructor
  · intro h
    exact ⟨_, _, _, (reconstruct w h).symm⟩
  · rintro ⟨rd, rs1, rs2, rfl⟩
    exact encode_is_add rd rs1 rs2

#print axioms raw_add_iff
end RawAddDecode
