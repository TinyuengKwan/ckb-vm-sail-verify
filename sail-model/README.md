# Sail Model Configuration

`ckb_vm_config.json` 是叠加到 sail-riscv 默认 RV64 配置上的 JSON override，不是独立完整配置。

当前 submodule 固定为 sail-riscv
`8f91355eee63a85738723603e23d32eecdd763dc`（`0.13.1-7-g8f91355e`）；正式门禁使用
政策固定的 Sail 源码构建 `8eb1fb6b…`，不能只按 `0.20.2` 版本号替换。旧
`27224ccb` / released Sail 0.20.2 组合的 Lean 失败只保留为历史记录，见
[semantic gaps](../docs/semantic-gaps.md)。

运行时使用：

```bash
sail_riscv_sim \
  --config sail-model/build/ckb_vm_config.json \
  --trace-rvfi \
  program.elf
```

该命令可验证参数和配置，但当前上游只有同时使用 `--rvfi-dii PORT` 并连接客户端时才输出 RVFI 包。不得把直接 ELF 模式的空 RVFI 输出作为空程序或 PASS；项目 CLI 会将其报告为错误。

证明后端需要编译期完整配置，因此先运行：

```bash
./scripts/prepare_sail_config.sh
```

脚本将：

1. 确认 sail-riscv 模拟器已经构建；
2. 取得当前版本生成的完整 RV64 默认配置；
3. 递归关闭上游默认扩展，再用 JSON deep merge 应用项目白名单 override；
4. 输出 `sail-model/build/ckb_vm_config.json`；
5. 使用模拟器 schema/配置检查验证结果。

运行时和证明生成必须使用同一份合并配置及其哈希。Lean 4 是当前 MVP 的
主证明后端；Sail Coq backend 使用同一配置生成 Rocq 兼容性 spike，不能
使用另一份 ISA 开关来制造表面等价。

当前配置白名单：RV64 I/M/Zca/Zba/Zbb/Zbc/Zbs。它表示模型构建配置，
不表示这些扩展已经全部获得差分或证明覆盖。固定的 ckb-vm 0.24.0
不再公开 A 扩展 decoder，因此 Sail 配置也明确关闭 A。

配置文件必须跟随 sail-riscv schema 更新，禁止沿用旧格式中的：

- `base.xlen: { value: 64 }`
- `extensions.V.supported`
- 不存在的 `extensions.I.supported`
