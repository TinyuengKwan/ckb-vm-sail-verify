# 实际生成执行与节点差异记录

2026-09-13。新增 [record_generation.py](../../scripts/record_generation.py)，在现有正式
生成器之外记录完整执行顺序、来源和前后输出。它不是发布验收器，不替代原
`proof-check`，也不更改原政策或任何已有报告的来源身份。

## 固定执行范围

入口没有任意命令、跳过阶段、替代 checkout 或自动刷新政策选项。正式工具解析与
来源核验成功后，依次执行：

1. `make sail-config`：现有 Sail 构建与合并配置入口。
2. `python3 scripts/generate_rebuilt_rust.py`：当前准入工具的真实生产提取与事务安装。
3. `bash scripts/generate_proof_model.sh lean`：Sail Lean 重新生成与事务安装。
4. `bash scripts/generate_proof_model.sh rocq`：Sail Rocq 重新生成与事务安装。

不使用旧 `generate_rust_model.sh` 代替新正式入口。现有事务保留旧目录与失败输出；
本入口不删除这些备份。重新生成会改变正式生成目录，不能只当作只读检查运行。

源码身份采用完整 HEAD 加工作树字节清单，另核验正式政策要求的源码、CKB 补丁、
工具与支持库。正式安装闭包在执行前后重新校验。环境只记录摘要，不发布可能含
凭据的完整环境变量。系统工具和宿主依赖并未因此成为已验证的全环境闭包。

## 输出范围与来源连接

前后采集保留 [清单组件](GENERATED_OUTPUT_INVENTORY.md) 的九个必需根，额外覆盖
`artifacts/rebuilt-main-runtime`。两次均记录完整目录节点，包括缓存、备份和链接文字。

Rust 生产器自行创建随机 `artifacts/boundary-check/rebuilt-production-rust-*` 目录。
记录器在执行前保存该父目录的全部直接子项名称，执行后记录新增项。只有符合生产器
固定前缀、此前不存在的根可以加入扩展清单，并显式记入执行前的 absent 节点；
原始执行前清单不修改。任何原有子项消失或非该前缀新增项都会拒绝，不静默过滤。
成功路径要求恰有一个新提取根，已安装 Rust provenance 必须引用该根下的真实报告。
旧有证据目录不会被伪造为执行前不存在。

Sail 两个阶段必须各自提供唯一事务标记，标记与实际事务 JSON 一致；检查源目录与
安装目录、全新备份目录、原始/安装文件清单，以及 Rocq 与主模型的配置身份。
因此零退出不能单独冒充实际生成来源。仍须审查全部差异，尤其新提取目录中的缓存、
依赖和复制的源码，不能将所有节点都称为生成器生成的模型。

目录观察非原子快照，也没有操作系统沙箱。记录器的非阻塞锁仅排斥同入口并发执行，
不能阻止编辑器或其他构建入口写入。生成器自身的事务锁仍由原入口负责。
这些声明根不覆盖整个工作区、临时目录、工具安装或所有宿主写入。

## 日志与失败语义

每个子进程保存不可覆盖的 started、process、finished 记录及原始 stdout/stderr 合并
日志，包含精确 argv、cwd、时间、PID、执行时限和终态。超时终止该进程组，普通
`exit_code` 保持 null，另记终止返回码，不把超时伪装成程序正常退出。

生成命令普通失败时停止后续命令，仍尝试采集执行后清单、源码和差异；若采集或
范围核验本身失败，则保留此前已完成的记录并返回失败。强制终止解释器/宿主崩溃
可能只留下阶段记录，不能用缺少最终报告来认定成功。

退出 0 的状态为 `generation_sequence_recorded_pending_review`，只表示该序列和
来源连接已记录。`generation_commands_completed` 可为 true；但生成物语义审查、
kernel、新环境、`worktree_audit`、release 与 Week6 的保证标志仍为 false。
全量 `regeneration_execution_proven` 也保持 false：记录声明范围不是整个交付的生成闭包。

## 使用及验收位置

```bash
mkdir -p artifacts/generation-runs
python3 -B -O scripts/record_generation.py \
  --out artifacts/generation-runs/UNUSED-RUN-NAME
```

输出必须是指定父目录下不存在的新目录。每个生成命令与每次清单采集默认各限时
3,600 秒，可分别用 `--command-timeout` 和 `--inventory-timeout` 显式设置正数。
本机全量采集曾耗时约 25–30 分钟，整个流程不可按短命令估算。

