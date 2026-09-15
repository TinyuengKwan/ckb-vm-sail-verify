# 可搬迁的公开 Rust 提取 harness

2026-09-11。这里固定现有公开入口的 Cargo 锁文件；Rust 根仍使用
[OuterRoot.rs](../full-mir/OuterRoot.rs)，不复制第二份 decoder 实现。
[decoder_harness.py](../../../../../scripts/decoder_harness.py) 将两者放入一个新目录，
生成仅指向指定、已核验 CKB checkout 的相对 Cargo 依赖路径。
它不复用旧 Cargo target、不覆盖既有目录，也不修改生产源码。

- Rust 根 SHA-256：`ce89211f2d139f2a7a3f4f5d69e6fe362ad2fd0b8bcf19e8e185cb589a15972c`。
- Cargo.lock SHA-256：`023588c4dac3bf3489f629bfd7eef67fa202a76918c737ad8ab1816d9ddfc2c3`。
- 包名、edition、根函数、依赖锁和提取配置未变；变化的是 Cargo 依赖的所在地。

## 实测搬迁

```bash
python3 scripts/probes/probe_decoder_relocation.py
python3 scripts/tests/test_decoder_harness.py
python3 scripts/tests/test_decoder_model_identity.py
```

探针在全新目录 clone 项目及 CKB 源码，固定项目 commit、CKB upstream commit 和既有补丁，
核验整个生产源码身份，然后重新运行 Charon/Aeneas。Cargo target 初始不存在。
两个 clone 未使用 Git alternates；没有把原 checkout 的可变文件直接作为新 Rust 依赖。
该探针只初始化提取所需的 CKB 子模块，不声称递归安装了整个 Week6 环境。

首次 [decoder-relocation-snvg5_om](../../../../../artifacts/boundary-check/decoder-relocation-snvg5_om/report.json)
被原始整文件哈希拒绝；失败记录保持原样。
复核 7,779 行输出发现，373 处差异全部是生成文档注释中的绝对 checkout 路径。
因此增加[来源注释比对器](../../../../../scripts/decoder_model_identity.py)：
只将完整 `Source:` 行的已知 checkout 前缀映射到原批准哈希使用的命名空间。
路径后缀、行列位置、注释定界符、所有声明和证明代码仍逐字节进入原哈希。
原路径仅是哈希命名空间，不是运行时读取旧 checkout 的地址；输出文件本身从不被改写。

第二次 [decoder-relocation-ap1v51hl](../../../../../artifacts/boundary-check/decoder-relocation-ap1v51hl/report.json)
于 08:24:06–08:25:11 UTC 通过七个阶段。报告 SHA-256：
`21b90c8565c3f9be6fccc722c350802cbeeb040c083860f6aed2f7dda97c56a5`。
新文件原始 SHA-256 为 `e0c3878e4d8f4532a9b8c0fda5afa7fe0c8f18a55f1bc0df84843e5a8f03909a`；
仅映射 373 处注释前缀后，与原批准模型 SHA-256
`b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061` 相同。
报告、七个日志及 harness/model 身份在进程结束后又被独立重读核验。

10 项 harness 测试和 9 项身份测试均在普通 Python 与 `-O` 下通过。
负测包含依赖重定向、锁文件/源码改变、错误函数体、源文件名/行列改变、额外公理、
伪装成来源字符串的可执行文本，以及已存在输出目录保护。

## 搬迁验证时的边界与后续正式接入

本轮没有改变主/公开政策、定理快照或实际生产源码基线。
这是搬迁可行性证据，不是一次新的 Lean kernel 检查、完整 clean-room 或 release 通过。
搬迁验证时原主门禁仍使用原 harness 位置及原始文件哈希。
随后调用层/来源政策已完成迁移审计，完整证明门禁及独立证据复核已通过，见
[正式迁移记录](../../../../../docs/release/PUBLIC_INPUT_MIGRATION.md)。

其余实际安装依赖已核查：

- 公开候选工具约 184 MiB；Charon driver 还依赖固定 nightly Rust 的动态库，
  Aeneas 依赖系统 GMP/zstd 等库，不能把可执行文件的存在等同于可运行。
- full-MIR sysroot 有 46 个库文件，目前全为外链；物化内容合计 279,554,691 字节。
  安装包必须包含受哈希约束的真实文件，不能打包指向本机旧 build 目录的链接。
- 两个工具源码 checkout 使用本机 Git alternates；安装时需要独立的 Git 对象或源码包，
  仍应核验固定 commit、补丁和二进制身份。
- 七类政策资格证据及三个下层生成的 Lean **源文件**也需分发；它们不是旧 `.olean` 缓存，
  不能拿历史报告或编译结果代替接收方的新运行。

上述依赖已在新本地输入包中物化、安装并实际用于公开主模型和迭代器重提取，原目录不变。
最新九阶段探针同时验证两份提取根，分别仅映射 373 / 20 处生成来源注释；
搬迁验证没有修改原始模型、定理和当时的正式政策；后续政策迁移单独记录。
安装命令、成功与失败证据见[输入包记录](../../../../../docs/release/DECODER_INPUTS.md)。
正式门禁切换及重跑已完成；完整工具环境和发布仍未完成，见
[Week6 清单](../../../../../docs/WEEK6_STATUS.md)。
