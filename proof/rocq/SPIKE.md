# Rocq/Coq Compatibility Spike — NO-GO

**Verdict: NO-GO for this cycle.** Neither half of the Rocq route reaches a
type-checked definition, for two independent reasons, both measured rather than
inferred. Per `docs/plan/week4.md`, a NO-GO does not substitute for the Lean 4
mainline — and the Lean mainline works: both sides generate and compile
(`make proof-build BACKEND=lean` and `BACKEND=rust`).

Reproduce with `./scripts/rocq_spike.sh`.

## Environment

Installed in a dedicated opam switch (`rocq-spike`, ocaml 5.2.1) so it cannot
disturb the switch that builds the pinned Sail. Versions follow sail-riscv's
own `.github/workflows/rocq.yml`:

| Package | Version |
|---|---|
| rocq-core | 9.1.1 |
| rocq-stdlib | 9.0.0 |
| rocq-stdpp / rocq-stdpp-bitvector | 1.13.0 |
| rocq-sail-stdpp | 0.20.2 |

## Half 1 — Rust to Rocq: blocked in the Aeneas Rocq backend

Aeneas translates the same LLBC that the Lean side uses. Two independent
problems:

**1. `result` is shadowed by the Rocq 9.1 prelude.** Aeneas's `Primitives.v`
defines `Inductive result A`, but `Corelib.Init.Datatypes` in Rocq 9.1 also
defines `result A E`, and the prelude wins. Every generated fallible signature
is therefore ill-typed. The generated file fails at line 17 — the first trait
declaration in it, `core::cmp::PartialEq`:

```
The term "result bool" has type "Type -> Type"
which should be Set, Prop or Type.
```

Minimal reproduction: `proof/rocq/spike/result_shadowing.v`, which prints
`result : Type -> Type -> Type ... Expands to: Inductive
Corelib.Init.Datatypes.result`. `scripts/rocq_spike.sh` compiles it against the
`Primitives.v` it has just generated -- not against a checked-in copy -- so the
reproduction cannot drift from the pinned Aeneas, and it fails the run if the
shadowing ever stops happening.

**2. Aeneas predicts its own failure.** Independently of the above, generation
warns:

```
Recursive trait implementations are not supported; the following recursive
impl is going to be extracted but its model will not type-check:
'ckb_vm::instructions::register::{impl Register for u64}'
```

The Lean backend handles this same impl: it is in the compiled Lean model. So
this is a Rocq-backend limitation of Aeneas, not a property of the CKB-VM code.

## Half 2 — Sail to Rocq: blocked on a support-library version

`rv64d_types.v` compiles (23 MB of `.vo`). `rv64d.v` fails at line 86892:

```
Error: The reference e_div was not found in the current environment.
```

`e_div` is emitted by the Sail Coq backend for `div` in numeric expressions
(`src/sail_coq_backend/pretty_print_coq.ml:698`) and has to come from the Sail
Rocq support library. The pinned Sail is a source build at `8eb1fb6b`, newer
than any release; the newest released `rocq-sail-stdpp` is 0.20.2 and does not
provide `e_div`.

This is the same shape as the Lean namespace problem that forced the pin move:
a source-built Sail needs a support library built from the matching source, and
only the release exists in opam. Unblocking would mean building
`rocq-sail-stdpp` from the Sail source at the pinned commit — plausible, but it
is a second from-source support library to pin and maintain, and it does not
help Half 1, which is blocked in Aeneas.

## Trust assumptions this spike would have added, had it succeeded

Recorded because a later GO must re-examine them:

- the Rocq kernel, in addition to the Lean 4 kernel;
- Aeneas's Rocq backend translation, which is separately maintained from its
  Lean backend and demonstrably weaker on this input;
- `rocq-sail-stdpp`, a second Sail support library whose version must track the
  Sail commit as tightly as the Lean one does.

## What would change the verdict

1. Aeneas's Rocq `Primitives.v` renaming its `result`, or Rocq's prelude
   `result` not shadowing it.
2. Aeneas gaining recursive-trait-impl support in the Rocq backend.
3. A `rocq-sail-stdpp` built from the pinned Sail source.

All three are upstream changes. None is on this project's critical path,
because the mandatory backend is Lean 4 and it works.
