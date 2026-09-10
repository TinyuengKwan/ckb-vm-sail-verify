import ProductionAdd

/-! Concrete non-vacuity checks against the generated Sail functions.
This is a model state witness, not a proof of reachability from platform reset.
-/
namespace AddWitness
open AddStep AddRegister LeanRV64D Functions
noncomputable section
set_option maxRecDepth 1000000
set_option maxHeartbeats 16000000
-- A shared reduction vocabulary covers both fetch halves and generated branches.
set_option linter.unusedSimpArgs false

def ram : PMA_Region :=
  { base := 0x80000000
    size := 4096
    include_in_device_tree := false
    attributes := { (default : PMA) with
      executable := true
      readable := true
      writable := true } }

def initialRegs : Std.ExtDHashMap Register RegisterType :=
    (∅ : Std.ExtDHashMap Register RegisterType)
      |>.insert .x4 0 |>.insert .x5 0 |>.insert .x6 0 |>.insert .x7 0
      |>.insert .x8 0 |>.insert .x9 0 |>.insert .x10 0 |>.insert .x11 0
      |>.insert .x12 0 |>.insert .x13 0 |>.insert .x14 0 |>.insert .x15 0
      |>.insert .x16 0 |>.insert .x17 0 |>.insert .x18 0 |>.insert .x19 0
      |>.insert .x20 0 |>.insert .x21 0 |>.insert .x22 0 |>.insert .x23 0
      |>.insert .x24 0 |>.insert .x25 0 |>.insert .x26 0 |>.insert .x27 0
      |>.insert .x28 0 |>.insert .x29 0 |>.insert .x30 0 |>.insert .x31 0
      |>.insert .cur_privilege .Machine
      |>.insert .PC 0x80000000
      |>.insert .hart_state (.HART_ACTIVE ())
      |>.insert .mcountinhibit 0
      |>.insert .minstretcfg 0
      |>.insert .minstret 0
      |>.insert .minstret_increment true
      |>.insert .mstatus 0
      |>.insert .mseccfg 0
      |>.insert .misa 0
      |>.insert .mie 0
      |>.insert .mip 0
      |>.insert .sig_meip 0
      |>.insert .elp 0
      |>.insert .pma_regions [ram]
      |>.insert .pmpcfg_n (Vector.ofFn (fun i : Fin 64 => if i = 0 then 0x0f else 0))
      |>.insert .pmpaddr_n (Vector.ofFn (fun i : Fin 64 => if i = 0 then 0x20000400 else 0))
      |>.insert .htif_tohost_base none
      |>.insert .x1 5
      |>.insert .x2 7
      |>.insert .x3 0

def initial : SailState :=
  { regs := initialRegs,
    choiceState := (), tags := (), cycleCount := 0, sailOutput := #[],
    mem := (∅ : Std.ExtHashMap Nat (BitVec 8)) |>.insert 0x80000000 0xb3
      |>.insert 0x80000001 0x81 |>.insert 0x80000002 0x20 |>.insert 0x80000003 0 }

theorem initial_regs : initial.regs = initialRegs := rfl

theorem initial_mem : initial.mem =
    ((∅ : Std.ExtHashMap Nat (BitVec 8)) |>.insert 0x80000000 0xb3
      |>.insert 0x80000001 0x81 |>.insert 0x80000002 0x20 |>.insert 0x80000003 0) := rfl

theorem state_get (s : SailState) : (get : SailM SailState) s = .ok s s := rfl

theorem state_eget {ε : Type} (s : SailState) :
    (get : SailME ε SailState) s = .ok (.ok s) s := rfl

theorem counter_decision : should_inc_minstret .Machine initial = .ok true initial := by
  simp [should_inc_minstret, bind_eq, map_eq, read_eq, initial_regs, initialRegs,
    Std.ExtDHashMap.get?_insert, _get_Counterin_IR, counter_priv_filter_bit,
    _get_CountSmcntrpmf_MINH, Sail.BitVec.extractLsb]
