# 新工具的原循环清理回归

2026-09-12。新 base / public Charon 已分别重提取原 upstream
`issue-1051-missing-loop-jump.rs`，同一新 public Aeneas 翻译两侧，原四条 Lean
回归定理和错误结果负测通过。**这是固定用例上的候选资格回归，不是一般清理变换
正确性、工具正式采纳或 clean-room 发布证明。**

```sh
python3 -O scripts/probes/probe_rebuilt_loop.py
```

## 实际结果

[报告](../../artifacts/boundary-check/rebuilt-loop-4psnamoz/report.json)：
21:24:56–21:30:51 UTC，12 阶段，11 项退出 0，错误入口结果负测以真正的
`Type mismatch` 退出 1。外层退出 2，状态为
`rebuilt_loop_regression_checked_admission_pending`。
报告 SHA-256：`d95e3a00022699e8a773b1aa11458ff7cd34259c066c18206dab4e59d35ec1f2`。

原 [LoopJumpProof.lean](../../proof/lean/decoder/toolchain/cfg-experimental/LoopJumpProof.lean)
逐字节保留，证明：

- 对任意 `Range I32`，两个新模型的循环体相等；
- 对任意 `Range I32`，两个循环函数相等；
- 两个真实入口相等；
- 候选入口确实返回 `.ok ()`。

四个定理的名称及精确公理列表与原资格日志一致，均只使用 `propext`、
`Classical.choice`、`Quot.sound`。没有新增定理类型表达式哈希快照；本项以原证明
源码的精确政策哈希及实际 kernel 执行为依据。原错误结果负例同样逐字节复制，
不能把缺依赖、资源失败或普通构造子名 `Error.panic` 算作内部崩溃/语义拒绝。

| 生成物 | 完整模型 SHA-256 |
| --- | --- |
| `LoopJumpBaseline.lean` | `b2cb05e97dfcfadd03e79f462a491f7323db6f2d4dc5e9094f09685798722f71` |
| `LoopJumpCandidate.lean` | `f9a571bc4fded921b361a7c542e1740a4c8770b9d856309674595ca01d4f6aa9` |

## 来源和复用边界

Rust 用例取自已核验的新 base Charon 固定 commit 源码，且与原 UI 资格报告绑定的
用例 SHA-256 `74978d0bf2d45f8246166e37ebd66646c680606d085042b6fe0a381831208dce`
一致。复制到新目录的原相对 `tests/ui/control-flow/` 路径；未修改 upstream 代码、
金样或 Rust 用例，未拿旧 LLBC 当作新提取。

两侧显式使用同一已物化核验的 full-MIR sysroot、相同 preset 和目标/提取选项，
仅输出位置不同。Charon 版本、crate 名、选择范围和检查开关均核验；Aeneas 的
`-namespace BaselineCfg / CandidateCfg` 直接生成可共同导入的命名空间，生成文件不手改。
原资格只绑定 Lean 日志，没有把历史 LLBC/模型身份升级为本次已证明事实；本项明确
不声称新旧 LLBC 或生成模型字节相同，而是在两份新实际模型上重新执行原定理。

Cargo home / target 起初为空，模型与证明从空 `.olean` 目录编译。使用私有 Lean 4.31.0；
主模型/支持库的 15 个目录、70,681 个编译文件明确复用，生产入口在执行前后完整核验。
这不替代[公开根的全依赖源码重建](REBUILT_PUBLIC_KERNEL.md)。工具源码、安装、full-MIR、
证明、实际生成物及正式政策在前后复核中不变。

6 项本入口测试与相关 rebuilt 测试合计 91 项，普通 Python / `-O` 通过。
完成后的独立复核已核对 12 个精确命令/cwd/LEAN_PATH、日志、用例、两份 LLBC/模型、
原证明/负例和四条公理记录，并再次核验工具源码/安装、full-MIR、私有 Lean 全安装及
正式生成物，退出 0。独立复核未再次读取全部支持编译文件；缓存的前后完整哈希检查
属于生产入口的执行证据。
后续 [guard 回归](REBUILT_GUARD_QUALIFICATION.md)也已完成；正式准入、Sail C++ 差异及
Week6 发布缺项保持未关闭。
