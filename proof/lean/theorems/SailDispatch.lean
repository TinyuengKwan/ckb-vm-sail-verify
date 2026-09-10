import SailStepSupport

namespace AddStep
open AddRegister LeanRV64D Functions
noncomputable section
set_option maxRecDepth 20000
set_option maxHeartbeats 8000000

/-- Only the actual prefix operations, with explicit intermediate states.
No premise mentions execute, run_hart_active, or the ADD result. -/
structure ActiveAddPath (start : SailState) (w : BitVec 32) (rd rs1 rs2 : Reg) where
  privilege : Privilege
  afterInterrupt : SailState
  afterFetch : SailState
  afterDecode : SailState
  ready : SailState
  readPrivilege : readReg .cur_privilege start = .ok privilege start
  noInterrupt : dispatchInterrupt privilege start = .ok none afterInterrupt
  fetchBase : fetch () afterInterrupt = .ok (.F_Base w) afterFetch
  decodeAdd : ext_decode w afterFetch =
    .ok (.RTYPE (sailReg rs2, sailReg rs1, sailReg rd, .ADD)) afterDecode
  noLandingPad : is_landing_pad_expected () afterDecode = .ok false ready
  frame : ArchFrame start ready

def stageSail (s : SailState) (p : BitVec 64) : SailState := putReg s .nextPC (p + 4)

theorem run_hart_add (start : SailState) (w : BitVec 32) (rd rs1 rs2 : Reg)
    (path : ActiveAddPath start w rd rs1 rs2) (p a b : BitVec 64)
    (hp : start.regs.get? .PC = some p)
    (ha : sailGpr start rs1 = some a) (hb : sailGpr start rs2 = some b)
    (stepNo : Nat) :
    run_hart_active stepNo start =
      .ok (.Step_Execute (RETIRE_SUCCESS, w))
        (putGpr (stageSail path.ready p) rd (a + b)) := by
  have hp' : path.ready.regs.get? .PC = some p := path.frame.pc.trans hp
  have ha' : sailGpr (stageSail path.ready p) rs1 = some a := by
    rw [stageSail, gpr_put_nextPC, path.frame.gprs, ha]
  have hb' : sailGpr (stageSail path.ready p) rs2 = some b := by
    rw [stageSail, gpr_put_nextPC, path.frame.gprs, hb]
  have hd := sail_dispatch (stageSail path.ready p) rd rs1 rs2 a b ha' hb'
  simp only [stageSail] at hd
  simp [run_hart_active, SailME.run, erun_eq, ebind_eq, emap_eq, lift_eq,
    path.readPrivilege, path.noInterrupt, path.fetchBase,
    ext_fetch_hook, path.decodeAdd, get_config_print_instr, path.noLandingPad,
    read_eq, hp', write_eq, stageSail, Sail.BitVec.addInt, RETIRE_SUCCESS, zero_extend]
  erw [hd]
  rfl

end
end AddStep
