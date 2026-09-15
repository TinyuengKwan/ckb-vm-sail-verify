# Week6 独立临时 VM、分阶段执行与 provenance 设计复审

2026-09-14。本页复审 [Week6 原始条款](../plan/week6.md)之下 clean-room / CI 下载 / 发布证据三项
的执行架构。原计划、[总览 Definition of Done](../plan/overview.md)、
[外部验收政策](external-acceptance-policy-v1.json)和 12 槽聚合器的验收定义均未修改；
本轮只修正生产者缺陷、补足 provider 的可审计性，并给出可执行的采纳顺序。
只读事实与本轮回归见[机器记录](../../artifacts/boundary-check/week6-ephemeral-vm-design-review-20260914/evidence/report.json)，SHA-256 `6f707738522f16822c0b1c64d0b4e8275feb6201ec2dbcfeeaa1a6d000357cab`；记录由同目录 `run.py` 只读生成，未启动 guest、未触碰远端。
**本页不宣称 clean-room、CI、发布或第三方复现已完成；Week6 仍未关闭。**

## 结论

1. **clean-room 执行改用政策已允许的 `independent-ephemeral-vm`。** 外部验收政策的
   `clean_room.allowed_providers` 从一开始就同时列出 `github-actions-ephemeral` 与
   `independent-ephemeral-vm`，聚合器的 `check_clean_room` 也按该列表接受；因此这不是放宽验收，
   而是启用一条已获批准的路径。
2. **GitHub 标准 runner 上的分阶段执行不成立，larger runner 也不是安全默认。** 一次完整链需要
   约 13.2 GB 固定安装加约 11 GB 构建输出，本机 24 核实测约 4 到 5 小时，而 GitHub-hosted
   作业一律 6 小时上限、标准 runner 为 4 vCPU / 14 GB SSD。拆成多个 job 也不能绕过“每个 job 都要
   先恢复 13.2 GB 安装根”这一事实。详见下文第 3 节。
3. **控制器存在一个与 runner 无关的新鲜检出缺陷，已修正。** 原 16 阶段控制器没有任何阶段用固定
   Sail 编译器配置 `deps/sail-riscv/build`：`rebuild-rust-model` 的 formal resolver 要求该 CMake
   cache 已存在且指向固定编译器，`rebuild-sail-model` 又会在 `PATH=/usr/bin:/bin` 下让
   `find_program(sail)` 失败。现在 `install-sail` 阶段按 `build_sail_emulator.sh` 的原参数加
   `-DSAIL_BIN:FILEPATH=<固定编译器>` 配置一次，并用 resolver 的同一检查核对 cache。该修正尚未在
   新环境中实跑。
4. **VM provider 的 provenance 由自述改为 operator-attested 记录并强制绑定。** 原来
   `provider.ephemeral=true`、`original_workspace_mounted=false` 只是控制器写入的常量。现在宿主
   launcher 在 guest 关机、证据提取、overlay 与 secrets 磁盘销毁之后写入 `vm-provenance.json`；
   聚合器对 VM 报告在该记录出现并核对通过前保持 `incomplete`；CI 归档若携带 VM 报告则必须同时携带
   该记录。记录明确 `platform_signed_identity=false`，不冒充 GitHub-hosted 或云平台签名身份。
5. **CI workflow 的 `clean-room` job 改为 intake。** 政策固定的五个 job 名不变；该 job 在标准
   `ubuntu-24.04` runner 上按字面哈希下载 VM 证据包、严格解包到精确候选检出、运行同一套
   clean-room 与 provenance 验证器、生成确定性归档并 attest。attestation 因而只证明“归档由该
   workflow 在该 commit 的 GitHub-hosted 作业中打包”，不证明 GitHub 执行了 16 阶段；这一点写进
   了候选 workflow 与 contract-v2。
6. **本机此刻不能启动 VM，候选也未推送。** `/dev/kvm` 存在但当前用户不在 `kvm` 组，
   `qemu-system-x86_64` 未安装，`sudo` 需要密码；远端 `main` 仍是 `1ef21d7…`，本地 HEAD
   `872d225…` 加 220 个未提交路径都不在 GitHub 上，而控制器只从 GitHub 克隆候选。
   这些都是用户侧动作，见第 6 节。

