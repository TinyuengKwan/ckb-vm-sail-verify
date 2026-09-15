# 新下层模型的原有负测与生产工厂运行核验

2026-09-12。入口：

```sh
python3 -O scripts/probes/probe_lower_original_negatives.py
```

本项承接 [map 等价与原 raw 定理候选检查](LOWER_MAP_EQUIVALENCE.md)，核验新候选模型
上的原字段/raw 负测，并重新构建原生产工厂运行检查器。它不采纳新工具、不修改正式
政策，也不把 runtime 穷举算作 Lean 证明或完整公开 decoder 检查。

## 输入与检查边界

- 固定实际重提取报告、候选 kernel 报告、模型/证明源码和工具安装清单；运行前后复核。
- 明确复用候选模型/证明和主模型/支持库 `.olean`，复核 70,681 项支持编译文件及
  候选缓存；不是全依赖源码重建。
- 重新运行 map / field / raw 三个 Lean 审计导出器，与前次候选审计完整 JSON 比较。
  原字段政策必须接受，原 raw 政策必须仍因限定两处 map 定义变化而拒绝。
- 四类错误结果变异沿用原门禁：错误 Sail 位域、Rust 位移、ADD selector 和源寄存器字段。
  必须取得相应语义诊断，导入、资源、超时或内部错误不能充当正确拒绝。
- 分别给原字段与 raw 编码定理增加 `False` 前提：允许变异定理编译，但精确类型比较
  必须发现且仅发现指定定理的类型变化，定义和公理集合不得改变。
  这是审计器负测，不声称整个削弱后的依赖图已重建。
- 新 join-only Aeneas 对实际新 MiniComplete LLBC 的严格合流模式必须按原原因退出 2。
- 在空 Cargo home / target 中，用私有 Rust、原冻结 runtime 锁和候选生产源码构建
  `RuntimeCheck.rs`；锁定下载后离线构建，运行本次产出的实际二进制并绑定其哈希。
  范围仅为 RV64 VERSION2 `i::factory`，不包括 `DefaultDecoder`、取指或执行退休证明。

## 执行记录

修正后的[报告](../../artifacts/boundary-check/lower-original-negatives-qridxngh/report.json)：
19:56:23–20:00:45 UTC，17 阶段完成，其中 12 项退出 0、四个错误结果负测退出 1、
严格合流负测退出 2。两个 False 变异及其审计导出均退出 0，随后由精确类型比较拒绝。
外层退出 2，状态 `original_lower_negatives_and_runtime_completed_admission_pending`，
不是候选准入或完整 `proof-check` PASS。

报告 SHA-256：`1b045c976d4d8de26fbb26443a1d74eb3f7bab320b7a7d2a2939da1dc9e3ad9e`。

| 检查 | 实际结果 |
| --- | --- |
| 三个候选基线审计 | 与前次完整 JSON 一致，原 raw 政策继续拒绝两处 map 定义变化 |
| 错误位域 / Rust 位移 | 分别取得 `type mismatch` / `Did not find an occurrence` |
| 错误 selector / 寄存器字段 | 均取得 `unsolved goals` |
| 两类 False 前提 | 仅指定定理类型变化，公理及定义不变，精确类型审计拒绝 |
| 严格合流 | 新工具对实际新 LLBC 按原共享借用原因拒绝 |
| 生产工厂 runtime | 32,768 个合法 ADD 编码、196,608 次非 ADD 邻域检查、32,768 次错误目标寄存器变异均通过 |

本次构建的实际运行二进制 SHA-256：
`e37a8235eeff0cdaeb6d048d1d06bd2086aac893490b9197a8eb43dd1d39bfa0`。
源码、冻结锁、候选与支持编译缓存、工具组件及正式生成物的收尾检查通过。

完成后另行以 `-O` 只读复核全部 17 阶段的精确命令、cwd、LEAN_PATH、退出码及日志哈希，
六份变异内容、三个基线审计、两份 False 类型差异和原 raw 政策拒绝均核对通过。
再次执行本次 runtime 二进制，取得相同计数；重新核对 70,681 项支持编译文件、候选
缓存、完整私有 Lean 安装清单、工具组件、源码快照与正式生成物，独立复核退出 0。
四份正式政策及原 week5 / week6 / overview 计划的哈希保持不变。

## 保留的首次失败

[首次报告](../../artifacts/boundary-check/lower-original-negatives-ixu9xr9o/report.json)
完成三个基线导出后，在位域变异定位检查失败，尚未执行负测。
报告 SHA-256：`a2f8cb40d01c17a084f6264410a4c8db8b5ac15bb5c3bf1da52ded0c629b8f7c`。
原脚本保存在该目录的 `probe-source.py`，SHA-256：
`222e17cd199d2395e8194cdc47cfef410d802cbad6e7040680bc73ff83a61415`。

原因是短位域片段在源文件中出现多次，而新入口要求定位唯一。修正只扩展匹配上下文
到 `rd` 定理头，仍要求唯一匹配；回归测试确认所得完整变异文本与原门禁的首次替换
完全相同。没有改变原证明、负测目标或正式政策。11 项本入口测试和相关 46 项测试，
普通 Python 与 `-O` 均通过。

## 后续边界

即使本项完成，候选准入审查、公开 decoder 候选根的全依赖源码重建和完整负测、
新工具其余资格回归，以及 Week6 七类发布缺项仍待关闭。现有条件性执行、具体初态、
取指/物理内存及 unsupported 边界不因本项扩大。
