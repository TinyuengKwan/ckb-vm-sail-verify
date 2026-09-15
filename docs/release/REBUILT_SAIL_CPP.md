# 新 Sail 的完整 C++ 模拟器冷构建

承接[C++ 受限标记对应](SAIL_CPP_CORRESPONDENCE.md)。本项执行新工具的真实模型生成和
模拟器编译，配置检查不计为指令运行差分，也不自动采纳新工具。

```sh
python3 scripts/probes/probe_rebuilt_sail_cpp.py
python3 -m unittest discover -s scripts/tests -p test_rebuilt_sail_cpp.py
python3 -O -m unittest discover -s scripts/tests -p test_rebuilt_sail_cpp.py
```

## 检查范围

- 固定已独立重建的 Sail 安装报告，重新核验完整 Sail 安装、OPAM 支持闭包及编译器源码。
- 独立 clone 固定 `sail-riscv` commit `8f91355eee63a85738723603e23d32eecdd763dc`；
  无 Git 对象硬链接/alternates，不复制旧模型、构建目录或 `z3_problems` 缓存。
- 使用固定上游 CMake 的 `generated_sail_riscv_model` 和 `sail_riscv_sim` 完整目标。
  配置为 `RelWithDebInfo`、`DOWNLOAD_GMP=TRUE`，不裁剪成只支持 ADD 的模型。
- 新生成实现与头文件在编译前对照留存候选，执行同一受限对应检查；schema 必须字节一致。
  保存全部映射，但不改写生成物或豁免原候选的原始字节比较失败。
- 完整编译后执行模拟器版本、默认配置输出、原递归合并规则及 ISA 配置检查。
  合并配置必须与原政策绑定的完整配置逐字节一致。
- 编译前后生成物及执行文件、原始源码、正式政策、实际加载的项目辅助脚本和所选宿主工具
  哈希必须无漂移。保存 CMake cache、编译命令清单和链接命令文件的哈希。

宿主 C/C++ 编译器、链接器、CMake、make、Z3 等复用且记录执行文件身份，**不是完整
宿主工具或动态库闭包的源码重建**。本机独立目录也不是 OS 沙箱或独立第三方。
配置 smoke 没有执行 runtime corpus、mutation 或 Lean kernel。

## 实际完成记录

2026-09-12 22:36:28–22:58:49 UTC，实际运行目录为
[`rebuilt-sail-cpp-p7x1idhj`](../../artifacts/boundary-check/rebuilt-sail-cpp-p7x1idhj/report.json)。
报告 SHA-256：`197438f259cba13b82c4c9cf9a636872050f428b5b8f6663021b561a40d65542`。
10 阶段全部退出 0；外层退出 2，状态
`rebuilt_sail_cpp_compiled_config_checked_admission_pending`。
完整生成已于 22:53:08 UTC 退出 0；受限对应检查随后通过，22:54:12 UTC 进入 C++ 编译。
完整模拟器编译、版本和配置检查随后均已完成。7 项入口测试在普通 Python 和 `-O`
下通过，不代替这些实际构建阶段。

本次生成的实现 SHA-256 为
`267c5ed3d15717b25ac27c87c28317a3e5f151e3c57934da44d0faf4bab81957`，
头文件为 `1fe5237a7d7d57ef87670d973cca7fe32f85acc90a4703d72ea7bb3b92cab19b`。
与前次候选相比原始字节仍不同，不能称为字节可复现；3,675 个方法区域和全部间隙的
对应检查通过，642 个字段对应类型一致，其中 166 个名称改变。Schema 字节一致，
SHA-256 为 `3d0ddcbfe0aabc1dac7c3dbcfbe96897b1b5fcb88450dc5ed177300733e9fc78`。
未改写生成物，也未据此证明 fresh-name 编号差异的根因或一般执行等价。

