# Week 7: Full Diff-Test Coverage & Semantic Gap Analysis

## Task 7.1: Run Per-Extension Differential Tests

```bash
CKB_VM_SPEC="/tmp/ckb-vm-ref/tests/artifact/spec"
SAIL_BIN="$HOME/workplace/sail-riscv/build/c_emulator/sail_riscv_sim"

echo "=== RV64I ===" && for f in "$CKB_VM_SPEC"/rv64ui-u-*; do
    cargo run --release -p ckb-vm-diff-test -- --elf "$f" --sail-bin "$SAIL_BIN"; done

echo "=== RV64M ===" && for f in "$CKB_VM_SPEC"/rv64um-u-*; do
    cargo run --release -p ckb-vm-diff-test -- --elf "$f" --sail-bin "$SAIL_BIN"; done

echo "=== RV64C ===" && for f in "$CKB_VM_SPEC"/rv64uc-u-*; do
    cargo run --release -p ckb-vm-diff-test -- --elf "$f" --sail-bin "$SAIL_BIN"; done

echo "=== RV64A ===" && for f in "$CKB_VM_SPEC"/rv64ua-u-*; do
    cargo run --release -p ckb-vm-diff-test -- --elf "$f" --sail-bin "$SAIL_BIN"; done
```

## Task 7.2: Add --extension Filter to CLI

In `crates/diff-test/src/main.rs`:

```rust
#[arg(long)]
extension: Option<String>,

fn matches_extension(path: &Path, ext: &str) -> bool {
    let name = path.file_name().unwrap_or_default().to_string_lossy();
    match ext {
        "I" => name.contains("rv64ui"),
        "M" => name.contains("rv64um"),
        "C" => name.contains("rv64uc"),
        "A" => name.contains("rv64ua"),
        _ => true,
    }
}
```

## Task 7.3: Write Semantic Gap Document

Create `doc/semantic_gaps.md` documenting 8 categories:

1. **x0 handling**: CKB-VM writes then clears vs Sail discards writes. Functionally equivalent.
2. **ECALL**: CKB-VM dispatches via A7; Sail traps to M-mode.
3. **Memory**: 4MB fixed, no MMU, W^X. Sail has full Sv39/48/57.
4. **FENCE**: No-op in CKB-VM.
5. **Atomics**: Single-address reservation vs reservation set.
6. **Versions**: VERSION0/1/2 boundary check differences.
7. **Cycles**: CKB-VM has per-instruction costs. Not in RISC-V spec.
8. **MOP**: Custom fusion instructions.

Each entry: what it is, how it differs, impact on verification.

## Task 7.4: Test Edge Cases

Write assembly tests for tricky behaviors:

```bash
# Division by zero: DIVU should return 0xFFFFFFFFFFFFFFFF
cat > /tmp/div_zero.S << 'EOF'
.global _start
_start:
    li a0, 42; li a1, 0; divu a2, a0, a1
    li t0, -1; bne a2, t0, fail
    li a0, 0; li a7, 93; ecall
fail: li a0, 1; li a7, 93; ecall
EOF
riscv64-unknown-elf-gcc -nostdlib -static -o /tmp/div_zero /tmp/div_zero.S
cargo run -p ckb-vm-diff-test -- --elf /tmp/div_zero --sail-bin $SAIL_BIN --verbose
```

Write similar for: max shift (SLLI x, x, 63), signed overflow.

## Task 7.5: Complete Instruction Mapping

Update `doc/instruction_mapping.md` with status columns:

```markdown
| Opcode | RISC-V | Coq Proved | Diff-Tested |
|--------|--------|------------|-------------|
| OP_ADD | ADD | Yes | Yes |
| OP_DIV | DIV | No | Yes |
| OP_WIDE_MUL | (MOP) | Partial | N/A |
```

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `doc/semantic_gaps.md` | Gap analysis |
| Modify | `doc/instruction_mapping.md` | Status columns |
| Modify | `crates/diff-test/src/main.rs` | --extension filter |
| Modify | `scripts/run_differential.sh` | Per-extension runs |

---

# 第七周：全面差分测试与语义差异分析

## 任务 7.1：按扩展分组跑测试

对 I/M/C/A 四组 ELF 分别运行差分测试，记录每组通过率。

## 任务 7.2：添加 --extension 过滤

CLI 新增参数按文件名前缀过滤扩展。

## 任务 7.3：编写语义差异文档

`doc/semantic_gaps.md` 系统记录 8 类差异及其对验证的影响。

## 任务 7.4：边界情况测试

手写汇编测试除零、最大移位量、溢出等边界行为。

## 任务 7.5：完善映射表

给每个 opcode 标注"Coq 已证明"和"差分已测试"状态。
