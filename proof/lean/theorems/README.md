# Shared Lean import, register and step-proof project

This project imports the generated production CKB-VM definitions and the generated
Sail execution model in one Lean environment. `SmokeImports.lean` checks both ADD
entry points and the surrounding execution/PC functions. It also imports
`ExtractedConstants.lean` (checked constant values and axiom-footprint guards)
and `AddPremises.lean` (uninstantiated delegation/input contracts and a dictionary
identity check). None is an ADD refinement theorem.

## Build

Install the pinned Charon/Aeneas bundle described in `VERIFICATION.md` and the
Lean version in this directory's `lean-toolchain`. `lake` (normally installed by
elan), Python 3, Git, GNU patch and timeout are required. From the repository root:

```bash
# Produce the inputs on a fresh checkout; see VERIFICATION.md for Sail setup.
make proof-gen-rust
make proof-gen BACKEND=lean

# Build both complete model libraries and their shared import file.
make proof-imports

# Also check the conditional register-only theorem and its exact axiom footprint.
make proof-registers

# Also connect the production root to Sail try_step under explicit contracts.
make proof-step

# Regenerate both inputs and audit source identity, final axioms and premises.
# Acceptance remains conditional; concrete contracts and release audit are pending.
make proof-check BACKEND=lean
```

If Aeneas is installed elsewhere:

```bash
AENEAS_HOME=/path/to/aeneas make proof-imports
```

The build reads the committed `lake-manifest.json`; it does not run `lake update`.
On first use, Lake may clone dependencies at the locked revisions. Mathlib's
prebuilt cache is optional; without it the first build can take much longer.
After dependency setup, `lake exe cache get` in this directory can populate it.
Set `PROOF_BUILD_TIMEOUT` (seconds, default 3600) for a cold build if necessary.

The wrapper prepares `.lake/aeneas` as a link to the installed Aeneas Lean library.
That link keeps the checked-in manifest independent of a developer's home path.
It checks the library's Lean version, the actual compiler, the resolved Sail pin,
the Git dependency checkouts and that Lake did not change the lock. It enables
`LEAN_ABORT_ON_PANIC=1`, rejects compiler panics even in cached Lake traces, and
runs the computable-enum regression probe. The build log is retained at
`.lake/import-build.log`, `.lake/register-build.log` or `.lake/step-build.log`. Aeneas itself
is a local dependency: its installation must still be the pinned bundle; checking
its toolchain string does not certify its source contents. The separate
[proof-check gate](../reports/PROOF_CHECK.md) also pins its source contents and tool binaries.

After this preparation, direct `lake build` checks the default `SmokeImports`
target. The Make target additionally builds the entire `LeanRV64D` and
`CkbVmProduction` libraries and checks the dependency lock/checkouts.

## Configuration and regeneration

This directory's `lean-toolchain` is the common version authority.
`scripts/configure_lean_project.sh` copies it into both generated projects and
pins Sail's support library to `expected_build_status.txt`. Both generators and
the standalone build checker use that helper, so regeneration does not restore
the upstream Sail project's older toolchain. The helper also applies the checked-in
`../compat/sail-defs-computable.patch` idempotently: only the top-level
`noncomputable section` in `LeanRV64D/Defs.lean` becomes `section`. Lean 4.31.0
panics on enum `BEq` derivation in the former scope. The whole types/helpers file
compiles in the latter; instruction function bodies and their noncomputable
sections remain unchanged. An unrecognized patch context fails, rather than
silently accepting changed generator output. No manual generated-file edit is
needed. See [compatibility evidence](../compat/README.md).

The manifest locks Git dependencies including mathlib's transitive dependencies.
Updating it is an explicit maintenance action: with the local Aeneas link in
place, run `lake update`, inspect the changes and rebuild. Moving the Sail pin
requires updating its build-status record as well.

Run `python3 scripts/tests/test_lean_imports.py` from the repository root for isolated
configuration/failure-path tests. They use a fake Lake and do not replace
`make proof-imports` with the real compiler.

## Evidence boundary

Successful imports establish compilation compatibility and availability of both
models in the same environment; the constant module additionally proves the two
extracted constant values. See [remaining premises](../reports/ADD_PREMISES.md).
`StateRel.lean`, `RustAdd.lean`, `SailRegisters.lean` and `AddRegisters.lean`
establish the conditional register-only result. `AddRegisterAxioms.lean` guards
its full 63-item transitive footprint; `RegisterRegression.lean` checks edge cases.
See [scope and remaining premises](../reports/ADD_REGISTERS.md). `WrapperContracts.lean`
proves the production wrapper delegation instances. `RustDispatch.lean`, `SailDispatch.lean`,
`SailRetirement.lean` and `AddStep.lean` connect actual dispatch, PC staging/commit
and normal retirement, with explicit framed prefix contracts. `AddStepAxioms.lean`
guards the full 137-item footprint, not the smaller leaf footprint;
`StepRegression.lean` checks edge cases. `ProductionAdd.lean` fixes the real inner
projection and proved wrapper contracts. See [step scope](../reports/ADD_STEP.md).
Run `python3 scripts/tests/test_lean_step.py` from the repository root after `make proof-step`
for real Lean rejection tests using temporary mutated copies.
These build targets are components of the separate `proof-check` audit gate. The known
Aeneas support-library `sorry` warnings remain documented in
[ADD_AUDIT.md](../reports/ADD_AUDIT.md).