theorem no_interrupt : dispatchInterrupt .Machine initial = .ok none initial := by
  simp [dispatchInterrupt, getPendingSet, currentlyEnabled, hartSupports,
    read_mip, external_interrupts_pending, bind_eq, map_eq, pure_eq, read_eq, initial_regs, initialRegs,
    Std.ExtDHashMap.get?_insert,
    Mk_Minterrupts, _update_Minterrupts_SEI, _update_Minterrupts_MEI,
    _get_Mstatus_MIE, _get_Mstatus_SIE, zeros, Sail.BitVec.extractLsb]
theorem decode_add : ext_decode 0x002081b3 initial =
    .ok (.RTYPE (sailReg 2, sailReg 1, sailReg 3, .ADD)) initial := by
  have pause : currentlyEnabled .Ext_Zihintpause = (pure false : SailM Bool) := by
    simp [currentlyEnabled, hartSupports]
  have lp : currentlyEnabled .Ext_Zicfilp initial = .ok false initial := by
    simp [currentlyEnabled, hartSupports, get_xLPE, bind_eq, map_eq, pure_eq,
      read_eq, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]
  unfold ext_decode encdec_backwards
  simp only [pause]
  simp +decide only [bind_eq, pure_eq, lp, ite_false]
  rfl
theorem no_landing_pad : is_landing_pad_expected () initial = .ok false initial := by
  simp [is_landing_pad_expected, bind_eq, pure_eq, read_eq, initial_regs, initialRegs,
    Std.ExtDHashMap.get?_insert, landing_pad_bits_backwards]