## 1. 只读事实

| 项 | 观察 |
| --- | --- |
| 固定安装根 | Rust/Lean 5.16 GB、Sail 2.13 GB、Aeneas OPAM 1.65 GB、Rocq 1.04 GB（`du -sb`），容量审计按包清单合计 10.77 GB |
| decoder 安装 | 2.42 GB（正式 admitted installer 重建五个源码变体） |
| 构建输出（本机） | `proof/lean/theorems/.lake` 7.4 GB、`target` 3.3 GB、`deps/sail-riscv/build` 0.56 GB |
| 固定输入包 | gzip 3,177,313,154 字节超过 GitHub release 单文件 2 GiB 上限；2026-09-15 同内容 xz 重封装为 1,801,059,088 字节（`c8e8ca27…`），见 [FIXED_INSTALL_BUNDLE](FIXED_INSTALL_BUNDLE.md) |
| 正式链耗时（24 核） | 记录 `formal-final-kfncD8ln` 共 1 h 56 min：proof-check 50 min、proof-spike 8.5 min、两次输出清单各约 25 min |
| 冷构建 + native | 记录 `ISOLATED_FOUNDATION` 13 阶段 22 min；native 差分/Rust 测试约 3 min |
| 单次 clean-room 估算 | `lean-kernel` 与 `rocq-spike` 各跑一次 Lean，加安装、模拟器冷构建、输出观察与审查：约 4 到 5 小时（24 核） |
| GitHub 限制 | 作业 6 小时；标准 Linux runner 4 vCPU / 16 GB / 14 GB SSD；larger runner 仅 Team/Enterprise 组织 |
| 宿主 | 24 核、33.6 GB 内存、根分区剩余约 260 GB；`/dev/kvm` 存在；用户组无 `kvm`；无 `qemu-system-x86_64`；有 `qemu-img`、`cloud-localds`；`HTTP(S)_PROXY` 已配置 |
| 远端 | `main` = `1ef21d7…`；本地 HEAD `872d225…` 未推送；工作树未提交 |
| 候选 guest 镜像 | Ubuntu 24.04 cloud image release-20260911，SHA-256 `612b2c0c…`，尚未批准 |

## 2. 三种架构对照

| 维度 | A. 组织 + larger runner（v1 候选） | B. 标准 runner 分阶段 | C. 独立临时 VM + CI intake（v2 候选，推荐） |
| --- | --- | --- | --- |
| 磁盘 | 需选择 ≥ 64 GB 的 larger runner | 每个 job 都要恢复 13.2 GB 安装根，14 GB 不够 | 由 launcher 指定（默认 96 GB overlay + 24 GB 证据盘） |
| 时间 | 6 小时上限对 4 到 5 小时链风险很高，且 vCPU 少于 24 时更慢 | 每个 job 仍受 6 小时约束 | 无平台上限（默认 12 小时超时） |
| 控制器改动 | 无 | 必须重写为跨 job 状态传递，验证器同步改 | 无；控制器原样在 guest 内运行 |
| 执行 provenance | GitHub 签名 attestation 绑定执行 | 同 A，但拆分后单次 attestation 无法覆盖全链 | operator-attested 宿主记录；GitHub attestation 只覆盖 intake 打包 |
| 外部授权 | 组织迁移、runner 标签、镜像 digest、输入 URL | 同 A 减去组织 | qemu/kvm 权限、镜像批准、输入 URL、bundle URL |
| 现状可行性 | 个人账户不可 | 不可 | 缺 qemu/kvm 组与推送后立即可行 |

B 被否决的根本原因不是工程量，而是控制器与验证器的设计：状态文件、canonical 路径、逐阶段对同一检出的
依赖、结束时对源码快照的终态核对，都假设同一个环境。拆分意味着新的生产者和新的验收定义，与“不修改
验收定义制造完成状态”的原则冲突。

A 仍是 provenance 最强的方案；若日后取得组织与 larger runner，v1 候选依旧可用，且本轮控制器修正对
它同样必要。在此之前 C 是唯一不改验收定义又能真实执行的路径。

## 3. 独立临时 VM 路径的设计

宿主 launcher：[`scripts/week6_ephemeral_vm.py`](../../scripts/week6_ephemeral_vm.py)。

