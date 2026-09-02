.PHONY: check test sail-compiler verify-env verify-smoke verify-negative verify-dii sail-emu sail-config diff diff-corpus proof-gen proof-gen-rust proof-build proof-spike clean-generated

BACKEND ?= lean

check:
	cargo fmt --all -- --check
	cargo check --workspace --all-targets --locked
	cargo clippy --workspace --all-targets --locked -- -D warnings

test:
	cargo test --workspace --locked

verify-env: sail-config
	./scripts/verify_environment.sh

# Sail itself, built from source at the pinned commit. Needed before sail-emu
# on a fresh machine; see proof/lean/expected_build_status.txt for why a
# release build is not enough.
sail-compiler:
	./scripts/build_sail.sh

sail-emu:
	./scripts/build_sail_emulator.sh

sail-config: sail-emu
	./scripts/prepare_sail_config.sh

diff:
	@test -n "$(ELF)" || (echo "usage: make diff ELF=path/to/test.elf"; exit 2)
	./scripts/run_differential.sh "$(ELF)"

# `VERIFICATION.md` §3 acceptance interface.
#
# verify-smoke:    strict two-sided comparison over the mandatory corpus.
# verify-negative: the mutation matrix plus the end-to-end tests that show the
#                  harness locating a real divergence. Neither target can pass
#                  without the other's evidence being meaningful, so CI runs
#                  both.
verify-smoke: sail-config
	cargo run --locked -p ckb-vm-sail-diff -- --corpus --artifact-dir artifacts/corpus

verify-negative: sail-config
	cargo test --locked -p ckb-vm-sail-diff -- --ignored
	cargo run --locked -p ckb-vm-sail-diff -- --corpus --mutate --artifact-dir artifacts/corpus

# Kept as the Week 2 entry point and as the single command CI invokes.
verify-dii: verify-smoke verify-negative

diff-corpus: verify-smoke

# Generation alone is not evidence that the model is usable, so proof-gen also
# compiles what it generated and compares the outcome against the recorded
# expectation. proof-build runs that check on its own.
proof-gen: sail-config
	./scripts/generate_proof_model.sh "$(BACKEND)"
	./scripts/check_proof_model.sh "$(BACKEND)"

# The Rust side: Charon extracts the production call graph from the roots in
# crates/proof-extract, Aeneas translates it, and the same build check applies.
proof-gen-rust:
	./scripts/generate_rust_model.sh
	./scripts/check_proof_model.sh rust

proof-build:
	./scripts/check_proof_model.sh "$(BACKEND)"

# `VERIFICATION.md` §3's proof-spike: reproduces the Rocq GO/NO-GO recorded in
# proof/rocq/SPIKE.md. Fails if either half starts succeeding, because that
# makes the record stale.
proof-spike:
	./scripts/rocq_spike.sh

clean-generated:
	@echo "Generated proof and Sail build directories are intentionally not removed automatically."
	@echo "Delete the exact proof/*/generated or sail-model/build target after reviewing it."
