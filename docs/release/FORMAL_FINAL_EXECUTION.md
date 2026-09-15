# 新案例政策下的完整正式链记录

2026-09-13。对应 [Week6 逐族案例修正](WEEK6_RUNTIME_FLOOR.md)后的主政策
`b5bdc4017628cb065f273a278c7d7458bb6d93b4572eaca0e4788e519e6ab2c3`。
执行目录为 `artifacts/boundary-check/formal-final-kfncD8ln/`。
整轮于 20:24:51–22:21:00 UTC 实际完成并退出 0；
[终态报告](../../artifacts/boundary-check/formal-final-kfncD8ln/report.json)为
`formal_execution_and_delta_recorded_pending_worktree_review`，`errors=[]`。
报告 SHA-256：`39cb3d246fccba96c11c037ad2946ab7451ca9698a67f5d7269877304b78929a`。
这是正式执行与差异记录完成，不是 worktree、clean-room 或发布验收完成。

## 已核对结果

- 原 `make proof-check BACKEND=lean` 于 21:40:39 UTC 退出 0：28 阶段、21 组共 287 项测试，
  公开子链 48 阶段、68 个定理，干净依赖构建 1,865 项。
  [主报告及同目录 32 份归档](../../artifacts/boundary-check/formal-final-kfncD8ln/main/report.json)
  SHA-256：`740f026dcf1ff8f93fff9d85fcd2d1500aabddb8f6d360706682adf46d35551e`。
- 原 `make proof-spike` 于 21:49:07 UTC 退出 0：11 阶段验收完成，结论仍为 NO-GO，
  `extra_proof_coverage=false`。Rust `result` 名称冲突与 Sail 缺失 `e_div` 均有最小复现。
  [Rocq 报告](../../artifacts/boundary-check/formal-final-kfncD8ln/rocq/report.json)
  SHA-256：`0454f80b6ab94ff9b931e9a17d99d27badf0340f100cb5198b58e8c4a8ae0e2b`。
- 两侧报告绑定同一最终生成身份；独立子进程重验 Lean/Rocq 原始记录通过。
  [独立验收日志](../../artifacts/boundary-check/formal-final-kfncD8ln/independent-acceptance.log)
  中的 `fresh_kernel_run_claimed=false` 表示该检查器只读验收先前执行，不是再次运行 kernel。
- 完整源码首尾快照相同，身份为
  `a06055b4c7460fcd9273527f34fd1e399b34d6e87b8e882af11d93476529530c`。
  生成后约定范围含 337,855 个节点、321,628 个文件、25,035,718,258 字节及 230 个符号链接。
- [完整差异](../../artifacts/boundary-check/formal-final-kfncD8ln/delta.json)共 46,651 项：
  46,648 项新增、3 项修改、无删除。修改项为 Rust `SOURCE_BASELINE.json`、
  Lean `step-build.log` 和 `target/CkbVmProduction.llbc`；
  后续[全部差异的逐路径说明](FORMAL_DELTA_REVIEW.md)已完成并通过第二进程复验。
  差异 SHA-256：`2360b56f5e9a42e16c7e02bf8b4383719b257fec4751ee8dbe69d0b9109a65b6`。

终态后只读复核了报告绑定的全部 110 个文件哈希，并从完整前后快照重新计算差异，均一致。
这不是再次扫描当前所有输出，也不等于差异语义或最终交付范围已获批准。
本页及关联文档在终态后更新，不属于上述冻结源码身份；后续源码增量须另行审查。

## 固定执行范围

驱动不修改正式生成器、定理或验收门禁，不提供 skip/替代命令路径：

1. 保存完整源码身份和现有 `artifacts/proof-check` 顶层记录，核验锁定工具与来源。
2. 采集九个必需输出根、运行时辅助目录和本次 Rocq 目录的生成前完整节点观察。
3. 运行原 `make proof-check BACKEND=lean`：实际重生成 Rust/Sail、主 kernel、公理/前提
   审计及完整公开 decoder 干净依赖链；保存新的主报告与全部顶层日志。
4. 运行原 `make proof-spike`，在本次新目录生成和编译 Rocq 输入，保留具体 NO-GO
   及最小复现。NO-GO 不计为额外证明。
5. 根据父目录前后记录，将本次新建的 Rust 提取和 public-check 目录加入完整输出观察；
   不省略其中的缓存、备份或元数据。任何意外新目录也记录，但不按预期成功放行。
6. 保存完整 delta，独立重验 Lean/Rocq 原始证据，并要求两者绑定同一最终 Rust/Lean
   生成身份；完整源码和政策在结束时再次核对。

出现普通命令失败时仍尝试保存输出后值和差异，不把失败或部分阶段当作正式通过。
原主报告可能被正式命令覆盖，因此事先逐字节保存所有顶层记录；既有嵌套历史 clean
build 目录不会删除、复制或冒称重新审计，它们的名字单独列出。
驱动自身的记录文件另行哈希绑定，不把选定输出根说成整个 workspace 的无遗漏扫描。

## 边界与运行期间约束

运行期间冻结源码修改。全量输出扫描曾耗时约 26 分钟；主证明链还有干净编译成本。
事件文件含原命令、PID、时间、退出码及日志身份；长时间没有新日志不表示进程已停止。
驱动与原生成记录入口共用录制锁，正式 `proof-check` 另使用自己的执行锁。

本次完整链通过，获得该政策下的条件性 Lean 证明、Rocq NO-GO 和完整输出差异记录。
后续差异说明已完成，并已[接入工作树部分验收器](WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)；
最终交付范围及后续增量未审定，记录绑定通过不关闭完整工作树验收。
后续[聚合中的最终执行连接](WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)已完成：
独立验收的 Lean/Rocq 引用与本记录精确对应，仅关闭执行连接义务，不声称新 kernel 执行。
它不自动批准 delta/交付范围，不关闭 worktree audit、clean-room、CI 下载、第三方或发布。
不会把此前 10,021 项旧生成差异说明归到本次新的生成身份。
本次 native 证据已通过；后续[当前 mismatch/demo 的重做、独立验收和六项聚合](FINAL_SUPPORT_REFRESH.md)
也已完成，但仍须另审这些新增输出及最终交付范围。
