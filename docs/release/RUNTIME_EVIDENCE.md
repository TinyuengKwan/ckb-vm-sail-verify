# 本地 runtime / mutation / 搬迁重放证据

这是 Week6 发布聚合所需的一个组件，不是 `audit-release` 总验收，也不关闭 Week6。

最新执行见[Week6 逐族案例门槛修正](WEEK6_RUNTIME_FLOOR.md)：33 项（13/10/10）、398 步、
194 次适用 mutation 及 33 次复制重放通过。旧 BEQ 9 项不满足逐族最低数，当前门禁拒绝它。
此前精确审计修正见[本地证据更新](AUDIT_FIX_EVIDENCE_REFRESH.md)；
下述早期报告保留为历史记录，不再作为新政策证据。

## 可执行入口

已准备好项目要求的 Sail emulator、合并配置和 Rust 依赖后，在仓库根运行：

```bash
python3 scripts/probes/probe_release_runtime.py
python3 -m unittest discover -s scripts/tests -p test_release_runtime_evidence.py
python3 -O -m unittest discover -s scripts/tests -p test_release_runtime_evidence.py
```

默认建立唯一的 `artifacts/boundary-check/release-runtime-*` 目录；也可用 `--out`
指定不存在的新目录。已存在目录会被拒绝，旧报告不覆盖。

流程选用现有 CMake 配置中的 Sail 编译器，并执行严格的 `verify_environment.sh`。
随后在空的 Cargo target 中 `cargo build --locked`，执行全 corpus 与 mutation 矩阵，
复制所有案例及 mutation JSON，再从复制产物逐案重新执行双端。每个子命令保存 argv、
开始/结束时间、退出码和 stdout/stderr 哈希；失败、超时或中断不能产出成功报告。

`scripts/release_runtime_evidence.py` 不只信任 `passed` 或计数：它重新读取实际 trace，
检查 schema 3、独立观测的环境身份、输入编码、初态、focus 指令类别及每族至少 10 项、PC 连续性、
规范化寄存器写、完整事件与严格终止；重新计算六种 mutation 的首差异与位置，检查
完整的案例 × mutation 矩阵、跳过理由、覆盖计数及例子。复制后还要求哈希不变；
重放后的输入、双端 trace 和原始 Sail packet 字节必须与原产物一致。

输入源码、配置、检查脚本、政策和所用 Sail 文件在运行前后核对；CKB checkout
按已采纳的 upstream + runtime-container patch 基线校验。二进制单独记录哈希。

## 2026-09-11 实跑

[结构化报告](../../artifacts/boundary-check/release-runtime-rsk80e9n/report.json)：

- 时间：10:40:40–10:41:17 UTC，35 个阶段均退出 0。
- 报告 SHA-256：`a8cfa59d758ab5c4c4237410f1b0617fe1cc0f422ab368289a9af35f6bbbba53`。
- ADD / ADDI / BEQ 案例分别为 13 / 10 / 9，合计 32，全部严格比较通过。
- mutation 矩阵 192 项：188 项应用且定位正确；4 项没有寄存器写入而跳过。
  PC、trap、长度、终止各 32 项；寄存器索引和值各 30 项。跳过不计为通过。
- `original/` 和 `relocated/` 各 33 个 JSON 文件逐字节相同；32 个案例全部重新执行。
- 本轮新构建 CLI SHA-256：
  `5b747eff5ee705a8382d833443a93e86427f77c3df8b6dac7d8cd26fd27f6275`。
- 21 项合成检查器测试在普通 Python 与 `-O` 模式均通过；它们不是 runtime 证据。

完成后另行重读全部 35 个阶段的退出码和日志哈希、两组文件、全部重放产物，
重新观测环境并复核源码哈希；结果一致。主 Lean 政策及其冻结源码保持不变，政策 SHA-256
仍为 `c8315684cf73d118703f98982e79303943d8c52d49e72d99117de25301b3a1af`。

先前 `release-runtime-JrtmQKkv/runtime.json` 的 trace 和矩阵一致，但环境中的
`sail_compiler` 是 PATH 上的 release 版而不是项目要求的固定源码版，因此没有作为
这次环境验收的证据；原报告保留。新入口使用 CMake 选择的源码版并实际检查完整版本串。
更早的常用 `artifacts/corpus` 中 schema 2 产物也不作为本轮来源身份验收证据。

## 保证边界与下一项

- 本次只从零重建 Rust CLI；复用并哈希核对现有 Sail emulator，未重新生成或编译它。
  观测到的编译器版本不是现有 emulator 的构建来源证明。
- 使用已有依赖缓存和本机工具；不是完整安装 clean-room，也不是独立第三方复现。
- 复制目录是本地字节一致性和可重放性检查，不是 CI 上传/下载或 release 下载证据。
- 检查器对原始 RVFI-DII packet 检查格式和保存/重放一致性，不独立重新解码协议，
  也不证明 adapter、编译器或全部 ISA 语义。它没有新增 Lean 定理覆盖。
- 证据用于固定的注入初态与本次有限 corpus，不扩展为任意初态或整个 VM 的等价性。
- 2026-09-12 已新增 [readiness v1 聚合](AUDIT_RELEASE.md)，复核已有三类报告但不放行发布；还需结合完整
  clean-room、失败分类/最小化清单、CI 下载、版本发布和第三方记录逐项验收。
