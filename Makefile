# CKB-VM Sail Formal Verification PoC
# ====================================

# Configuration
SAIL_RISCV_DIR ?= $(HOME)/workplace/sail-riscv
COQ_OUTPUT_DIR := coq/generated
DIFF_TEST_DIR  := differential-test

# Sail compiler flags for Coq generation
SAIL_COQ_FLAGS := --dcoq-undef-axioms --coq \
                  --coq-lib riscv_extras \
                  --coq-output-dir $(COQ_OUTPUT_DIR)

.PHONY: all coq-gen coq diff-test clean report help

all: coq diff-test ## Build everything

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================
# Phase 1: Generate Coq from Sail RISC-V
# ============================================================

coq-gen: $(COQ_OUTPUT_DIR)/CkbVmSpec.v ## Generate Coq spec from Sail

$(COQ_OUTPUT_DIR)/CkbVmSpec.v: sail-model/ckb_vm_config.json
	@echo "==> Generating Coq from Sail RISC-V model..."
	@mkdir -p $(COQ_OUTPUT_DIR)
	./scripts/generate_coq.sh $(SAIL_RISCV_DIR) $(COQ_OUTPUT_DIR)
	@echo "==> Coq generation complete."

# ============================================================
# Phase 2: Build and check Coq proofs
# ============================================================

coq: coq-gen ## Build and verify Coq proofs
	@echo "==> Compiling Coq proofs..."
	$(MAKE) -C coq
	@echo "==> All Coq proofs verified."

coq-check: ## Check Coq proofs only (no regeneration)
	@echo "==> Compiling Coq proofs (no regen)..."
	$(MAKE) -C coq
	@echo "==> All Coq proofs verified."

# ============================================================
# Phase 3: Differential testing
# ============================================================

diff-test: ## Run differential tests (CKB-VM vs Sail)
	@echo "==> Building differential test harness..."
	cargo build --release --manifest-path $(DIFF_TEST_DIR)/Cargo.toml
	@echo "==> Running differential tests..."
	cargo run --release --manifest-path $(DIFF_TEST_DIR)/Cargo.toml
	@echo "==> Differential tests complete."

diff-test-verbose: ## Run differential tests with verbose output
	cargo run --release --manifest-path $(DIFF_TEST_DIR)/Cargo.toml -- --verbose

# ============================================================
# Sail C++ emulator (for differential testing)
# ============================================================

sail-emu: ## Build Sail C++ emulator
	@echo "==> Building Sail RISC-V C++ emulator..."
	./scripts/build_sail_emulator.sh $(SAIL_RISCV_DIR)
	@echo "==> Sail emulator built."

# ============================================================
# Reports and documentation
# ============================================================

report: ## Generate verification report
	@echo "=== CKB-VM Sail Verification Report ==="
	@echo ""
	@echo "--- Coq Proof Status ---"
	@find coq/ -name '*.vo' -exec echo "  VERIFIED: {}" \; 2>/dev/null || echo "  No proofs compiled yet."
	@echo ""
	@echo "--- Differential Test Status ---"
	@if [ -f $(DIFF_TEST_DIR)/target/release/ckb-vm-diff-test ]; then \
		echo "  Binary: built"; \
	else \
		echo "  Binary: not built yet"; \
	fi

# ============================================================
# Cleanup
# ============================================================

clean: ## Remove all build artifacts
	@echo "==> Cleaning..."
	rm -rf $(COQ_OUTPUT_DIR)
	$(MAKE) -C coq clean 2>/dev/null || true
	cargo clean --manifest-path $(DIFF_TEST_DIR)/Cargo.toml 2>/dev/null || true
	@echo "==> Clean complete."
