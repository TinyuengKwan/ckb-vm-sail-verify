# 本轮生成差异的逐路径说明

2026-09-13。针对[真实生成序列](GENERATION_EXECUTION_RECORD.md)的完整 10,021 项差异，
19:38:26–19:38:42 UTC 完成[审查记录](../../artifacts/boundary-check/generated-delta-review-m9iGbbV9/report.json)，
报告 SHA-256 为 `fae9c9f59349366fa73947fc133af76a9fe6587abb8afd54f5619ea16cfd663d`。
[逐路径记录](../../artifacts/boundary-check/generated-delta-review-m9iGbbV9/reviews.json)每项均绑定
原差异的 canonical SHA-256、分类、理由和对应证据；未按目录名省略任何差异。

这是该次观察的来源与差异说明，不是当前整个工作区重扫、生成物语义正确性、候选交付
审批或 Week6 关闭。缓存/注册表/Git 元数据的处置仅为保留诊断记录，未批准进入发布包。

## 已核对的内容

| 范围 | 差异项数 | 核验与处置 |
| --- | ---: | --- |
| checkout 与 source-payload 源码副本 | 3,612 | 两份副本对应生成时完整源码快照的字节、大小与可执行位；实际 checkout 的源码清单也匹配 |
| 锁定依赖包与解包源码 | 1,743 | 52 个 `.crate` 归档 SHA-256 匹配该次 Cargo.lock，1,691 个文件匹配相应归档成员的内容和大小；只读归档，不落盘解包或运行包内代码 |
| 保留备份及原路径移除 | 2,375 | 1,363 个新增备份节点匹配旧节点；1,012 个原路径删除项有精确备份对应，并非丢弃数据 |
| CMake 依赖记录 | 8 | 四个 `.make` 修改项及四个新增 `.internal` 文件按完整依赖集合核对 |
| LLBC 与 Rust provenance | 2 | 连接本次新提取身份，沿用上一轮精确 JSON 差异及 provenance 核验；旧值保留 |
| 目录、提取记录及构建/注册表/Git 元数据 | 2,281 | 逐成员列出，不冒充新模型证明，不批准为发布负载 |

最后一组细分为 1,178 个目录、17 个提取输出/记录、309 个构建缓存文件、112 个注册表
元数据文件、662 个 Git 元数据文件和 3 个事务记录。源码与依赖的内容来源核对不证明
每个依赖的语义、安全性或工具供应链可信；Git 元数据分类也不是一次新的 `git fsck`。
审查依据是已保存的全量节点观察，另对相关归档、事务和 CMake 文件核对当前字节，
没有再读取整个 21 GB 输出目录来声称新的全树稳定性。

## 四组 CMake 变化的解释

旧 `.make` 文件的候选内容由确定的两行空依赖占位文本构造，其长度和 SHA-256 均
精确匹配生成前清单。它们是**本轮重构后核对哈希的前值**，不是伪称原采集时保存的字节。
[事实文件](../../artifacts/boundary-check/generated-delta-review-m9iGbbV9/facts.json)保存文本、
对应 `.internal` 路径、对象/依赖数和完整集合摘要。

新 `.make` 的对象依赖和空目标规则，与 `.internal` 的依赖集合一致；相对依赖以该次
CMake build 根解释。解析仅接受所需的数据语法，不执行 Makefile，拒绝 recipe、变量、
include、额外/缺失目标及依赖、重复对象目标等。本轮说明不等同于宿主头文件/ABI 闭包验证，
也不把 `make sail-config` 的增量构建日志说成新的从零编译。

## 复核与后续门槛

19:40:56–19:41:00 UTC 的[绑定与测试复核](../../artifacts/boundary-check/generated-delta-review-m9iGbbV9/independent-report.json)
退出 0：精确覆盖 10,021 个差异成员，重新核对变化摘要、分类计数、备份映射及来源引用。
14 个受限 CMake 解析测试在普通 Python / `-O` 模式下全部通过，共 28 次测试完成。
它不是独立第三方复现，也不是再次执行生成器、工具安装校验或 kernel。

[生成记录组合入口](WORKTREE_GENERATION_VALIDATOR.md)现已接入工作树部分验收，核对
记录与逐路径说明的完整绑定，不重新证明说明内容。源码后续增量与候选审批仍待接入。
最终 kernel/Rocq 证据必须绑定最终生成身份；原 `proof-check` 会重新生成 Rust/Sail，
不能跑完后仍把本轮旧 LLBC/provenance 当作最终状态。应使用覆盖最终生成与验收阶段的
同一次前后记录，或显式审查后续生成增量；不能靠反复更新文档/快照制造同一候选的假象。
最终交付范围、clean-room、CI 下载、第三方和实际发布仍是独立未关闭义务。
