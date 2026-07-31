# Week 2 — RVFI 运行时闭环

## 任务

- CKB runner 从真实 interpreter 采集 PC、raw instruction 和 rd delta。
- Sail runner 用固定 fixture 验证 parser，并接入 RVFI-DII binary client；直接 ELF 的空 RVFI 输出必须失败。
- 加入 `--json`、seed、artifact 输出。
- 统一 x0、compressed instruction 与终止状态规范化。
- 对缺失 memory observation 默认报不支持或 mismatch，不静默相等。

## 语料

- ADD、ADDI、BEQ 的共享单步初态。
- 零值、全一、符号边界、溢出、rd 别名、rd=x0、BEQ taken/not-taken 与正负偏移。
- 固定随机 seed 生成的案例。
- 不依赖平台 syscall 的最小重放 artifact。

## Exit gate

- ADD、ADDI、BEQ 均至少一个场景端到端可重放，为 Week 3 的 10 个案例建立闭环。
- 两端任一执行失败导致测试失败。
- 最后一个事件缺失可被检测。
- parser fixture 固定当前 sail-riscv commit 和输出格式。
