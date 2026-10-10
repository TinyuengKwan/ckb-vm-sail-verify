# 发布与验收流程

本文是现行的验收合同：六个证据槽、它们各自的产生方式与验证方式、发布步骤，以及第三方
如何从发布包复现。政策参数（仓库、版本号、签名者、固定输入哈希、阶段清单、禁用短语）
只在一个文件里：[`docs/release/policy.json`](release/policy.json)。过程记录在
[`docs/history/`](history/README.md)，不是现行要求。

## 威胁模型

验收只防五件事：比较器误报 PASS、证明里藏公理或 `sorry`、环境污染（陈旧生成物或宿主工具链）、
发布后被篡改、公开文档夸大。它不防流水线操作者自己造假；对这一点的回答是任何人都能按本文
在全新环境里复现，而不是更多验证器。

## 六个证据槽

| 槽 | 产生 | 验证（`scripts/audit_release.py`） |
|---|---|---|
| `runtime` | VM 内 `runtime_evidence.py tests` 与 `run`：全部 Rust 测试、ADD/ADDI/BEQ 语料差分、6 类 mutation 矩阵、每个案例从字节相同的复制产物重放 | 重开每个 artifact 重算比较与 mutation；三族各 ≥ 10 案例；强制引擎测试全部执行 |
| `lean` | VM 内 `make proof-check BACKEND=lean` | 报告绑定当前 `step-policy.json`；每阶段退出 0；公理集合等于政策 allowlist 且无 `sorryAx`；边界哈希一致 |
| `rocq` | VM 内 `make proof-spike` | 结论 NO-GO；三个预期拒绝阶段的编译错误与记录的两处阻塞逐字匹配；无基础设施失败 |
| `clean_room` | `ephemeral_vm.py` 启动固定镜像的全新 KVM guest，`clean_room.py` 跑 11 阶段；host 写 `vm-provenance.json`；bundle 经 workflow intake 任务 attest；`ci_evidence.py` 外部收集 | 11 阶段退出 0、源码快照等于当前检出、生成后 tracked 文件无改动、6 个工具身份；VM 记录绑定报告且磁盘已销毁；CI run 成功、attestation 覆盖 bundle 字节、两次独立下载相同、归档报告与本地逐字节相同、归档二进制重放通过 |
| `release` | 所有者签 tag、签主包、发布不可变 release；`release_package.py record` | `git verify-tag` 对仓库 allowed_signers 且 tag 指向候选；主包 SSH 签名；manifest 与成员清单一致；三个资产的大小与摘要与实时 API 一致、`immutable=true`；下载副本与本地相同；源码胶囊快照等于当前检出 |
| `third_party` | CKB 官方按本文复现后交回签名声明；所有者用发布密钥签署复现者的信任名单，随报告提交，不进源码树 | 缺省 `deferred`；提供时先验所有者对信任名单的签名，再验复现者对声明的签名、候选、快照、十阶段退出码 |

聚合结果：`passed` 要求六槽全部 verified，或 `third_party` 为 deferred；任何 verified 槽记录的源码
快照必须相同且等于当前检出。`incomplete`（退出 2）表示有槽缺失；`invalid`（退出 1）表示某份报告
不通过。公开文档的禁用短语与断链检查在每次聚合中执行。

## clean-room 的 11 个阶段

checkout → snapshot → install（下载三个固定输入、暂存、移入五个安装根、安装 decoder 输入、记录
6 个工具身份）→ configure-sail → regenerate（Rust 模型、Sail 配置与 Lean 模型）→ rust-tests →
runtime → lean-kernel → rocq-spike → tree-clean（`git status --porcelain` 必须为空，记录生成树根
哈希）→ public-claims。

## 发布步骤

1. **冻结候选** `C`（main 上的一个提交）。此后到最终聚合通过前不得改动任何受跟踪文件。
2. **VM 实跑**（宿主需 `/dev/kvm`、`qemu-system-x86_64`、`qemu-img`、`cloud-localds`，固定输入 URL 以环境变量传入，不进 argv）：
   ```sh
   git clone --no-checkout <repo> /path/evidence-root && git -C /path/evidence-root checkout --detach C \
     && git -C /path/evidence-root submodule update --init --recursive && make -C /path/evidence-root ckb-baseline-apply
   WEEK6_INSTALL_ARCHIVE_URL=… WEEK6_INSTALL_MANIFEST_URL=… WEEK6_DECODER_ARCHIVE_URL=… \
   python3 scripts/ephemeral_vm.py --mode run --commit C --image /path/ubuntu-24.04-server-cloudimg-amd64.img \
     --evidence-root /path/evidence-root --out artifacts/boundary-check/vm-run-<date>
   python3 scripts/evidence_bundle.py pack --root /path/evidence-root --out /path/vm-evidence.tar.gz
   ```
