import StateRel
import LeanRV64D.InstsEnd

namespace AddRegister
open LeanRV64D Functions
noncomputable section
set_option maxRecDepth 10000
set_option maxHeartbeats 4000000
set_option linter.unusedSimpArgs false

-- Closed key equations avoid simplifying a dependent Nat matcher under casts.
@[local simp] private theorem key_1 : key (1 : Reg) = ⟨Register.x1, rfl⟩ := rfl
@[local simp] private theorem key_2 : key (2 : Reg) = ⟨Register.x2, rfl⟩ := rfl
@[local simp] private theorem key_3 : key (3 : Reg) = ⟨Register.x3, rfl⟩ := rfl
@[local simp] private theorem key_4 : key (4 : Reg) = ⟨Register.x4, rfl⟩ := rfl
@[local simp] private theorem key_5 : key (5 : Reg) = ⟨Register.x5, rfl⟩ := rfl
@[local simp] private theorem key_6 : key (6 : Reg) = ⟨Register.x6, rfl⟩ := rfl
@[local simp] private theorem key_7 : key (7 : Reg) = ⟨Register.x7, rfl⟩ := rfl
@[local simp] private theorem key_8 : key (8 : Reg) = ⟨Register.x8, rfl⟩ := rfl
@[local simp] private theorem key_9 : key (9 : Reg) = ⟨Register.x9, rfl⟩ := rfl
@[local simp] private theorem key_10 : key (10 : Reg) = ⟨Register.x10, rfl⟩ := rfl
@[local simp] private theorem key_11 : key (11 : Reg) = ⟨Register.x11, rfl⟩ := rfl
@[local simp] private theorem key_12 : key (12 : Reg) = ⟨Register.x12, rfl⟩ := rfl
@[local simp] private theorem key_13 : key (13 : Reg) = ⟨Register.x13, rfl⟩ := rfl
@[local simp] private theorem key_14 : key (14 : Reg) = ⟨Register.x14, rfl⟩ := rfl
@[local simp] private theorem key_15 : key (15 : Reg) = ⟨Register.x15, rfl⟩ := rfl
@[local simp] private theorem key_16 : key (16 : Reg) = ⟨Register.x16, rfl⟩ := rfl
@[local simp] private theorem key_17 : key (17 : Reg) = ⟨Register.x17, rfl⟩ := rfl
@[local simp] private theorem key_18 : key (18 : Reg) = ⟨Register.x18, rfl⟩ := rfl
@[local simp] private theorem key_19 : key (19 : Reg) = ⟨Register.x19, rfl⟩ := rfl
@[local simp] private theorem key_20 : key (20 : Reg) = ⟨Register.x20, rfl⟩ := rfl
@[local simp] private theorem key_21 : key (21 : Reg) = ⟨Register.x21, rfl⟩ := rfl
@[local simp] private theorem key_22 : key (22 : Reg) = ⟨Register.x22, rfl⟩ := rfl
@[local simp] private theorem key_23 : key (23 : Reg) = ⟨Register.x23, rfl⟩ := rfl
@[local simp] private theorem key_24 : key (24 : Reg) = ⟨Register.x24, rfl⟩ := rfl
@[local simp] private theorem key_25 : key (25 : Reg) = ⟨Register.x25, rfl⟩ := rfl
@[local simp] private theorem key_26 : key (26 : Reg) = ⟨Register.x26, rfl⟩ := rfl
@[local simp] private theorem key_27 : key (27 : Reg) = ⟨Register.x27, rfl⟩ := rfl
@[local simp] private theorem key_28 : key (28 : Reg) = ⟨Register.x28, rfl⟩ := rfl
@[local simp] private theorem key_29 : key (29 : Reg) = ⟨Register.x29, rfl⟩ := rfl
@[local simp] private theorem key_30 : key (30 : Reg) = ⟨Register.x30, rfl⟩ := rfl
@[local simp] private theorem key_31 : key (31 : Reg) = ⟨Register.x31, rfl⟩ := rfl

private theorem readReg_eq (s : SailState) (r : Register) :
    readReg r s = match s.regs.get? r with
      | some v => .ok v s
      | none => .error .Unreachable s := by
  cases h : s.regs.get? r <;>
    simp only [readReg, Sail.ConcurrencyInterfaceV1.PreSail.readReg,
      get, getThe, MonadStateOf.get, Bind.bind, Pure.pure, EStateM.bind, EStateM.pure, EStateM.get] <;>
    rw [h] <;> rfl

private theorem writeReg_eq (s : SailState) (r : Register) (v : RegisterType r) :
    writeReg r v s = .ok () {s with regs := s.regs.insert r v} := by rfl

private theorem bind_eq {α β : Type} (f : SailM α) (g : α → SailM β) (s : SailState) :
    (f >>= g) s = match f s with
      | .ok a s' => g a s'
      | .error e s' => .error e s' := by
  change EStateM.bind f g s = _
  unfold EStateM.bind
  cases f s <;> rfl

private theorem pure_eq {α : Type} (a : α) (s : SailState) :
    (pure a : SailM α) s = .ok a s := by rfl

private theorem map_eq {α β : Type} (f : α → β) (x : SailM α) (s : SailState) :
    (f <$> x) s = match x s with
      | .ok a s' => .ok (f a) s'
      | .error e s' => .error e s' := by
  change EStateM.map f x s = _
  unfold EStateM.map
  cases x s <;> rfl

theorem sail_read (s : SailState) (i : Reg) (v : BitVec 64)
    (h : sailGpr s i = some v) :
    rX_bits (sailReg i) s = .ok v s := by
  fin_cases i <;>
    simp_all [sailGpr, sailReg, rX_bits, rX, regval_from_reg, zero_reg,
      zeros, Sail.BitVec.toNatInt, bind_eq, pure_eq, readReg_eq]

theorem sail_write (s : SailState) (i : Reg) (v : BitVec 64) :
    wX_bits (sailReg i) v s = .ok () (putGpr s i v) := by
  fin_cases i <;>
    simp [putGpr, key, sailReg, wX_bits, wX, regval_into_reg,
      Sail.BitVec.toNatInt, xreg_write_callback, xreg_full_write_callback,
      reg_name_forwards, encdec_reg_forwards_matches, encdec_reg_forwards,
      get_config_use_abi_names, Functions.not, to_bits, bind_eq, pure_eq, writeReg_eq]

theorem sail_add (s : SailState) (rd rs1 rs2 : Reg) (a b : BitVec 64)
    (ha : sailGpr s rs1 = some a) (hb : sailGpr s rs2 = some b) :
    execute_RTYPE (sailReg rs2) (sailReg rs1) (sailReg rd) .ADD s =
      .ok RETIRE_SUCCESS (putGpr s rd (a + b)) := by
  simp [execute_RTYPE, bind_eq, pure_eq, map_eq, sail_read s rs1 a ha,
    sail_read s rs2 b hb, sail_write]

end
end AddRegister
