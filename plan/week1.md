# Week 1: Environment Setup & Instruction Mapping

## Task 1.1: Install Sail Toolchain

You already have sail and sail-riscv in `~/workplace/`. Verify they work:

```bash
cd ~/workplace/sail
opam exec -- sail --version
# Expected: Sail 0.20.x or later

# If not installed or outdated:
opam update
opam install sail
```

Then verify the Coq backend dependencies:

```bash
opam install coq.9.0.0 coq-sail-stdpp
coqc --version
# Expected: The Coq/Rocq Proof Assistant, version 9.0.0
```

**Checkpoint**: `sail --version` and `coqc --version` both work.

## Task 1.2: Generate Coq from sail-riscv

```bash
cd ~/workplace/sail-riscv

# Configure cmake build if build/ doesn't exist:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release

# Generate Coq for RV64
cmake --build build --target generated_rocq_rv64d
```

This produces `build/rocq/rv64d.v` and `build/rocq/rv64d_types.v`. Verify they compile:

```bash
cd build/rocq
cp ../../handwritten_support/riscv_extras.v .
coqc -R . Riscv riscv_extras.v
coqc -R . Riscv rv64d_types.v
coqc -R . Riscv rv64d.v
```

If `coqc` fails with missing `SailStdpp`, run `opam install coq-sail-stdpp`.

Copy to our project:

```bash
cd ~/workplace/ckb-vm-sail-verify
mkdir -p coq/generated
cp ~/workplace/sail-riscv/build/rocq/rv64d.v coq/generated/CkbVmSpec.v
cp ~/workplace/sail-riscv/build/rocq/rv64d_types.v coq/generated/CkbVmSpec_types.v
cp ~/workplace/sail-riscv/handwritten_support/riscv_extras.v coq/generated/riscv_extras.v
```

Or use the script: `./scripts/generate_coq.sh ~/workplace/sail-riscv coq/generated`

**Checkpoint**: `coq/generated/CkbVmSpec.v` exists and `coqc` compiles it.

## Task 1.3: Verify Rust Workspace Builds

```bash
cd ~/workplace/ckb-vm-sail-verify
cargo build --workspace
```

If ckb-vm requires a specific Rust version:

```bash
rustup install 1.92.0
rustup default 1.92.0
cargo build --workspace
```

**Checkpoint**: `cargo build --workspace` succeeds.

## Task 1.4: Build Sail C++ Emulator

```bash
cd ~/workplace/sail-riscv
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_GMP=TRUE
cmake --build build -j$(nproc) --target sail_riscv_sim
```

Test with a minimal program:

```bash
cat > /tmp/test_add.S << 'EOF'
.global _start
_start:
    li a0, 42
    li a7, 93
    ecall
EOF

riscv64-unknown-elf-gcc -nostdlib -static -o /tmp/test_add /tmp/test_add.S
./build/c_emulator/sail_riscv_sim /tmp/test_add --trace 2>&1 | head -20
```

If you lack `riscv64-unknown-elf-gcc`: `sudo apt install gcc-riscv64-unknown-elf`

**Checkpoint**: `sail_riscv_sim` runs and produces trace output.

## Task 1.5: Build the Instruction Mapping Table

Open two files side by side:

**File A** — CKB-VM opcodes in `ckb-vm/definitions/src/instructions.rs`:
```rust
// The macro defines opcodes like:
$m!(OP_ADD, 0x10)
$m!(OP_SUB, 0x11)
// ... 158 total
```

**File B** — Sail execute clauses. Use grep to locate each instruction:

```bash
cd ~/workplace/sail-riscv
grep -rn "RISCV_ADD" model/extensions/I/
```

Sail ADD looks like:

```sail
function clause execute (RISCV_ADD(rs2, rs1, rd)) = {
  let rs1_val = X(rs1);
  let rs2_val = X(rs2);
  let result : xlenbits = rs1_val + rs2_val;
  X(rd) = result;
  RETIRE_SUCCESS
}
```

CKB-VM ADD in `src/instructions/execute.rs`:

```rust
pub fn handle_add<...>(inst: Instruction, machine: &mut Mac) -> Result<(), Error> {
    let i = Rtype(inst);
    let rs1_value = &machine.registers()[i.rs1()];
    let rs2_value = &machine.registers()[i.rs2()];
    let value = rs1_value.overflowing_add(rs2_value);
    update_register(machine, i.rd(), value);
    Ok(())
}
```

Create `doc/instruction_mapping.md` with every opcode mapped. Mark MOP fusion instructions (WIDE_MUL, FAR_JUMP, ADC, etc.) as "CKB-VM only".

**Checkpoint**: Mapping table covers at least I+M+C extensions.

## Task 1.6: Create Environment Setup Script

Write `scripts/setup_env.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "=== CKB-VM Sail Verify: Environment Setup ==="

command -v opam >/dev/null || { echo "Install opam: https://opam.ocaml.org/"; exit 1; }
opam update && opam install -y sail coq.9.0.0 coq-sail-stdpp

command -v cargo >/dev/null || { echo "Install Rust: https://rustup.rs"; exit 1; }

SAIL_RISCV="${SAIL_RISCV_DIR:-$HOME/workplace/sail-riscv}"
if [ -d "$SAIL_RISCV" ]; then
    cmake -S "$SAIL_RISCV" -B "$SAIL_RISCV/build" -DCMAKE_BUILD_TYPE=Release
    cmake --build "$SAIL_RISCV/build" --target generated_rocq_rv64d
    cmake --build "$SAIL_RISCV/build" --target sail_riscv_sim
fi

cargo build --workspace
echo "=== All checks passed ==="
```

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/generated/` (3 files) | Generated, gitignored |
| Add | `doc/instruction_mapping.md` | Opcode mapping table |
| Add | `scripts/setup_env.sh` | One-shot env setup |
| Modify | `scripts/generate_coq.sh` | Fix paths if needed |

---

# 第一周：环境搭建与指令映射

## 任务 1.1：安装 Sail 工具链

验证 `~/workplace/sail` 中的 sail 编译器版本 >= 0.20.x。安装 Coq 9.0 和 coq-sail-stdpp。

## 任务 1.2：从 sail-riscv 生成 Coq

运行 cmake 构建 sail-riscv，用 `generated_rocq_rv64d` 目标生成 Coq 文件，验证能被 `coqc` 编译，然后拷贝到 `coq/generated/`。

## 任务 1.3：验证 Rust 工作空间

`cargo build --workspace` 通过即可。如果 Rust 版本不满足要求用 rustup 安装。

## 任务 1.4：编译 Sail C++ 模拟器

构建 `sail_riscv_sim`，用一个简单的 `li a0, 42; ecall` 汇编程序加 `--trace` 跑通。

## 任务 1.5：建立指令映射表

同时阅读 CKB-VM 的 158 个 opcode 定义和 sail-riscv 的 execute clause，用 grep 逐一匹配，写入 `doc/instruction_mapping.md`。MOP 融合指令标记为"CKB-VM only"。

## 任务 1.6：创建环境搭建脚本

写 `scripts/setup_env.sh` 一键装依赖+构建。
