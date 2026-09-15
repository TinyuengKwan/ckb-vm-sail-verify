# Rust / Lean 独立安装验证

2026-09-12 已在三个全新私有工具目录完成固定 Rust/Lean 的下载、安装和编译 smoke。
**只完成 Linux x86_64 的这部分工具安装，不是完整 clean-room 或新 ADD 证明。**

## 入口与固定身份

在仓库根、已有 `rustup` 和 `elan` 安装器的机器上执行：

```bash
python3 scripts/probes/probe_isolated_rust_lean.py
```

默认新建 `artifacts/boundary-check/isolated-rust-lean-*`；`--out` 仅接受新目录。
[实现](../../scripts/probes/probe_isolated_rust_lean.py) 为每次运行新建 `RUSTUP_HOME`、
`CARGO_HOME`、`ELAN_HOME`，拒绝已有或 symlink 目标，不复制旧工具链或下载缓存。
显式选择版本与组件，禁止 rustup 自更新，清除继承的工具链选择、分发地址覆盖和
编译器/导入路径覆盖；不改变用户 `HOME`、全局默认工具链或已有工具安装目标。
宿主系统、网络栈和安装器本身仍复用，并记录安装器路径及 SHA-256。

| 安装项 | 固定身份 / 范围 |
| --- | --- |
| Rust foundation | 1.97.1，commit `8bab26f4f68e0e26f0bb7960be334d5b520ea452`；minimal + clippy/rustfmt |
| Rust extraction | nightly-2026-08-18，commit `8fa1c96cfd489e4c27654c144ae871ce2c4db6c6`；minimal + llvm-tools/rust-src/rustc-dev |
| Lean / Lake | Lean 4.31.0，commit `68218e876d2a38b1985b8590fff244a83c321783`；对应 Lake 5.0.0-src+68218e8 |

[安装 pin 清单](rust-lean-install-pins.json) 记录完整版本和六个关键可执行文件哈希。
版本来自仓库配置；哈希来自此前已使用的本机安装，在本轮下载前固定。
这是与既有基线的字节对应检查，**不是独立发布者签名或供应链认证**，也没有迁移证明政策。
pin 清单 SHA-256：
`949b1c58027103cad03d721c0a9ee541bd6ad1d461528ce0ccb7fc31825d4f51`。

安装后解析实际可执行文件路径，要求位于新工具目录且非硬链接，核验版本/commit、
精确组件清单和二进制哈希。两个 Rust 版本各自编译运行
[Rust smoke](../../scripts/fixtures/tool_install_smoke.rs)；Lean 编译
[独立小定理](../../scripts/fixtures/ToolInstallSmoke.lean) 并生成 `.olean`。
这些用例只说明安装可用，不是双方 VM 对应、提取成功或 ADD kernel 重验。

## 实跑结果

2026-09-12 06:52:45–06:59:43 UTC，20 个阶段全部退出 0。
[报告及同目录日志](../../artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/report.json)
状态为 `isolated_rust_lean_installation_and_smoke_passed`。
报告 SHA-256：
`80058acabeef59e0eb424aa2028a28a7018e4acad0da8531da83db9b4bc9cbad`。

全部六个关键二进制与原基线哈希匹配。报告还枚举安装目录内的库/源文件、大小、权限及
内部 symlink，拒绝外部 symlink；不是仅检查启动程序：

- Rust 两套工具链：7,189 项；清单 SHA-256
  `e9300722a06d7670939d009feceaec951ec1e364b8b8401d44e4d12763b6a22a`。
- Lean 工具链：14,632 项；清单 SHA-256
  `5bacb7efb8a49f13344b136b88a75b595013216ad85760d2645fcb912d9430e7`。

在普通安装执行之外，用 `python3 -O` 独立重读全部阶段日志哈希、来源/pin、
实际工具路径与字节、安装文件清单和 smoke 产物，复核通过。
新 nightly 的标准库 `Cargo.lock` 也匹配 full-MIR 重建脚本要求的
`34656569ab979fdf259efffc99d2b68e253e73e0e6fba6762dc51e83df71aa76`；
**尚未因此重建 full-MIR sysroot**。
这些清单绑定本次实际安装内容，不是预先批准的全部库哈希或对宿主系统依赖的完整封闭证明。

[15 项安装检查回归测试](../../scripts/tests/test_isolated_rust_lean.py) 及已有 17 项
源码快照测试均在普通 Python 和 `-O` 下通过，共 32 项。
原全局 Rust/Lean 工具链列表复查未变化；主/公开 Lean 政策和冻结证明源码保持不变。

## 使用本次安装及剩余工作

本次目录在报告的 `private_homes` 中，后续命令须显式使用这些路径，不要回退到旧环境。
例如，从仓库根只读核对：

```bash
tool_install_dir="$PWD/artifacts/boundary-check/isolated-rust-lean-ad7o1fsn"
env RUSTUP_HOME="$tool_install_dir/rustup" CARGO_HOME="$tool_install_dir/cargo" \
  rustup run 1.97.1 rustc -vV
env ELAN_HOME="$tool_install_dir/elan" ELAN_TOOLCHAIN=leanprover/lean4:v4.31.0 \
  elan which lean
```

尚未安装 Miri 或交叉目标，不声称覆盖所有平台/Charon 自身全部测试。
Rust/Lean 是固定发布包的全新安装，不是从源码重建这些编译器。
Sail、Aeneas/Charon、Rocq/OPAM 的独立环境及 full-MIR 标准库重建仍待完成；
新构建的翻译器若不匹配现有精确政策身份，必须审查，不能自动刷新 allowlist。
之后还需用同一候选源码和完整新工具链运行 runtime、双方提取、Lean 主门禁及 Rocq spike，
再审计生成后的工作树。此前隔离基础重建和旧证明报告不能拼接成这次完整链 PASS。

readiness v3 尚不把这份局部安装报告计为 `clean_room` 或其他缺失条款通过；
Week6 的七类完整验收缺项仍保留。

后续进展：[Rocq/OPAM 的独立源码重建及既有输入 NO-GO 复验](ISOLATED_ROCQ.md)
已另行完成；不追溯扩大本页 Rust/Lean 安装报告的范围。

随后 [Sail 源码重建](ISOLATED_SAIL.md) 和使用本页 Rust 安装的
[full-MIR 标准库重建](ISOLATED_FULL_MIR.md) 也已完成；新 Sail / 新库哈希与旧政策不同，
保留待审查/提取资格核验状态，未自动采纳或拼接成完整 clean-room。
