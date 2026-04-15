# Sail Model Configuration

This directory contains the Sail RISC-V configuration for the CKB-VM instruction subset.

The Sail RISC-V model itself lives at `deps/sail-riscv/` (git submodule).

## Configuration

`ckb_vm_config.json` defines the exact RISC-V extensions supported by CKB-VM:

- **RV64I**: Base 64-bit integer instructions
- **RV64M**: Integer multiplication and division
- **RVC (Zca)**: Compressed instructions (integer subset only, no F/D)
- **Zba/Zbb/Zbc/Zbs**: Bit-manipulation extensions
- **Zaamo/Zalrsc**: Atomic instructions

Floating-point (F/D), vector (V), and hypervisor (H) are disabled.

## Usage

```bash
# Initialize submodule (first time)
make init

# Generate Coq from Sail
make coq-gen

# Build Sail C++ emulator
make sail-emu
```

## Notes

- CKB-VM's compressed instructions map to Zca (integer-only), not full C extension.
- MOP fusion instructions have no Sail equivalent; verified as compositions.
