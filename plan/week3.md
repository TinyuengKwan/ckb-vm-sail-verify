# Week 3: Coq Infrastructure & Sail Interface Study

## Task 3.1: Read the Generated Coq Code

The generated file is huge (30k+ lines). Use grep to find key structures:

```bash
grep -n "execute_RISCV_ADD\|RISCV_ADD" coq/generated/CkbVmSpec.v | head -20
grep -n "rX\|wX" coq/generated/CkbVmSpec.v | head -20
grep -n "set_next_pc\|nextPC" coq/generated/CkbVmSpec.v | head -20
```

Sail's Coq output uses a **state monad** (`M a`). A typical instruction:

```coq
Definition execute_RISCV_ADD (rs2 : mword 5) (rs1 : mword 5) (rd : mword 5) : M unit :=
  rX rs1 >>= fun rs1_val =>
  rX rs2 >>= fun rs2_val =>
  let result := add_vec rs1_val rs2_val in
  wX rd result >>= fun _ =>
  retire_success.
```

Key types: `mword n` = n-bit bitvector, `rX`/`wX` = register read/write, `>>= ` = monadic bind.

Write findings to `doc/sail_coq_notes.md`:

```markdown
# Sail Coq Output Notes

## Monad: all functions return `M a`
## Registers: rX (read), wX (write), index is `mword 5`
## Bitvectors: `mword n`, arithmetic via add_vec/sub_vec/and_vec
## PC: set_next_pc : mword 64 -> M unit
## Key names: execute_RISCV_ADD, execute_RISCV_SUB, etc.
```

**Checkpoint**: You can locate and understand ADD, SUB, ADDI definitions.

## Task 3.2: Understand the Monad Extraction Problem

Our model is pure (`machine_state -> machine_state`), Sail is monadic (`M a`). To bridge:

1. Define what `sail_state` contains (regs, PC, memory, CSRs, ...)
2. Extract just the parts we care about
3. Show running the Sail function produces the same observable state changes

Create `coq/SailInterface.v`:

```coq
Require Import Coq.ZArith.ZArith.
Require Import CkbVmVerify.MachineState.
(* Require Import Riscv.CkbVmSpec. *)
(* Require Import Riscv.CkbVmSpec_types. *)

(** State equivalence: same registers, PC, and memory *)
(* Placeholder — fill in after studying the actual Sail state type:
Definition state_equiv (ckb : machine_state) (sail : sail_regstate) : Prop :=
  (forall i, i < 32 -> get_reg ckb i = mword_to_Z (sail_get_reg sail (Z.of_nat i))) /\
  (pc ckb = mword_to_Z (sail_get_pc sail)) /\
  (forall addr, 0 <= addr < 4194304 -> mem ckb addr = mword_to_Z (sail_read_byte sail addr)).
*)
```

## Task 3.3: Try a Minimal Coq Import

Create `coq/TestImport.v` (temporary):

```coq
Require Import SailStdpp.Base.
Require Import Riscv.riscv_extras.
Require Import Riscv.CkbVmSpec_types.
Require Import Riscv.CkbVmSpec.

Check execute_RISCV_ADD.  (* Should print type signature *)
Check rX.
Check wX.
```

Update `coq/_CoqProject`:

```
-R . CkbVmVerify
-R generated Riscv

MachineState.v
CkbVmModel.v
SailInterface.v
InstructionEquiv.v
```

Compile:

```bash
cd coq
coq_makefile -f _CoqProject -o Makefile.coq
make -f Makefile.coq
```

**This will likely fail first time.** Debug each error — missing libraries, name conflicts, etc. This is the hardest task of the week. Expect multiple iterations.

**Checkpoint**: `Check execute_RISCV_ADD.` prints a type.

## Task 3.4: Document the Bridging Strategy

Complete `doc/sail_coq_notes.md` with:
- Exact Sail state type name
- How to construct initial state from `machine_state`
- How to extract `machine_state` after execution
- Sail function name for each target instruction
- Required simplifications (ignore CSRs, privilege mode, etc.)

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `coq/SailInterface.v` | State equivalence relation |
| Add | `coq/TestImport.v` | Temporary: test imports |
| Add | `doc/sail_coq_notes.md` | Sail Coq structure notes |
| Modify | `coq/_CoqProject` | New files + generated/ |

---

# 第三周：Coq 基础设施与 Sail 接口研究

## 任务 3.1：阅读生成的 Coq 代码

用 grep 在几万行的生成文件中定位 ADD 等指令的 Coq 定义。理解 state monad (`M a`)、寄存器读写 (`rX`/`wX`)、bitvector 类型 (`mword n`) 等关键概念。记录到 `doc/sail_coq_notes.md`。

## 任务 3.2：理解 monad 提取问题

我们的模型是纯函数，Sail 是 monadic。需要设计一个"运行"函数来提取可观察状态。创建 `coq/SailInterface.v` 定义 `state_equiv` 关系。

## 任务 3.3：尝试最小 Coq 连接

创建临时文件 `coq/TestImport.v`，用 `Check execute_RISCV_ADD.` 验证导入成功。更新 `_CoqProject`。编译很可能失败——逐个排错。**本周最耗时的任务。**

## 任务 3.4：记录桥接策略

完善文档，记录 Sail 状态类型、构造/提取方法、每条指令的 Sail 函数名、需要的简化假设。
