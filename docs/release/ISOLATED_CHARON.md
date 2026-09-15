# Charon 未打补丁／公开补丁双版本独立重建

2026-09-12。入口：

```sh
python3 scripts/probes/probe_isolated_charon.py
```

本项只重建 Rust 侧 Charon 及 driver，不构建 Aeneas 或 Charon OCaml 库，
不替代完整翻译器资格测试、生产重提取、Lean kernel 或 Week6 clean-room。

## 固定输入与隔离方式

- 从批准输入包的自包含 Git bundle 独立恢复 commit
  `89ac118194b978d8cf753222c19f313521377aa0`；不共享 Git alternates 或对象硬链接。
- `base` 保持原提交无修改；`public` 仅应用原批准的 cleanup-suffix 补丁，
  SHA-256 `17f5c34ca63f66987498331d9712b8affb00e25867e4746b5b660893d3d6eebf`。
- 两侧分别使用全新 Cargo home、全新 target 和独立源码副本，不复用前一侧编译缓存。
- 使用此前独立安装的 `nightly-2026-08-18`；核验完整 Rust 安装清单及实际编译器路径。
- `cargo fetch --locked --target x86_64-unknown-linux-gnu` 后执行
  `cargo build --locked --offline --release --bins`；依照上游 Makefile 设置
  `CARGO_PROFILE_RELEASE_DEBUG=true`，禁用增量编译，四个构建 job。
- 原正式工具、输入包和政策保持不变；新二进制独立保存并与批准身份比较，绝不自动采纳。

每侧还执行版本核对及一个真实 `add_words` 提取 smoke，使用发行版标准库
`--sysroot default`，明确不是新 full-MIR sysroot 的生产提取资格。
源码/锁文件、输入、日志和生成 LLBC 均记录哈希。

## 首轮停止及修正

首轮 `isolated-charon-0k1schrd` 在两次 Git 操作成功后停止，尚未进行 Cargo 编译。
原因是通用源码清单拒绝上游提交中的三个符号链接。失败报告 SHA-256：
`8840c6918fbcba52f1fd7b89b4c980b0eede20daef90c7b4c838dc8db3af55be`。
当时的入口源码另存为该目录的 `probe-source.py`，SHA-256：
`44ad1b2dbf17779ac0ee27d9ce5ccc51e8ac9a518845a73d915a515b12ae3ff4`。

后续使用 Charon 专用清单，只允许三个精确的已提交链接文本：

| 路径 | 精确目标 |
| --- | --- |
| `rust-toolchain` | `charon/rust-toolchain` |
| `doc-ml.html` | `./_build/default/_doc/_html/charon/index.html` |
| `doc-rust.html` | `./charon/target/doc/charon/index.html` |

文档目标不被遍历，链接文本仍受 Git blob 和固定 commit 约束。其余源码继续拒绝
链接替换、额外文件或超出批准补丁的改动；未放宽通用 `source_snapshot`。
原提交的完整 1,225 项源码清单已核对。13 项回归测试普通 Python 与 `-O` 通过。

## 双版本源码重建已完成

第二次运行：[isolated-charon-oy65t8ts](../../artifacts/boundary-check/isolated-charon-oy65t8ts/report.json)。
16:59:36–17:09:29 UTC，两侧共 18 个阶段均退出 0，包括独立 release 编译、
版本检查和真实提取 smoke。外层返回 2，状态为
`independent_base_and_public_charon_built_qualification_pending`。
最终报告 SHA-256：`691c805d3d9c8b5f17e68b32774d15dcb2facc483693ace1ab5abacfdb72e3c3`。

| 新构建二进制 | SHA-256 |
| --- | --- |
| base / charon | `59363fdaa771e300f576c458c6faab0b9d9fa0ae80706e04f5eae760ed7fb523` |
| base / driver | `e10cea3b756de291fff060e7eac3d58868468fe71c1b2a85162a2ac02be14441` |
| public / charon | `260b6c239dc79c859db65af811fa43381d96775c7f564b3fb290a6015c0a1f23` |
| public / driver | `bd4cc808a6f8dfb7ed51908857323e258dc6f9611ef8e3cb4a45554475c498a1` |

四个新哈希均不同于各自批准工具。差异未被认定为仅路径／调试信息；
下一步仍需身份审查、实际生产提取与资格链。
两份 smoke LLBC 哈希也不同，仅记录实际生成，不声称 LLBC AST 等价。

已另以 `python3 -O` 独立复核全部 18 阶段日志、输入前后哈希、批准输入包、
完整 private Rust 安装与 bootstrap、两侧 1,225 项源码和 Git 独立性、精确补丁、
Cargo 目录／选项、安装二进制与实际构建输出及两份 smoke LLBC。
正式工具和政策未替换，没有新增 Lean 定理覆盖或上游全测试通过结论。
本机宿主工具被复用，无 OS 沙箱；不能与其他候选报告拼接为完整 clean-room。

后续已使用这些新二进制、新 Aeneas 和新 full-MIR 在同一源码候选中
[实际重提取主生产 / 公开 decoder / iterator](REBUILT_EXTRACTION_CHAIN.md)。
20 阶段及三份完整模型比较通过；这补充生产提取证据，但未采纳工具或完成 kernel / 资格全链。

随后[新工具的 435 项 UI 对照](REBUILT_CHARON_UI.md)也已完成：433 项实际执行的两侧退出码
相同，423 项选定输出相同、10 项不同。两侧仍各有 24 项命令失败，金样不符为 21 / 28 项；
不是全量上游测试通过，原金样和工具政策均未修改。
