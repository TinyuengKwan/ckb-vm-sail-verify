.PHONY: check test verify-env verify-dii sail-emu sail-config diff diff-corpus proof-gen clean-generated

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

# Week 2 evidence: the RVFI-DII corpus and the negative tests that prove the
# comparator can still fail.
diff-corpus: sail-config
	cargo run --locked -p ckb-vm-sail-diff -- --corpus --artifact-dir artifacts/corpus

verify-dii: sail-config
	cargo test --locked -p ckb-vm-sail-diff -- --ignored
	$(MAKE) diff-corpus

proof-gen: sail-config
	./scripts/generate_proof_model.sh "$(BACKEND)"

clean-generated:
	@echo "Generated proof and Sail build directories are intentionally not removed automatically."
	@echo "Delete the exact proof/*/generated or sail-model/build target after reviewing it."
