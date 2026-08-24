.PHONY: check test verify-env verify-smoke verify-negative verify-dii sail-emu sail-config diff diff-corpus proof-gen clean-generated

BACKEND ?= lean

check:
	cargo fmt --all -- --check
	cargo check --workspace --all-targets --locked
	cargo clippy --workspace --all-targets --locked -- -D warnings

test:
	cargo test --workspace --locked

verify-env: sail-config
	./scripts/verify_environment.sh

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

proof-gen: sail-config
	./scripts/generate_proof_model.sh "$(BACKEND)"

clean-generated:
	@echo "Generated proof and Sail build directories are intentionally not removed automatically."
	@echo "Delete the exact proof/*/generated or sail-model/build target after reviewing it."
