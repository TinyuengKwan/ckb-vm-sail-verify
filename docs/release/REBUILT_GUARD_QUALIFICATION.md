# 新工具的原短路守卫资格回归

2026-09-12。原 owned-error 用例和手写 factored 参考用例已由新工具实际重提取，
原全输入等价证明、具体错误守卫反例及错误等式负测通过。此项只检查固定用例的提取
结果，不证明一般 CFG/借用/Drop 变换正确，也不以参考用例替代生产 decoder。

```sh
python3 -O scripts/probes/probe_rebuilt_guard.py
```

## 实际结果

[完成报告](../../artifacts/boundary-check/rebuilt-guard-qyes6caj/report.json)：
21:50:00–21:53:06 UTC，15 阶段，14 项退出 0、错误守卫等式以原 `rfl` 诊断退出 1。
外层退出 2，`rebuilt_guard_regression_checked_admission_pending`。
报告 SHA-256：`7d60a0d39587f6d5f5af310ef3ed02ea8acba6778cb58720ec5a35c8856093ce`。

| 检查 | 实际结果 |
| --- | --- |
| `GuardedFactored.rs` | 新 base Charon / base Aeneas 实际提取及翻译，不启用 public 环境开关 |
| 原 `guarded-owned-error.rs` | 新 public Charon / public Aeneas 实际提取及翻译，保留两个原批准的 public 环境开关 |
| 原 `guarded_equivalence` | 对任意 `head : U64` 和两个 `Result U64 String` 参数，实际新模型相等；原证明字节、公理列表不变 |
| 原反例证明 | 只反转第一个生成的 `return_guard`；全零用例的原结果为 `Ok none`，变异结果为 `Ok (some 11)`，结果不等由 kernel 证明 |
| 错误等式 | 变异模型可编译，但原 `RejectWrongGuard.lean` 的 `rfl` 被真正的错误诊断拒绝 |

两份实际生成模型的完整 SHA-256：

- `GuardedFactored.lean`：`6e5e3bd5bf88de60e78f54683a1bccf2be1a13dad732c808083589a61326153c`；
- `OwnedCleanup.lean`：`c9a0a533a6875b9ac6abff4c78cfe2d2defbd14495cbe9489c2a3373c6c8571f`。

两个审计根 `guarded_equivalence` / `wrong_guard_changes_result` 的依赖均只有
`propext`、`Classical.choice`、`Quot.sound`。前者的精确公理列表匹配原政策绑定的
guard 资格日志；反例证明和负例同样使用原政策绑定的源文件。没有新增类型表达式
哈希快照，也不把历史未绑定的 LLBC/模型当作已证明的身份。

## 来源、环境和复用

Owned-error Rust 源码与原 UI 报告绑定的 SHA-256
`a2c6af305057d61aa01354f87502c9ea9e2ec9dd3b8024dfa01fe1cabe5281d2` 一致。
参考源码 SHA-256 `7def62b5f550d6e14e5fac3f2b3417b229c56e9a41b46d5fc135134f0e62f720`
还与主仓库固定 commit `872d225dc4e16c449be37d92761b20c6aefe853c` 的对应 Git blob 比较。
两份源文件复制到原相对路径，不编辑生成模型以凑齐旧哈希。

两侧使用相同的显式、已物化核验的 full-MIR sysroot 和提取配置；crate 名分别匹配
用例，目标和其余选项一致，未添加 opaque/选择范围或跳过检查。生成命名空间由
Aeneas 参数直接指定。隔离反例仅改外层 namespace 供共同导入，以及唯一一行守卫取反；
原生成文件保持不变。

Cargo home / target 起初为空；模型与证明从空 `.olean` 目录编译。私有 Lean 4.31.0、
主模型和支持库缓存明确复用：15 个目录、70,681 个编译文件在生产入口运行前后完整
核验。工具源码/安装、full-MIR、私有 Lean、原证明及正式生成物前后无漂移。
不是全依赖源码重建、完整 `proof-check` 新 PASS 或工具正式采纳。

6 项本入口测试、相关 91 项 rebuilt 及 37 项 lower 测试，共 134 项普通 Python / `-O`
通过。独立复核已检查全部 15 个精确命令/cwd/LEAN_PATH/public 环境开关、日志、
原源码/证明、LLBC/模型及唯一守卫变异，并再次核验工具源码/安装、full-MIR、私有
Lean 全安装和正式生成物，退出 0。独立复核未再次读取全部支持编译文件；缓存前后
完整核验属于生产入口的执行证据。

## 保留的中止记录

[首轮](../../artifacts/boundary-check/rebuilt-guard-4q05i7v5/report.json)在第八阶段的第二份
Rust 提取期间主动中止，状态为 `failed / KeyboardInterrupt`，没有执行 kernel。
原因是代码复核发现负例 regex 的备选 `Type mismatch` 可能未受诊断行前缀约束；
改为仅接受原负例实际产生的 `Tactic … rfl … failed` 诊断，新增测试拒绝普通文本、
错误类型及缺失诊断。未修改共享门禁或任何正式政策，未将中止记录当作语义失败/成功。
报告 SHA-256：`2996491010297c1708264a7c99f32bb4e8a8db51d520d4ea2b0de3e06bb51fc1`；
原运行脚本 `probe-source.py` SHA-256：
`2770a18e4ae0581d6b4ae586c6f7ed1339ceb2eb245d6f5c3296cfb3ae193eee`。
