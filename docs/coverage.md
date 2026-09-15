# Coverage Matrix

Status values follow `methodology.md`. Generated definitions alone are not runtime evidence or a proof.

The MVP target column is a commitment, not current evidence. Current status remains `unsupported` until the evidence gates are met.

The table below uses the [fresh family-floor run](release/WEEK6_RUNTIME_FLOOR.md): 33 injected corpus cases,
398 committed steps compared step by step against the pinned Sail model over
RVFI-DII, with every case replayable from its own artifact.
The previous distribution (13/10/9) did not meet Week6's minimum of ten per family.
The correction adds a tenth BEQ and enforces the per-family minimum; all 33 cases
and relocated replays passed. This does not close clean-room or release acceptance.

| Instruction family | VERSION | Runtime RVFI | Extraction | Theorem | MVP target | Current status |
|---|---:|---|---|---|---|---|
| ADD | 2 | 13 corpus cases, 209 steps | reviewed patched production model; scoped public decoder baseline | [cold_public_add_step](../proof/lean/decoder/toolchain/full-entry/OuterPublicStep.lean) (same-word decode+GPR+PC; conditional) | runtime + Lean 4 proved | runtime-only |
| ADDI | 2 | 10 corpus cases, 69 steps | pending | none | runtime-only | runtime-only |
| BEQ | 2 | 10 corpus cases, 120 steps | pending | none | runtime-only | runtime-only |
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
of `VERIFICATION.md` §4 to the recorded traces — 194 injections over the 33
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
explicit fetch contracts. Its original 47-stage independent clean check passed.
The 2026-09-12 17:36:37 UTC rerun (22 main stages, 206 checker tests, 47 public
stages) is a [historical baseline record](release/SAIL_STALE_GENERATED_FILE.md).
The initial `rebuilt-main-v1` migration completed on 2026-09-13 at
06:26 UTC and passed independent validation at 06:29 UTC: 28 main stages,
287 tests, 48 public stages and 68 public theorems; see
[formal integration](release/FORMAL_MAIN_INTEGRATION.md) and
[scoped theorem adoption](../proof/lean/decoder/ADOPTION.md).
That migration used the historical `7ced9f42…` policy. After the family-floor
correction, the current `b5bdc401…` policy completed its
[full formal chain and independent validation](release/FORMAL_FINAL_EXECUTION.md)
at 22:21 UTC, with the same 28/287/48/68 inventory. The
[current aggregate execution linkage](release/WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)
binds the accepted Lean/Rocq reports to that exact generation record; it adds no coverage.
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

## Week 6 candidate evidence (not additional coverage)

The [Week 6 checklist](WEEK6_STATUS.md) separates the approved proof above from
rebuilt-tool candidates. Actual candidate extraction has covered the production
root, public decoder, iterator and three lower models. Two lower `Option.map`
bodies changed with the explicit full-MIR configuration; their
[kernel equivalence](release/LOWER_MAP_EQUIVALENCE.md) does not silently update
the original raw-definition policy. [Original negatives and a fresh production
factory runtime check](release/LOWER_ORIGINAL_NEGATIVES.md) were also rerun.

The rebuilt tools' [borrow](release/REBUILT_BORROW_QUALIFICATION.md),
[local fnptr](release/REBUILT_FNPTR_QUALIFICATION.md),
[loop-cleanup](release/REBUILT_LOOP_QUALIFICATION.md), and
[short-circuit guard](release/REBUILT_GUARD_QUALIFICATION.md) regressions have completed.
These reuse explicitly verified support compilation caches. The separate
[public candidate source-only rebuild](release/REBUILT_PUBLIC_KERNEL.md) has
completed all 66 stages, including exact audits and both public negatives.
Those qualification reports alone do not admit tool hashes or upgrade the
instruction-family status. Subsequent explicit [v2 admission and formal gate
execution](release/REBUILT_GATE_ACCEPTANCE.md) completed; the initial
[rebuilt main profile migration](release/FORMAL_MAIN_INTEGRATION.md) completed
at 06:26 UTC and passed independent validation at 06:29 UTC: 28 main stages,
287 tests, 48 public stages and 68 public theorems, including the mandatory cold
build. New formal native tests and eleven-stage Rocq NO-GO
have completed and been independently revalidated. The later current-policy
formal record is linked above; these earlier reports retain their original identities.
Current Sail C++ differences
passed the restricted token-correspondence check, not an execution-equivalence proof.
None of this proves physical-memory coupling or completes clean-room/release
requirements; the family coverage labels above remain unchanged.
