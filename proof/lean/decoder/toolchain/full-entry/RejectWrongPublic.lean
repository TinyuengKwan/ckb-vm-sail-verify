import OuterPublicWitness
open Aeneas.Std RawAddDecode OuterDecodeCandidate OuterAdd

-- A negative fixture: the exact public decoder result is not a panic.
-- The gate must require a semantic type mismatch, not a missing dependency.
example : ckb_vm.decoder.DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.decode
    (wordMemory 0x002081b3) (initial 2#u32) () 0#u64 = .fail .panic := by
  exact fast_public_witness 0x002081b3 ⟨rfl, rfl, rfl⟩