- **镜像固定**：`--image` 必须是 SHA-256 等于 `IMAGE_SHA256` 的 Ubuntu 24.04 cloud image；
  `PROVIDER_IMAGE` 即 `<文件名>@sha256:<该值>`，与控制器 `provider()` 的正则一致。
- **一次性 overlay**：`qemu-img create -b <镜像>` 生成新 qcow2；guest 关机后擦除并删除。
- **无共享文件系统**：qemu argv 由 launcher 生成并记录，禁止 `-virtfs`/`-fsdev`/virtio-9p/virtiofs；
  验证器同样拒绝含这些标志的记录。原工作区不可能被挂载，`original_workspace_mounted=false`
  因此有据可查。
- **secrets 隔离**：三个固定输入 URL 与代理变量只写入一块 1 MiB 的只读 raw 磁盘；不进入
  cloud-init seed、argv、JSON、日志；guest 读入后即删除；宿主在 qemu 退出后先擦除该磁盘再做其它事。
  测试断言所有产出文件不含秘密 URL 或代理凭据。
- **公开 seed**：user-data 内嵌 guest 驱动脚本（apt 安装 12 个固定宿主命令所需软件包、创建 uid 1000
  用户、从 GitHub 克隆 bootstrap 检出、以 `env -i` 启动控制器），meta-data 携带环境 id；两者哈希进入记录。
- **证据回传**：guest 在 EXIT trap 中把 `artifacts/boundary-check/week6-*` 与运行日志写成 tar 到
  第二块 raw 磁盘；宿主只接受两个前缀下的常规文件，拒绝链接、设备、路径穿越与覆盖，解包进一个
  处于候选 commit 的全新检出。
- **记录**：`vm-provenance.json` 绑定 provider 四元组、hypervisor 可执行文件哈希与版本、基础镜像哈希、
  overlay/证据盘/secrets 盘的销毁事实、seed 哈希、完整 argv、起止时间、guest 控制器退出码与日志、
  以及 `report.json` 的精确哈希。

验证与聚合：

- `release_external_evidence.check_vm_provenance` 只对 `independent-ephemeral-vm` 报告适用，
  逐字段核对上述内容；报告改动、环境 id 不符、非 KVM、共享文件系统、磁盘未销毁或边界翻转均拒绝。
- `audit_release` 对 VM 报告在记录缺失时给出 `incomplete`（不是 `invalid`，因为 guest 内的
  自检与预聚合必然发生在记录写入之前），记录无效时 `invalid`，记录通过后才计为已验证；全槽成功
  路径额外要求 `host_provenance.operator_attested=true`。
- `check_ci_download` 在归档内的 clean-room 报告为 VM provider 时，要求同目录的
  `vm-provenance.json` 同在归档且哈希一致，并再次运行同一验证器。
- [`scripts/week6_vm_evidence_bundle.py`](../../scripts/week6_vm_evidence_bundle.py) 提供确定性
  `pack` 与严格 `unpack`，后者即 CI intake job 的入口，解包后立即运行 clean-room 与 provenance 验证器。

诚实边界：这条路径的执行 provenance 依赖操作者的宿主记录与 Ubuntu 镜像哈希，不是平台签名；
它比 GitHub-hosted 执行弱，比原先的自述常量强。独立第三方复现（第 10 个 stage 集合）仍是对它的
独立检查，不能省略。

## 4. 本轮变更

| 文件 | 变更 |
| --- | --- |
| `scripts/week6_clean_room.py` | `install-sail` 阶段新增固定编译器 CMake 配置与 cache 核对 |
| `scripts/week6_ephemeral_vm.py` | 新增：本地 KVM 临时 VM launcher（plan / run 两种模式） |
| `scripts/week6_vm_evidence_bundle.py` | 新增：VM 证据包 pack / unpack（CI intake 入口） |
| `scripts/release_external_evidence.py` | 新增 `check_vm_provenance`、`VmProvenanceAbsent`；CI 归档要求携带记录 |
| `scripts/audit_release.py` | VM 报告 incomplete-until-bound；全槽成功要求 operator-attested；新增两对源码 pin |
| `scripts/tests/…` | 四个既有测试文件扩展，两个新测试文件（假 hypervisor 端到端） |
| `artifacts/boundary-check/week6-ephemeral-vm-design-review-20260914/` | 只读事实记录、`week6-release-v2.yml`、`contract-v2.json` |
| `artifacts/boundary-check/week6-workflow-candidate-v1-20260914/` | 仅重新封印 `remote_capacity_audit` 的过期哈希；其余记录保持历史身份，其中 `clean_room_producer` 哈希因本轮控制器修正而成为历史值 |

