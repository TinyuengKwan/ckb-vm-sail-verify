# Differential Artifacts

`--artifact-dir DIR` writes one self-contained JSON per case, named after the
case identifier. The schema is `crates/diff-test/src/artifact.rs`; the fields
are the ones `VERIFICATION.md` §6 requires:

- `environment`: ckb-vm and sail-riscv commits, emulator version, merged config
  path and its SHA-256, CKB-VM ISA byte and VERSION;
- `case` and `instructions_hex`: identity, description, family, seed and the
  injected program as hexadecimal words;
- `initial_state`: the architectural reset state both engines start from;
- `ckb_trace` and `sail_trace`: both normalized event streams with their
  terminations;
- `comparison`: compared steps and the first differing field, if any;
- `sail_raw_packets`: the raw 88-byte v1 RVFI-DII packets, hexadecimal;
- `classification`: `match`, `unclassified_mismatch`, `runner_error` or
  `unsupported`. Deciding between a CKB bug candidate, a configuration or
  version difference and an adapter defect stays a human judgement, so nothing
  is auto-labelled as one of those;
- `replay`: a command that re-runs the program from the artifact alone, and one
  that re-derives it from the corpus generator and seed.

Replay with:

```bash
cargo run -p ckb-vm-sail-diff -- --replay artifacts/corpus/<case>.json
```

A replay refuses to run if the artifact's hexadecimal program disagrees with its
recorded case, so a hand-edited artifact fails instead of quietly testing
something else.

The ELF path does not write artifacts; it is not the closed loop.

Large generated failures are ignored by Git; promoted regression fixtures belong
under the relevant test directory.