新执行文件 SHA-256：`d6a8dd6820ffbe5754973a5df9d10e76d5f318ffa3c50f398a557a0b7497b8bb`，
版本输出 `0.13.1`；新物化配置 SHA-256
`41a0facde4f83210f6c0857c67ba38edc5221f0926d75ab4213a33465d85e024`，
与原绑定配置相同，ISA 输出 `rv64imcb_zca_zba_zbb_zbc_zbs`。
完整映射文件 SHA-256：`d7402c5dd3be1df4773726a71999443ca81521731b64cc11453068f5e0ea41ea`。
入口源码 SHA-256：`0d5a3bbd2ead8672e17bb7cb357060a9b0fa33ef5e8be3493954b8f2852e403f`。

独立只读复核已重算报告的输入、日志、生成物、源码、执行文件及编译元数据，逐一
重建并比较全部 10 个命令/cwd。`compile_commands.json` 中生成模型只有一个对应
翻译单元，使用记录的 C++ 编译器、`-O2` 和 `-UNDEBUG`；实际对象文件 SHA-256
`13dd402dc95edf8256145dc41baa38b934899235db2a407b496aa718e31b113d`。
该复核没有重编译或再次读取完整工具安装闭包，完整安装前后核验属于生产入口证据。

成功也返回 2，不自动采纳；失败返回 1 并保留阶段和日志。下一步是新模拟器的实际
双端差分、mutation 和重放，再处理正式工具身份与资格准入。Week6 七类发布缺口仍未关闭。

## 后续 runtime 入口（已完成）

`scripts/probes/probe_rebuilt_sail_runtime.py` 已实现，必须显式传入 `--build-report`
和经核验的 `--build-report-sha256`。它拒绝运行中、失败、未编译、缺少配置检查或
阶段/日志不全的构建报告，也拒绝将执行文件路径指向其他旧缓存。

该入口复用固定联合提取源码快照
`99127abf38f30cdf9e6feef11fcdd619bb8eaf328c4e3cabf991d57782d2ca12` 的原目录及私有安装的 Rust
1.97.1，但建立全新的 Cargo home / target。新 CLI 用绑定的新模拟器和新合并配置执行
完整 corpus / mutation，再将全部输入 artifact 逐字复制到新目录逐项实际重放。
每项 trace、mutation 定位及重放由既有独立检查逻辑重算，而非只信汇总的 PASS。
前后重核验源快照、Rust 全安装、新 Sail 安装和 C++ 构建输入。

```sh
python3 scripts/probes/probe_rebuilt_sail_runtime.py \
  --build-report artifacts/boundary-check/rebuilt-sail-cpp-p7x1idhj/report.json \
  --build-report-sha256 197438f259cba13b82c4c9cf9a636872050f428b5b8f6663021b561a40d65542
```

9 项入口测试已通过。完成运行目录为
[`rebuilt-sail-runtime-6t_ouoxe`](../../artifacts/boundary-check/rebuilt-sail-runtime-6t_ouoxe/report.json)，
38 阶段、32 个案例、188 项适用 mutation 和全部 32 项实际重放均通过，详见
[执行身份与独立复核](REBUILT_SAIL_RUNTIME.md)。复制后的本机重放不是 CI 下载、
release 下载或第三方复现，未自动采纳新工具。

首轮 [`rebuilt-sail-runtime-2rsgxb4l`](../../artifacts/boundary-check/rebuilt-sail-runtime-2rsgxb4l/report.json)
于 23:00:17–23:00:54 UTC 失败；报告 SHA-256
`fe99d098f7fb6e426e27a8a3acc6b3f02a02f76a21e7a536791f8c7c3f27b6cf`。
四项版本检查和实际 Rust CLI 编译均退出 0，但编译后的守卫错误地要求 Cargo 输出只有
一个硬链接。实测该执行文件的两个链接都位于本轮新 target：`debug/ckb-vm-sail-diff`
及 `debug/deps/ckb_vm_sail_diff-45b262cad1a153ba`；没有进入 corpus。
当时的 `probe-source.py` 已保存，SHA-256
`af144fb8d265801fc278f61033db8e4ea2d25b6b8164ce0981015ce6d8a2bcdd`。

现入口逐个核验所有硬链接都位于本轮新 target，再复制出单链接、字节一致的独立 CLI，
记录原构建产物、全部链接及安装后哈希，不删除或修改 Cargo 输出。新增测试拒绝 target
外链接及 symlink。失败报告保留，新一轮使用新的 Cargo home/target，未重编译 Sail。
