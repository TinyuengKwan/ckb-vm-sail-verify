# CKB-VM Sail Formal Verification PoC
# ====================================

SAIL_RISCV_DIR ?= $(HOME)/workplace/sail-riscv
COQ_OUTPUT_DIR := coq/generated

.PHONY: all coq-gen coq diff-test sail-emu clean report help

all: coq diff-test ## Build everything

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Sail -> Coq generation ---
coq-gen: $(COQ_OUTPUT_DIR)/CkbVmSpec.v ## Generate Coq from Sail

$(COQ_OUTPUT_DIR)/CkbVmSpec.v: sail-model/ckb_vm_config.json
	@mkdir -p $(COQ_OUTPUT_DIR)
	./scripts/generate_coq.sh $(SAIL_RISCV_DIR) $(COQ_OUTPUT_DIR)

# --- Coq proofs ---
coq: coq-gen ## Compile Coq proofs
	$(MAKE) -C coq

coq-check: ## Check proofs without regenerating
	$(MAKE) -C coq

# --- Differential testing ---
diff-test: ## Run differential tests
	cargo build --release -p ckb-vm-diff-test
	cargo run  --release -p ckb-vm-diff-test

diff-test-verbose: ## Diff tests with verbose output
	cargo run --release -p ckb-vm-diff-test -- --verbose

# --- Sail emulator ---
sail-emu: ## Build Sail C++ emulator
	./scripts/build_sail_emulator.sh $(SAIL_RISCV_DIR)

# --- Report ---
report: ## Print verification status
	@echo "=== Coq ===" && find coq/ -name '*.vo' 2>/dev/null | head -20 || echo "  (none)"
	@echo "=== Rust ===" && cargo test --workspace --no-run 2>&1 | tail -3

# --- Clean ---
clean: ## Remove all build artifacts
	rm -rf $(COQ_OUTPUT_DIR)
	$(MAKE) -C coq clean 2>/dev/null || true
	cargo clean 2>/dev/null || true
