import DecodedRawAdd
import RawEncoding

namespace RawAddDecode
open Aeneas.Std LeanRV64D Functions AddRegister AddBoundary AddStep ProductionWrapper
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

def rdOf (w : BitVec 32) : BitVec 5 := Sail.BitVec.extractLsb w 11 7
def rs1Of (w : BitVec 32) : BitVec 5 := Sail.BitVec.extractLsb w 19 15
def rs2Of (w : BitVec 32) : BitVec 5 := Sail.BitVec.extractLsb w 24 20

theorem raw_decoders_correspond (w : BitVec 32) (h : IsRawAdd w)
    (s : SailState) (hcontext : currentlyEnabled .Ext_Zicfilp s = .ok false s) :
    RawDecodeFactory.decode (⟨w⟩ : U32) = .ok (some (internal (rdOf w) (rs1Of w) (rs2Of w))) ∧
    DecodedAdd (internal (rdOf w) (rs1Of w) (rs2Of w))
      (rustReg (reg (rdOf w))) (rustReg (reg (rs1Of w))) (rustReg (reg (rs2Of w))) ∧
    ext_decode w s = .ok (.RTYPE (sailReg (reg (rs2Of w)), sailReg (reg (rs1Of w)),
      sailReg (reg (rdOf w)), .ADD)) s := by
  refine ⟨?_, internal_decoded _ _ _, ?_⟩
  · have hr := rust_decode (rdOf w) (rs1Of w) (rs2Of w)
    simpa only [rdOf, rs1Of, rs2Of, reconstruct w h] using hr
  · have hs := sail_decode (rdOf w) (rs1Of w) (rs2Of w) s hcontext
    simpa only [rdOf, rs1Of, rs2Of, reconstruct w h, reg_sail] using hs

/-- Prefix requirements only: no decoded constructor or Rust decoded-input premise. -/
structure RawFetchPath (start : SailState) (w : BitVec 32) where
  privilege : Privilege
  afterInterrupt : SailState
  afterFetch : SailState
  ready : SailState
  readPrivilege : readReg .cur_privilege start = .ok privilege start
  noInterrupt : dispatchInterrupt privilege start = .ok none afterInterrupt
  fetchBase : fetch () afterInterrupt = .ok (.F_Base w) afterFetch
  decodeContext : currentlyEnabled .Ext_Zicfilp afterFetch = .ok false afterFetch
  noLandingPad : is_landing_pad_expected () afterFetch = .ok false ready
  frame : ArchFrame start ready

def RawFetchPath.toActive {s : SailState} {w : BitVec 32}
    (path : RawFetchPath s w) (h : IsRawAdd w) :
    ActiveAddPath s w (reg (rdOf w)) (reg (rs1Of w)) (reg (rs2Of w)) :=
  { privilege := path.privilege
    afterInterrupt := path.afterInterrupt
    afterFetch := path.afterFetch
    afterDecode := path.afterFetch
    ready := path.ready
    readPrivilege := path.readPrivilege
    noInterrupt := path.noInterrupt
    fetchBase := path.fetchBase
    decodeAdd := (raw_decoders_correspond w h path.afterFetch path.decodeContext).2.2
    noLandingPad := path.noLandingPad
    frame := path.frame }

/-- Connection to the unchanged final production ADD execution theorem.
The raw word supplies both decoded operands; fetch, initialization and retirement remain explicit.
This root calls the actual RV64 VERSION2 factory, not DefaultDecoder's cache/MOP interface. -/
theorem raw_add_step
    (m : Machine) (s : SailState) (hrel : state_rel_pc view m s)
    (w : BitVec 32) (hraw : IsRawAdd w)
    (entry : StepEntry s) (path : RawFetchPath entry.prepared w)
    (ready : RetireReady path.ready)
    (hactive : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (stepNo : Nat) (exitWait : Bool) :
    ∃ inst m' s',
      RawDecodeFactory.decode (⟨w⟩ : U32) = .ok (some inst) ∧
      ckb_vm_sail_extract.execute_production inst m = .ok (.Ok (), m') ∧
      try_step stepNo exitWait s = .ok false s' ∧
      state_rel_pc view m' s' ∧
      (view m').pc.bv = (view m).pc.bv + 4 ∧
      (view m').next_pc.bv = (view m).pc.bv + 4 ∧
      s'.regs.get? .nextPC = some ((view m).pc.bv + 4) ∧
      (∀ j : Reg, (gpr (view m') j).bv =
        if reg (rdOf w) ≠ 0 ∧ j = reg (rdOf w) then
          (gpr (view m) (reg (rs1Of w))).bv + (gpr (view m) (reg (rs2Of w))).bv
        else (gpr (view m) j).bv) ∧
      (view m').memory = (view m).memory ∧ s'.mem = s.mem := by
  obtain ⟨hd, hi, _⟩ := raw_decoders_correspond w hraw path.afterFetch path.decodeContext
  obtain ⟨m', s', hr, hs, hrel', hp, hn, hsn, hg, hm, hsm⟩ :=
    ProductionAdd.decoded_add_step m s hrel _ w _ _ _ hi entry (path.toActive hraw)
      ready hactive stepNo exitWait
  exact ⟨_, m', s', hd, hr, hs, hrel', hp, hn, hsn, hg, hm, hsm⟩

#print axioms raw_add_step
end
end RawAddDecode
