# CKB-VM 容器化重构：正式源码基线采用决议

后续进展：两个合同、最终定理及新 policy 已迁入正式工程；当前验收入口还要求干净
Lean 依赖重建，见 [Week 5 证据](../reports/WEEK5_EXIT.md)。下文“本步”特指源码采用阶段，
包括当时旧 policy 的预期拒绝，不代表后续证明迁移仍未进行。

日期：2026-09-07。决议：采用，范围为当前项目的生产 Rust 路径和 Lean 提取。
本步完成源码/配置基线，不批准新的最终定理 policy，不提升 coverage 或 release 状态。

## 源码身份与交付方式

| 项目 | 固定值 |
|---|---|
| 新基线 ID | `ckb-vm-1ffba3977da9-runtime-container-v1` |
| 上游锚点 | `1ffba3977da9dcdef8092e9ab1fd2516b27ec939` |
| crate 元数据版本 | `0.24.0`，不能单独标识本修改版 |
| 补丁 SHA-256 | `5ae9ec54d43034d9e4010e7373a516283f86a54519f9d79391f1c0c4f5883d2a` |
| 完整源码树 SHA-256 | `12b4df6daacf83f95980eba8eecbbf117f3ec2efaab845405efe242b95ef4c14` |
| 新生成 Lean 文件 SHA-256 | `9eb4be0e65c6653c2c08d3707b475c8d5c38ed032ebe358dd3a330342172fe4e` |

权威记录为 [ckb-source-baseline.json](ckb-source-baseline.json)，补丁为
[runtime-container.patch](../../../patches/ckb-vm/runtime-container.patch)。
源码树哈希覆盖上游全部 tracked 文件和新增回归文件的相对路径、文件模式与内容哈希，
不包含 Git/构建缓存。另行固定 Cargo lock、工具链、生产提取根、机器别名、提取脚本和配置。
所有源码身份均指本地可核验内容，不是上游签名或运行中二进制的构建认证。

没有创建或推送新的 Git commit，也没有改变子模块 gitlink。子模块 HEAD 仍是上述上游
锚点，但工作树有受审补丁，不能称为该 commit 的干净源码。只提交 gitlink 无法交付此
基线；必须一起提交父仓库中的补丁、manifest、守卫与配置。后续若改用 fork commit，
需要记录真实新 commit 并重新审计，不能把本地修改伪装成上游版本。

干净 clone 的显式准备步骤：

```bash
git submodule update --init --recursive
make ckb-baseline-apply
make ckb-baseline
```

`--apply` 只接受精确干净上游，或已完整应用的精确基线（幂等）；遇到其他修改、半应用
补丁、额外文件或错误 commit 会拒绝，绝不自动修复或覆盖用户修改。
日常检查/提取只验证，不自动应用。CI 两个 job 都显式应用并校验补丁。

## 补丁审查

- 生产修改仅 `deps/ckb-vm/src/machine/mod.rs`：将 cycle callback、debugger、syscalls
  三个原本相邻字段按原顺序封装进私有 `MachineRuntime<Inner>`。
- 外层保留 `inner`、`pause`、`exit_code`、`phantom`；不增加堆分配或自定义 `Drop`。
  builder 的公开接口保持原样，调整最终构造和动态字段访问。
- 整个 `CoreMachine for DefaultMachine` 实现与上游逐字相同，包含五个目标委托方法。
  生产 `execute_production` 和 runner 的 `InjectedMachine` 类型别名未改。
- 新增 `tests/runtime_container_probe.rs`，覆盖真实 ADD step/cycle、ECALL/EBREAK、
  初始化顺序、恰好一次销毁、`take_inner` 剩余字段销毁及 inner/runtime 销毁先后。
- 正式补丁相对隔离实验只调整了解释性注释；生成 Lean 文件与隔离验证结果逐字一致。

该审查加回归测试支持采用，但不是全行为源码等价证明。没有承诺 ABI/layout、性能、
ASM/JIT/pprof 特性或所有 panic/unwind 路径等价。没有从 opaque runtime 类型构造
初始机器，亦没有证明具体 Rust/Sail 初始化合同可满足。

## 提取配置与生成来源

[ckb-vm.json](ckb-vm.json) 是实际脚本消费的固定选择清单，不是与命令脱离的说明副本：

- Charon `0.1.247 (89ac118194b978d8cf753222c19f313521377aa0)`，Aeneas
  `nightly-2026.09.01-379890b`，共同 Lean `4.31.0`。
- 根仍为 `ckb_vm_sail_extract::execute_production`，指向真实生产入口。
- 保留原 instructions、两个常量、DefaultCoreMachine 的 include；增加真实
  DefaultMachine 结构及五个 register/PC 方法的精确 include。
- 不再 opaque DefaultMachine；显式 opaque MachineRuntime。内存和四个比较辅助
  的选择不变；Pause 是仍可到达的外部 opaque 类型，不是新加行为规律。
