import AddRegisters
import LeanRV64D.Step

namespace AddStep
open AddRegister LeanRV64D Functions
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

def putReg (s : SailState) (r : Register) (v : RegisterType r) : SailState :=
  {s with regs := s.regs.insert r v}

theorem read_eq (s : SailState) (r : Register) :
    readReg r s = match s.regs.get? r with
      | some v => .ok v s
      | none => .error .Unreachable s := by
  cases h : s.regs.get? r <;>
    simp only [readReg, Sail.ConcurrencyInterfaceV1.PreSail.readReg,
      get, getThe, MonadStateOf.get, Bind.bind, Pure.pure, EStateM.bind, EStateM.get] <;>
    rw [h] <;> rfl

theorem write_eq (s : SailState) (r : Register) (v : RegisterType r) :
    writeReg r v s = .ok () (putReg s r v) := rfl

theorem bind_eq {α β : Type} (f : SailM α) (g : α → SailM β) (s : SailState) :
    (f >>= g) s = match f s with
      | .ok a s' => g a s'
      | .error e s' => .error e s' := by
  change EStateM.bind f g s = _
  unfold EStateM.bind
  cases f s <;> rfl

theorem pure_eq {α : Type} (a : α) (s : SailState) :
    (pure a : SailM α) s = .ok a s := rfl

theorem map_eq {α β : Type} (f : α → β) (x : SailM α) (s : SailState) :
    (f <$> x) s = match x s with
      | .ok a s' => .ok (f a) s'
      | .error e s' => .error e s' := by
  change EStateM.map f x s = _
  unfold EStateM.map
  cases x s <;> rfl

theorem lift_eq {α ε : Type} (x : SailM α) (s : SailState) :
    (liftM x : SailME ε α) s = match x s with
      | .ok a s' => .ok (.ok a) s'
      | .error e s' => .error e s' := by
  change EStateM.map Except.ok x s = _
  unfold EStateM.map
  cases x s <;> rfl

theorem ebind_eq {α β ε : Type} (f : SailME ε α) (g : α → SailME ε β) (s : SailState) :
    (f >>= g) s = match f s with
      | .ok (.ok a) s' => g a s'
      | .ok (.error e) s' => .ok (.error e) s'
      | .error e s' => .error e s' := by
  change EStateM.bind f (ExceptT.bindCont g) s = _
  unfold EStateM.bind
  cases f s with
  | ok a s' => cases a <;> rfl
  | error e s' => rfl

theorem epure_eq {α ε : Type} (a : α) (s : SailState) :
    (pure a : SailME ε α) s = .ok (.ok a) s := rfl

theorem emap_eq {α β ε : Type} (f : α → β) (x : SailME ε α) (s : SailState) :
    (f <$> x) s = match x s with
      | .ok (.ok a) s' => .ok (.ok (f a)) s'
      | .ok (.error e) s' => .ok (.error e) s'
      | .error e s' => .error e s' := by
  change EStateM.bind x _ s = _
  unfold EStateM.bind
  cases x s with
  | ok a s' => cases a <;> rfl
  | error e s' => rfl

theorem erun_eq {α : Type} (x : SailME α α) (s : SailState) :
    Sail.ConcurrencyInterfaceV1.PreSail.PreSailME.run x s = match x s with
      | .ok (.ok a) s' => .ok a s'
      | .ok (.error (.inr a)) s' => .ok a s'
      | .ok (.error (.inl e)) s' => .error e s'
      | .error e s' => .error e s' := by
  change EStateM.bind x _ s = _
  unfold EStateM.bind
  cases x s with
  | ok a s' => cases a with
    | ok a => rfl
    | error e => cases e <;> rfl
  | error e s' => rfl

theorem gpr_put_nextPC (s : SailState) (p : BitVec 64) (i : Reg) :
    sailGpr (putReg s .nextPC p) i = sailGpr s i := by
  fin_cases i <;> simp [sailGpr, putReg, key, Std.ExtDHashMap.get?_insert]

theorem gpr_put_PC (s : SailState) (p : BitVec 64) (i : Reg) :
    sailGpr (putReg s .PC p) i = sailGpr s i := by
  fin_cases i <;> simp [sailGpr, putReg, key, Std.ExtDHashMap.get?_insert]

theorem sail_dispatch (s : SailState) (rd rs1 rs2 : Reg) (a b : BitVec 64)
    (ha : sailGpr s rs1 = some a) (hb : sailGpr s rs2 = some b) :
    execute (.RTYPE (sailReg rs2, sailReg rs1, sailReg rd, .ADD)) s =
      .ok RETIRE_SUCCESS (putGpr s rd (a + b)) := by
  exact sail_add s rd rs1 rs2 a b ha hb

theorem sail_tick_pc (s : SailState) (p : BitVec 64)
    (h : s.regs.get? .nextPC = some p) :
    tick_pc () s = .ok () (putReg s .PC p) := by
  simp [tick_pc, bind_eq, map_eq, read_eq, write_eq, h,
    putReg, pc_write_callback]

-- Only the selected architectural observations; other platform state may change.
structure ArchFrame (before after : SailState) : Prop where
  gprs : ∀ i : Reg, sailGpr after i = sailGpr before i
  pc : after.regs.get? .PC = before.regs.get? .PC
  memory : after.mem = before.mem

end
end AddStep
