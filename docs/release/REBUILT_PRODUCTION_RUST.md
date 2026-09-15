# 生产 Rust 重建工具的独立暂存入口

`scripts/rebuilt_production_rust.py` 用已准入 v2 包的 **base** Charon/Aeneas、
已核验 full-MIR sysroot 和私有 Rust/OPAM 安装，在全新源码副本与 Cargo/Charon
缓存中提取 `execute_production`，只向新证据目录输出，不安装到正式生成目录。

```sh
python3 scripts/rebuilt_production_rust.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_production_rust.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_production_rust.py
```

入口保留 `ckb-vm.json` 的完整字节身份与所有 root/include/opaque 选择。
其中旧 Aeneas 版本标签仍描述历史工具；新工具实际版本另由准入包中的固定证据约束，
不会为了让版本字符串匹配而修改 CKB 源码基线或放宽模型身份。

每次运行导出 HEAD＋显式工作树覆盖快照，克隆三个独立 Git 仓库并复原快照；
前后检查原目录、副本、工具来源、安装闭包和政策输入。只有输出位置及已核验的
sysroot 位置可在 LLBC **提取元数据**比较中改变；这不是 LLBC AST 等价证明。
生成 Lean 必须与固定生产模型全文件 SHA-256 相同，不做路径或语义归一化。
非零退出、超时及身份漂移均保留为失败报告。

这是一个供后续主工具链迁移使用的本地暂存入口，不是当前正式 `generate-rust`
替代项，也没有接入 `proof-check`。它不编译工具、不运行 Lean kernel，不包含
Sail/Rocq 全链，不声称 OS 沙箱、完整 clean-room、第三方复现或发布。
已准入包和私有工具安装仍需预先存在；完整独立安装编排尚未关闭。

## 2026-09-13 实测

**01:43:49–01:48:32 UTC** 实际运行退出 0，13 个阶段全部退出 0：三个仓库各自
clone/checkout、私有 rustc 路径及版本、两个基础工具版本、locked fetch、生产提取和
Lean 翻译。普通 Python 与 `-O` 下的 12 项单元测试也均通过。

- [实际报告](../../artifacts/boundary-check/rebuilt-production-rust-efnnej7p/report.json)
  SHA-256：`3c7ff79877367c3854bcf98c6c04fc3bda91c51351c53a8e2c65470a47773cee`。
- [完整源码快照](../../artifacts/boundary-check/rebuilt-production-rust-efnnej7p/source-snapshot.json)
  的内容身份：`79fbdb4c81b939e2d2f5d9182272404bae3811f2f358761765b9fa66b23f6ed4`。
  这是运行时的 HEAD＋工作树覆盖，不是新生产 commit；本节后续文档记录不在该快照内。
- 新 LLBC SHA-256：`ec7c33f34d7d02320b44ce6b7fb64975c11a2fa5b3357063e2747f551b4c6ab3`。
- 生成 Lean SHA-256：`9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e`，
  与准入包内生产模型全文件相同。

运行后另以 `python3 -O` 只读复核全部 13 个阶段/日志哈希、实际提取和翻译命令、
源码快照与三个独立 Git 仓库、准入包/来源清单、基础工具二进制，以及新 LLBC 元数据
和 Lean 完整文件；均通过。运行器自身在结束前重新核验私有 Rust/OPAM 的完整安装闭包。

报告状态明确为 `production_rust_staged_identity_verified_main_adoption_pending`。
在暂存结束时，既有完整门禁是另一项仍在运行的检查；其后已[完整验收通过](REBUILT_GATE_ACCEPTANCE.md)，
但本记录没有将暂存输出接入正式门禁或发布聚合。
下一步是审查主工具身份与生成入口的精确迁移方案，再在新副本中
验证完整链，不能仅凭这个相同文件哈希宣布 Week6 clean-room 已完成。

## 主工具身份接入预检（尚未采纳）

随后于 **01:57:28–01:59:13 UTC** 执行
[`probe_main_rebuilt_preflight.py`](../../scripts/probes/probe_main_rebuilt_preflight.py)，
退出 0；[报告](../../artifacts/boundary-check/main-rebuilt-preflight-9y5je62i/report.json)
SHA-256 为 `f0e84486c17b5384f8e4f89f30291ab5b919ad40dbbd072d5b056ee23bd54fed`。

实际调用原主 `source_evidence` 检查器：旧政策按预期拒绝新基础 Aeneas、Charon、driver
与新 Sail 四份二进制；只在内存中替换这四项哈希及 Aeneas 的一个版本标签后，完整来源
检查通过。新基础支持库的完整 Lean 源码身份仍为原政策的 `b82fe07c…`，原生产源码基线、
手写证明、提取选择、合同/公理与生成模型未变。包内工具来源、私有 Rust/OPAM 闭包以及
Sail 安装/来源在预检前后均核验，原政策文件始终保持 `ca6e062b…`。

内存候选政策的规范 JSON 身份为
`289d44199ba12b1bbb26c0399befeebf2435886bc5a3beece571d0cf3c8fcd8f`；
它**没有被写入或批准为正式政策**。结束后独立重读报告，核对来源、支持库、候选精确
差异、输入哈希及未采纳/未执行 kernel 标志。此项仅说明主来源审计的身份接入可行。

接入面复核同时确认：

- 旧 `generate_rust_model.sh` 与 `ckb-vm.json` 均由源码基线绑定，不能直接修改后仍
  宣称基线未变。新生成入口及其来源证明需要单独明确审查和绑定。
- `tools_and_environment` 仍按旧 `AENEAS_HOME` 布局寻找二进制和支持库；两者在
  新准入安装中分开存放，必须显式核验和连接。
- 现主入口按 CMake cache 选择 Sail，按环境 PATH 选择 Lake；新 Sail 安装/插件和
  私有 Lean 安装需要显式接入，不能以相同版本号代替安装身份核验。
- 本预检没有运行新工具的完整 `proof-check`，也没有关闭 Sail/Rocq 重生成、
  最终 clean-room、CI 下载、第三方或发布义务。
