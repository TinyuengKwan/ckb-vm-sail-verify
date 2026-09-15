# 新工具的原 borrow 资格回归

2026-09-12。新 public Charon / Aeneas、私有 Rust 和新 full-MIR 已重新提取原两个
borrow 用例，生成模型逐字节符合原身份，九条原定理及负测通过。**仅完成该项候选资格
回归，不采纳工具、不宣称完整上游测试通过，也不替代公开 decoder kernel 链。**

```sh
python3 -O scripts/probes/probe_rebuilt_borrows.py
```

## 实际报告

[报告](../../artifacts/boundary-check/rebuilt-borrows-_rl7vzss/report.json)：
20:35:42–20:43:26 UTC，17 阶段，其中 16 项退出 0、错误回边负测退出 1。
外层退出 2，`rebuilt_borrow_regressions_checked_admission_pending`。
报告 SHA-256：`624413e13a949f9b3a56442e097dcff9bd5853e5bf193c3828308918a2e62120`。

| 项目 | 结果 |
| --- | --- |
| `join-duplicate.rs` → `JoinNested` | 新工具实际 Rust 提取及翻译，完整生成模型与原批准模型字节一致 |
| `loop_shared_loan_in_join.rs` → `SharedLoop` | 同上，未改写模型或增加规范化规则 |
| 原九条 borrow 定理 | 类型 SHA-256 和公理列表与原 `borrow-audit-snapshot.json` 完全一致 |
| 额外 False 前提 | 变异定理可编译，仅 `BorrowRegression.nested_assert` 类型改变；公理不变，精确类型审计拒绝 |
| 错误循环回边 | 只把继续循环时的更新数组 `a1` 换为旧数组 `a`；变异模型可编译，原正确效果证明以 `unsolved goals` 拒绝 |
| 变异实际轨迹 | kernel 证明错误结果确为 `11, 11`，不是原来的 `11, 12`，且最终数组保持旧值 |

两份模型 SHA-256：

- JoinNested：`2c76e9a8b1431ecfca2097bf12106cc18c05d99fca15e96cd68b0575f6822f2a`。
- SharedLoop：`47014aa8de3a12f3a302e1884f94cf87ce9f1bf0b96cd5446855cdfa241c47e9`。

九条定理审计 JSON SHA-256：
`093088da906ff9ddc30a1cc802dcaea7c7ab1e821bd5b2c4b850af9171e5ce9c`。
全部公理均在原标准集合 `propext`、`Classical.choice`、`Quot.sound` 内。

## 来源与复用边界

Rust 用例取自已核验的新 Aeneas public 源码，逐字节匹配原资格用例，再复制到新目录。
沿用原相对来源路径和提取参数，显式替换为已物化核验的新 full-MIR 路径；LLBC 选项
比较只允许既有 sysroot / 输出位置差异。运行前后核对工具构建、安装清单、LLBC、
用例、证明及正式生成物。Cargo home / target 起初为空，没有从旧构建目录复制。

使用私有 Lean 4.31.0，模型及本项证明从空 `.olean` 目录编译。主模型和支持库编译缓存
明确复用：沿用先前固定 kernel 报告的 15 个目录、70,681 个编译文件，生产入口在本次
运行前后完整核验其哈希。**不是源码级全依赖重建或独立环境 clean-room。**
新公开根的全依赖源码重建在[另一项流程](REBUILT_PUBLIC_KERNEL.md)中进行，不能与此项
缓存复用混淆；当前不把两份报告合并成一个正式 `proof-check` PASS。

8 项新增守卫测试和相关 79 项，共 87 项普通 Python / `-O` 测试通过。
完成后另以 `-O` 独立复核全部 17 阶段的精确命令、cwd、LEAN_PATH、日志哈希及退出码，
两份实际源文件/LLBC/生成模型、九条原类型/公理，以及 False、回边和实际错误轨迹的
逐处变异均通过；重新核对新工具组件、私有 Lean 安装和正式生成物，独立检查退出 0。
该独立复核没有再次读取全部支持编译文件；缓存前后完整哈希检查属于生产入口的执行证据。
后续 [fnptr](REBUILT_FNPTR_QUALIFICATION.md)、[loop](REBUILT_LOOP_QUALIFICATION.md)
回归、[guard](REBUILT_GUARD_QUALIFICATION.md)及[公开候选根](REBUILT_PUBLIC_KERNEL.md)
也已完成；这些是限定资格，不使上游全量失败消失，正式准入仍未完成。
