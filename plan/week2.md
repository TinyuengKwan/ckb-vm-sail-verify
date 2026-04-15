# Week 2: Differential Testing Framework

## Task 2.1: Understand Sail Emulator Trace Format

Run the emulator and observe the output:

```bash
./build/c_emulator/sail_riscv_sim /path/to/rv64ui-u-add --trace 2>&1 | head -50
```

Typical format: `[0] [M]: 0x0000000080000000 (0x00000297) auipc t0, 0`

Check available trace options: `sail_riscv_sim --help 2>&1 | grep -i trace`

**Problem**: Default trace only shows PC, not registers. For the PoC, start with PC-only + exit-code comparison. Full register comparison can use RVFI-DII protocol later.

## Task 2.2: Update Sail Runner Parser

Update `crates/diff-test/src/sail_runner.rs` to match real output:

```rust
fn parse_trace(output: &str) -> Result<Vec<StepState>> {
    let mut trace = Vec::new();
    for line in output.lines() {
        let line = line.trim();
        if !line.starts_with('[') { continue; }

        // Pattern: [N] [X]: 0xHEX (...)
        let Some(bracket_end) = line.find("]: ") else { continue };
        let after = &line[bracket_end + 3..];
        let pc_start = if after.starts_with('[') {
            match after.find("]: ") { Some(i) => i + 3, None => continue }
        } else { 0 };
        let rest = &after[pc_start..];
        if !rest.starts_with("0x") { continue; }
        let hex: String = rest[2..].chars().take_while(|c| c.is_ascii_hexdigit()).collect();
        if hex.is_empty() { continue; }
        let pc = u64::from_str_radix(&hex, 16)?;
        trace.push(StepState::new(pc, [0u64; 32]));
    }
    Ok(trace)
}
```

Test: `cargo run -p ckb-vm-diff-test -- --elf /path/to/test --sail-bin ~/workplace/sail-riscv/build/c_emulator/sail_riscv_sim --verbose`

## Task 2.3: Get CKB-VM Test Artifacts

```bash
git clone --depth=1 https://github.com/nervosnetwork/ckb-vm /tmp/ckb-vm-ref
ls /tmp/ckb-vm-ref/tests/artifact/spec/   # rv64ui, rv64um, rv64uc, rv64ua tests
```

Run full suite: `cargo run -p ckb-vm-diff-test -- --test-dir /tmp/ckb-vm-ref/tests/artifact/spec/ --sail-bin ...`

## Task 2.4: Handle ECALL Behavior Differences

riscv-tests use `tohost` memory-mapped exit; CKB-VM uses `ecall(a7=93)`. Update `lib/src/runner.rs` to return exit code:

```rust
pub struct ExecutionResult {
    pub trace: Vec<StepState>,
    pub exit_code: u64,
}
```

Compare PC traces only up to the ECALL divergence point.

## Task 2.5: Add Trace Debugging Tools

Create `lib/src/trace.rs`:

```rust
pub fn save_trace(trace: &[StepState], path: &Path) -> anyhow::Result<()> {
    let json = serde_json::to_string_pretty(trace)?;
    std::fs::write(path, json)?;
    Ok(())
}

pub fn print_diff(ckb: &[StepState], reference: &[StepState], context: usize) {
    let len = ckb.len().min(reference.len());
    let mut diff_at = None;
    for i in 0..len {
        if ckb[i] != reference[i] { diff_at = Some(i); break; }
    }
    let Some(d) = diff_at else {
        println!("Traces match for {} steps.", len);
        return;
    };
    let start = d.saturating_sub(context);
    let end = (d + context + 1).min(len);
    println!("Divergence at step {}:", d);
    println!("{:<8} {:<22} {:<22}", "Step", "CKB-VM PC", "Sail PC");
    for i in start..end {
        let m = if i == d { ">>" } else { "  " };
        println!("{} {:<6} {:#018x}  {:#018x}", m, i, ckb[i].pc, reference[i].pc);
    }
}
```

## Task 2.6: Update Scripts

Update `scripts/run_differential.sh` to auto-discover CKB-VM test artifacts:

```bash
CKB_VM_DIR=""
for d in "$HOME/workplace/ckb-vm" "/tmp/ckb-vm-ref"; do
    [ -d "$d/tests/artifact/spec" ] && CKB_VM_DIR="$d" && break
done
[ -z "$CKB_VM_DIR" ] && git clone --depth=1 https://github.com/nervosnetwork/ckb-vm /tmp/ckb-vm-ref && CKB_VM_DIR="/tmp/ckb-vm-ref"

cargo run --release -p ckb-vm-diff-test -- --test-dir "$CKB_VM_DIR/tests/artifact/spec/" --sail-bin "$SAIL_BIN" "$@"
```

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Modify | `crates/diff-test/src/sail_runner.rs` | Real trace parsing |
| Modify | `crates/diff-test/src/main.rs` | Better reporting |
| Add | `lib/src/trace.rs` | JSON serialization + diff printing |
| Modify | `lib/src/runner.rs` | Return ExecutionResult with exit_code |
| Modify | `lib/src/lib.rs` | Re-export trace module |
| Modify | `scripts/run_differential.sh` | Auto-discover test artifacts |

---

# 第二周：差分测试框架

## 任务 2.1：理解 Sail trace 输出格式

跑 `sail_riscv_sim --trace`，观察实际格式。默认只有 PC，没有寄存器。PoC 阶段先比 PC 轨迹+退出码。

## 任务 2.2：更新 Sail Runner 解析器

根据实际格式改 `sail_runner.rs` 的解析逻辑。代码见英文部分。

## 任务 2.3：获取测试 ELF

clone ckb-vm 获取 `tests/artifact/spec/` 下的 riscv-tests ELF，跑全套差分测试。

## 任务 2.4：处理 ECALL 差异

修改 runner 返回 exit_code，比较时只比到 ECALL 之前。

## 任务 2.5：添加调试工具

新建 `lib/src/trace.rs`，提供 JSON 保存/加载和 side-by-side diff 打印。

## 任务 2.6：更新脚本

让 `run_differential.sh` 自动发现测试目录。
