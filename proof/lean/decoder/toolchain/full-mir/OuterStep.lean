import OuterGeneral

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
open LeanRV64D Functions AddRegister AddBoundary AddStep ProductionWrapper
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

/-- Derive Sail's path from the same word without using a second Rust factory
    proof merely to project its Sail component. -/
def sailActive {s : SailState} {w : BitVec 32}
    (path : RawFetchPath s w) (hraw : IsRawAdd w) :
    ActiveAddPath s w (reg (rdOf w)) (reg (rs1Of w)) (reg (rs2Of w)) where
  privilege := path.privilege
  afterInterrupt := path.afterInterrupt
  afterFetch := path.afterFetch
  afterDecode := path.afterFetch
  ready := path.ready
  readPrivilege := path.readPrivilege
  noInterrupt := path.noInterrupt
  fetchBase := path.fetchBase
  decodeAdd := by
    have hs := RawAddDecode.sail_decode (rdOf w) (rs1Of w) (rs2Of w)
      path.afterFetch path.decodeContext
    simpa only [rdOf, rs1Of, rs2Of, reconstruct w hraw, reg_sail] using hs
  noLandingPad := path.noLandingPad
  frame := path.frame

/-- Actual cold-cache decode_raw followed by the unchanged production execution
    theorem. Both sides consume the same raw word at the common architectural PC.
    Rust's read interface is explicit; no physical coupling between its parameter
    memory and the opaque execution Machine is proved here. Public decode/MOP
    is also not the root of this theorem. -/
theorem cold_raw_add_step {M R : Type} (mi : ckb_vm.memory.Memory M R)
    (mem memAfterFetch : M) (size : Usize)
    (m : Machine) (s : SailState) (hrel : state_rel_pc view m s)
    (hsize : mi.memory_size mem = .ok size)
    (hbound : UScalar.cast .Usize (view m).pc < size)
    (w : BitVec 32) (hraw : IsRawAdd w)
    (rustFetch : WordFetch mi mem (view m).pc w memAfterFetch)
    (entry : StepEntry s) (path : RawFetchPath entry.prepared w)
    (ready : RetireReady path.ready)
    (hactive : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()))
    (stepNo : Nat) (exitWait : Bool) :
    ∃ inst decoder' m' s',
      ckb_vm.decoder.DefaultDecoder.decode_raw mi (initial 2#u32) mem (view m).pc =
        .ok (.Ok inst, decoder', memAfterFetch) ∧
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
  have hd := decode_cold_word mi mem memAfterFetch (view m).pc size hsize hbound w hraw rustFetch
  have hi := RawAddDecode.internal_decoded (rdOf w) (rs1Of w) (rs2Of w)
  obtain ⟨m', s', hr, hs, hrel', hp, hn, hsn, hg, hm, hsm⟩ :=
    ProductionAdd.decoded_add_step m s hrel _ w _ _ _ hi entry (sailActive path hraw)
      ready hactive stepNo exitWait
  exact ⟨_, _, m', s', hd, hr, hs, hrel', hp, hn, hsn, hg, hm, hsm⟩

#print axioms cold_raw_add_step
end
end OuterAdd
