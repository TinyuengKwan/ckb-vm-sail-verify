# Differential Artifacts

Each mismatch directory should contain:

- `metadata.json`: tool commits, merged config hash, seed and CLI arguments;
- `input.elf` or a minimized instruction/state fixture;
- `ckb-trace.json` and `sail-trace.json`;
- `comparison.json` with the first mismatching field;
- `disposition.md`: CKB bug candidate, configuration/version difference, adapter defect,
  unsupported, or not yet classified.

Large generated failures are ignored by Git; promoted regression fixtures belong under the relevant test directory.
