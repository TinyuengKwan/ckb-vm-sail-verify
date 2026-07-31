# Week 5 — 生产关联的 Lean 4 ADD 精化

## 目标

完成一条真实的 Lean 4 ADD 定理，直接引用生产关联的 Rust 生成物与 Sail 生成物。

## 证明内容

- operand read 对应。
- wrapping/sign extension 对应。
- rd 写回与 x0 对应。
- PC 更新对应。
- 其他寄存器保持。

## 差分内容

- runtime corpus 覆盖寄存器别名、rd=x0 与 wrapping 边界。
- ADD 至少一个负面 mutation 能被 runtime diff 捕获。

## Exit gate

Lean 4 kernel 从干净构建检查 ADD 定理通过，无未说明 `sorry`/`axiom`；覆盖矩阵链接到定理名、生产 Rust 函数和 Sail 函数。Rocq 只有在 kernel 检查通过时才计入额外证明覆盖。
