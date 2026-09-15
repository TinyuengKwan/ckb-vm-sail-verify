# 生成物节点清单与差异计算

2026-09-13。新增 [清单入口](../../scripts/generated_output_inventory.py)及
[27 项测试](../../scripts/tests/test_generated_output_inventory.py)。它为后续生成物审计提供
完整目录节点记录和差异计算，**不证明重新生成已执行，也不关闭 `worktree_audit`**。
新增[实际生成记录入口](GENERATION_EXECUTION_RECORD.md)调用这些前后清单，并关联
固定生成命令和事务来源；本轮实跑及记录复核已完成，详见该页的新报告。
逐项审查和候选审批尚未关闭。

## 范围来自哪些入口

九个固定根不能从输入清单中删除；允许显式追加本轮独立输出目录，但禁止重叠：

| 固定根 | 入口或范围理由 |
| --- | --- |
| `sail-model/build` | `prepare_sail_config.sh` 的合并配置及摘要 |
| `deps/sail-riscv/build` | `build_sail_emulator.sh` 的 CMake 构建、生成代码及模拟器 |
| `target` | 默认 Cargo 输出及 `generate_rebuilt_rust.py` 安装的生产 LLBC |
| `deps/ckb-vm/target` | 子模块独立 Cargo 输出的保守覆盖；不存在时显式记 absent |
| `proof/lean/generated` | Rust/Sail 安装目录；不跳过缓存、支持文件或事务保留备份 |
| `proof/lean/theorems/.lake` | 主定理构建缓存和结果 |
| `proof/rocq/generated` | Sail Rocq 事务安装输出 |
| `proof/rocq/spike` | 最小复现目录：包含受版本控制源码与潜在生成输出，属于混合目录 |
| `build` | 项目顶层可选构建输出；不存在时显式记 absent |

这些根不是整个工作区的输出闭包。公开证明、native 和 Rocq 的实际运行使用独立的
`artifacts/...` 输出目录，必须追加；安装包、工具前缀和历史实验也不能因位于
Git 忽略目录就自动获得“本轮生成物”身份。目录节点清单只记录位置和字节，
不会把树中的依赖、缓存、源码和日志一概认证为生成器产品。

## 记录和拒绝条件

每个根都记录存在/缺失；存在的树递归记录全部节点，不按扩展名过滤，也不跳过
`.lake`、嵌套 Git 元数据或旧备份。普通文件流式记录 SHA-256、大小和权限；
目录包含空目录；符号链接记录链接文字而不跟随，包括断链或循环链接。
链接目标的内容及依赖闭包仍须另外验收。

使用目录文件描述符和 `O_NOFOLLOW` 遍历，拒绝根祖先的文件/符号链接，防止读取
期间通过替换祖先重定向路径。拒绝 FIFO、设备、socket 等特殊节点；检查单文件和
目录读取期间的元数据/子项变化。这不是文件系统原子快照；生成链仍需停写或稳定的
前后采集与来源检查，不能据此证明任意并发写入都不存在。

比较时严格重算输入摘要，核对必需根、全部节点结构及父子关系；两份清单必须具有
相同范围。新增、删除、内容变化、权限变化、目录/文件/链接类型变化均进入差异。
报告中的 `regeneration_execution_proven`、`generated_outputs_audited`、
`worktree_audit_closed`、`release_claimed`、`week6_closed` 均保持 `false`。

## 用法

输出目录必须不存在，且采集输出不能置于被采集树内。比较不会执行任何生成命令。
下列路径仅为操作示例，不代表已有批准候选或执行记录：

```bash
python3 -O scripts/generated_output_inventory.py capture \
  --extra-root artifacts/example-run/products \
  --out artifacts/generated-review/example-before

# 在受控生成流程中保留真实命令、来源、工具、日志和终态后，再采集同样范围。
python3 -O scripts/generated_output_inventory.py capture \
  --extra-root artifacts/example-run/products \
  --out artifacts/generated-review/example-after

python3 -O scripts/generated_output_inventory.py compare \
  --before artifacts/generated-review/example-before/snapshot.json \
  --after artifacts/generated-review/example-after/snapshot.json \
  --out artifacts/generated-review/example-delta
```

退出 0 仅表示完成记录/差异计算，不是验收成功；错误退出 1，不覆盖已有输出。
`snapshot_sha256` 是内部 canonical JSON 摘要，不是格式化 JSON 文件的 SHA-256。
即便比较结果零差异，也可能只是两次读取同一批旧文件，不能冒充重生成成功。

## 本轮实测及后续连接

首轮对上述九个根，以及当前正式 native、Rocq 和公开证明冷构建三个独立目录尝试
只读采集。09:38:40–10:08:40 UTC 的首个 capture 触发 1,800 秒执行时限，
[原报告](../../artifacts/boundary-check/generated-inventory-yye4qehm/report.json)为 `failed` /
`TimeoutExpired`，SHA-256 为
`260d600974adea240dd117640eb26ddeceaeae557ab71f06d3feb878f9490b2d`。
27 项测试双模式通过，但没有完整清单，第二次采集、比较和独立重哈希未执行。
原驱动没有给超时阶段落独立日志；不补写历史日志或改成成功。