[29 项回归测试](../../scripts/tests/test_record_generation.py)覆盖固定命令顺序、互斥锁、
路径/链接拒绝、真实小型子进程日志与超时、动态根缺失证据、Sail 事务新鲜性和文件
清单，以及编排失败后保留差异、旧 Rust 来源拒绝和源码漂移。测试夹具不会记为正式
Rust/Sail 重生成；实跑结果只以新运行目录的最终报告和独立复核为准。

18:12:28–18:12:33 UTC 的[测试记录](../../artifacts/boundary-check/generation-recorder-tests-LFfsqTUE/report.json)
完成记录器 29 项和清单组件 27 项测试的普通 / `-O` 双模式运行，共 112 次测试完成。
报告绑定当时的代码与文档哈希；本段文字是测试之后的文档增量，不回填旧快照。

## 本轮真实执行与记录复核

18:13:15–19:27:25 UTC 的[实际执行报告](../../artifacts/generation-runs/local-20260913-v1/report.json)
退出 0，状态为 `generation_sequence_recorded_pending_review`。报告 SHA-256 为
`82088737733d1549aa923cbcaaf318439ea9dac52ea0aceedaf156afffbeefb3`。
四个固定生成命令与两次全量采集均退出 0，完整源码前后快照一致，执行器的最终正式
来源与工具核验通过；不是新环境或 kernel 验收。

生成前清单有 290,844 个节点、278,550 个普通文件、21,271,737,866 字节。
本次新增 Rust 提取根为 `artifacts/boundary-check/rebuilt-production-rust-ao1_7ji6`，
其执行前不存在由父目录清单证明；扩展的前清单增加该根的一个 absent 节点，原前清单不改。
生成后清单有 298,835 个节点、285,356 个普通文件、21,943,943,655 字节、226 个链接。
`build` 与 `artifacts/rebuilt-main-runtime` 均不存在。

[完整差异](../../artifacts/generation-runs/local-20260913-v1/delta.json)共 10,021 项：

| 根 | 新增 | 删除 | 原路径修改 |
| --- | ---: | ---: | ---: |
| 本次 Rust 提取目录 | 7,628 | 0 | 0 |
| `deps/sail-riscv/build` | 176 | 0 | 4 |
| `proof/lean/generated` | 1,192 | 1,012 | 1 |
| `proof/rocq/generated` | 7 | 0 | 0 |
| `target` | 0 | 0 | 1 |

其他声明根无差异。这是实际前后非原子观察的差异，不是每项语义审批结果。
19:30:21–19:30:51 UTC 的[记录复核](../../artifacts/boundary-check/generation-record-acceptance-y1HHHbjA/report.json)
退出 0：核验全部 35 个引用、6 个阶段的精确命令/时间/终态/日志，重算完整差异，
核对当前源码和模型身份；全部 1,012 个删除节点均在事务备份中找到完全一致的节点。
该复核消费保存的清单，不再次扫描 21 GB 输出树，也不再独立重哈希工具安装闭包。

6 项原路径修改包括四份 CMake `compiler_depend.make`、Rust `SOURCE_BASELINE.json`
及生产 LLBC。备份与新 LLBC 均按差异哈希核验；JSON 中仅 `translated.options.dest_file`
和 `translated.short_names` 不同：前者改为本次提取输出路径，后者为同一批 611 个唯一
键的完整键值记录的排列，其他 JSON 值相同。未改写或规范化原文件以匹配旧哈希。
这项数据比较不证明一般提取器正确性；后续已完成[全部差异的逐路径说明](GENERATED_DELTA_REVIEW.md)，
包括四组 CMake 依赖文件、锁定包与源码副本的核对。它不因目录名称而自动批准缓存或
证据进入交付范围，最终候选审批仍待完成。

Rocq 生成日志保留了后端参数重排限制提示；生成退出 0 不证明生成模型可由 Rocq
编译，原 NO-GO 不因此改为 GO。Rust/Lean 模型身份核验也不替代本轮 kernel 执行。

本轮改变了 LLBC 和提取 provenance。原 v10 Lean/Rocq 报告及归档保持历史身份，不能
将它们按原生成身份直接当作当前重新生成状态的验收；需要明确后续生成/验收链的连接。
本节及 Week6 状态更新发生在实跑和记录复核之后，是新文档增量，不回填旧源码快照。

下一步将真实执行报告与逐路径差异说明接入 `worktree_audit`，并连接最终生成身份与
kernel / Rocq spike 验收。由于原 `proof-check` 会再次生成，后续记录必须覆盖该次最终
生成及其验收，不能沿用本轮 LLBC/provenance 冒充最终状态。
候选范围审批、clean-room、CI 下载、第三方和发布义务仍独立。
