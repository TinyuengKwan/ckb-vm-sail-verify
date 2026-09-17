# Week6 关闭清单与当前证据

更新至 2026-09-14。任务以 [Week6 原始条款](plan/week6.md) 和
[总览 Definition of Done](plan/overview.md) 为准；不修改验收定义。
**当前未关闭 Week6，也未完成发布。** 既有 ADD 解码/执行的条件性证明不替代
全环境 clean-room、独立第三方复现、CI 下载重放或实际 release 证据。

**验收缺口修正：** 旧 runtime 的 13 / 10 / 9 分布不满足 Week6 每族至少 10 项。
已[补入 BEQ 零位移案例并加强逐族计数门禁](release/WEEK6_RUNTIME_FLOOR.md)，20:13:19 UTC
完整实跑与独立验收完成：33 项（13 / 10 / 10）、398 步、194 次适用 mutation、33 次
复制重放及全部 78 项 Rust 测试通过。本地逐族数量要求现已满足。主政策仅更新 corpus 源码绑定，
SHA-256 为 `b5bdc401…`；下文 `7ced9f42…` 的 Lean/Rocq 和 v10 均保留历史身份。
20:15:54 UTC 新专用清单聚合完成：runtime/Rust 两项被接受，其余十项明确缺失，整体
仍 `incomplete`、退出 2；该历史专用清单只填 native 两项，不自动接入后续证据。
[新政策完整正式链记录](release/FORMAL_FINAL_EXECUTION.md)已于 22:21:00 UTC 完成：
Lean 28 阶段/287 测试、公开子链 48 阶段/68 定理、Rocq 11 阶段 NO-GO 均通过独立验收。
主记录归档 32 个文件；源码首尾相同，完整输出差异为 46,648 项新增、3 项修改、无删除。
终态后核对 110 个绑定文件并重算差异一致。
[46,651 项正式 delta 的逐路径说明](release/FORMAL_DELTA_REVIEW.md)于 23:06:48 UTC
完成第二进程复验，26 项回归双模式通过。10 个依赖副本共享本机 Git 对象库、一个 gitlink
未展开，均明确记录而非计作 clean-room；最终范围、后续增量仍待完成。
[新格式工作树部分验收](release/WORKTREE_GENERATION_VALIDATOR.md#正式链记录分支)已接入，
23:26:44 UTC 完成 314 次双模式回归及实际聚合：核对 133 个引用和全部 46,651 项差异，
六项证据仍被接受，工作树为 `incomplete`、其余五类缺失。
后续[最终执行连接检查](release/WORKTREE_GENERATION_VALIDATOR.md#聚合中的最终执行连接)
已于 23:42:59 UTC 完成：370 次双模式回归、真实聚合及引用变更检查通过；
聚合的 Lean/Rocq 与同一正式生成记录精确对应，执行连接项已移除。
该轮记录仍有完整当前源码、源码增量、当前输出身份及最终范围/语义审批四项工作树义务。
当前完整源码组件另按[本轮 275 项来源审查记录](release/WORKTREE_SOURCE_VALIDATOR.md#本轮完整源码来源记录)
验收，实际状态以其机器报告为准；来源绑定不能代替最终语义/交付审批。
[当前输出身份复核](release/CURRENT_OUTPUT_REVIEW.md)已把观察新增的 7,445 个节点分成
3,596 / 2,893 / 956 三个互斥且完备的记录审查集合，最后一组双模式各 40 项通过；
首轮失败、缓存边界和源码副本权限差异均保留。生产验收器已实现 v3 组合入口；最终状态
以[同一 24 根的重扫与 v3 组合记录](release/CURRENT_OUTPUT_REVIEW.md)为准，旧
`91332523…` 观察本身不冒充当前确认。第一次重扫因先消除本页会立即过期的措辞而主动
终止，失败记录保留；最终尝试从新目录重新读取全部范围。
[当前负测、演示及新六项聚合](release/FINAL_SUPPORT_REFRESH.md)已于 22:35:53 UTC 完成：
三类负测均重做、33 案例演示已录制及播放，独立检查通过；新聚合六项接受、六项缺失，
整体 `incomplete`、退出 2。旧 v10 和 native-only 清单不回写为当前通过记录。
[当前候选公开结论全量复核](release/PUBLIC_CLAIMS_FINAL.md)已把范围从六份核心文档扩展到
完整源码清单中的全部项目 Markdown，新增生产检查器及双模式负测；计划、历史记录、
当前保证和技术边界分别分类。其机器报告必须在最终源码/工作树身份下重新验收八类证据；
即使通过也只关闭 `public_claims`，不替代其他发布义务。
在 `43218a71…` 源码身份下，该生产检查、普通/`-O` 独立重算和最终聚合已实际通过；
后续外部验收器源码变更后，该报告保留原身份，必须在新最终源码下重新冻结，
不把旧 PASS 自动平移到新候选。

**2026-09-14 独立临时 VM / 分阶段执行 / provenance 复审：** 见[设计复审](release/EPHEMERAL_VM_STAGED_PROVENANCE_REVIEW.md)
与其[只读机器记录](../artifacts/boundary-check/week6-ephemeral-vm-design-review-20260914/evidence/report.json)
（SHA-256 `6f707738…`）。结论：外部验收政策本就允许 `independent-ephemeral-vm`，因此 clean-room 执行改走
本地 KVM 临时 VM，GitHub workflow 的 `clean-room` job 改为只做 intake、验证、归档与 attestation（候选
`week6-release-v2.yml` 与 `contract-v2.json` 随记录保存，未采纳）；标准 runner 分阶段执行因 14 GB / 6 小时 /
每 job 都需 13.2 GB 安装根而否决，larger runner 仍需组织且 6 小时上限对 4 到 5 小时的链有风险。复审同时发现并
修正一个与 runner 无关的控制器缺陷：原 16 阶段没有任何阶段用固定 Sail 编译器配置 `deps/sail-riscv/build`，
新鲜检出会在 `rebuild-rust-model` 的 resolver 处失败；现在 `install-sail` 完成该配置并核对 cache。VM provider 的
provenance 由自述常量改为宿主 launcher（`scripts/week6_ephemeral_vm.py`）在 guest 关机、证据提取、overlay 与
secrets 磁盘销毁后写入的 operator-attested 记录；聚合器在记录绑定前保持 `clean_room` incomplete，CI 归档携带
VM 报告时必须同时携带该记录，记录明确 `platform_signed_identity=false`。`scripts/week6_vm_evidence_bundle.py`
提供确定性 pack 与严格 unpack 作为 CI intake 入口。相关五个测试文件 94 项在普通与 `-O` 下通过。
本机此刻不能启动 VM（用户不在 `kvm` 组、无 `qemu-system-x86_64`、`sudo` 需密码），候选亦未推送
（远端 `main` 仍为 `1ef21d7…`），且 3.18 GB 安装包超过 GitHub release 单文件 2 GiB 上限；这些用户侧动作与精确
命令列在复审第 6 节。未启动 guest、未推送、未 dispatch；五个外部槽仍未关闭，Week6 仍未关闭。v1 workflow 候选
记录只重新封印了 `remote_capacity_audit` 的过期哈希，其余保持历史身份。
2026-09-15 补充：固定安装包已[同内容重新封装为 xz](release/FIXED_INSTALL_BUNDLE.md#2026-09-15-xz-重新封装同成员同清单只换容器)，
1,801,059,088 字节、`c8e8ca27…`，清单 `ac7b468e…` 不变，低于 2 GiB 上限；包加载/暂存按魔数识别 gzip 与 xz，
控制器与 launcher 已固定新哈希。这只是容器更换，不改变任何验收结论。
同日按引用扫描删除 22 个无任何脚本、测试、文档或政策引用的本地文件：两个早期 readiness 清单
（20260912-v2/v3）、三个迁移审查探针和 17 个历史探针的测试文件；历史探针本身及其记录文档保留。
删除后公开结论清单重新验证通过，聚合器源码 pin 不受影响。
同日发现第二个新鲜检出缺陷：70 份文档共 344 个链接指向被 Git 忽略的 `artifacts/` 证据目录，公开结论验证器
原本要求每个本地链接目标存在，因此 clean-room 第 16 阶段在全新 clone 中必然失败。现改为：源码快照内的链接
必须存在；指向 `artifacts/` 且不在快照内的链接只做语法与不逃逸检查，单独计为
`evidence_links_not_shipped_with_source`，宿主与 guest 分类一致。宿主重算为 830 个已核对本地链接、344 个
未随源码交付的证据引用；在去掉全部 `artifacts/` 的模拟 clone 中除 11 个由生成阶段产出的
`proof/lean/generated/` 目标外全部可解析。这 344 个证据引用不因此变成已验证链接，仍须靠发布包与第三方复现补齐。

**2026-09-17 候选 `236c094` 的 VM 实跑：** 正式记录器再次完整跑完，delta 审查器越过操作清单检查后在 Sail 事务
备份断言处拒绝："missing Sail backups"。本机上 Lean 与 Rocq 两份 Sail 模型都早已存在，重新生成时都有旧输出可备份；
全新环境里 Rocq 模型在第 14 阶段第一次生成，事务如实记录 `old_*_saved=false`。审查器现按精确不变量核对：
事务声称备份时 before 清单里必须存在该路径，否则 before 清单里必须没有该路径下的任何节点并记为首次生成；
两种情形之外仍拒绝。失败运行 `…-run-20260917a`（约 239 分钟）保留。需要新的候选提交与推送后重跑。

**2026-09-16 候选 `349fbfd` 的 VM 实跑：** 第 1 到 13 阶段通过后，第 14 阶段的正式记录器在 guest 内完整跑完
（第二次 Lean、Rocq spike、两次全量输出清单、独立验收），delta 为 45,875 项新增、4 项修改，与本机已接受记录的
46,648 项新增、3 项修改同形。失败在紧随其后的正式 delta 审查器：它把"修改恰好 3 项"写死为本机历史形状，而 guest
多出的第 4 项修改是 `deps/sail-riscv/build/model/sail_smt_cache`——Sail 的 `--memo-z3-path` 求解缓存，在缓存尚冷的
新环境里被重新生成模型的过程改写，本机上它早已"热"。审查器现改为：操作只允许 added/modified，三项必现修改
（SOURCE_BASELINE、step-build.log、LLBC）必须在场，额外允许并显式绑定该缓存文件为 `solver_memo_cache`
（内容不是证据），其它任何修改仍拒绝；不放宽计数以外的任何规则。失败运行 `…-run-20260916e`（约 232 分钟）保留。
需要新的候选提交与推送后重跑。

**2026-09-16 候选 `3a368e5` 的 VM 实跑：** 代理修正后检出一次通过；第 1 到 13 阶段在 guest 内全部通过，其中
第 13 阶段 `lean-kernel`（`make proof-check BACKEND=lean`）首次在全新环境完成，第 12 阶段的负例、mismatch 清单与
演示录制也已产出。第 14 阶段 `rocq-spike` 的正式记录器在第一步就拒绝：`record_generation.py` 要求被 Git 忽略的
`artifacts/generation-runs` 目录预先存在。控制器现在在创建输出目录时一并创建 `generation-runs`、`proof-check`、
`rocq-spike`、`release-audit` 四个被忽略的证据父目录；输出清单对缺失的规范根本就容忍（本机也没有 `build/`）。
失败运行 `…-run-20260916d`（约 146 分钟）保留。需要新的候选提交与推送后重跑；预计单次完整运行 5 到 6 小时。

**2026-09-16 候选 `d3c373b` 的 VM 实跑与代理根因：** 检出日志这次成功带回：顶层克隆成功，两个子模块克隆报
"Failed to connect to github.com port 443"，是直连而非走代理时的错误；重试后整个检出阶段在 1800 秒超时。
诊断 VM 打印控制器视角的环境与 git 的 curl 详细输出后确认根因：guest 脚本用 `env -i` 启动控制器时把未设置的
小写 `https_proxy`/`http_proxy` 传成了空字符串，而 libcurl 规定小写变量优先且空值等于"不用代理"，于是 git 一律
直连 github；宿主与 guest 的直连链路时通时不通，正好解释了 2026-09-15 至 16 日检出阶段的随机失败与 TLS 断连。
修正：guest 只向控制器传递非空代理变量并镜像大小写；控制器的基础环境在存在代理时显式写入 git 的 `http.proxy`
并删除空的代理变量。失败运行 `…-run-20260916c` 与两个诊断记录保留。需要新的候选提交与推送后重跑。

**2026-09-16 候选 `9b3cdae` 的两次 VM 实跑：** 两次都在控制器的递归检出阶段失败（第 12 分钟与第 6 分钟），
发生在输出目录创建之前，日志留在 guest 内。用同一份 seed 起的诊断 VM 把日志打到串口后确认：bootstrap 克隆刚成功，
紧接着对同一仓库的正式克隆报 `GnuTLS recv error (-110): The TLS connection was non-properly terminated`，
是代理链路的间歇性 TLS 断连，宿主同一时刻对两个子模块仓库的完整克隆均正常。控制器现对 `git clone` 与子模块更新
做最多 3 次重试（失败的部分克隆先清空；commit 与子模块指针固定，重试不改变检出内容），`checkout`、补丁与
`fsck` 不重试；launcher 同时把 `week6-checkout-*` 的检出日志带回。两次失败运行 `…-run-20260916a/b` 保留。
需要新的候选提交与推送后重跑。

**2026-09-15 候选 `0dcac56` 的第六次 VM 实跑：** 第 1 到 11 阶段再次通过；第 12 阶段的 trap 最小化器拒绝
"未识别的重放环境：sail_compiler"。原因是控制器直接发起的重放没有把固定 Sail 编译器放到 PATH，差分工具记录
`sail_compiler: null`（runtime 阶段由探针自行补 PATH，所以其报告是正常的）。现已把固定 Sail 前缀加入三个
native 阶段的 PATH，并用第六次带回的 guest 二进制（差分工具、模拟器、配置）在宿主上实跑重放与最小化：编译器
身份被记录，4 次试验完成、状态 `minimized`（记录在该次证据根的 `week6-trap-localcheck/`）。清单核验与演示录制
依赖 guest 内的 CMake cache，未在宿主模拟，其调用形状与已接受记录一致。失败运行 `…-run-20260915f` 保留；
需要新的候选提交与推送后重跑。

**2026-09-15 候选 `305f50c` 的第五次 VM 实跑：** 第 1 到 11 阶段在 guest 内全部通过，首次在全新环境完成了
Sail 模拟器冷构建、Rust 模型重建、78 项 Rust 测试与 runtime 差分。第 12 阶段 `mutation-matrix` 的负例生成失败：
控制器把 trap 重放产物写死为 `original/candidate.json`，而差分工具按案例名写为 `trap-divergence-input.json`
（本地被接受的记录正是这样调用最小化器的）；已修正并加入负例生成形状测试。另一处：guest 回传证据时 cargo 目标
目录中的硬链接被 tar 记为 link 成员、宿主按规则拒绝，导致该次证据未解出（已从 raw 盘直接读取日志定位）；
guest 现以 `--hard-dereference` 打包。失败运行 `…-run-20260915e` 与其 raw 证据盘保留。这是第五、六个仅在
新鲜检出中暴露的缺陷；需要新的候选提交与推送后重跑。

**2026-09-15 候选 `7890148` 的第四次 VM 实跑：** 第 8 阶段 `rebuild-rust-model` 通过（诊断目录也已带回）；
第 9 阶段 `rebuild-sail-model` 在 sail-riscv 本地构建 GMP 的 configure 处失败，guest 缺 `m4`。同时发现一处
卫生问题：预检的 `rustup --version` 在仓库目录内执行，被 `rust-toolchain.toml` 触发自动向网络下载了一套工具链到
guest 的 `~/.rustup`（未固定的网络获取，虽未影响固定工具链的使用）。本轮不再逐阶段试错：把[固定宿主输入审查](release/FIXED_HOST_INPUT_REVIEW.md)
记录的全部 31 个宿主命令对应的 Ubuntu 包与系统动态库包一次性加入 guest 软件包列表；控制器预检改为核对
33 个宿主命令（opam、rustup、jq、m4 四个按哈希固定），探针在检出目录之外、使用一次性 Rust home 且拒绝任何
"syncing/downloading" 输出。本机预检干跑通过。失败运行 `…-run-20260915d` 保留；需要新的候选提交与推送后重跑。

**2026-09-15 候选 `e8928d6` 的第三次 VM 实跑：** 前 7 个阶段（递归检出、快照、Rust/Sail/Aeneas-Charon/Lean/Rocq
安装与固定编译器 CMake 配置）在 guest 内全部通过，六个工具身份与本机固定值一致；第 8 阶段 `rebuild-rust-model`
在 `rustup which` 处失败，因为 guest 没有 Ubuntu 的 `rustup` 包（宿主上 `rustup`/`cargo`/`rustc` 都是该包在
`/usr/bin` 下的代理）；同类缺口还有第 9、11 阶段需要的 `jq`。两者此前既不在 guest 软件包列表，也不在控制器固定的
宿主命令清单里。现已加入 guest 软件包，并按宿主二进制哈希与 opam 同样纳入预检；launcher 的证据回传扩展为同时
带回非 `week6-*` 运行目录中的小型诊断文件，避免失败报告留在 guest 内。失败运行 `…-run-20260915c` 保留。
这是第四个仅在新鲜检出中暴露的缺陷，需要新的候选提交与推送后重跑。

**2026-09-15 候选 `a105db3a` 的首次 VM 实跑：** 候选分支已推送；固定输入已作为 pre-release
`week6-fixed-inputs-v1` 发布，服务端摘要与匿名下载哈希均与固定值一致；guest 镜像已批准并经 Canonical 签名的
校验清单核对。两次启动都在真正执行 16 阶段之前失败，各自的 launcher 失败记录保留：第一次 SeaBIOS 把显式
挂载的证据盘当作第一块硬盘、引导失败后不再尝试 overlay（launcher 现给 overlay 设 `bootindex=0`，修正后引导
验证通过）；第二次 guest 内 apt、代理、GitHub 克隆全部成功，控制器却因全新 clone 里没有被 Git 忽略的
`artifacts/boundary-check/` 父目录而拒绝创建输出（控制器现自行创建该父目录并拒绝链接祖先）。这是第三个
仅在新鲜检出中暴露的缺陷；两处修正各有回归测试。控制器源码变更意味着 `a105db3a` 不再是可执行候选，
需要新的候选提交与推送后重跑。clean-room 仍未执行，五个外部槽仍缺失。

**外部槽验收器更新：** `clean_room`、`ci_download`、`release_package`、
`third_party` 已由 [v8 聚合器](release/AUDIT_RELEASE.md)接入严格 schema 和跨组件连接。
CI 必须实际离线验证 GitHub provenance attestation；发布包和第三方声明必须使用
仓库固定的 SSH allowed-signers，不接受报告自带公钥。当前政策中版本、交付 profile、
发布签名者和第三方签名者均未批准，真实报告也缺失；所以这是验收面补齐，
不是四个槽已通过。
政策固定的 `.github/workflows/week6-release.yml` 目前也尚未落地；现有 `ci.yml` 只有
fast/differential 路径，不能生成这里要求的五作业、clean-room 及 provenance 归档。
在版本/profile、签名者和可承载完整工具/生成物磁盘规模的 runner 确定前，不放置一个
只会伪装成完整流程的绿色 workflow。

**本轮生产辅助入口更新（尚未产生外部 PASS）：** 已把确定性 CI 证据归档、受限解包及
预发布聚合边界检查、GitHub Actions 外部只读收集/双下载重放、profile A 发布包构建及
已发布 release 的只读记录入口纳入 `scripts/`，并全部加入发布检查器源码 pin。另已加入
source-inventoried source-review policy 与确定性物化入口：最终候选根仓库必须干净，且只允许政策逐路径
列出的两项 CKB 补丁差异；当前未提交工作树实测在创建输出前拒绝。组合回归普通 Python
与 `-O` 各 **260 项**通过。历史 one-off 的正式 Lean/Rocq 输出记录器也已改为受限新目录的
source-inventoried production CLI，使用现有 validator 的同一份固定独立验收命令，并把自身源码复制进
记录以供哈希审计；尚未在未冻结工作树上启动昂贵的正式重跑。配套 formal-delta reviewer
也已生产化，并对历史正式记录实际预演：65 秒内逐项解释 46,651 个变化，普通/`-O` 分类负测、
record、独立 check 四阶段均退出 0，严格 validator 核对 133 个引用；该预演仍绑定历史 formal
源码，不冒充最终候选新执行。source/generation/output/approval
的带哈希输入也可确定性组成
v4 envelope；该入口强制保留 `final_generation_kernel_and_rocq_linkage`，只有聚合器随后核对
同一份 Lean/Rocq 报告才可能关闭，不能由 materializer 自行标绿。发布包验收现同时在线复核归档资产和签名资产的
唯一 URL、大小及 `sha256:` 摘要；本地有效签名不能再冒充“签名已随 release 发布”。
此外已生产化 fresh native runtime/Rust 记录器，以及 current-output 的扩展观察、additional
节点三分区审核和同根精确重扫确认；确认器实际进入既有严格组合 validator。它们仍未在未来
冻结候选上执行，不把历史 24-root 观察平移成当前证据，也不宣称输出语义已获批准。
固定 16 阶段 clean-room 编排器也已实现：URL 不进入 argv/JSON，source/formal/native/
output/public-claims 通过固定阶段连接，clean-room 内只生成未批准 v3 worktree envelope。
它尚未在经批准的临时 runner 与 digest-pinned container 中实跑，因此未生成 clean-room
事实。本地另以清除工具链覆盖变量后的环境逐一启动 Rust、Sail、Aeneas、Charon、Lean、
Rocq 版本命令，六项均退出 0，并据此修正了 Charon 必须使用 `version` 子命令的问题；固定包
中的 production Aeneas/Charon 身份也已与最终 formal resolver 对齐。Rust tests、runtime 和
负例生成三个阶段现分别使用独立 Cargo home，并把 PATH/RUSTUP_HOME 锁到归档 Rust 1.97.1，
不会退回容器默认 Rust。固定包仍明确标注 `host_closure_complete=false`，所以这只是可执行性
与编排核验，不是环境 clean-room。
clean-room 的 decoder 安装也已由只解包 payload 修正为正式 admitted installer：该入口会从
固定 bundle 重建 `base/public/join` 五个源码变体并产生安装收据；真实临时目录预演完成
27 个 clone/checkout/fsck/patch 阶段，随后正式 loader 复核 92 个 payload 文件和全部五个
源码变体。原先只存在 payload 的连接在全新 checkout 中不可满足 formal resolver，不能算作
有效 clean-room 路径。
2026-09-14 的只读远端核验还确认当前仓库属于个人账户，远端仅有现有 `CI` workflow，且没有
仓库级 runner。GitHub 当前官方规格把标准 Linux runner 的 SSD 列为 14 GB，而 larger runner
只向 Team/Enterprise 的组织或企业提供；因此候选中的 large-runner 占位符不能在当前个人仓库
直接获批。必须迁移到具备 larger runner 的组织，或另行审查能满足同等来源约束的分阶段/独立
临时环境方案；不能把 `ubuntu-24.04` 标准 runner 当成已经证明容量足够。
这些入口不创建 release、不上传、不签名、不触发 workflow。新物化器和输出链不伪造
profile-A 批准；该批准仍须由有权维护者在 output-identity 五件套完成后独立产生。
批准报告现强制逐字段绑定 current-output 的 observation、三份分区 review 与 confirmation，
所以必须在这些记录生成后签发，不能用只绑定源码的预批准替换任意输出审查。
clean-room orchestrator、字面量大容量 GitHub-hosted runner、
容器 digest、外部输入 URL、版本/profile/签名者批准和第三方复现仍未落实；因此旧报告均保留
历史源码身份，当前四个外部槽仍是 `missing`。

**最新本地实现：** [工作树源码部分验收器](release/WORKTREE_SOURCE_VALIDATOR.md)
已接入发布聚合器，重新计算完整源码清单并核对每项 HEAD 差异的审查记录。
现已增加[历史生成差异组合入口](release/WORKTREE_GENERATION_VALIDATOR.md)，连接固定
生成记录、完整前后观察和逐路径审查绑定；缺失源码组件与后续源码增量仍明确列为待办。
20:01:23 UTC 复核完成：232 次双模式测试通过，真实专用聚合核对 40 个引用及 10,021 项
差异后仍退出 2、`incomplete`。专用清单仅填生成组件，不替换下文 v10 历史清单。
该部分通过仍为 `incomplete`；生成物审计和最终交付审批未关闭，也没有制作真实候选
审查报告。修改后的聚合器来源不同于下面 v10 历史实跑和旧工作树复核快照，
不把旧报告当作当前入口的新 PASS。正式证明政策、原始计划及历史证据不改写。

后续新增[生成物节点清单与差异计算](release/GENERATED_OUTPUT_INVENTORY.md)：
九个必需输出根不可省略，独立运行目录须显式追加；记录全部节点，不跟随链接。
已新增[实际生成记录入口](release/GENERATION_EXECUTION_RECORD.md)，连接固定的配置、
Rust、Sail Lean/Rocq 命令与前后清单。19:27:25 UTC 实跑退出 0，19:30:51 UTC 记录复核
退出 0：四个生成命令、两次完整采集、35 个引用和 10,021 项差异已核对，源码前后一致。
1,012 个原路径删除节点均在事务备份中完整保留；仍不是生成物语义审批或 Week6 验收。
首轮 27 项测试双模式通过，但实际采集触发 1,800 秒时限，失败报告保留；
相同范围的新目录尝试改用 3,600 秒时限，完成两次 330,452 节点采集且零差异；
随后独立复核发现与旧清单不一致并退出 1。17:55:47 UTC 完成的全量内容比对逐根
保存观察，确定本次与旧清单的差异仅有 `target/flycheck2/stdout` / `stderr` 内容哈希；
18:01:58 UTC 的记录复核确认 12 个检查点、完整并集、差异、计数和保留日志一致。
详见[生成物记录](release/GENERATED_OUTPUT_INVENTORY.md)。这是非原子观察的完整差异，
不追溯认定前次失败扫描的全部差异，也不证明实际重生成或日志语义已获批准。
失败记录和旧哈希保留；本次状态文档更新不回填旧源码快照。
19:38:42 UTC 完成[10,021 项生成差异的逐路径说明](release/GENERATED_DELTA_REVIEW.md)，
19:41:00 UTC 绑定复核及 28 次解析测试完成；含 52 个锁定包归档、1,691 个包内文件、
3,612 份源码副本和四组 CMake 依赖集合的核对。缓存/元数据仅保留，不批准作为发布负载。
这些旧差异说明现已接入只读部分校验；本次 kernel/Rocq 与最终生成身份已由新正式记录连接，
新的 46,651 项输出差异已有独立说明，不能套用旧 10,021 项结论；后续源码和支持输出
增量、最终范围及完整工作树审计仍待完成，新格式的记录绑定已由上述分支接入。
本轮 LLBC/provenance 已变化；v10 Lean/Rocq 归档保留历史身份，不当作当前生成状态的新 PASS。

**需用户决定的宿主变更：** 06:01–06:03 UTC 的环境查询意外触发了本机 `lxc`
包装脚本自动安装 LXD、core24 和 snapd snap。已停止客户端，取消安装因权限不足未成功；
助手未手动初始化或创建容器，也未执行卸载。进一步 LXD/宿主环境操作暂停，详情及影响见
[非预期安装记录](release/LXD_WRAPPER_SIDE_EFFECT.md)。不能据此宣称 clean-room 完成。

**历史 `7ced9f42…` 正式入口迁移记录。** [当时的正式门禁](release/FORMAL_MAIN_INTEGRATION.md)
于 06:26 UTC 退出 0，06:29 UTC 独立验收通过：28 主阶段、287 测试、48 公开阶段、68 公开定理。
release/Rocq 检查器已接入新 profile；[v10 清单](release/local-readiness-20260913-v10.json)
接入完整 Lean 归档，06:34 UTC [实际聚合](release/AUDIT_RELEASE.md)完成：六项组件验收通过，
六类发布义务缺失，`incomplete`、退出 2，不是 Week6 PASS。
原 v8 归档保持历史身份；因政策和检查器源码已改变，
不能再把 v8 的旧输入快照当作当前完整来源验收；新正式组件报告已另行生成。

## 当前摘要（历史记录见后文）

| 层次 | 当前结论 |
| --- | --- |
| 正式批准输入的 Lean 门禁 | 当前主政策 `b5bdc401…` 的 [完整正式执行及独立验收](release/FORMAL_FINAL_EXECUTION.md)已通过（28/287/48/68）；32 文件归档保存原始报告与日志。`7ced9f42…` 及更早结果仅保留各自历史身份 |
| 原正式 v8 本地验收证据 | 历史 `ca6e062b…` 来源下六项组件通过，聚合仍 incomplete。旧输入快照不代表当前来源；本次已另行刷新组件并建立 v10，旧报告及失败记录不改写 |
| 维护者演示 | [22:31 UTC 当前录像及独立验收](release/FINAL_SUPPORT_REFRESH.md)完成，实际执行 33 案例、194 项适用 mutation、ADD 和已知 trap 重放；旧 32 案例录像保留历史身份，不替代 Lean、clean-room 或发布 |
| 新工具实际提取 | 主生产、公开 decoder、full-MIR iterator 及三份下层模型均已重提取；两处 map 定义变化有 kernel 等价证据，原 raw 政策仍拒绝新身份 |
| 主生产 Rust 暂存入口 | [正式实跑](release/FORMAL_MAIN_INTEGRATION.md)于 05:32:50 UTC 完成 13 阶段，生成 Lean 全文件相同；模型与新 LLBC 已由正式生成器一并安装。此前候选暂存报告保留候选身份，不计为 clean-room |
| 新公开根的无项目缓存重建 | 候选第六轮 66 阶段与随后正式 48 阶段分别完整通过；本次正式主构建 1,865 项、原定理/合同审计及两类公开负测通过；候选前五轮及首次正式失败记录不改写 |
| 新工具资格 | Charon UI 双侧对照及[独立失败诊断报告](release/REBUILT_CHARON_DIAGNOSTICS.md)完成，但非全量 PASS；borrow、局部 fnptr、循环及 guard 固定回归完成，均不代表一般编译器正确性 |
| Sail C++ 差异 | [受限标记对应](release/SAIL_CPP_CORRESPONDENCE.md)及[完整冷构建](release/REBUILT_SAIL_CPP.md)完成；[实际新模拟器差分](release/REBUILT_SAIL_RUNTIME.md)38 阶段通过：32 案例、188 项适用 mutation 和 32 次重放；非一般执行等价证明 |
| 工具和提取配置正式采纳 | [独立候选](release/REBUILT_MAIN_CANDIDATE.md)与新正式基线分别完成完整门禁及独立验收；各自 30 文件归档保留各自政策身份，候选 PASS 不归给新政策 |
| 正式接入审查 | 04:21 UTC 审查发现的旧验收清单、CMake 和 Rocq 上下文缺口已落实接口及测试，并完成政策/构建切换与新正式完整验收；新清单为 28 阶段/287 测试，Rocq 为显式双 OPAM 上下文 |
| 同候选的新 native 验收 | 03:17:54–03:21:08 UTC 实跑并独立验收通过：32 案例、188 项适用 mutation、32 次重放、78 Rust 测试（含 10 项真实引擎）；私有工具闭包、源码与生成物首尾一致。新入口 10 项回归测试通过，提前启动拒绝记录保留；不替代完整主门禁/Rocq 验收 |
| 新正式 native 验收 | [20:10–20:13 UTC 实跑](release/WEEK6_RUNTIME_FLOOR.md)及独立验收完成：33 案例、194 项适用 mutation、33 次重放、78 Rust 测试；完整形式链重生成后的只读复验也通过，不扩大为 clean-room 或 Week6 PASS |
| 新正式 Rocq / 聚合 | [本轮 11 阶段 Rocq 及独立验收](release/FORMAL_FINAL_EXECUTION.md)完成，仍为 NO-GO、无额外证明；[22:35 UTC 新聚合](release/FINAL_SUPPORT_REFRESH.md)六项通过、六项缺失，整体 incomplete。06:34 UTC v10 仅属旧来源，当前政策拒绝其旧 pin |
| 同候选的新 Rocq 输入与连接 | 03:40:27–03:53:53 UTC 全链重跑及独立验收通过：新 Sail Rocq 输入、该候选新提取 LLBC、显式双 OPAM 根和受审支持库，原十阶段 NO-GO/最小复现均确认；14 项入口测试通过。首轮缺支持库失败和旧驱动保留；不编辑原 spike 或编译器源码，额外证明覆盖为 false |
| Week6 发布证据 | 当前 runtime、Rust tests、Lean、Rocq、负测、演示已通过新聚合的独立重验。clean-room、最终 worktree 审计、CI 下载重放、release 包、独立第三方复现及发布结论审计仍未关闭 |
| 固定安装包容器 | gzip 包 3.18 GB 超 GitHub release 2 GiB 上限；2026-09-15 同内容 xz 重封装 1.80 GB、独立验收暂存 56,702 项通过；清单哈希不变，控制器/launcher 固定新包哈希 |
| 独立临时 VM 执行路径 | [复审](release/EPHEMERAL_VM_STAGED_PROVENANCE_REVIEW.md)完成：政策允许的 VM provider 已有 launcher、operator-attested 记录、聚合器绑定与 CI intake 候选；控制器新鲜检出缺陷已修正但未在新环境实跑；guest 未启动、候选未推送，`clean_room` 仍缺失 |
| 实际远端 CI 来源 | [05:12 UTC 只读核验](release/CI_READINESS.md)：本地 HEAD 的运行数为 0，最近五次成功均为旧提交 `1ef21d…`，最新只有 Rust/差分两个 job；旧 artifact 仅查询元数据，未下载或重放，不能充当本轮 CI 证据 |
| 安装输入分发准备 | [06:40–06:42 UTC 核验](release/INSTALL_DISTRIBUTION_REVIEW.md)完成六组 8.27 GB 安装哈希及额外 OPAM 控制文件观察；复制 Sail 前缀的四步 smoke 通过，五个生成文件与旧 smoke 相同。报告绝对路径绑定、完整 OPAM/宿主依赖及整套分发仍未关闭，不计为 clean-room |
| 固定路径安装补充包 | [第三轮完整打包及独立验收](release/FIXED_INSTALL_BUNDLE.md)于 07:23/07:29 UTC 完成：56,702 项、约 3.18 GB 压缩包，含目录和独立 Sail Git 源码；23 项测试双模式通过，两轮失败保留。不扩大为工具可运行或 clean-room 完成 |
| 同快照源码交付 | [源码归档及实际离线递归复原](release/FIXED_SOURCE_CAPSULE.md)完成：17 个 Git 阶段、1,783 个源文件，独立复核通过；约 86 MB 归档也已校验。[交付准备清单](release/fixed-input-handoff-20260913-v1.json)连接三类输入，不替代 worktree 语义审计或第三方复现 |
| 统一固定输入恢复 | [恢复入口及独立验收](release/UNIFIED_FIXED_RESTORE.md)完成：16 个命令阶段、冻结源码、56,702 项安装内容及恢复副本的 decoder 校验；08:09 UTC 独立验收通过，首轮父目录误报记录保留。已有生产目录保护实测拒绝覆盖，19/23 项测试均双模式通过。仍无 canonical 部署、宿主闭包、工具运行或新环境全链 PASS；四文件 bootstrap 仅有限检查、不属于冻结候选 |
| 宿主前置条件静态记录 | [08:18/08:22 UTC 执行与独立复核](release/FIXED_HOST_INPUT_REVIEW.md)完成：673 个 ELF 路径、650 份不同内容、13 个关键文件跨读取程序核对，18 项测试双模式通过。库名候选不等于实际装载或 ABI 兼容；两份 Lean glibc 支持文件的 Nix 解释器路径本机缺失，未据此推断 Lean 主程序失败，亦未修改工具或宿主 |
| 冷构建下载输入 | [四项 CMake 下载补充包](release/FIXED_CMAKE_DOWNLOADS.md)已按冻结源码 SHA256/SHA3_256 保存并独立校验，8 个损坏负测完成；后续[实际冷配置与 GMP 构建](release/FIXED_CMAKE_CONFIGURATION.md)08:36/08:39 UTC 执行和独立验收通过：9 阶段、三项显式本地源码覆盖、GMP 哈希跳过下载并构建，17 项测试双模式通过。未改 handoff v1；未接入正式构建路径、未构建完整模拟器或运行新环境全链，也不是网络隔离或完整 build-input 闭包 |
| 主要公开文档结论复核 | [六份主要文档的核心结论复核](release/PUBLIC_CLAIMS_REVIEW.md)完成：修正旧正式状态、Rocq 过强措辞、CI 配置/执行混淆、初态与上游测试推断；实际重算 32/395/188 和主门禁 28/287/48/68，核对 136 个本地链接。不是全部发布文档/结论的完整审计，`public_claims` 仍缺失；文档更新不归入旧冻结源码身份 |
| 工作树来源差异复核 | [当前快照与冻结交付的逐文件审查](release/WORKTREE_DELTA_REVIEW.md)另列完整 HEAD 差异和冻结后增量，并核对辅助入口的验证来源；精确快照及执行结果见该页机器报告。此项不替代最终交付范围的全部语义审批，`worktree_audit` 仍未关闭 |

后文按执行时间保留历史状态；某次旧失败或阶段性“待完成”不覆盖本摘要，但也不因后续
进展被回写为成功。完整证据链见各项链接报告，不能将不同范围的报告拼成发布 PASS。

## 历史起点复核（不是当前工作树状态）

本轮开始时主仓库 HEAD 为 `872d225`，主仓库 worktree 干净，CKB 子模块保留已采纳的
runtime-container 补丁。开始时主证明政策 SHA-256 为
`079f22a9e9f04868d42c337a9eb02c083e5e6e1f3cb7a1b6cc1eaa8eba1e54c0`，
本轮开始的 `local_sources()` 与政策完全一致。
现存主报告记录 2026-09-10 04:09:27–04:43:34 UTC 的 `passed`；这只是先前执行记录，
不能当成本轮或第三方 clean-room 报告。

## 原始任务逐项对照

| Week6 任务 | 当前证据 / 缺口 | 关闭所需 |
| --- | --- | --- |
| 完成 Verification Guide，区分现有与新增命令 | [VERIFICATION.md](../VERIFICATION.md) 已修正“具体 Sail 前提未证明”和旧 CI 二进制安装说明；新增输入包使用记录 | 继续审计发布级公开结论；逐条实跑完整新流程 |
| 固化环境、smoke、mutation、Lean、Rocq 入口 | 五类入口及独立 Makefile 的 `audit-release` 已实跑；当前六项组件已通过新聚合重验，整体仍 incomplete；v8/v10 保留历史身份 | 完成剩余发布条款和完整 clean-room 流程实测 |
| coverage、semantic gaps、TCB、保证边界 | ADD 原主根 137 项、公开根 158 项依赖及工具补丁已有政策；不能消除取指/初态/物理内存边界 | 发布清单绑定来源/依赖/工具身份及各项公开结论 |
| 每个 mismatch 保存分类、最小输入、重放命令 | 本轮三类语义负测已有分类、有限子序列最小化与真实重放证据；当前 corpus 无意外 mismatch | 最终候选/CI 如产生新差异仍须逐项归档审查，不将有限最小性扩大为根因证明 |
| 发布版本、配置哈希、CI 日志、下载 artifact | 当前 CI 有 Rust/差分及上传后下载重放，但没有全套 release 聚合门禁 | release candidate、版本/哈希清单、完整 CI 运行及发布下载记录 |
| 录制简短维护者演示 | [22:31 UTC 当前 33 案例实际录像](release/FINAL_SUPPORT_REFRESH.md)、真实播放与独立验收已完成 | 随最终候选打包并保持输入身份有效，不替代其他条款 |
| 公开结论追溯 | ADD 层已有完成审计；Week6 发布级证据还不完整 | 发布结论逐项链接到对应本轮证据，缺项保持未完成 |

## Clean-room 各项（早期记录与当前缺口）

下列重建记录按各自执行时的身份保留；其中“尚未采纳”等描述属于早期阶段。
后续公开 v2 已采纳并通过旧主入口完整验收，新的正式主工具迁移、Rust/Sail 生成、native
和 11 阶段 Rocq 进展以顶部摘要及 [正式接入记录](release/FORMAL_MAIN_INTEGRATION.md) 为准。
这些分项记录仍不构成从普通 clone 开始、完整安装与全链执行的 clean-room 证据；
受审安装输入及私有工具目录尚不随普通 clone 提供。

- 递归 clone、固定 submodule：已在本机三个独立 Git clone 中复原精确 HEAD＋工作树快照，
  无对象硬链接/alternates，CKB 补丁校验通过；这不是第三方远程递归 clone，见
  [隔离基础重建](release/ISOLATED_FOUNDATION.md)。
- 锁定工具安装：[Rust/Lean 独立安装](release/ISOLATED_RUST_LEAN.md) 已完成：全新工具目录中
  安装 Rust 1.97.1、指定 nightly 和 Lean 4.31.0，版本、二进制及编译 smoke 通过。
  [Rocq/OPAM 独立重建](release/ISOLATED_ROCQ.md) 也已完成：21 个固定包源码重建、
  精确编译器约束审计及既有输入上的十阶段 NO-GO 复验通过。
  [Sail 独立重建](release/ISOLATED_SAIL.md) 已完成 56 包及固定 commit 的源码构建，
  C / Lean 生成 smoke 通过；新二进制与既有政策哈希不同，身份审查/采纳仍未完成。
  [后续 ELF 审查](release/SAIL_MODEL_IDENTITY.md) 已定位主程序三个目录配置字段并核对
  全部原生插件。原完整比较在旧工具侧发现一个历史残留文件后失败；
  [独立清理与候选比较](release/SAIL_STALE_GENERATED_FILE.md) 已结束：清理后主 kernel / 边界通过，
  候选 Lean / Rocq 原始输出一致，但 C++ 两文件不同，整项工具比较仍失败。
  [full-MIR 独立重建](release/ISOLATED_FULL_MIR.md) 也已完成，46 个新库哈希均不同于
  原批准输入；[新 sysroot 实际重提取](release/FULL_MIR_REEXTRACTION.md) 的 11 阶段已通过，
  公开 decoder / iterator 的生成模型匹配既有身份规则，正式资格采纳及 kernel 链仍待完成。
  [Charon 双版本独立源码重建](release/ISOLATED_CHARON.md) 已完成，但新二进制身份和生产资格仍待审查。
  Aeneas 的[116 包依赖环境重建与收尾审计](release/AENEAS_OPAM_DEPENDENCIES.md) 已完成，
  [编译器双版本源码重建](release/ISOLATED_AENEAS.md) 的 20 阶段已完成，三份完整模型匹配；
  此项复用原 LLBC，尚未采纳新工具。
  后续[新工具联合提取](release/REBUILT_EXTRACTION_CHAIN.md) 已在同一候选中实际重提取
  主生产、公开 decoder 和 iterator，20 阶段及完整模型比对通过；资格与 kernel 全链待完成。
  公开 decoder 的工具、物化标准库、相对路径 harness、LLBC 和资格证据已有可安装分发包，
  并用包内输入实测重提取，见 [输入包记录](release/DECODER_INPUTS.md)；
  正式主门禁已切换并全量重跑，旧 `outer/Cargo.toml` 绝对路径不再是正式入口。
  这仍不等于完整工具环境 clean-room。
- 合并配置、双方生成物重建：隔离副本已冷构建 Sail 模拟器并重建合并配置；
  双方 Lean/Rocq 提取生成物及完整工具安装仍待完成。
- Rust tests、runtime、mutation、Lean、Rocq：隔离副本中 78 项 Rust 测试、32 案例及重放、
  188 项适用 mutation 已通过；Lean/Rocq 完整链仍待运行，不能拼接旧 PASS。
- 生成后的 worktree：已记录基础重建前后精确源码快照且无漂移，CKB 补丁显式标识；
  最终候选的完整差异语义审查和全链生成后审计仍待完成。
- 第三方仅按文档复现：需要独立执行者及其原始记录；助手本机的第二目录不是第三方。

本机 Docker CLI 存在，但当前进程无权访问 daemon；这不是已执行容器 clean-room 的证据。
先完成不依赖该权限的实现和安装输入整理，不能因此直接把整个目标标为阻塞。

## Release gate

| 条款 | 当前判定 |
| --- | --- |
| ADD/ADDI/BEQ 至少 10 个案例严格比较 | 新 33 项（13/10/10）/398 步严格比较及33次复制重放通过，满足本地数量门槛；旧 13/10/9 被新检查器拒绝。CI/release 下载仍待实测 |
| 5 类 mutation 全被检测 | [本轮 6 个字段类别、198 项矩阵](release/WEEK6_RUNTIME_FLOOR.md)：194 项应用且正确定位、4 项不可应用；完整 clean-room 中仍须运行 |
| Lean ADD kernel 通过，生产连接可审计 | 当前 `b5bdc401…` [完整门禁及独立验收](release/FORMAL_FINAL_EXECUTION.md)通过（28/287/48/68），32 文件归档保存；正式 delta 说明已复验，最终范围审定与完整工具安装 clean-room 仍待完成 |
| Rocq GO/NO-GO 有最小复现 | [本轮 11 阶段实跑及独立验收](release/FORMAL_FINAL_EXECUTION.md)完成，实际新生成 Sail 输入，并从同一政策绑定的 LLBC 翻译 Rust；仍为 NO-GO、无额外证明，不能替代完整 clean-room |
| 零未说明占位 / 上游假设受审 | 现有 Lean 政策记录支持库四处 sorry 及最终根的精确依赖；release 检查不能只做 grep 计数 |
| release 含版本、哈希、覆盖、非目标、重放 artifact | 尚未制作或发布本轮完整包 |
| 不夸大为整个 CKB-VM 已形式化验证 | 保持 conditional、runtime-only 及 post-MVP 排除范围；仍需最终公开文档审计 |

## 本轮推进顺序

1. 修正 Rocq spike 误报成功路径，保存结构化报告和两侧最小复现。
2. 使固定工具/资格证据/提取输入可在新 clone 安装和核验，处理本机路径依赖。
3. 实现 `audit-release`，组合新运行、来源、runtime/mutation、Lean/Rocq、重放与包内容检查。
4. 实测隔离全环境流程，补 CI 全量作业、下载重放、版本清单与演示。
5. 收集独立第三方复现及经确认的发布证据；逐项验收后才关闭 Week6。

第三方执行者及发布位置/方式已向用户征询；本地实现继续推进，不冒填外部证据。

## 2026-09-11 已完成的第一项

`make proof-spike` 于 08:10:24–08:15:13 UTC 实跑，返回 0；结构化报告为
`status=passed`、`verdict=NO-GO`、`extra_proof_coverage=false`。
报告和十个阶段日志见 [run-rbx9livc](../artifacts/rocq-spike/run-rbx9livc/report.json)，
报告 SHA-256 为 `653ef3badf9a52586e29104fe58f8e270e4f8dccc24cdeac54ca722b7571107f`。
已独立重读所有阶段日志、诊断及输入哈希，并确认 Lean 主政策和冻结源码未变化。

新增 [16 项检查器测试](../scripts/tests/test_rocq_spike.py) 在普通 Python 和 `-O` 下通过，
覆盖缺失输入、错误版本、错误原因、意外成功、信号/资源失败、重复错误、超时及旧目录保护。
详情见 [Rocq 记录](../proof/rocq/SPIKE.md)。这不是全环境重建或第三方复现记录。

## 同日搬迁验证

新增[可搬迁 harness 与身份比对](../proof/lean/decoder/toolchain/public-harness/README.md)。
独立 clone 中的重新提取通过；生成物的差异只在 373 行来源注释前缀，其他全部字节
与批准模型相同，原始输出未改写。首次严格原始哈希拒绝的报告保留；后续通过报告为
`decoder-relocation-ap1v51hl/report.json`。10 + 9 项新测试均通过普通与 `-O` 模式。

这解决了路径变化是否会改变提取语义的实测问题，但还不是正式政策迁移或完整安装。
原位置的 full-MIR 标准库有 46 个外链，两个候选工具 Git checkout 依赖本机 alternates。
本轮已在新输入包中物化库文件，并导出完整独立 Git 历史；原目录保持不变。

## 同日公开解码输入包

[输入包记录](release/DECODER_INPUTS.md) 保存制作、安装、包内工具真实重提取的命令和哈希。
v3 包 68 个输入文件，归档约 160 MB，安装为新目录；标准库零外链，工具源码无 alternates。
`decoder-relocation-8r4cdxxr` 的七阶段重提取通过，公开模型仍与批准版本一致。
v1 历史 Git 对象缺失及 v2 清单权限拒绝均保留失败记录，未改写为成功。
新增包校验 21 项、安装位置检查 7 项测试在普通 Python 与 `-O` 下通过。
随后补齐迭代器：`decoder-relocation-495a5xcb` 九阶段全部通过，公开主模型与迭代器分别
只有 373 / 20 处来源注释位置需要映射，其他字节仍匹配原批准哈希；新增 10 项身份负测通过。
首次迭代器原始哈希失败的 `decoder-relocation-vpr7ubuz` 报告保留，未修改成成功。
检查器全量发现执行为 189 项（包含真实 Lean 负测），普通 Python 与 `-O` 均通过；
主门禁固定测试列表尚未纳入新增项，不能声称主门禁本身已执行这 189 项。
这不是主门禁新 PASS、完整环境 clean-room 或对外发布；正式政策迁移与主门禁接入仍待完成。

## 同日正式输入布局迁移（完整门禁通过）

随后已完成[正式调用层/政策/验收器迁移](release/PUBLIC_INPUT_MIGRATION.md)，安装至
`artifacts/decoder-inputs/public-v1`。新增 5 组输入测试纳入主门禁；相关 130 项测试
在普通 Python 与 `-O` 下通过。差异审计确认定理、合同、模型与工具身份及原计划字节不变。
新主政策为 `c8315684cf73d118703f98982e79303943d8c52d49e72d99117de25301b3a1af`。
本轮 `make proof-check BACKEND=lean` 于 09:16:03–09:49:41 UTC 实际完成并退出 0；
21 个主阶段、185 项门禁测试及 47 个公开子阶段通过。完成后独立重验全部引用日志、
公开证据验收、来源政策与类型/定义/合同快照；归档主报告 SHA-256 为
`66fb26d92860e6dde6198d1657a9aaf85b3d18f2c608033cb0340d69628a0dab`。
这关闭的是正式输入布局迁移，不是整个环境从零安装或 Week6 发布验收。

## 同日 mismatch 最小化实测

新增[独立最小化工具及证据](release/MISMATCH_MINIMIZATION.md)。对仓库原有真实 trap
差异，在两端重新执行后，将三条指令缩减为单条 `0x0000107b`，再次执行和独立 CLI
重放均保留 `pc_after` 差异，分类为已声明的 `unsupported`。原始 artifact 未改写。
预算为 2 的真实负测退出 2、报告 incomplete；19 项测试在普通 Python 与 `-O` 下通过。
这补齐一个真实 mismatch 的完整记录和可用工具，发布聚合门禁仍需覆盖本轮全部失败。

## 同日本地 runtime 证据组件

新增[证据校验器、运行入口和实跑记录](release/RUNTIME_EVIDENCE.md)。入口先核验
CMake 固定的 Sail 源码版环境，再在空 Cargo target 中构建 CLI，运行完整 corpus /
mutation，复制 33 个 JSON 并将 32 个案例逐一重新执行。10:40:40–10:41:17 UTC
的 35 个阶段全部退出 0；完成后独立重读日志、哈希、双端 trace 与 mutation 矩阵通过。
报告 SHA-256 为 `a8cfa59d758ab5c4c4237410f1b0617fe1cc0f422ab368289a9af35f6bbbba53`。
21 项检查器测试在普通 Python 和 `-O` 均通过，主 Lean 冻结政策和源码未改动。

早先本轮运行记录使用 PATH 中的 Sail release 版，虽 trace 一致但没有计入环境验收；
新入口明确选择 CMake 固定编译器并检查完整版本。旧记录保留，未改写身份。
该组件复用现有 Sail emulator，不是全环境重建、CI 下载重放、独立第三方或发布。
此时 `audit-release` 聚合仍未实现；翌日进展见下。

## 2026-09-12 聚合 readiness v1

新增 [`audit-release` 聚合入口](release/AUDIT_RELEASE.md)，通过独立
`scripts/release.mk` 调用，未修改冻结主 Makefile 或证明政策。
本机绑定哈希的清单实跑退出 2、`status=incomplete`：runtime、Lean 和当前政策
Rocq 记录重新验收通过，另九类条款明确缺项。v1 没有发布成功路径，未把本地复核
计为 fresh execution、clean-room 或 Week6 完成。21 项新测试普通和 `-O` 均通过。

旧 Rocq 记录因绑定迁移前政策被拒绝；本轮另行 `make proof-spike` 于
03:31:07–03:35:43 UTC 十阶段完成，绑定当前政策并确认两侧原 NO-GO，未增加证明覆盖。
聚合实跑报告为 `artifacts/release-audit/run-rd7hoddj/report.json`，SHA-256
`2ded3a990aeae19da75c5d4e8c5bfc50583077a2dd2fabb42172e304dcbedc22`。
待接入的九类是 clean-room、完整 Rust 测试、mismatch 清单、工作树审计、CI 下载、
发布包、演示录像、第三方和公开结论；提供文件本身不会替代尚未实现的验收器。

## 同日 readiness v2：完整 Rust 测试与部分 mismatch 清单

[Rust 测试入口](release/RUST_TESTS.md) 在空 Cargo target 中编译，逐目标列举和执行：
7 个二进制、78 项测试（含全部 10 项真实引擎测试）、0 ignored / filtered-out；
5 个 doctest 目标实跑，当前 0 用例。03:48:23–03:48:45 UTC 十九阶段通过。

修正最小化工具的 trace_length 末尾位置检查，并[重新采集和最小化 trap](release/MISMATCH_MINIMIZATION.md)。
独立清单验收重读真实 trace 和有限搜索步骤；不同输入流与缺失末尾事件需要双方程序
的配对证据，仍报告未完成。本轮 71 项相关检查器测试普通和 `-O` 均通过。

[v2 聚合](release/AUDIT_RELEASE.md) 于 03:52:10–03:52:28 UTC 实跑退出 2：
runtime、Lean、Rocq、Rust tests 四项复核通过；mismatch incomplete，另七类缺失。
报告 SHA-256 为 `fbc46b22fe53f5980e0df45ccbe0d84f3350151f4efce408601cf3f998cdc821`。
原计划、主 Makefile、Lean 冻结政策未改动，Week6 和发布仍未关闭。

## 同日 readiness v3：配对输入负测清单通过

[配对证据程序](release/PAIRED_NEGATIVES.md) 在空 Cargo target 中构建库并链接现有
runner/比较器，不改生产源码。两项最小化分别完成 37 / 12 次真实双端执行，
最小总长度为 4 / 3；分别从字节相同的复制输入重放并保留原负测要求，退出 1。
最终报告 `paired-negatives-4ui2afuf/report.json` 共 54 阶段，预算为 2 的负测则正确
返回 incomplete、退出 2，并被验收器拒绝。

04:15:19–04:15:38 UTC 的 [v3 聚合](release/AUDIT_RELEASE.md) 报告 SHA-256：
`93861f8122ac586de4514a917c5d483ffa296fd900fbed0edc8aa13fab81172a`。
runtime、Lean、Rocq、Rust tests、mismatches 五项复核通过，另七类仍缺失，整体退出 2。
128 项相关检查器测试普通和 `-O` 均通过；原计划、主 Makefile、Lean 冻结政策未改动。
本次只关闭明确的本轮三项语义负测产物清单，不是所有历史失败或 Week6 发布完成。

## 同日隔离基础重建通过

[隔离源码与基础重建记录](release/ISOLATED_FOUNDATION.md) 保存 06:20:14–06:42:19 UTC
的 13 阶段实际运行、冷构建模拟器和配置、78 项 Rust 测试及完整 runtime/mutation/重放。
1,617 个源码文件的快照在复原、生成及测试前后完全一致，并完成独立只读复核。
报告 SHA-256 为 `8a7e2b4dbc8e92781d13f18d315805fbdaa6f4f99617f3b45f71f8922883280d`。
初次 README 误判的失败保留，17 项新测试和 128 项既有检查器测试在普通及 `-O` 下通过。

这里复用本机工具/支持库/缓存，未安装完整环境、未跑隔离 Lean/Rocq 链。
被验证的身份是报告中的 HEAD＋工作树快照，不是裸 HEAD；本节等后续文档更新不在该快照中。
readiness v3 新复核仍有七类缺项，Week6 未关闭；下一步为独立工具安装与双方完整提取/证明链。

## 同日 Rust / Lean 独立安装通过

[安装记录](release/ISOLATED_RUST_LEAN.md) 保存 06:52:45–06:59:43 UTC 的 20 阶段执行。
全新 `RUSTUP_HOME`、`CARGO_HOME`、`ELAN_HOME` 中的两个 Rust 版本和 Lean/Lake 已安装，
六个关键二进制匹配既有基线；两个 Rust 程序和一个小型 Lean kernel 编译检查通过。
报告 SHA-256 为 `80058acabeef59e0eb424aa2028a28a7018e4acad0da8531da83db9b4bc9cbad`。
安装文件清单和日志已独立复核；15 项新测试及 17 项快照测试在普通与 `-O` 下通过。

本次仍复用宿主系统与安装器，不是新 ADD 证明或完整 clean-room；
其余翻译器/OPAM 环境、full-MIR 标准库重建及同一候选的完整执行链仍待完成。
原计划、生产源码及主/公开 Lean 政策未修改，七类完整验收缺项不变。

## 同日 Rocq / OPAM 独立重建通过

[Rocq 重建记录](release/ISOLATED_ROCQ.md) 保存 14:00:25–14:17:17 UTC 的 13 个外层阶段，
21 包源码重建及使用新 Rocq 的十阶段原 NO-GO 复验全部通过。
报告 SHA-256 为 `3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540`。
实际编译器 invariant 已精确固定；OPAM 导出唯一缺少的 compiler 清单行被显式审计，
其余包元数据保持一致。首轮验收失败及后续诊断保留；第二轮未复用首轮构建。
8,659 项安装文件及日志已独立复核，32 项相关回归测试普通与 `-O` 通过。

该新根仍复用宿主系统/安装器，包构建没有 OS 沙箱；Aeneas 和既有 LLBC/Sail 输入也复用。
没有增加 Rocq 证明覆盖，Sail/Aeneas/Charon、full-MIR 和同一候选全链验收仍待完成。
原计划、生产源码与证明政策未迁移；Week6 和七类完整验收缺项保持未关闭。

## 同日 Sail 独立重建完成，工具身份待审查

[Sail 重建记录](release/ISOLATED_SAIL.md) 保存 15:21:14–15:29:49 UTC 的 18 个成功阶段。
新 OPAM 根重建全部 56 个固定包，独立源码 clone 编译固定 commit 的 Sail；
C / Lean 小型生成检查通过。报告 SHA-256：
`a765bc5f4cbaa9af62909ea9cd1e1d2af50a5b9f8437aaf80a7be0cf91b88739`。

入口整体返回 2：新 Sail 执行文件哈希 `783dd162…` 不同于政策中的 `5ea16bff…`，
因此状态为 `isolated_sail_rebuild_identity_review_required`，没有自动刷新政策。
新旧小型 smoke 的 C 和四个 Lean 文件逐字节相同，全部 146 项 Sail 支持文件也相同；
这不证明完整模型或二进制等价。两份 ELF 含不同安装/调试路径，尚未穷尽其他差异。

1,099 项新 Sail 安装清单、6,791 项新 OPAM 安装清单、源码、输入及日志已独立复核。
47 项相关测试普通及 `-O` 通过，首个主动中止候选的失败记录保留。
原生产源码/证明政策不变；还须审查新工具、重建其余提取链，并在同一候选上全量验收。
无 OS 沙箱、无第三方复现、无新 ADD 证明，Week6 七类完整验收缺项不变。

## 同日 full-MIR 独立重建完成，提取资格待核验

[full-MIR 记录](release/ISOLATED_FULL_MIR.md)：15:50:47–15:52:17 UTC，使用此前独立安装的
固定 nightly、空 Cargo 缓存和新 target 构建标准库，46 个文件全部生成并物化为无外链 sysroot。
外层报告 SHA-256：`13d82971a424442ea3fc4fbd4deda0672cb1725c0cda9e32817465830a618516`。
实际 Cargo 构建退出 0，但 46 个文件哈希均不同于原批准库，外层返回 2、身份审查待完成。
未替换正式输入，未声称差异只有路径；后续真实重提取已完成，见下节，正式资格仍待采纳。
Rust 完整安装清单、旧/新库、日志、资产和政策已独立复核，11 项新测试普通及 `-O` 通过。
这不是新增 ADD 证明、完整 clean-room 或 Week6 关闭。

## 同日 Sail ELF 差异审查与完整模型比较启动

[ELF / 模型审查记录](release/SAIL_MODEL_IDENTITY.md) 绑定原、新安装文件身份。
主编译器代码段相同，`.data` 只有三个精确 4,096 字节目录配置字段改变；
十个原生插件中七个整文件相同，另三个仅观察到构建标识及调试段差异。
只读审查报告 SHA-256：`4b2e177360d6101253f0fa96144d8284092d1fe4b188a17b047fa2243a0b72d6`。
这不是 ELF 整文件等价、宿主依赖认证或编译器正确性证明。

`sail-model-identity-v1weq3h5` 于 16:05:37 UTC 结束，状态为失败，非仍在运行。
旧工具的三个后端均生成成功，但适配后的 Lean 清单比原政策少一个历史残留文件
`LeanRV64D/Specialization.lean`；其余 162 项字节相同。未执行该入口的新工具阶段。
后续 `sail-candidate-model-rjsls7ks` 已结束：Lean / Rocq 原始输出一致，但 C++ 两文件不同，
整体返回 1，未采纳新工具。`sail-stale-cleanup-w3osvf64` 返回 0，
在可恢复的隔离清理副本中完成 1,864 个构建任务和实际导入模块审计，主根仍为 137 项依赖。
详细来源、精确哈希和未关闭边界见 [残留文件记录](release/SAIL_STALE_GENERATED_FILE.md)。
新增模型比较 15 项、ELF 20 项、full-MIR 11 项回归，加上原独立安装 47 项，
合计 93 项在普通 Python 与 `-O` 下通过。主政策、生产源码及原验收计划保持不变。

## 同日新 full-MIR sysroot 的真实重提取通过

[重提取记录](release/FULL_MIR_REEXTRACTION.md)：16:05:07–16:06:45 UTC，
独立源码副本、新 Cargo 缓存与 target 中的 11 个阶段全部退出 0。
使用新构建的 46 个标准库和原批准的 Charon/Aeneas 工具，保持原公开 decoder / iterator
提取范围、选项及既有源位置注释映射；两份完整 Lean 模型均匹配原规范化身份。
报告 SHA-256：`a170b3c45ce291c07f8feb8e03c56a5c06b68f09d08634932da80df06f7a9cfe`。

阶段日志、输入前后清单、源码/补丁、工具和新库、LLBC 与完整生成物已经独立复核。
10 项新回归测试普通与 `-O` 通过。外层仍返回 2，状态为
`new_sysroot_public_and_iterator_models_match_admission_pending`：
未采纳新库，未重建 Charon/Aeneas，也未在本次执行新 kernel 或完整 clean-room。
不能用本次模型一致性替代原始 LLBC AST 等价或编译器正确性证明；Week6 仍未关闭。

## 同日接入精确 Sail 安装与限定政策迁移

[迁移记录](release/SAIL_INSTALL_MIGRATION.md)：旧输出先备份，强制重新生成；
在独立 staging 完成适配后精确替换正式目录，失败恢复且不删除备份。
21 项新测试、19 项既有 import 测试和 18 项主门禁测试通过。
限定审查仅允许四个相关源码 pin、两个新增实现/测试 pin 和旧 `Specialization.lean`
这一清单项变化；主政策更新为 `9308acea…`，公开政策及所有工具、定理/合同/见证边界保持不变。
迁移前源码、政策和主报告/日志已归档，不能将更新后的工作树归为旧裸 commit。
完整 `make proof-check BACKEND=lean` 于 16:47:47–17:36:37 UTC 完成，退出 0；
主报告 SHA-256：`dbb8654592aea7dc90c9c5b9b3e1efc669256353e96dae11181c29dcfe2ba4cb`。
22 个主阶段、15 组 / 206 项回归及 47 个公开子阶段均通过。
新 162 项正式清单和旧 163 项可恢复备份已独立核对；公开重新提取、source-only 全依赖
构建以及错误结论／削弱前提负测通过。发布检查器已接入新增 21 项安装测试，并在 `-O`
下独立复核完整主/公开证据；聚合器 26 项测试普通和 `-O` 均通过。
七类 Week6 完整缺项仍不因此关闭，新候选工具也未采纳。

## 同日推进 Charon 与 Aeneas 独立重建

[Charon 双版本重建](release/ISOLATED_CHARON.md) 已在两个独立源码／Cargo／target 中执行，
未打补丁和原公开解码补丁版本的 18 阶段均已完成并独立复核，包含版本及真实提取 smoke。
报告 SHA-256 为 `691c805d3d9c8b5f17e68b32774d15dcb2facc483693ace1ab5abacfdb72e3c3`；
外层返回 2、资格待审查，四个新二进制哈希均不同于各自批准基线，没有自动采纳。
首轮源码符号链接核验失败已保留；专用检查只允许上游三个精确链接文本，不遍历文档目标。
13 项相关测试普通与 `-O` 通过，原正式工具未替换。

[Aeneas OPAM 依赖环境](release/AENEAS_OPAM_DEPENDENCIES.md) 的 116 包完整旧锁已固化，
与原实际安装包集一致，已在全新 OPAM 根完成源码重建；收尾修复 CLI 参数后，七阶段元数据审计
通过，11,469 项安装文件未变，相关十项测试普通与 `-O` 通过。
Aeneas 双版本重建于 17:35:09 UTC 完成，20 阶段通过，主模型及公开 decoder / iterator
三份完整生成物匹配；报告 SHA-256 为
`6e9bdc1e7f98691ad0d1953f68bb9f57a1a5ea9b60afd49d5f847cd22d98b1a5`。
独立复核两侧源码/安装闭包、实际编译产物、日志、三份模型及 Lean 支持源通过。
外层仍返回 2，复用原 LLBC、未采纳新工具；锁中的 visitors 与上游声明版本差异明确保留。
下一项是把新 Charon / Aeneas / full-MIR 接到同一候选重提取及资格链，而非拼接单项 PASS。

## 同日精确安装迁移后的本地证据补跑

[本地证据更新](release/LOCAL_EVIDENCE_REFRESH.md) 保存新的 runtime / mutation / 32 次重放、
78 项 Rust 测试、两类配对负测及新 runtime CLI 上的 trap 最小化，全部执行并独立复核通过。
Rocq 输入强制重生成后与备份字节相同；17:47:47–17:52:20 UTC 的十阶段 spike
重新确认原 NO-GO，无额外证明覆盖，旧报告和生成目录备份均保留。

[v4 清单](release/local-readiness-20260912-v4.json) 绑定当前 `9308acea…` 政策及这些新报告，
不复用旧政策报告冒充新执行。17:52:59–17:53:18 UTC 的
[聚合报告](../artifacts/release-audit/run-du7w5vuk/report.json) SHA-256 为
`8d205b69efa7e60e4be53972cfb78439c8bec78736abcfa0720a49b3b9d2fcf0`。
五类已有组件复核通过；整体退出 2、`incomplete`，仍有 clean-room、worktree 审计、
CI 下载、release 包、维护者演示、第三方和公开结论七类缺项。
131 项相关 Python 检查器测试普通及 `-O` 通过，原计划、工具及定理边界未变化。

## 同日新翻译器与 full-MIR 联合生产提取通过

[联合提取记录](release/REBUILT_EXTRACTION_CHAIN.md)：18:00:51–18:05:33 UTC，使用新 Charon
base/public、新 Aeneas base/public 和新 full-MIR，在独立恢复的完整源码快照中实际
提取并翻译三个根，20 阶段全部退出 0。主模型逐字节一致，公开 / iterator 仅通过既有
373 / 20 处 Source 位置映射匹配完整身份；没有翻译旧 LLBC、扩大 opaque 或改写生成物。
报告 SHA-256：`db0ddb324274e9ab1fa69650eed19ea661ef5b4f68face18aa72113c96414c9e`。

独立 `-O` 复核完整源码载荷、候选快照、组件源码/构建/安装清单、20 阶段日志和精确
命令、LLBC 选项与三份模型通过；47 项相关测试普通及 `-O` 通过。
正式政策/工具/生成物未替换，外层仍返回 2。后续需要候选工具资格回归、下层模型来源
重生成及本轮模型的 kernel 链；新 Sail C++ 差异和 Week6 七类完整发布缺项仍保留。

## 同日新 Charon 的全量 UI 对照完成

[UI 记录](release/REBUILT_CHARON_UI.md)：18:14:39–18:16:58 UTC，用新 base/public 工具、
私有 Rust 和 native full-MIR 重跑固定 435 项原用例，金样不改。2 项忽略，433 项两侧
退出码相同；423 项选定输出相同、10 项不同，无缺失执行。两侧金样通过 386 / 379 项，
不符 21 / 28 项、命令失败各 24 项，另有各一项无金样和不检查输出。
外层报告 SHA-256：`325e6f340bd365dcea0992309d38a6635b264a198ce70afd8999c9cd8b563e00`。

24 项失败均保留 E0463（缺失 std / core）的真实诊断，stderr 差异复核为 12 对一致、
4 对仅行序、8 对仅最先失败目标汇总及行序。所有文件、日志、金样、工具/安装身份已独立
复核；17 项相关守卫测试普通和 `-O` 通过。这不是全量测试通过或工具采纳，外层仍退出 2。

[下层来源核验](release/LOWER_MODEL_REGENERATION.md)确认现有 LocalFields / FactoryScoped /
MiniComplete 原模型均符合原政策，但没有纳入上一轮三根新提取。

## 同日下层模型实际重提取：发现函数体身份差异

随后[补建第三种 Aeneas 并重提取](release/LOWER_MODEL_REGENERATION.md)，26 阶段完成，
严格合流负测按原原因拒绝。字段模型原始字节一致；工厂与最小模型除了 Source 路径，
还有 `Option.map` 函数体变化，均未通过既有身份检查。该函数的定义在 raw 政策中锁定，
不能单独刷新文件哈希来绕过。报告 SHA-256 为
`5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35`，外层退出 2。

过程中的忽略锁文件缺失、外层 Cargo workspace 干扰两次失败均保留；新入口恢复同一
快照到 workspace 外的独立 clone，并显式绑定原锁，没有改生产 Cargo manifest。
26 阶段、来源/工具/安装闭包及原政策/模型不变已独立复核，54 项相关测试普通和 `-O` 通过。
下一步是定位差异来源、提供所需 kernel 等价证据并审查准入，再连接原定理/负测；
不是已有新工具全链 PASS，Week6 仍未关闭。

后续新旧 Aeneas × 新旧 LLBC 的八次实际翻译，四对同输入结果均原始字节相同；
差异随 LLBC 出现，尚未进一步区分 Charon 与新标准库 MIR。交叉报告 SHA-256：
`cd956d4300e19b0b29492dbc84cf9cd015c67d88d05168f4449d9164faaf900c`。
此项只诊断已有 LLBC，不增加 kernel 证明。包括新增矩阵守卫在内共 59 项测试，
普通及 `-O` 均通过，所有未通过身份检查的模型与失败预检原记录继续保留。

## 同日下层 sysroot 对照与实际 map kernel 等价

[sysroot 四格对照](release/LOWER_SYSROOT_DIFFERENCE.md)用新旧 Charon 各做两次新提取：
已安装 std 重现旧 MiniComplete，full-MIR 重现新模型；同一 sysroot 下两份原始输出相同。
它不追认旧报告当时未记录的隐式库身份，也不是整个翻译器/标准库等价证明。

[kernel 候选检查](release/LOWER_MAP_EQUIVALENCE.md)于 19:24:50–19:30:46 UTC 完成：
4 条实际 map 等价、9 条字段及 15 条原 raw ADD 定理通过。原定理类型/公理集合全部不变，
定义审计只有两处 map 不同，原 raw 政策如预期拒绝候选。错误返回值、额外 False 前提
两个负测正确拒绝，23 阶段完成，外层仍退出 2。报告 SHA-256：
`57cb243c8742513062547a8983b6cafeca689907250146e78f46cbea3d8101cd`。

使用新安装 Lean 和空模型/证明缓存，但明确复用了主模型与支持库编译缓存，
搜索目录中 70,681 项编译文件运行前后身份一致；不是全依赖 clean-room 或公开候选根的新门禁。
两次中间失败记录保留，原政策/正式生成物不改；80 项相关检查器测试普通与 `-O` 通过。
后续仍需候选准入审查、原有完整负测和工具资格、全依赖公开根重建及 Week6 发布缺项。

## 同日新下层候选的原有负测与工厂运行检查完成

[原有负测记录](release/LOWER_ORIGINAL_NEGATIVES.md)：19:56:23–20:00:45 UTC，17 阶段完成。
四类错误结果、两类额外 False 前提，以及新工具严格合流模式均按预期拒绝。
空 Cargo home / target 中使用原冻结锁重新构建生产工厂检查器，32,768 个合法 ADD
编码、196,608 次非 ADD 邻域和 32,768 次错误目标寄存器变异检查通过。
报告 SHA-256：`1b045c976d4d8de26fbb26443a1d74eb3f7bab320b7a7d2a2939da1dc9e3ad9e`。

首次运行在重复位域片段的定位检查失败；原报告/脚本保留，修正为唯一 `rd` 定理上下文，
回归测试确认与原门禁的实际变异字节一致。57 项相关测试普通 Python 和 `-O` 通过。
本项明确复用 Lean 编译缓存，不增加证明覆盖；原 raw 政策仍拒绝候选，外层退出 2。
下一步是候选准入审查及新模型公开根的源码级全依赖重建、公开负测和工具资格；
Sail C++ 差异及 Week6 七类发布缺项保持未关闭，原计划与正式政策不变。

## 同日新候选公开根的源码级重建已启动

[候选公开 kernel 记录](release/REBUILT_PUBLIC_KERNEL.md)：新入口使用已固定的新工具实际
输出源码，从空项目/支持编译缓存开始，主根和公开根继续按原定理/合同快照审计；
限定两处 map 差异须由本次重新编译的等价证明对应，正式 raw 政策仍不得接受候选。
候选 Sail 适配后 162 项源码清单已匹配政策，十个支持依赖的独立 Git clone / 跟踪源码
已核验。第四轮 `rebuilt-public-kernel-tnice9wk` 的 1,865 个真实主构建任务成功，但入口
误将正常 `Aeneas.Std.Core.Panic` 模块名当作 panic，尚未进入主审计与公开模块。
原失败报告保留；第五轮 `rebuilt-public-kernel-ktp49cde` 完成主构建、主/下层/三组公开
正向审计后，正确失败的负例又因结论中的 `Error.panic` 被误报为内部错误。
修正后全部 64 个原阶段日志通过分类复验，新增测试保留实际内部/导入/资源错误拒绝。
第六轮 `rebuilt-public-kernel-kahdzauc` 已在新目录从空缓存重跑，尚无完整候选 kernel 结论。

准备中发现旧 JS 哈希缓存、内部脚本符号链接及一个未初始化的历史 aesop gitlink；
三次失败和各自脚本保留。修正后明确区分跟踪源码和未复制元数据，绑定内部链接内容，
仅对精确历史 gitlink 记录其 commit 并要求保持为空，未下载或冒填其源码。
77 项相关测试普通及 `-O` 通过。此项不是工具采纳、完整 proof-check 或 Week6 关闭。

## 同日新工具 borrow 资格回归完成

[borrow 记录](release/REBUILT_BORROW_QUALIFICATION.md)：20:35:42–20:43:26 UTC，使用新
public Charon / Aeneas、私有 Rust 与新 full-MIR 实际重提取两个原用例，完整模型与原
身份逐字节一致。九条定理类型/公理审计一致，额外 False 前提、错误回边均正确拒绝，
另由 kernel 证明变异实际产生 `11, 11` 的错误轨迹。
报告 SHA-256：`624413e13a949f9b3a56442e097dcff9bd5853e5bf193c3828308918a2e62120`。

17 阶段完成，外层仍退出 2、待准入；本项明确复用原主模型/支持编译缓存，并在执行
前后核验，不是全依赖源码重建。87 项相关守卫测试普通 Python / `-O` 通过。
后续 fnptr 回归已完成，见下节；guard / loop 等新工具资格及公开候选完整 kernel 链
仍待完成，原政策与 Week6 验收定义不改。

## 同日新工具 fnptr 资格回归完成

[fnptr 记录](release/REBUILT_FNPTR_QUALIFICATION.md)：20:58:07–21:03:30 UTC，22 阶段完成。
六份原 Rust 用例由新工具实际提取，完整模型字节一致；原 16 条局部定理公理列表一致，
新 join-only 工具拒绝、错误调用参数和五类不支持签名共七项负测按预期拒绝。
报告 SHA-256：`1ad2d7355f6f517e1f8d1c05b5373e59a5b659fec33ba336c8f617032f061315`。

本项显式使用已核验的私有普通标准库，仍保留原 opaque 迭代入口，不冒充 full-MIR
公开入口证明；复用支持编译缓存，外层退出 2、待准入。完成后已独立核验所有精确命令、
日志、输入、原证明/公理、变异及工具/Lean 安装清单。原政策及完整发布缺项保持不变。

## 同日新工具循环清理资格回归完成

[循环回归记录](release/REBUILT_LOOP_QUALIFICATION.md)：21:24:56–21:30:51 UTC，12 阶段完成。
新 base / public Charon 分别提取原 `issue-1051-missing-loop-jump.rs`，同一新 public
Aeneas 和显式 full-MIR 下，原四条定理及精确公理列表一致，原错误结果负测正确拒绝。
报告 SHA-256：`d95e3a00022699e8a773b1aa11458ff7cd34259c066c18206dab4e59d35ec1f2`。

本项明确复用经前后核验的支持编译缓存，原证明字节不变；不宣称历史未绑定的 LLBC/
模型身份已证明、不声称一般编译 pass 正确性。外层退出 2、待准入；新工具 guard
回归、Sail C++ 输出差异和完整 Week6 发布仍须分别处理。

## 同日新候选公开根完整源码级 kernel 检查完成

[第六轮记录](release/REBUILT_PUBLIC_KERNEL.md)：21:14:15–21:37:12 UTC，66 阶段完整结束，
1,865 项主构建成功、主根 137 项依赖符合原政策，4 条 map / 9 条字段 / 15 条 raw
定理及三组公开快照（68 条定理、45 个定义、3 个合同）均通过。
错误公开结论以真正的 `Type mismatch` 拒绝；增加 `False` 后虽能编译，精确类型审计
仍拒绝。最终源码、依赖、工具、私有 Lean 和正式生成物复核通过。
报告 SHA-256：`e94b2e9f59e41fffb2e4d2c525cef42e6bc7a786393e842879e053f89d01bf08`。

完成后独立核对全部阶段/来源/变异，并实际重新执行七个审计器，输出完全一致。
本次复用固定实际提取报告的源文件，不复用项目/支持编译缓存，也不宣称又重提取一次
Rust/Sail。原 raw 政策继续拒绝两处已证明等价的新 map 定义，外层退出 2、待准入。
正式完整 `proof-check` 报告未替换，新工具 guard 资格、Sail C++ 差异及 Week6 七类
发布证据仍未关闭。

## 同日新工具短路守卫资格回归完成

[guard 回归](release/REBUILT_GUARD_QUALIFICATION.md)：21:50:00–21:53:06 UTC，15 阶段完成。
新 base 工具实际提取参考用例，新 public 工具实际提取原 owned-error 用例；相同显式
full-MIR 配置下，原全输入等价证明、具体错误守卫反例和错误等式负测通过。
报告 SHA-256：`7d60a0d39587f6d5f5af310ef3ed02ea8acba6778cb58720ec5a35c8856093ce`。

原证明/负例和正式政策不改，缓存复用边界显式记录；首轮因负例匹配条件复核而主动
中止，报告/脚本保留，重跑没有复用其中的 LLBC 或模型。这不是一般变换正确性证明，
也不把手写参考用例当作生产 decoder。Sail C++ 差异的
[进一步清点](release/SAIL_MODEL_IDENTITY.md)显示六个同名生成成员的声明类型也不同，
不能只按顺序/路径变化放行；新身份正式准入及 Week6 七类发布条款仍未关闭。
