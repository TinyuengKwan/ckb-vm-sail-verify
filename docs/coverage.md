# Coverage Matrix

Status values follow `methodology.md`. A Rust scaffold alone is not runtime evidence or a proof.

The MVP target column is a commitment, not current evidence. Current status remains `unsupported` until the evidence gates are met.

| Instruction family | VERSION | Pure kernel | Runtime RVFI | Extraction | Theorem | MVP target | Current status |
|---|---:|---|---|---|---|---|---|
| ADD | 2 | scaffold + unit tests | DII client pending | pending | none | runtime + Lean 4 proved | unsupported |
| SUB | 2 | scaffold + unit tests | DII client pending | pending | none | post-MVP | unsupported |
| ADDI | 2 | scaffold + unit tests | DII client pending | pending | none | runtime-only | unsupported |
| BEQ | 2 | scaffold + unit tests | DII client pending | pending | none | runtime-only | unsupported |
| MUL | 2 | scaffold + unit tests | DII client pending | pending | none | runtime stretch | unsupported |
| SLLI/SRLI/SRAI | 2 | scaffold + unit tests | DII client pending | pending | none | post-MVP | unsupported |
| JAL | 2 | scaffold + unit tests | DII client pending | pending | none | post-MVP | unsupported |
| Load/store | 2 | not modeled | CKB memory event missing | pending | none | post-MVP | unsupported |
| MOP | 2 | not modeled | pending | pending | none | post-MVP | unsupported |
| A extension | 2 | not modeled | no public decoder | pending | none | post-MVP | unsupported |

The matrix moves to `runtime-only` only after both actual implementations emit complete events for a replayable input. It moves to `kernel-extracted` only after checked translation artifacts exist.
