# 新工具的原 fnptr 资格回归

2026-09-12。新 base Charon / public Aeneas 已实际重提取原函数指针用例，完整模型
逐字节匹配原批准身份，原 16 条回归证明和全部七项负测通过。这里只完成该项候选
资格回归，未采纳新工具，也不声称翻译器正确性或 Week6 clean-room 已完成。

```sh
python3 -O scripts/probes/probe_rebuilt_fnptr.py
```

## 实际结果

[报告](../../artifacts/boundary-check/rebuilt-fnptr-_j1r1xm7/report.json)：
20:58:07–21:03:30 UTC，22 阶段：15 项退出 0、六项预期翻译拒绝退出 2、
交换调用参数的 Lean 负测退出 1。外层退出 2，状态为
`rebuilt_fnptr_regressions_checked_admission_pending`。
报告 SHA-256：`1ad2d7355f6f517e1f8d1c05b5373e59a5b659fec33ba336c8f617032f061315`。

- 六份原 Rust 用例实际重新提取；未用旧 LLBC 替代新提取。
- `FnPtrCases.lean` 完整 SHA-256 为
  `f277282aa5e154db587881e43d52ee569900370bde4d563fe351b5055e0a910f`，与原模型相同。
- 原 `FnPtrProof.lean` 字节不变，16 个定理名称和精确公理列表与原资格报告一致，
  只含原标准逻辑公理或为空。本项没有新增定理类型表达式哈希审计。
- 新 join-only Aeneas 对同一实际 LLBC 仍以不支持箭头类型拒绝。
- 将唯一 `f bits version` 改为 `f version bits` 后，模型仍可编译，原效果证明正确失败。
- 借用参数、外部 ABI、隐藏 `'static` 借用结果、unsafe 和零参数五类签名分别按原原因拒绝；
  不能将导入、资源不足、信号退出或内部错误算作语义负测成功。

## 提取与证明边界

使用私有 Rust 安装的**普通标准库**，由实际 `rustc --print sysroot` 确认绝对路径，
整个 Rust 安装清单已核验。这对应原局部 fnptr 回归的配置，不是 full-MIR 迭代入口证明。
本模型的 `SharedAVec…into_iter` 仍为 opaque；[公开 kernel 链](REBUILT_PUBLIC_KERNEL.md)
单独使用实际 full-MIR 模型，不能把两者混成一个提取结果。

原报告没有绑定五份负例 LLBC 的哈希，因此不使用那些现存旧文件作为历史证据。
本次以原报告绑定的正例 LLBC 及原统一提取命令核验六份新 LLBC：crate 名分别匹配用例，
target / Charon 格式版本不变，只允许原隐式 sysroot 改为已核验的显式普通标准库路径，
并排除原规则允许的输出位置差异；不宣称 LLBC AST 等价。

八份编译/证明输入（六份 Rust、证明及原补丁）逐字节核对历史哈希。历史 README
单独标明不是编译/证明输入；本轮修正其过期当前状态说明，不用现行说明冒充旧文档。
Cargo home / target 起初为空。模型及局部证明从空模块缓存编译；主模型和支持库的
15 个目录、70,681 个编译文件明确复用，并由生产入口在运行前后完整核验。
这不是全依赖源码重建、完整 `proof-check` 或第三方复现。

## 复核

9 项本入口测试与相关 87 项测试曾在普通 Python / `-O` 下全部通过。
完成后另以 `-O` 独立重构并核对 22 阶段的精确命令、cwd、LEAN_PATH、日志哈希及退出码，
核验六份源码/LLBC、模型/证明、唯一参数交换和原 16 条公理列表；重新核对新工具组件、
join 源码、私有 Lean 全安装及正式生成物，退出 0。该独立复核未再次读取全部支持缓存；
缓存的前后完整哈希检查属于生产入口证据。

报告引用的公开 kernel helper 随后只修正了另一个入口的负例诊断分类。修改前已核验
全部当前输入并保留精确副本 `public-helper-source.py`，SHA-256 为
`a5d6cd0d8a9a2c6ed8ebd683c8e714093b98b53498f3f6cdc3d32870b5596fc4`；
独立复核仅对这一历史 helper 使用该副本，其他输入仍必须匹配当前文件。
原报告不改写，正式政策、定理、工具准入和 Week6 验收定义不变。