3. **发布 bundle** 为 prerelease 资产，把其 URL 放入仓库 secret `WEEK6_VM_EVIDENCE_URL`，以
   `candidate_commit=C`、`candidate_ready=true`、`bundle_sha256=<哈希>` dispatch `release.yml`。
4. **收集 CI**：`python3 scripts/ci_evidence.py --run-id <id> --candidate C --out artifacts/boundary-check/ci-<id>`
   （在 evidence root 内运行，需要 `gh` 登录）。
5. **签 tag**（所有者）：`git -c gpg.format=ssh -c user.signingkey=~/.ssh/<key>.pub tag -s <version> C && git push origin <version>`。
6. **构建主包**：`make -f scripts/release.mk release-package CANDIDATE=C INPUTS=<五个固定输入所在目录> EVIDENCE=<证据目录> OUT=<新目录>`；
   `OUT` 必须位于候选检出的 `artifacts/boundary-check/` 之下，最终聚合只引用检出内的记录。
7. **签主包**（所有者）：`ssh-keygen -Y sign -f ~/.ssh/<key> -n ckb-vm-sail-release <主包>`。
8. **发布**：以 tag `<version>` 创建 draft release，上传主包、`.sig`、`extra-installations.tar.xz`，核对三者的
   大小与 SHA-256 后 publish。仓库已开启不可变发布，发布后不能增删资产。
9. **记录与聚合**：`python3 scripts/release_package.py record --package-dir <OUT> --release-id <id>`，然后
   `make -f scripts/release.mk audit CANDIDATE=C RUNTIME=… LEAN=… ROCQ=… CLEAN_ROOM=<ci 记录> RELEASE=<record 报告> OUT=<新目录>`。
10. 状态文档的更新作为 `C` 之后的新提交，不移动 tag。

## 第三方复现

复现者在自己控制的全新 Ubuntu 24.04 环境中：

1. 独立克隆仓库并检出 tag；从这份检出读取 `docs/release/release-allowed-signers`，不要用包内副本。
2. 从 release 下载三个资产，核对 `immutable=true`、大小与 SHA-256，验证签名：
   `ssh-keygen -Y verify -f docs/release/release-allowed-signers -I <签名者> -n ckb-vm-sail-release -s <主包>.sig < <主包>`。
3. `make -f scripts/release.mk restore ARCHIVE=… SIGNATURE=… TOOL=… CANDIDATE=C OUT=<新目录> MODE=canonical`。工具是固定前缀的，
   目标目录由 `policy.json` 的 `canonical_checkout` 决定，必须事先不存在。
4. 在恢复出的检出内依次执行 `make test`、`make verify-dii`、`make proof-check BACKEND=lean`、`make proof-spike`、
   `git status --porcelain`、`python3 scripts/public_claims.py`，保存每一步的命令、退出码与输出。
5. 用自己的 SSH 密钥在命名空间 `ckb-vm-sail-week6` 下签署声明文件
   `{"schema_version": 2, "kind": "third-party-reproduction-statement-v2", "candidate": C, "performer": {...},
   "source_snapshot_sha256": …, "release_id": …, "result": "passed"}`，连同报告（`third-party-reproduction-v2`，
   含十个阶段的 argv/cwd/退出码/日志）和公钥交回。
6. 仓库所有者审核后，把复现者身份与公钥写成一行 allowed_signers
   （`<identity> namespaces="ckb-vm-sail-week6" ssh-ed25519 …`），用发布密钥在命名空间
   `ckb-vm-sail-release` 下签署该文件，两者一并放入报告目录并填入报告的 `authorization` 字段。
   信任名单不进源码树：候选的源码快照因此保持不变，聚合器用受跟踪的发布者公钥验证所有者的授权，
   再用该名单验证复现者的声明，之后该槽转为 verified。
7. 验收时用**当前 main 的聚合器**，以 `--root` 指向**保持原样的候选检出**，并把第三方报告加入清单：
   ```sh
   python3 <main>/scripts/audit_release.py --root <候选检出> --candidate C \
     --runtime … --lean … --rocq … --clean-room … --release … --third-party <报告>/report.json --out <新目录>
   ```
   不能在 main 自己的检出里聚合旧证据（快照不同），也不能把新脚本复制进候选检出（会改变其快照）。
   候选里冻结的聚合器版本可能早于本步所需的验证逻辑；聚合器只从 `--root` 读取政策、证据和签名者
   信任根，所以新版脚本配旧候选是受支持的组合。已对 `week6-0.2.0` 验证：主分支聚合器加
   `--root` 对冻结候选重算，结论与候选自带聚合器一致。

Rocq 阶段的预期结果是 NO-GO 及其最小复现；复现成功意味着得到同样的 NO-GO，不是得到证明。
Lean 阶段验证的是生产关联的条件性 ADD 步精化定理，显式前提见 [覆盖矩阵](coverage.md) 与
[语义缺口](semantic-gaps.md)。
