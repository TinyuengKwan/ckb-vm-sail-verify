# Proof Workspace

This directory contains checked conditional ADD register and instruction-step proofs, not a full VM proof.

- `lean/` is the mandatory main path: Charon/Aeneas + Sail Lean backend.
- `rocq/` is the compatibility GO/NO-GO spike for Aeneas/Rocq-of-Rust + Sail Coq backend.
- `generated/` directories are reproducible build products and are not edited by hand.

A theorem may be counted only when it imports both the Rust translation and Sail-generated definitions, states the explicit `state_rel`, builds without `sorry`/`Admitted`, and the translated Rust function is connected to the production interpreter.

`scripts/generate_proof_model.sh` generates the Sail half;
`scripts/generate_rust_model.sh` extracts the production call graph through
`crates/proof-extract` and translates it with Aeneas. Both Lean halves have
successful separate build records. `make proof-imports` checks both complete
libraries and their shared import under Lean 4.31.0; see the
[compatibility report](lean/compat/README.md). `make proof-registers` checks the
GPR state relation and [conditional ADD leaf theorem](lean/reports/ADD_REGISTERS.md).
`make proof-step` additionally checks [dispatch/PC and normal retirement](lean/reports/ADD_STEP.md)
at the actual generated entry points. Production delegation contracts are proved;
Sail prefix and initial-state conditions remain explicit. Source reachability does not
discharge opaque production methods; see the
[ADD audit](lean/reports/ADD_AUDIT.md).

`make proof-check BACKEND=lean` now regenerates both inputs, audits the final
theorem's exact axioms and elaborated premises against reviewed source/tool
identity pins, and runs regression/negative tests. Its report remains conditional;
see [proof-check](lean/reports/PROOF_CHECK.md). It is not the still-pending release audit.
The [public ADD decoder extension](lean/decoder/ADOPTION.md) is now a required stage:
fresh production Rust extraction and a source-only build of the full Lean dependency
graph. Its independent check and first integrated main-gate run both passed;
the latter checked 116 tests and all 47 public-decoder stages.

The [Rocq spike](rocq/SPIKE.md) records a reproducible NO-GO for the two-sided
route: both definition sets are generated, but import/build failures prevent a
state bridge and theorem. `make proof-spike` checks that recorded outcome;
it does not establish proof coverage. A hand-written replacement must not be
substituted under either claim.
