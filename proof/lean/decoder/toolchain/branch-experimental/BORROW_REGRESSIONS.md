# 共享借用回归：从 Rust 提取到行为证明

2026-09-09。补充候选 v2 的行为核验，不是正式工具采纳，也不是一般性的编译器正确性证明。
实际输入是未修改的上游 `join-duplicate.rs` 和 `loop_shared_loan_in_join.rs`；
检查器重新运行 Charon 和 Aeneas，在新的模型缓存中编译，不复用这两个模型的 `.olean`。

## 证明覆盖

- [BorrowProof.lean](BorrowProof.lean)：嵌套共享引用断言；对任意 `n i : U32` 的循环
  正常返回；对任意布尔值和 `u32` 次数，实际入口返回正确的共享引用值。
  终止证明使用 `n.val - i.val` 的良基递归，没有人为 fuel 上限。
- [SharedEffectProof.lean](SharedEffectProof.lean)：实际四元素转换对任意 `U64` 值逐元素
  wrapping 加一；长度零提取保持任意初态；两次触发更新时，输出依次为 `11、12`，
  最终数组为 `[12,22,32,42]`。后者是明确的具体两步行为证明，不是任意长度提取定理。
- [精确审计](borrow-audit-snapshot.json) 固定上述定理及辅助引理共九项的完整类型和依赖。
  依赖只含 `propext`、`Classical.choice`、`Quot.sound`，不含 `sorryAx` 或 native 决策。

## 负面检查

生成模型的循环回边若把已更新数组 `a1` 改成旧数组 `a`，模型本身仍能编译，
但正确结果的证明被内核拒绝。随后内核正向证明该错误模型的实际轨迹：输出变成
`11、11`，最终数组仍为 `[10,20,30,40]`。因此不是用超时或缺失实例冒充语义负测。
变体仅生成在隔离测试目录，不改变生产模型。

另给 `nested_assert` 添加未使用的 `False` 前提：变体可编译，公理集合不变，
但精确类型审计发现且只发现该定理签名改变，避免仅数公理漏掉空前提弱化。

## 复现与结果

```sh
python3 scripts/experiments/probe_decoder_borrows.py \
  --inputs artifacts/boundary-check/aeneas-branch-ZR2ur7
```

[报告](../../../../../artifacts/boundary-check/borrow-check-71_p72a7/report.json)
为 `BORROW_REGRESSIONS_PASS_NOT_ADOPTED`：14 阶段通过（含预期语义拒绝），九条审计精确匹配。
报告 SHA-256：`419a12b5f03cc0f9a5f2810a3fff8d6e282a1c933c5bdfd2f8c1d92cb0346cae`。
快照 SHA-256：`9806e98cba5033a180cd7a846860ddd767b99ffaee0c012fe802bde21d2eb7b7`。

新提取模型与此前核验模型逐字相同；固定 Rust 源码、工具二进制和 rustc commit。
复用既有 full-MIR sysroot 和 Lean 支持库缓存，不是完整 clean-room 构建。
不能据此声称 Charon 全量测试通过、任意借用连接保持语义或主 proof-check 已采纳新工具。
