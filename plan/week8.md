# Week 8: Documentation, Deliverables & Roadmap

## Task 8.1: Clean-Room Build Test

Test from a clean clone:

```bash
cd /tmp
git clone ~/workplace/ckb-vm-sail-verify test-clone
cd test-clone
export SAIL_RISCV_DIR=~/workplace/sail-riscv
make all   # must succeed
```

Or use Docker:

```dockerfile
FROM ocaml/opam:ubuntu-24.04-ocaml-5.2
RUN sudo apt-get update && sudo apt-get install -y cmake build-essential libgmp-dev gcc-riscv64-unknown-elf
RUN opam update && opam install -y sail coq.9.0.0 coq-sail-stdpp
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/home/opam/.cargo/bin:${PATH}"
RUN git clone --depth=1 https://github.com/riscv/sail-riscv /workspace/sail-riscv && \
    cd /workspace/sail-riscv && cmake -S . -B build && \
    cmake --build build --target generated_rocq_rv64d --target sail_riscv_sim
COPY . /workspace/project
WORKDIR /workspace/project
ENV SAIL_RISCV_DIR=/workspace/sail-riscv
RUN make all
```

## Task 8.2: Write Completion Report

Create `doc/completion_report.md`:

```markdown
# Completion Report

## Summary
First formal verification framework for CKB-VM, connecting to official Sail RISC-V spec.

## Deliverables
1. **Coq proofs**: N theorems for M instructions (K lines)
2. **Diff-test framework**: X tests across I/M/C/A/B extensions
3. **Documentation**: instruction mapping (158 opcodes), semantic gaps (8 categories)
4. **Roadmap**: Phase 2-4 defined

## How to Verify
git clone <repo> && make all
```

Fill in actual numbers.

## Task 8.3: Write Roadmap

Create `doc/roadmap.md`:

```markdown
| Phase | Scope | Duration | Funding |
|-------|-------|----------|---------|
| PoC (done) | 10+ instructions, diff-test, docs | 8 weeks | Spark $2k |
| Phase 2 | Full RV64I (~50 instructions) | 3 months | DAO ~$5k |
| Phase 3 | M/C/B extensions | 4 months | DAO ~$8k |
| Phase 4 | ASM mode (Islaris) | 6+ months | Grant ~$20k+ |
```

## Task 8.4: Code Cleanup

```bash
cargo fmt --all
cargo clippy --workspace
rm -f coq/TestImport.v
grep -rn "TODO\|FIXME\|HACK" coq/ lib/ crates/
make clean && make all
```

## Task 8.5: Update README

Add actual results:

```markdown
## Results
- **N Coq theorems** for M RISC-V instructions
- **X ISA tests** passed in differential testing
- **8 semantic gaps** documented
- **158 opcodes** mapped
```

## Task 8.6: Submit to Spark

Post to Nervos Talk:
- Title: `[Spark] CKB-VM Sail Formal Verification PoC — Completion Report`
- Body: from `doc/completion_report.md`
- Tag: `Spark-Program`

Checklist:
```
[ ] Code on GitHub under MIT
[ ] make coq succeeds
[ ] make diff-test succeeds
[ ] "How to Verify" independently tested
[ ] Report on Nervos Talk
[ ] Phase 2 roadmap included
```

## Files Added/Modified This Week

| Action | Path | Description |
|--------|------|-------------|
| Add | `doc/completion_report.md` | Spark report |
| Add | `doc/roadmap.md` | Phase 2+ |
| Add | `Dockerfile` | Optional |
| Modify | `README.md` | Final numbers |

---

# 第八周：文档完善、交付物与路线图

## 任务 8.1：净室构建

在 `/tmp` 下 clone 新副本测试 `make all`。或用 Docker。

## 任务 8.2：完成报告

`doc/completion_report.md`，填入实际统计数字。

## 任务 8.3：路线图

`doc/roadmap.md`，规划 Phase 2（全 RV64I）、Phase 3（M/C/B）、Phase 4（ASM）。

## 任务 8.4：代码清理

`cargo fmt`、`clippy`、删临时文件、`make clean && make all`。

## 任务 8.5：更新 README

填入实际证明/测试数量。

## 任务 8.6：Spark 提交

在 Nervos Talk 发帖，附 GitHub 链接，打 `Spark-Program` 标签。核对提交清单全部打勾。
