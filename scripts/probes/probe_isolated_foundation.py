#!/usr/bin/env python3
"""Fresh-checkout output check shared with the proof-pinned source snapshot test.

The 2026-09 isolated-foundation probe that lived here was retired with the
acceptance simplification (records: docs/history/release/ISOLATED_FOUNDATION.md).
``scripts/tests/test_source_snapshot.py`` is hash-pinned by the Lean proof policy
and imports this one helper, so the helper stays under its original name.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_snapshot as snapshot


def check_initial_outputs(checkout):
    """A restored checkout must carry no generated, built or historical evidence."""
    absent = ['target', 'deps/sail-riscv/build', 'sail-model/build',
              'proof/lean/generated', 'proof/rocq/generated']
    snapshot.require(all(not (checkout / p).exists() and not (checkout / p).is_symlink()
                         for p in absent), 'generated/build inputs were copied')
    # artifacts/README.md is versioned documentation, not historical evidence.
    artifacts = checkout / 'artifacts'
    snapshot.require(not artifacts.is_symlink(), 'artifact directory symlink')
    if artifacts.exists():
        snapshot.require(artifacts.is_dir() and
                         all(p.name == 'README.md' and p.is_file() and not p.is_symlink()
                             for p in artifacts.iterdir()), 'historical evidence was copied')
    return absent
