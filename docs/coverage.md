# Coverage Matrix

Status values follow `methodology.md`. A Rust scaffold alone is not runtime evidence or a proof.

The MVP target column is a commitment, not current evidence. Current status remains `unsupported` until the evidence gates are met.

Runtime evidence below comes from `make verify-dii`: 32 injected corpus cases,
395 committed steps compared step by step against the pinned Sail model over
RVFI-DII, with every case replayable from its own artifact.

| Instruction family | VERSION | Pure kernel | Runtime RVFI | Extraction | Theorem | MVP target | Current status |
|---|---:|---|---|---|---|---|---|
| ADD | 2 | scaffold + unit tests | 13 corpus cases, 209 steps | pending | none | runtime + Lean 4 proved | runtime-only |
| ADDI | 2 | scaffold + unit tests | 10 corpus cases, 69 steps | pending | none | runtime-only | runtime-only |
| BEQ | 2 | scaffold + unit tests | 9 corpus cases, 117 steps | pending | none | runtime-only | runtime-only |
| SLLI | 2 | scaffold + unit tests | incidental: setup sequences | pending | none | post-MVP | unsupported |
| SUB | 2 | scaffold + unit tests | not injected | pending | none | post-MVP | unsupported |
| MUL | 2 | scaffold + unit tests | not injected | pending | none | runtime stretch | unsupported |
| SRLI/SRAI | 2 | scaffold + unit tests | not injected | pending | none | post-MVP | unsupported |
| JAL | 2 | scaffold + unit tests | not injected | pending | none | post-MVP | unsupported |
| Load/store | 2 | not modeled | refused: no CKB memory event | pending | none | post-MVP | unsupported |
| MOP | 2 | not modeled | not injected | pending | none | post-MVP | unsupported |
| A extension | 2 | not modeled | no public decoder | pending | none | post-MVP | unsupported |

`runtime-only` means both actual implementations emitted complete, equal events
for replayable inputs. It says nothing about inputs outside the corpus, and it
is not extraction or proof evidence.

The equality above is only worth reading because the comparison has been shown
to fail: `make verify-negative` applies the six mandatory mutation categories
of `VERIFICATION.md` §4 to the recorded traces — 188 injections over the 32
cases — and every one is detected and reported against the field it damaged.
Four injections do not apply, because `add-zero` and `addi-zero` commit no
register write at all; they are listed with that reason rather than counted.

SLLI appears in almost every case because `encode::materialize` builds operands
with it. That is real execution on both engines, but it was not chosen for
boundary coverage, so it stays `unsupported` rather than claiming a scope the
corpus was not designed for.

The matrix moves to `kernel-extracted` only after checked translation artifacts
exist.
