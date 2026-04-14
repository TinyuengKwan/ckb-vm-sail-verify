# Week 8: Documentation, Deliverables & Roadmap

## Objectives

- Finalize all documentation for Spark submission
- Ensure full reproducibility (clean-room build test)
- Write Phase 2+ roadmap

## Tasks

1. **Clean-room build verification**
   - Test on a fresh environment (Docker or new VM)
   - Ensure `make all` works from a clean clone
   - Fix any undocumented dependencies

2. **Finalize methodology document**
   - Update `doc/methodology.md` with lessons learned
   - Add concrete examples from completed proofs
   - Document proof effort per instruction (lines of Coq, time spent)

3. **Write completion report**
   - Summary of what was proved and what was tested
   - Statistics: N instructions proved, M tests run, K lines of Coq
   - Known limitations and assumptions

4. **Write Phase 2+ roadmap**
   - Phase 2: Full RV64I (all ~50 instructions) — scope, estimate, funding
   - Phase 3: M/C/B extensions — additional complexity
   - Phase 4: ASM mode verification via Islaris — research needed
   - Potential for Community Fund DAO proposal

5. **Final code cleanup**
   - Remove dead code, fix warnings
   - Consistent formatting (rustfmt, coq style)
   - License headers on all files

## Files to Add/Modify

| Action | Path | Description |
|--------|------|-------------|
| Add | `doc/completion_report.md` | Spark completion report |
| Add | `doc/roadmap.md` | Phase 2+ roadmap |
| Modify | `doc/methodology.md` | Final version with lessons learned |
| Modify | `doc/architecture.md` | Final version |
| Modify | `README.md` | Update with final status and results |
| Add | `Dockerfile` | (Optional) Reproducible build environment |

## Verification Criteria

- [ ] `git clone && make all` succeeds on fresh machine
- [ ] All documentation reviewed and complete
- [ ] Completion report ready for Spark submission
- [ ] Roadmap defines clear next steps
- [ ] Zero compiler warnings in Rust and Coq

## Spark Submission Checklist

- [ ] Project deliverables (code, proofs, tests) on GitHub
- [ ] Completion report posted to Nervos Talk
- [ ] "How to Verify" section tested by someone other than the author
- [ ] All open-source under MIT license

---

# 第八周：文档完善、交付物与路线图

## 目标

- 完成 Spark 提交所需的全部文档
- 确保完全可复现（净室构建测试）
- 撰写 Phase 2+ 路线图

## 任务

1. 在全新环境测试 `make all`，修复未记录的依赖
2. 完善方法论文档，加入实际证明经验和统计数据
3. 撰写完成报告：证明了什么、测试了什么、统计数据、已知限制
4. 撰写路线图：Phase 2（全 RV64I）、Phase 3（M/C/B 扩展）、Phase 4（ASM 验证）
5. 代码清理：去除无用代码、格式统一、许可证头

## 新增/修改文件

| 操作 | 路径 | 说明 |
|------|------|------|
| 新增 | `doc/completion_report.md` | Spark 完成报告 |
| 新增 | `doc/roadmap.md` | Phase 2+ 路线图 |
| 修改 | `doc/methodology.md` | 最终版（含经验教训） |
| 修改 | `README.md` | 更新最终状态和结果 |
| 新增 | `Dockerfile` | （可选）可复现构建环境 |

## 验收标准

- `git clone && make all` 在全新机器通过
- 全部文档审查完成
- 完成报告可提交 Nervos Talk
- 路线图定义清晰的后续步骤
- Rust 和 Coq 零编译警告

## Spark 提交清单

- [ ] 项目交付物（代码、证明、测试）在 GitHub 公开
- [ ] 完成报告发布到 Nervos Talk
- [ ] "How to Verify" 经他人独立测试
- [ ] 全部 MIT 许可
