# full-MIR 标准库独立重建

2026-09-12。已用[独立安装的 Rust](ISOLATED_RUST_LEAN.md) 和空 Cargo 缓存重建
full-MIR 标准库；**新库与原批准输入不同，尚未采纳，也未用它重新证明 ADD**。

## 入口与固定输入

```sh
python3 scripts/probes/probe_isolated_full_mir.py
python3 -m unittest discover -s scripts/tests -p test_isolated_full_mir.py
python3 -O -m unittest discover -s scripts/tests -p test_isolated_full_mir.py
```

入口使用已归档的 Rust 独立安装报告，而非 PATH 中任意 nightly：

- Rust 安装报告 SHA-256：`80058acabeef59e0eb424aa2028a28a7018e4acad0da8531da83db9b4bc9cbad`。
- nightly：`nightly-2026-08-18`，commit `8fa1c96cfd489e4c27654c144ae871ce2c4db6c6`。
- rustc SHA-256：`47e8b6d2328416ac07115cd1cf2accb3cebd200a77a0362162386349bc3d1eae`。
- rust-src 标准库 lockfile：`34656569ab979fdf259efffc99d2b68e253e73e0e6fba6762dc51e83df71aa76`。
- 沿用原 [full-MIR 构建脚本](../../scripts/experiments/build_decoder_sysroot.py)，不修改它。
  `cargo +nightly-2026-08-18 build -Zbuild-std=std,panic_abort --target x86_64-unknown-linux-gnu --locked -j4`。
  `RUSTFLAGS=-Zalways-encode-mir=yes -Zmir-opt-level=0 -Zinline-mir=no`。

每次创建新的 `isolated-full-mir-*` 和空 `CARGO_HOME`，复用先前新安装目录中的
`RUSTUP_HOME`。清除 Cargo/Rust/OPAM/OCaml 环境覆盖，显式使用宿主 rustup 代理；
不复制旧 Cargo 缓存、target 或旧 full-MIR 库。原构建脚本另建全新
`decoder-sysroot-build-*`。它的 46 个 sysroot 链接必须全部落在该子构建目录内，
入口再复制为父报告目录下的实际库文件，拒绝外链、硬链接及不完整库清单。

这仍复用宿主构建工具、网络和已独立安装的 Rust，没有 OS 沙箱；
不是完整工具链从空宿主开始安装，也不是第三方执行。

## 实测结果

15:50:47–15:52:17 UTC 完成。Cargo 实际构建用时 35.53 秒，退出 0；
46 个库文件全部生成，物化 sysroot 无外链。

- [外层报告](../../artifacts/boundary-check/isolated-full-mir-r3t1nq8t/report.json)：
  `13d82971a424442ea3fc4fbd4deda0672cb1725c0cda9e32817465830a618516`。
- [实际 std 构建报告](../../artifacts/boundary-check/decoder-sysroot-build-isblnehm/report.json)：
  `9fb48be4fafaa9a657c533f628511d07362f64e73e90f1ebf3eb7577f894b968`。
- 新 sysroot：`artifacts/boundary-check/isolated-full-mir-r3t1nq8t/sysroot`。

原安装包中的 46 个文件名全部保留，没有缺少或增加文件，但 **46 个文件的哈希均不同**。
因此外层返回 2，状态 `isolated_full_mir_identity_review_required`，
不是正式解码输入验收通过。没有根据相同 nightly、选项或文件名自动放行。
目前没有证明这些差异仅由源码路径或调试信息造成。

## 独立核验

构建结束后，在 `python3 -O` 下重新计算旧/新全部库哈希、物化文件、构建脚本复制的
三个资产、外层/子构建日志与报告哈希，并重新清点 Rust 安装中的全部工具链文件。
Rust 安装、标准库 lockfile、正式输入库和两份证明政策均保持不变。

入口将基线库与输入包 manifest 对照并记录其哈希；独立复核还调用
`decoder_input_bundle.catalogue`，将它们进一步对照仓库政策和固定 sysroot 资格报告，
不只信任包自己声明的哈希。已核对 manifest SHA-256：
`a2598bdb19600e56840c856e8cc66c540e9ce44be5b6d9a692ca609f807e26d2`。
11 项新回归测试在普通 Python 与 `-O` 下通过。

## 尚未关闭

后续已用这份新 sysroot 完成[公开 decoder 与迭代器的真实重提取](FULL_MIR_REEXTRACTION.md)，
生成模型匹配原批准身份；本页原重建报告本身不因此变成模型或 kernel 报告。
完整资格/公开 kernel 门禁及正式输入基线迁移仍待完成，不得仅改输入包清单哈希使检查通过。
最终还要把新工具、同一源码候选和完整 runtime/证明流程连接起来；
Week6 的完整 clean-room 和其他发布门槛仍未关闭。
