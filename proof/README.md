# Proof Workspace

This directory is a gate, not proof evidence yet.

- `lean/` is the mandatory main path: Charon/Aeneas + Sail Lean backend.
- `rocq/` is the compatibility GO/NO-GO spike for Aeneas/Rocq-of-Rust + Sail Coq backend.
- `generated/` directories are reproducible build products and are not edited by hand.

A theorem may be counted only when it imports both the Rust translation and Sail-generated definitions, states the explicit `state_rel`, builds without `sorry`/`Admitted`, and the translated Rust function is connected to the production interpreter.

`scripts/generate_proof_model.sh` currently generates the Sail half only. Rust extraction,
the production connection and the Lean 4 ADD theorem are Week 4–5 work. Rocq/Coq must
produce reproducible generation/import evidence, but a GO/NO-GO report is not a proof.
A hand-written replacement must not be substituted under either claim.