theorem pmp_open (offset : Fin 2) :
    pmpCheck (.Physaddr (0x80000000 + 2 * offset.val)) 2 (.InstructionFetch ()) .Machine initial =
      .ok none initial := by
  fin_cases offset <;>
    simp +decide only [pmpCheck, sys_pmp_count, SailME.run, erun_eq,
      ebind_eq, emap_eq, epure_eq, lift_eq, bind_eq, map_eq, pure_eq,
      ForIn.forIn, ForIn'.forIn', IntRange.forIn', ite_false]
  all_goals rw [IntRange.forIn'.loop]
  all_goals simp +decide [
    pmpCheck, sys_pmp_count, SailME.run, erun_eq, ebind_eq, emap_eq, epure_eq,
    lift_eq, bind_eq, map_eq, pure_eq, read_eq, initial_regs, initialRegs,
    Std.ExtDHashMap.get?_insert, pmpReadAddrReg, pmpMatchAddr, _get_Pmpcfg_ent_A,
    pmpAddrMatchType_encdec_backwards, sys_pmp_grain, Sail.BitVec.access,
    Sail.BitVec.extractLsb, ForIn.forIn, ForIn'.forIn', IntRange.forIn',
    IntRange.instMemIntRange,
    pmpRangeMatch, pmpCheckRWX, pmpLocked, _get_Pmpcfg_ent_L,
    _get_Pmpcfg_ent_X, to_bits, zeros, SailME.throw,
    Sail.ConcurrencyInterfaceV1.PreSail.PreSailME.throw]
  all_goals rfl
-- Fetch is checked after the smaller prefix observations.
theorem fetch_add : fetch () initial = .ok (.F_Base 0x002081b3) initial := by
  have plo : pmpCheck (.Physaddr 0x80000000#64) 2 (.InstructionFetch ()) .Machine initial =
      .ok none initial := pmp_open 0
  have phi : pmpCheck (.Physaddr 0x80000002#64) 2 (.InstructionFetch ()) .Machine initial =
      .ok none initial := pmp_open 1
  simp +decide [fetch, SailME.run, erun_eq, ebind_eq, emap_eq, epure_eq, lift_eq, bind_eq, map_eq, pure_eq,
    read_eq, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert, get_config_rvfi,
    ext_fetch_check_pc, is_aligned_vaddr, currentlyEnabled, hartSupports,
    fetch_bytes, translateAddr, effectivePrivilege, translationMode,
    is_shadow_stack_access, mem_read, mem_read_meta, mem_read_priv_meta,
    checked_mem_read, check_pma_with_pmp_priority, phys_access_check,
    Sail.BitVec.access, Functions.not, Functions.xlen, _get_Misa_C,
    Sail.BitVec.extractLsb, _get_Mstatus_MPRV, _get_Mstatus_MPP,
    pmaCheck, matching_pma_region, matching_pma_region_bits_range, override_PMA,
    ram, mag_pma_check, is_mag_applicable_access, mem_read_priv,
    split_misaligned, misaligned_order, sys_misaligned_order_decreasing,
    bits_of_virtaddr, bits_of_physaddr, zero_extend, read_kind_of_flags,
    untilFuelM, untilFuelM.go, Sail.ConcurrencyInterfaceV1.PreSail.assert,
    plo, phi, Sail.BitVec.addInt, Sail.BitVec.zeroExtend,
    within_mmio_readable, within_clint, within_sig, within_htif_readable,
    within_htif_writable, plat_have_clint, plat_have_sig,
    read_ram, Sail.ConcurrencyInterfaceV1.PreSail.sail_mem_read,
    Sail.ConcurrencyInterfaceV1.PreSail.readBytes,
    Sail.ConcurrencyInterfaceV1.PreSail.readByte, state_get, state_eget, initial_mem,
    Std.ExtHashMap.getElem?_insert, Std.ExtHashMap.getElem_insert,
    isRVC, zeros, default_meta, MemoryOpResult_drop_meta,
    Sail.BitVec.updateSubrange, Sail.BitVec.updateSubrange']

theorem put_existing (s : SailState) (r : Register) (v : RegisterType r)
    (h : s.regs.get? r = some v) : putReg s r v = s := by
  have hr : s.regs.insert r v = s.regs := by
    apply Std.ExtDHashMap.ext_get?
    intro a
    by_cases ha : r = a
    · subst a
      simpa only [Std.ExtDHashMap.get?_insert_self] using h.symm
    · simp [Std.ExtDHashMap.get?_insert, ha]
  cases s
  simp_all [putReg]

theorem privilege_read : readReg .cur_privilege initial = .ok .Machine initial := by
  simp [read_eq, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]

def entry : StepEntry initial :=
  { privilege := .Machine, increment := true, afterDecision := initial,
    readPrivilege := privilege_read, decideIncrement := counter_decision,
    frame := ⟨fun _ => rfl, rfl, rfl⟩ }

theorem prepared_eq : entry.prepared = initial := by
  change putReg initial .minstret_increment true = initial
  apply put_existing
  simp [initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]

def path : ActiveAddPath entry.prepared 0x002081b3 3 1 2 :=
  { privilege := .Machine
    afterInterrupt := initial
    afterFetch := initial
    afterDecode := initial
    ready := initial
    readPrivilege := by simpa only [prepared_eq] using privilege_read
    noInterrupt := by simpa only [prepared_eq] using no_interrupt
    fetchBase := fetch_add
    decodeAdd := decode_add
    noLandingPad := no_landing_pad
    frame := by rw [prepared_eq]; exact ⟨fun _ => rfl, rfl, rfl⟩ }

def ready : RetireReady path.ready :=
  { increment := true
    counter := 0
    hart := by simp [path, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]
    flag := by simp [path, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]
    count := by intro _; simp [path, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert] }

theorem active : entry.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()) := by
  simp [prepared_eq, initial_regs, initialRegs, Std.ExtDHashMap.get?_insert]

/-- All Sail path contracts hold on one and the same concrete state chain. -/
theorem sail_contracts_jointly_inhabited :
    ∃ s : SailState, ∃ e : StepEntry s,
      ∃ p : ActiveAddPath e.prepared 0x002081b3 3 1 2,
        Nonempty (RetireReady p.ready) ∧
        e.prepared.regs.get? .hart_state = some (.HART_ACTIVE ()) :=
  ⟨initial, entry, path, ⟨ready⟩, active⟩

end
end AddWitness
