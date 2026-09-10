# Rocq Spike

This route evaluates Aeneas' Rocq output (or Rocq-of-Rust as a secondary spike) against Sail's `generated_rocq_rv64d` definitions. It replaces the old hand-written `CkbVmModel.v`; generated definitions and a relational theorem must be used directly.

The mandatory result is a reproducible GO/NO-GO report for both generated sides,
imports and the minimum state bridge. A GO result may continue to an ADD theorem as an
extra deliverable. A NO-GO result must include a minimal reproducer and must not be
reported as proof completion.

The two-sided generation/import attempt now has a reproducible
[NO-GO report](SPIKE.md), checked by `make proof-spike`. The Rust-side generated
file fails on the `result` type conflict; the Sail-side main definition file
fails on missing `e_div` (its types file compiles). Successful two-sided imports,
a state bridge and a theorem have not been achieved. This route therefore
supports no `proved` coverage entry.