- Aeneas 使用 `-abort-on-error`；生成前后都校验源码身份。每次生成额外写出
  `generated/rust/SOURCE_BASELINE.json`，绑定源码身份、LLBC 和生成 Lean 的哈希。

复现：`make proof-gen-rust`。生成物的编译通过不等于定理通过。提取日志仍有已知的
Miri 缺失后回退 rustc sysroot、Step 支持库字段不匹配和外部未知声明警告；没有将它们
隐藏为“无警告提取”，也没有据此宣布整个模型闭包无 opaque/sorry。

## 审计清单与正式迁移边界

| 审计项 | 本步状态 |
|---|---|
| 生产补丁范围、字段顺序、CoreMachine 实现未改 | 已复核 |
| 上游锚点 + 补丁 + 完整源码树 + 提取输入身份 | 已固定，守卫检查 |
| 干净上游真实重放 / 幂等 / 非基线修改拒绝 | 已测试 |
| 正式 Rust→LLBC→Lean 再生成 | 已完成，与隔离模型逐字相同 |
| 当前源码的 Rust 回归、真实双端 corpus/mutation | 已完成，见下节 |
| 两个 wrapper 合同与无委托参数的最终定理 | 隔离证明已通过，正式迁移待做 |
| 新最终定理 137 项依赖及签名 | 隔离已审计，正式 policy 未批准 |
| 原始字双侧解码对应 / Sail 初态与前缀合同 | 待证明，不能由源码采用替代 |
| 全依赖 clean-room / 二进制来源绑定 / audit-release | 未完成 |

下一次正式 policy 审查必须逐项核对，而不是自动刷新哈希：

1. 将 `view = m.inner`、`valid = True` 的两个合同和 `ProductionAdd.decoded_add_step`
   迁移进正式工程，检查定理不再量化 wrapper 委托假设；解码/Sail 前提保持显式。
2. 将旧最终定理的 141 项与新最终定理的 137 项按完整名称比较：移除
   `ckb_vm_sail_extract.ckb_vm.machine.DefaultMachine`，以及其
   `Insts.Ckb_vmMachineCoreMachine.{registers,set_register,pc,update_pc,commit_pc}`
   五个方法；新增 `ckb_vm_sail_extract.ckb_vm.machine.{MachineRuntime,Pause}`。
   这里花括号只是审查说明，正式 allowlist 必须逐个枚举全名，不能通配放行。
3. 对两个合同、最终签名、状态关系及所有构造器从 Lean 环境重新导出并核验；
   更新正式 guards 和负向测试，拒绝额外公理、`sorryAx`、`False` 前提或弱化关系。
4. policy 明确固定 `ckb_source_baseline_sha256`、所有来源/生成物/工具哈希；
   完整重跑 `make proof-check BACKEND=lean`，不得跳过来源或测试阶段。

本步保留旧 `step-policy.json` 原字节，SHA-256 为
`5e5de4966560690d2e3476c0c76320c3dd43c68f1093c24487e9ae0a8e6ae5d0`。
当前正式门禁实际以 `theorem/policy migration pending` 失败，报告包含新源码身份；
这正是防止将修改版证明归到原始 commit 的拒绝机制。旧 guards 仍描述旧模型，
`proof-registers` / `proof-step` 也不能作为新基线已验收的证据。

## 本轮验证记录

- 基线守卫测试：12 项通过，包括从真实干净上游应用正式补丁并得到精确源码树哈希。
- proof-check 自身测试：15 项通过；实际旧 policy 验收运行被预期拒绝。
- 正式工作区 Rust 测试：68 项通过，10 项既有 DII 集成测试按默认配置 ignored。
- 正式 CKB-VM 默认 features 的 lib/tests：86 项通过，包含 5 项新增探针。
- 新生成 Rust Lean 模型：Lean 4.31.0 编译通过；285 个 `def`、51 个 `axiom`、
  12 个 `structure` 是文件级统计，不是最终定理依赖计数。
- `cargo fmt --all -- --check`、`cargo clippy --workspace --all-targets --locked -- -D warnings` 通过。
- 更新后的环境核验通过，打印完整源码基线身份；提取与模型编译日志保留在
  `artifacts/source-baseline/logs/`，机器可读总记录为 `artifacts/source-baseline/report.json`。
- 重编译的真实差分 CLI：32 案例通过，188 次 mutation 检测并定位，4 次不适用跳过。
  运行证据见 `artifacts/source-baseline/corpus/`；新 schema 3 明确区分 upstream anchor
  与验证过的源码基线。旧 schema 2 输入仍可重放，但不会补认其来源。

本轮来源/测试证据不认证全依赖缓存或运行二进制；生成模型及证明支持库仍使用本机
既有依赖。正式证明批准和 Week 5/发布验收状态没有随本次源码采用自动提升。
