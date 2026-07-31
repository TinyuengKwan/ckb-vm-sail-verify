# Week 1 — Foundation 与诚实基线

## 任务

- 修复 Rust workspace 与锁定版 CKB-VM API 的编译。
- 定义 `CommitEvent`、`ExecutionTrace`、`TraceEnd`。
- 实现严格比较器：字段、长度、终止状态全部进入结果。
- 保留纯 Rust `semantics` scaffold；本轮只有 ADD 进入强制证明范围。
- 更新 sail-riscv 配置 override 与合并脚本。
- 固定当前执行基线的 Rust 要求、CKB-VM、Sail 与 sail-riscv；Aeneas/Charon、Lean 4 和 Rocq/OPAM 在 Week 4 首次启用前固定。
- 建立 `proof/lean` 主证明入口和 `proof/rocq` 兼容性 spike 入口。
- 建立 `VERIFICATION.md`、当前 foundation 环境检查和六周范围基线。

## 测试

- ADD overflow、x0、branch taken/not-taken scaffold 测试。
- 注入 PC、rd 编号、rd 值、trap、trace 长度/终止差异必须 FAIL。
- 空事件、execution error 和公共前缀相同但尾部不同必须 FAIL。
- JSON roundtrip 保持事件。
- 合并后的 Sail 配置哈希与白名单一致。

## 交付证据

- `cargo test --workspace --locked`
- `cargo fmt --all -- --check`
- `cargo clippy --workspace --all-targets --locked -- -D warnings`
- `make verify-env`
- foundation 状态说明和 `VERIFICATION.md` 基线，不产生“proved”条目。

## Exit gate

workspace 可构建；当前版本、ISA 与配置哈希通过环境检查；比较器不存在空 trace
或公共前缀误报；旧手写 Coq 模型不再作为验证结论入口。
