import OuterFactories

namespace OuterAdd
open Aeneas.Std RawAddDecode OuterDecodeCandidate
noncomputable section
set_option maxRecDepth 100000
set_option maxHeartbeats 8000000

def initial (v : U32) : ckb_vm.decoder.DefaultDecoder where
  factories := ⟨[compressedFactory, addFactory,
    ckb_vm.instructions.m.factory regInst, ckb_vm.instructions.b.factory regInst], by scalar_tac⟩
  mop := false
  version := v
  instructions_cache := Array.repeat 4096#usize (core.num.U64.MAX, 0#u64)

theorem initial_new (v : U32) :
    ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.new regInst 1#u8 v =
      .ok (initial v) := by
  unfold ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.new
    ckb_vm_definitions.ISA_MOP ckb_vm_definitions.ISA_B
    ckb_vm.decoder.DefaultDecoder.empty
    ckb_vm.decoder.DefaultDecoder.add_instruction_factory alloc.vec.Vec.push
  norm_num [initial, lift, alloc.vec.Vec.new, U32.max, U32.numBits]
  rfl

theorem initial_factories (v : U32) :
    (initial v).factories.val = [compressedFactory, addFactory,
      ckb_vm.instructions.m.factory regInst, ckb_vm.instructions.b.factory regInst] := rfl

theorem initial_mop_off (v : U32) : (initial v).mop = false := rfl

theorem initial_cache (v : U32) (k : Usize) (hk : k.val < 4096) :
    Array.index_usize (initial v).instructions_cache k = .ok (core.num.U64.MAX, 0#u64) := by
  have hn : (4096#usize).val = 4096 := by scalar_tac
  simp only [initial, Array.index_usize, Array.getElem?_Usize_eq,
    Array.repeat_val, hn, List.getElem?_replicate, hk, ↓reduceIte]

#print axioms initial_new
#print axioms initial_factories
#print axioms initial_mop_off
#print axioms initial_cache
end
end OuterAdd
