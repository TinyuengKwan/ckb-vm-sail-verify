# Common Lean compatibility evidence

This report records the initial shared-import milestone (1839 Lake jobs and the
pre-constant-extraction Rust hash below). The subsequent constant-extraction
change and its current Rust hash are recorded in [ADD_AUDIT.md](../reports/ADD_AUDIT.md)
and [ADD_PREMISES.md](../reports/ADD_PREMISES.md); the common toolchain/Sail adapter remain
unchanged. The expanded import gate also checks constant lemmas and method contracts.

Baseline: the CKB-VM/Sail/Aeneas revisions recorded in
[VERIFICATION.md](../../../VERIFICATION.md), Lean **4.31.0**, compiler commit
`68218e876d2a38b1985b8590fff244a83c321783` (Linux x86-64 release).
The common project is [../theorems](../theorems/README.md); its manifest locks
lean-sail to `079463134b9c50450b8393e1566a09fc492a34d9` and mathlib to
`fabf563a7c95a166b8d7b6efca11c8b4dc9d911f`, including transitive Git dependencies.
Aeneas's locally installed Lean library must use the same toolchain.

## Measured result (2026-09-07)

| Configuration | Result |
|---|---|
| Lean 4.31.0, pinned lean-sail support library alone | `lake build Sail` passed |
| Lean 4.31.0, unadapted Sail types | Compiler panic; not accepted despite a zero exit status |
| Lean 4.31.0, adapted Sail + production Rust + `SmokeImports` | `make proof-imports` passed: 1839 Lake jobs, enum probe and dependency checks passed |

The model build recompiled the Sail import closure, using cached mathlib/Aeneas
support artifacts; this was not a cache-free bootstrap of every dependency.
`SmokeImports` checked the actual Rust production/ADD entries and Sail
`execute_RTYPE`, `run_hart_active` and `tick_pc` in one file. A separate negative
probe importing both and checking a deliberately missing symbol failed with
Lean exit 1, as expected. All nine isolated gate tests passed.

Both generation scripts were then executed again. The common toolchain and Sail
scope adapter were applied automatically; the three generated-file hashes below
(`Defs`, `InstsEnd`, `CkbVmProduction`) were unchanged. A final `make proof-imports`
after both regenerations exited 0, including the enum probe and dependency checks.

Both diagnostic files under `../audit/` were also re-run in the common project:
both exited 0, the reported ADD dependency classes were unchanged, and neither
query output contained `sorryAx`. These are declaration queries, not an audit of
a completed refinement theorem. The import manifest SHA-256 was
`c379d9a5a8010d12129530289e1e5c5bd5ce0caf335715ffcfc303be7037f5fd`.

## Required scope adapter

Changing only the toolchain is **not** sufficient. The unmodified generated
`Defs.lean` triggers Lean's `LCNF.ExplicitBoxing.tryCorrectLetDeclType` panic
at enum `BEq` derivations. Lake can still report `Built` and Lean can exit 0.
This minimal standard-library-only input reproduces the issue on 4.31.0:

```lean
noncomputable section
inductive AtomicSupport where
  | AMONone | AMOSwap | AMOLogical | AMOArithmetic | AMOCASW | AMOCASD | AMOCASQ
  deriving BEq, Inhabited, Repr
```

In the local reproduction, `LEAN_ABORT_ON_PANIC=1` changed the compiler exit
status to 134. Both model build wrappers now enable it (with core dumps disabled)
and reject panic messages replayed from old Lake traces as well.
An isolated Lake project confirmed the cached case: both its original build and
the replay with `LEAN_ABORT_ON_PANIC=1` returned 0 and printed the panic. The log
check is therefore necessary in addition to the environment setting.

[sail-defs-computable.patch](sail-defs-computable.patch) changes exactly one line:
the `noncomputable section` in `LeanRV64D/Defs.lean` becomes `section`. The entire
generated types/helpers file was tested under this scope, not just the minimal
enum. This changes compilation eligibility, not any type, constructor, function
body or axiom declaration. Execution modules keep their original noncomputable
sections. No Sail support-library checkout or upstream submodule is patched.

`configure_lean_project.sh` applies the patch during generation and before either
build gate, accepts an already-applied patch, and fails on an unknown context.
[EnumComputable.lean](EnumComputable.lean) checks the corrected scope and two
definitional enum comparisons; it is a compiler regression probe, not an ADD proof.

| Generated file | SHA-256 |
|---|---|
| Original `Defs.lean` | `8bf915264717163342aba3e2f41f0b446849219432e148e936b96b137081b99f` |
| Adapted `Defs.lean` | `182f5e780a9d8ecd2d0b98957de2708bd81289f83a327796e914a8d79fa12910` |
| Unchanged `InstsEnd.lean` | `0aaf3f0e9cfc0e25631e180f3a08142a60196701ff229c1071c2e0fd2e5028f3` |
| Unchanged `CkbVmProduction.lean` | `3ebbb73734b4c607cfcbe661790d5e8907cfb7e6f62a916ccd49298c57d38794` |

## Acceptance boundary

The strict acceptance command is `make proof-imports`: it must build both complete
model libraries and the single `SmokeImports.lean` that imports both, check the
enum probe, and verify locked Git checkouts. Cached support artifacts are allowed;
a compiler panic or failed/timed-out build is not. The isolated shell-flow tests
are run with `python3 scripts/tests/test_lean_imports.py` and do not certify Lean code.

This does not prove ADD refinement, decoder correspondence or production wrapper
delegation. The Aeneas library's four existing `sorry` warnings remain; imports
alone do not establish absence of `sorryAx` in a future theorem. The local Aeneas
bundle's source provenance remains a trust boundary beyond checking its version.