回归：`test_week6_clean_room` 11、`test_week6_ephemeral_vm` 7、`test_week6_vm_evidence_bundle` 3、
`test_release_external_evidence` 15、`test_audit_release` 58，共 94 项在普通与 `-O` 模式各自通过；`py_compile` 与 `git diff --check` 退出 0；源码哈希见机器记录。

## 5. 分阶段执行的复审结论

不采纳。若将来必须在 GitHub-hosted 环境执行，正确顺序是先取得 larger runner（A），而不是拆分控制器。
唯一可接受的“分阶段”是本页的 C：执行在 VM，一次完成 16 阶段；CI 只承担 intake、attestation 与
独立 job 的下载重放；发布与第三方复现在其后。

## 6. 用户侧动作与精确命令

1. 宿主准备（需要密码 sudo，助手未执行）：

   ```bash
   sudo apt-get install -y qemu-system-x86 cloud-image-utils
   sudo usermod -aG kvm clair   # 重新登录后生效
   ```

2. 冻结并推送候选：提交当前工作树到专用候选分支并推送（控制器从 GitHub 克隆该 commit）。
   推送前请在新提交上重算源码快照与本地证据；旧报告保留各自身份。
3. 固定输入发布：`extra-installations.tar.xz`（1.80 GB，`c8e8ca27…`）、其 manifest（`ac7b468e…`）与
   decoder 包（`1a81921b…`）需要放到保持哈希的 HTTPS 位置。xz 重封装后三者都低于 GitHub release 单文件
   2 GiB 上限，可直接作为 release asset；控制器与 launcher 已固定新哈希。
4. 下载并校验镜像，然后启动：

   ```bash
   curl -fLo /path/ubuntu-24.04-server-cloudimg-amd64.img \
     https://cloud-images.ubuntu.com/releases/noble/release-20260911/ubuntu-24.04-server-cloudimg-amd64.img
   sha256sum /path/ubuntu-24.04-server-cloudimg-amd64.img   # 须为 612b2c0c…7354
   git clone https://github.com/TinyuengKwan/ckb-vm-sail-verify.git /path/candidate \
     && git -C /path/candidate checkout --detach <候选 commit> \
     && git -C /path/candidate submodule update --init --recursive \
     && make -C /path/candidate ckb-baseline-apply
   WEEK6_INSTALL_ARCHIVE_URL=… WEEK6_INSTALL_MANIFEST_URL=… WEEK6_DECODER_ARCHIVE_URL=… \
   python3 scripts/week6_ephemeral_vm.py --mode run --commit <候选 commit> \
     --image /path/ubuntu-24.04-server-cloudimg-amd64.img --evidence-root /path/candidate \
     --out artifacts/boundary-check/week6-ephemeral-vm-<日期>
   ```

   `--mode plan` 只生成 seed 与 argv、不启动任何东西，可先用来审阅。
5. 审阅 `/path/candidate/artifacts/boundary-check/week6-clean-room/{report.json,vm-provenance.json}`，
   然后 `python3 scripts/week6_vm_evidence_bundle.py pack --root /path/candidate --out <bundle>`，
   把 bundle 发布到授权 HTTPS 位置，将其 SHA-256 作为字面值写入 `week6-release-v2.yml` 后采纳到
   候选分支并 dispatch；再用 `scripts/week6_collect_ci.py` 外部下载、attest、查询与重放。
6. 其后依次为：profile-A 批准与 v4 envelope、发布包签名与 immutable release、独立第三方复现、
   最终 12 槽聚合。

## 边界

未启动 guest；未推送、未 dispatch、未发布、未签名；未修改原计划、政策或验收定义；
`clean_room`、`ci_download`、`release_package`、`third_party`、`worktree_audit` 五个槽仍未关闭。
