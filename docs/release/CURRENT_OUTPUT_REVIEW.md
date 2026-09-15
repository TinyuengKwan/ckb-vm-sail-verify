# 当前输出身份复核

本页记录 `worktree_audit` 中“当前生成输出身份”组件的边界。它不修改
[Week6 原始条款](../plan/week6.md)，也不把文件分类或两次相同读取提升为生成物语义正确、
编译器正确、clean-room、交付审批或 release。

## 验收结构

[验收器](../../scripts/release_current_output_review.py)组合五项输入：

1. 24 个显式输出根的完整观察，以及向正式生成时 13 根范围的精确投影；
2. Cargo archive/source 的逐成员、checksum 和权限记录复核；
3. build/cache/目录节点的显式格式、编译输出及原执行二进制绑定；
4. 其余报告、日志、重放数据、Cargo 索引和失败记录的路径绑定复核；
5. 在最终源码身份下，对同一 24 根执行一次新的完整重哈希，结果必须与第一项清单
   **逐字节相同**。

前三份 review 的成员必须两两不交且并集恰等于观察中 7,445 个新增节点：
3,596 + 2,893 + 956。正式范围的 337,855 个历史节点必须零变化；扩展观察共
345,300 个节点。每个 review 行绑定节点摘要、类别和支持记录，并保持
`semantic_correctness_proven` / `delivery_approved` 为 `false`。

最终重扫使用已有 `generated_output_inventory.py capture`，读取普通文件全部字节，记录
权限、大小、目录、缺失根和不跟随的 symlink。它仍是非原子文件系统观察；验收器要求
重扫清单的格式化 JSON 文件与既有观察完全相同，并核对命令启动、进程、结束、日志和
源码快照。没有这次重扫，历史观察不能消除 `current_generated_output_identity`。

## 已完成的新增节点记录审查

2026-09-14 的[最终新增节点记录](../../artifacts/boundary-check/additional-record-review-nKSiwcjG/report.json)
完成双模式各 40 项回归、记录生成和第二进程复核；956/956 项完成，累计为
7,445/7,445。原六项 evidence 加工作树部分聚合由原验收器重新返回预期的
`incomplete` / 退出 2；被动 read-open 记录只说明验收器尝试打开了某个路径，
不证明读取完成或全部字节影响了结果。

首轮正式 delta review 的最终检查退出 1，第二轮退出 0；两者在新记录中分别保留，
不会因内容相同或后续成功而合并。四份修改前源码副本内容与源快照一致，但容器文件
权限为 `0664`，并未继承源文件 `0644`；这一差异也被明确保存。

新增节点记录的终态 SHA-256 为：

- 顶层报告：`1eaeb39ad378cd89a56624c5e837372c8aa48042eeee130355be8f517cb2a026`
- 完整 review：`5677583d64c6911a670423185f340bb4f183ed4e6e79a4a839b3e004dbf1f5c6`

上述记录仍使用源码快照 `91332523…`。接入生产验收器之后源码身份会变化；第 5 项的
最终执行状态以[重扫报告](../../artifacts/boundary-check/current-output-confirmation-final-J2LrUPYG/report.json)
和 [v3 组合报告](../../artifacts/boundary-check/current-output-integration-zvlwq2MM/report.json)
为准。只有重扫成功、源码/增量记录复核成功且实际聚合只剩最终交付审批时，才能从工作树
剩余项中移除“当前输出身份”。最终交付范围与语义审批仍为另一项独立义务。

[第一次重扫尝试](../../artifacts/boundary-check/current-output-confirmation-c14VcJTI/report.json)
在遍历过程中主动终止，避免重扫完成后再修改这两页状态文档而使源码绑定立即过期；
报告保持 `failed`，SHA-256 为
`6cca42848b3aabc78baae7becff2e25e779578743ae744b9d171f9f2a5e0a5c1`，不计作确认。
最终尝试使用新目录从头读取全部 24 根，不复用第一次尝试的未完成遍历。
