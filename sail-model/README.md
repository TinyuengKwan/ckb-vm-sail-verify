# Sail Model Configuration

This directory contains the Sail RISC-V configuration for the CKB-VM instruction subset.

## Configuration

`ckb_vm_config.json` defines the exact RISC-V extensions supported by CKB-VM:

- **RV64I**: Base 64-bit integer instructions
- **RV64M**: Integer multiplication and division
- **RVC (Zca)**: Compressed instructions (integer subset only, no F/D)
- **Zba/Zbb/Zbc/Zbs**: Bit-manipulation extensions
- **Zaamo/Zalrsc**: Atomic instructions

Floating-point (F/D), vector (V), and hypervisor (H) extensions are explicitly disabled,
as CKB-VM does not implement them.

## Usage

The config is consumed by `scripts/generate_coq.sh` to drive Sail's Coq backend:

```bash
sail --coq --config ckb_vm_config.json ...
```

## Notes

- CKB-VM's compressed instruction support maps to Zca (integer-only C extension),
  not the full C extension which includes Zcf/Zcd for floating-point.
- CKB-VM also has custom MOP (Macro-Operation Fusion) instructions that have no
  Sail equivalent. These are verified separately as compositions of standard instructions.
