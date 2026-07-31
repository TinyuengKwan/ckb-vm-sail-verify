# Week 3 — CLI/CI、语料与负向验证

## 任务

- 将 DII 闭环封装成维护者可调用的 CLI/Make target。
- 为成功和 mismatch 输出稳定 JSON、文本摘要与非零退出码。
- 接入 PR CI，并保存报告、原始 Sail 包和最小重放输入。
- 固定版本、配置哈希、随机 seed 和测试 ID。

## 强制语料

- ADD、ADDI、BEQ 合计至少 10 个可重放案例。
- 覆盖零值、全一、符号边界、溢出、寄存器别名与 rd=x0。
- BEQ 同时覆盖 taken/not-taken 与正负偏移。
- MUL 可作为 stretch 加入，但不替代前三条强制指令。

## 负向验证

- 注入 `pc_after` 差异。
- 注入 rd 编号或 rd 值差异。
- 注入 trap 差异。
- 注入 trace 长度或终止状态差异。

## Exit gate

- 至少 `10/10` 基线案例通过严格比较。
- 至少 5 类 mutation 均被检测并定位首个差异字段。
- 空 trace、runner error 或只匹配公共前缀不能返回 PASS。
- CI artifact 能在本地用一个命令重放。
