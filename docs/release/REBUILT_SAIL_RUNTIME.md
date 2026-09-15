# 新模拟器的实际双端差分、mutation 与重放

承接[新 Sail 完整 C++ 冷构建](REBUILT_SAIL_CPP.md)。此项把真实新模拟器连接到新构建的
Rust CLI，运行既有完整 corpus/mutation 和逐项复制重放。它不是一般执行等价证明、
正式工具准入或完整 clean-room/release 验收。

```sh
python3 scripts/probes/probe_rebuilt_sail_runtime.py \
  --build-report artifacts/boundary-check/rebuilt-sail-cpp-p7x1idhj/report.json \
  --build-report-sha256 197438f259cba13b82c4c9cf9a636872050f428b5b8f6663021b561a40d65542
```

## 实际结果

[完成报告](../../artifacts/boundary-check/rebuilt-sail-runtime-6t_ouoxe/report.json)
SHA-256：`5f24f40a2b034c40193a917e052171bf70e5732eb6e2a223af55a5e3a80465ed`。
2026-09-12 23:02:52–23:03:58 UTC，38 阶段全部退出 0；外层退出 2，状态
`rebuilt_sail_runtime_mutations_replays_checked_admission_pending`。
入口源码 SHA-256：`d99b78be1da12c5f2ced845125d62ab95c2b095649499926d372e28f5a346cd3`。

| 检查 | 实测 |
| --- | --- |
| 正常双端差分 | 32 个案例全部一致：ADD 13、ADDI 10、BEQ 9 |
| mutation 矩阵 | 192 项中 188 项适用，全部被检测且首差异定位正确；4 项不可适用，未计为通过 |
| 六个 mutation 字段类别 | PC、寄存器索引、寄存器值、trap、trace 长度及终止状态均覆盖 |
| 复制与实际重放 | 33 份 artifact（32 案例加矩阵）逐字复制；32 个案例逐个重新运行双方引擎 |
| 原始观察 | 核对完整归一化 trace、原始 RVFI-DII packet 格式与数量、终止状态、输入及环境 |

188 项的分布：PC、trap、trace 长度、终止状态各 32 项，寄存器索引及值各 30 项。
不能把 4 项不可适用报告成已检测，也不将此有限 corpus 扩大为全部 ADD 编码/状态或 ISA。

## 实际执行身份

- 模拟器为前一项新构建结果，SHA-256
  `d6a8dd6820ffbe5754973a5df9d10e76d5f318ffa3c50f398a557a0b7497b8bb`；没有回退到旧模拟器。
- 新物化的配置 SHA-256
  `41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024`。
- 私有 Rust 1.97.1 构建的新 CLI SHA-256
  `701f322ce3c8359e25c6572fd69295d01b859ae086b8060ae5dd14e2a057c11d`。
- 复用固定联合提取源码快照
  `99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12`
  的独立目录，不复制旧 Cargo home/target 或 runtime 结果。CKB 基线仍为
  `ckb-vm-1ffba3977da9-runtime-container-v1`；本项未增加 CKB 补丁。
- 使用普通 stable Rust 标准库运行 CLI；不是 Charon 的 full-MIR 提取或新 Lean kernel 检查。
  运行配置仍为 VERSION2、IMC+B、MOP off，观察边界不扩展到 ASM/JIT、物理内存或全 VM。

入口核验已完成 C++ 报告及全部原始阶段日志/输入，版本来自实际选用的执行文件。
前后重算 Rust 全安装、Sail/OPAM 安装与编译器源码、固定源快照、编译产物、脚本及证据。

独立复核已重新构造并核对全部 38 个命令/cwd/退出码及显式环境，重读两个 corpus 目录、
32 个 replay 报告及 artifact，并逐项调用证据检查器重算 trace/mutation/重放比较。
它还核验 Cargo 的两个内部硬链接、安装后单链接文件、完整 Rust/Sail/OPAM 安装和
Sail 编译器源码，退出 0；这次复核没有再次运行引擎，实际执行属于前述 38 阶段。

9 项入口测试在普通 Python 与 `-O` 下通过，既有 runtime 证据检查器另有 21 项测试。
首轮因 Cargo 内部硬链接被误判而停止的报告及原脚本，见[冷构建记录中的失败说明](REBUILT_SAIL_CPP.md)。
失败记录未改写；成功轮采用全新 Cargo home/target。

## 准入与发布边界

正式四份证明政策和原批准的 `proof-check` 报告保持不变。本项尚未成为原
`audit-release` 的 runtime slot，也没有把旧环境报告替换为候选报告。
后续需明确采用的新工具身份、物化标准库、提取配置、资格报告和两处 `Option.map`
模型身份变化，再构建/验收新输入包并运行对应正式门禁。
Charon UI 金样/交叉目标缺口及 visitors 版本约束差异仍需明确处置。

本机复制重放不是 CI 下载或 release 下载；独立第三方、发布包、维护者演示、最终工作树
与公开结论审计等七类发布条款仍未关闭。不存在 Week6 完成或整体 CKB-VM 已形式化验证的声明。