确认原进程退出且源码未变后，在
[新证据目录](../../artifacts/boundary-check/generated-inventory-retry-ULNALdda/run.py)
保持相同 12 根和相同采集器重试，仅将驱动单阶段时限提高为 3,600 秒，并为可能的
超时记录实际命令、部分输出、时间和 `exit_code: null`。新驱动绑定并首尾核对原失败
报告的哈希，不覆盖任何旧输出。当前尝试是否完成以
[新报告](../../artifacts/boundary-check/generated-inventory-retry-ULNALdda/report.json)为准。

该尝试于 11:01:32 UTC 完成：两份清单各有 330,452 节点、315,157 普通文件、
24,462,069,279 字节、230 个符号链接，`build` 根不存在；两次观察零差异，54 次测试
执行和两个 CLI 拒绝检查通过。这仍不是独立复核通过。
16:49:45–17:18:07 UTC 的
[独立复核](../../artifacts/boundary-check/generated-inventory-retry-ULNALdda/independent-report.json)
实际退出 1，发现当时目录树与旧清单不一致。报告 SHA-256 为
`623db18c03cf31bcbcfc3f40888d4043af3b571a4f58ee83ee280caa347812bf`，保留失败身份。
原独立检查器在异常前没有保存已枚举的清单或逐项差异，因此不能从该报告确定全部差异。

随后[元数据与较新文件诊断](../../artifacts/boundary-check/generated-inventory-diagnosis-v0rgZhVy/report.json)
重列全部 330,452 个节点，未发现节点、类型、权限、大小或链接文字变化。
两份较新文件 `target/flycheck2/stdout` / `stderr` 的内容哈希改变，mtime 为 16:48:17 UTC；
当前字节已另外复制保存，内容为 Cargo 检查输出。不能由文件名推断确切写入者，
也不能因字节数相同就声称仅耗时文字改变：旧日志内容未归档。
这次元数据诊断本身不是其余文件内容一致的证明；完整内容比对见下节。
未删掉 flycheck 文件、关闭编辑器或更新旧基线为 PASS。

### 全量差异已记录并复核

17:27:07–17:55:47 UTC 的
[完整比对](../../artifacts/boundary-check/generated-inventory-diagnosis-v0rgZhVy/full-report.json)
使用保留的独立遍历器重新读取全部 12 根，并逐根保存完整节点观察和差异。
报告状态为 `full_comparison_recorded_with_differences`，SHA-256 为
`6ec7cb8bc38c79795517ef753ad84fc6ee15bb19ee422811b360b9cfabb4973d`。
在此次非原子观察中，330,452 个节点仍包含 315,157 个普通文件、24,462,069,279 字节
和 230 个符号链接；与原 `capture-a` 比较，差异**仅有上述 stdout / stderr 两个文件的
内容哈希**。其余记录的内容哈希、节点类型、权限、大小和链接文字一致。
这不是目录树在所有时刻稳定的证明，也不能追溯确定 16:49 那次失败扫描的全部差异。

18:01:47–18:01:58 UTC 的
[记录复核](../../artifacts/boundary-check/generated-inventory-diagnosis-v0rgZhVy/records-verification.json)
实际退出 0：逐一核验 12 个检查点哈希，确认它们不重叠、并集精确等于汇总观察，
独立从旧清单重算全部差异并与逐根及汇总差异一致；核对计数、来源引用、保留的
两份日志字节与历史报告哈希。此次消费已保存的观察，不再重新扫描 24 GB 输出树。
完整比对记录源码首尾一致，记录复核时源码也仍匹配；随后本页及 Week6 状态的更新
属于新的文档增量，不回填到旧源码快照。

两份旧日志只保存过哈希，无法进行前后文本比较，因此仍不声称具体写入者、
仅耗时文字改变或这些日志已经获得语义审查批准。原超时报告和独立检查失败报告
均保持不变。完整差异已定位，不需要为了定位同一差异再做一次全树扫描；下一项
工程工作应是连接真实生成执行与差异审查。

计划的两次采集之间不执行生成器，所以即便完成，也不称为重建前后证据。
原 v10、上一轮源码验收报告和固定交付包不改写；本轮新代码也不归入它们的旧源码快照。

新增的实际生成记录入口负责采集清单，连接同候选的源码/工具身份、命令顺序、
输出范围、原始日志和前后清单；本轮实际生成序列和记录复核已完成，下一步须完成
全部差异审查并连接后续 kernel/生成身份，再交给工作树验收器。
应由实际执行输出推导追加根，而不是由报告任意省略；范围审批、生成物语义审查和
新环境执行仍不可由本组件代替。
