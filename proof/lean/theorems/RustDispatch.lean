import AddRegisters

namespace AddStep
open Aeneas.Std AddBoundary AddRegister ckb_vm_sail_extract
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

-- Post-state descriptions, not replacements for generated execution.
def stageCore (c : Core) : Core := {c with next_pc := addValue c.pc 4#u64}
def commitCore (c : Core) : Core := {c with pc := c.next_pc}
def addCore (c : Core) (rd rs1 rs2 : Reg) : Core :=
  commitCore (putCore (stageCore c) rd (addValue (gpr c rs1) (gpr c rs2)))

theorem core_pc (c : Core) : coreOps.pc c = .ok c.pc := rfl
theorem core_update_pc (c : Core) (p : U64) :
    coreOps.update_pc c p = .ok {c with next_pc := p} := rfl
theorem core_commit_pc (c : Core) : coreOps.commit_pc c = .ok (commitCore c) := rfl
theorem from_u8_four :
    machineOps.CoreMachineInst.instructionsregisterRegisterInst.from_u8 4#u8 = .ok 4#u64 := rfl

theorem rust_dispatch (view : Machine → Core) (valid : Machine → Prop)
    (regs : RegisterDelegation view valid) (m : Machine) (hm : valid m)
    (inst : U64) (rd rs1 rs2 : Reg)
    (hd : DecodedAdd inst (rustReg rd) (rustReg rs1) (rustReg rs2)) :
    ∃ m', ckb_vm.instructions.execute.execute_instruction machineOps inst m =
      .ok (.Ok (), m') ∧ valid m' ∧
      view m' = putCore (view m) rd (addValue (gpr (view m) rs1) (gpr (view m) rs2)) := by
  obtain ⟨m', ha, hm', hv⟩ := rust_add view valid regs m hm rd rs1 rs2
  refine ⟨m', ?_, hm', hv⟩
  have hh : ckb_vm.instructions.execute.handle_add machineOps m inst = .ok (.Ok (), m') := by
    simp only [ckb_vm.instructions.execute.handle_add, hd.rd_field, hd.rs1_field,
      hd.rs2_field, Aeneas.Std.bind_tc_ok, ha]
  unfold ckb_vm.instructions.execute.execute_instruction
  rw [hd.opcode]
  conv_lhs => whnf
  rw [hh]
  rfl

/-- The generated production root, including staging, dispatch, and commit.
Both Aeneas failure and the inner VM error are excluded by the result equation. -/
theorem rust_production_add (view : Machine → Core) (valid : Machine → Prop)
    (regs : RegisterDelegation view valid) (pcs : PcDelegation view valid)
    (m : Machine) (hm : valid m) (inst : U64) (rd rs1 rs2 : Reg)
    (hd : DecodedAdd inst (rustReg rd) (rustReg rs1) (rustReg rs2)) :
    ∃ m', execute_production inst m = .ok (.Ok (), m') ∧
      valid m' ∧ view m' = addCore (view m) rd rs1 rs2 := by
  obtain ⟨m1, h1, hm1, hc1⟩ := pcs.update_pc m hm (addValue (view m).pc 4#u64)
  rw [core_update_pc] at hc1
  have hv1 : view m1 = stageCore (view m) := (Result.ok.inj hc1).symm
  obtain ⟨m2, h2, hm2, hv2⟩ := rust_dispatch view valid regs m1 hm1 inst rd rs1 rs2 hd
  obtain ⟨m3, h3, hm3, hc3⟩ := pcs.commit_pc m2 hm2
  rw [core_commit_pc] at hc3
  refine ⟨m3, ?_, hm3, ?_⟩
  · rw [production_dictionary]
    simp [ckb_vm.instructions.execute.execute, hd.length, pcs.pc m hm, core_pc,
      from_u8_four, rust_overflowing_add, h1, h2, h3]
  · rw [← Result.ok.inj hc3, hv2, hv1]
    rfl

theorem addCore_pc (c : Core) (rd rs1 rs2 : Reg) :
    (addCore c rd rs1 rs2).pc = addValue c.pc 4#u64 ∧
      (addCore c rd rs1 rs2).next_pc = addValue c.pc 4#u64 := by
  change (putCore (stageCore c) rd _).next_pc = _ ∧
    (putCore (stageCore c) rd _).next_pc = _
  constructor <;> exact (putCore_frame (stageCore c) rd _).2.1

theorem addCore_gpr (c : Core) (rd rs1 rs2 j : Reg) :
    gpr (addCore c rd rs1 rs2) j =
      if rd ≠ 0 ∧ j = rd then addValue (gpr c rs1) (gpr c rs2) else gpr c j := by
  change gpr (putCore (stageCore c) rd _) j = _
  rw [gpr_putCore]
  rfl

theorem addCore_memory (c : Core) (rd rs1 rs2 : Reg) :
    (addCore c rd rs1 rs2).memory = c.memory := by
  exact (putCore_frame (stageCore c) rd _).2.2

end
end AddStep
