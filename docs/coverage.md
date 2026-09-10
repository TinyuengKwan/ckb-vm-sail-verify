# Coverage Matrix

Status values follow `methodology.md`. Generated definitions alone are not runtime evidence or a proof.

The MVP target column is a commitment, not current evidence. Current status remains `unsupported` until the evidence gates are met.

Runtime evidence below comes from `make verify-dii`: 32 injected corpus cases,
395 committed steps compared step by step against the pinned Sail model over
RVFI-DII, with every case replayable from its own artifact.

| Instruction family | VERSION | Runtime RVFI | Extraction | Theorem | MVP target | Current status |
|---|---:|---|---|---|---|---|
| ADD | 2 | 13 corpus cases, 209 steps | reviewed patched production model; scoped public decoder baseline | [cold_public_add_step](../proof/lean/decoder/toolchain/full-entry/OuterPublicStep.lean) (same-word decode+GPR+PC; conditional) | runtime + Lean 4 proved | runtime-only |
| ADDI | 2 | 10 corpus cases, 69 steps | pending | none | runtime-only | runtime-only |
| BEQ | 2 | 9 corpus cases, 117 steps | pending | none | runtime-only | runtime-only |
| SLLI | 2 | incidental: setup sequences | pending | none | post-MVP | unsupported |
| SUB | 2 | not injected | pending | none | post-MVP | unsupported |
| MUL | 2 | not injected | pending | none | runtime stretch | unsupported |
| SRLI/SRAI | 2 | not injected | pending | none | post-MVP | unsupported |
| JAL | 2 | not injected | pending | none | post-MVP | unsupported |
| Load/store | 2 | refused: no CKB memory event | pending | none | post-MVP | unsupported |
| MOP | 2 | not injected | pending | none | post-MVP | unsupported |
| A extension | 2 | no public decoder | pending | none | post-MVP | unsupported |

`runtime-only` means both actual implementations emitted complete, equal events
for replayable inputs. It says nothing about inputs outside the corpus, and it
is not extraction or proof evidence.

The equality above is only worth reading because the comparison has been shown
to fail: `make verify-negative` applies the six mandatory mutation categories
of `VERIFICATION.md` §4 to the recorded traces — 188 injections over the 32
cases — and every one is detected and reported against the field it damaged.
Four injections do not apply, because `add-zero` and `addi-zero` commit no
register write at all; they are listed with that reason rather than counted.

SLLI appears in almost every case because `encode::materialize` builds operands
with it. That is real execution on both engines, but it was not chosen for
boundary coverage, so it stays `unsupported` rather than claiming a scope the
corpus was not designed for.

The production source is [upstream + the reviewed runtime-container patch](../proof/lean/extraction/ADOPTION.md),
not the unmodified upstream commit. The real five wrapper methods now have generated
bodies and [proved contract witnesses](../proof/lean/theorems/WrapperContracts.lean).
The final theorem fixes the actual inner projection and admits every supplied machine.

The Week 5 proof/source connection is explicit in this matrix:

| Theorem / evidence | Production Rust functions | Sail functions |
|---|---|---|
| [ProductionAdd.decoded_add_step](../proof/lean/theorems/ProductionAdd.lean) | [execute_production](../crates/proof-extract/src/lib.rs) → [instructions::execute / handle_add](../deps/ckb-vm/src/instructions/execute.rs) → [common::add](../deps/ckb-vm/src/instructions/common.rs) | [try_step](../deps/sail-riscv/model/postlude/step.sail) → [execute RTYPE ADD](../deps/sail-riscv/model/extensions/I/base_insts.sail) |
| [OuterAdd.cold_public_add_step](../proof/lean/decoder/toolchain/full-entry/OuterPublicStep.lean) | [InstDecoder::decode / decode_raw](../deps/ckb-vm/src/decoder.rs) → [i::factory](../deps/ckb-vm/src/instructions/i.rs) → the production execution above | [ext_decode](../deps/sail-riscv/model/postlude/decode_ext.sail) → the production step above |
| Actual imported definitions | [CkbVmProduction.lean](../proof/lean/generated/rust/CkbVmProduction.lean) | [Functions.try_step](../proof/lean/generated/sail/LeanRV64D/Step.lean), [Functions.execute_RTYPE](../proof/lean/generated/sail/LeanRV64D/InstsEnd.lean) |
| Kernel, exact dependencies and clean build | [fixed source identity](../proof/lean/extraction/ckb-source-baseline.json) | [formal audit policy](../proof/lean/audit/step-policy.json), [Week 5 evidence](../proof/lean/reports/WEEK5_EXIT.md) |

The 137-item final axiom set and decoded-input/Sail prefix conditions are explicitly
audited; no `sorryAx` occurs in the final theorem or wrapper witnesses. This remains a
conditional internal theorem. The added public theorem has 158 audited dependencies
and proves same-word ADD decoding for VERSION2, IMC+B, MOP off, a fresh cache and
explicit fetch contracts. Its 47-stage independent clean check passed; the first
integrated main-gate rerun passed (116 tests; see [adoption](../proof/lean/decoder/ADOPTION.md)).
Neither result proves physical-memory coupling, platform-reset reachability, or all
instruction paths. Instruction-level status remains `runtime-only`, while
the Theorem column records the actual kernel-checked result. BEQ's comparison still
lands on an axiom; occurrence in extraction does not upgrade another family's status.

[Concrete joint witness](../proof/lean/reports/ADD_NONVACUITY.md):
`AddWitness.sail_contracts_jointly_inhabited` constructs all Sail contracts on one state
chain; `AddWitness.paired_step` applies the unchanged general theorem with a supplied
Rust seed. This proves a concrete model instance, not unconditional `Nonempty Machine`
or general decoder/initialization correctness, and does not replace the primary theorem.

The matrix moves to `kernel-extracted` only after checked translation artifacts
exist.
