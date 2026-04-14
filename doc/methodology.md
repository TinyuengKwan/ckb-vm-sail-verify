# Verification Methodology

## Proof Strategy

### Per-Instruction Equivalence

For each RISC-V instruction `I`, we prove:

```
forall state : machine_state,
  ckb_vm_execute(I, state) = sail_execute(I, state)
```

where:
- `ckb_vm_execute(I, state)` is the CKB-VM model (from `CkbVmModel.v`)
- `sail_execute(I, state)` is the Sail specification (from generated `CkbVmSpec.v`)

### State Equivalence

Two machine states are considered equivalent when:
1. All 32 registers hold the same values (mod 2^64)
2. The program counter is the same
3. All reachable memory locations hold the same values

### Proof Decomposition

Each instruction proof follows these steps:

1. **Decode equivalence**: Both models decode the same instruction encoding identically
2. **Operand read equivalence**: Both read the same register/immediate values
3. **Computation equivalence**: The ALU/memory operation produces the same result
4. **Write-back equivalence**: The destination register/memory is updated identically
5. **PC update equivalence**: The next PC value is the same

### Handling Undefined Behavior

RISC-V leaves some behaviors implementation-defined or undefined:
- Misaligned memory access: CKB-VM supports it (no trap)
- Division by zero: Returns defined values per spec (DIVU: 2^64-1, DIV: -1)
- FENCE/FENCE.I: No-ops in CKB-VM (single-threaded)

These are documented and handled case-by-case in the proofs.

## Differential Testing Strategy

### Test Corpus

1. **RISC-V ISA compliance tests** (from riscv-tests)
   - rv64ui: Base integer
   - rv64um: Multiply/divide
   - rv64uc: Compressed
   - rv64ua: Atomic

2. **Architecture conformance tests** (from riscv-arch-test)
   - B-extension tests (Zba, Zbb, Zbc, Zbs)

3. **CKB-VM's own test programs**
   - `tests/programs/` in the ckb-vm repository

### Trace Comparison

For each test binary, we compare:
1. **PC trace**: Sequence of program counter values
2. **Register state**: Full register file after each instruction
3. **Exit code**: Final value in A0 register

### Known Divergence Points

The following are expected differences between CKB-VM and Sail:
- Cycle counting (CKB-VM specific, not in RISC-V spec)
- ECALL handling (CKB-VM has custom syscall dispatch)
- Memory size limits (CKB-VM: 4MB fixed)

These are filtered during comparison.

## Roadmap

### Phase 1 (PoC - This Project)
- 10 core instructions with Coq proofs
- Differential testing framework
- Methodology documentation

### Phase 2 (Full RV64I)
- All ~50 RV64I instructions proved
- Automated regression testing

### Phase 3 (Extensions)
- M extension (8 instructions)
- C extension (~40 compressed instructions)
- B extension (Zba: 8, Zbb: 24, Zbc: 3, Zbs: 8)

### Phase 4 (ASM Mode)
- Verification of x86-64 assembly interpreter
- Potentially using Islaris framework
- Prove ASM mode equivalent to Rust interpreter mode
