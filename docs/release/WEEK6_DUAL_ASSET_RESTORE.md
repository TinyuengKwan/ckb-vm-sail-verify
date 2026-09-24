# Week6 profile A：双资产与当前候选恢复合同

2026-09-24：仓库所有者明确采用同一不可变 release 的双资产方案。这里的“双资产”指两个**数据资产**，
另有主包的 SSH detached signature；不是只有两个 GitHub asset。此文是交付合同和操作指南，
不声称正式包已经签名、发布，或新候选的 clean-room / CI / 第三方复现已经通过。Week6 未关闭。

## 资产和信任链

同一条 tag 为 `week6-0.1.0` 的最终 immutable release 必须同时发布：

- `ckb-vm-sail-verify-week6-0.1.0.tar.gz`：当前候选 source capsule、安装清单、已准入 decoder、
  四项 CMake 输入、实际证据、覆盖/非目标/恢复指南、`MANIFEST.json` 与 `SHA256SUMS`。
- `extra-installations.tar.xz`：固定前缀工具包，1,801,059,088 字节，SHA-256
  `c8e8ca2797aeabcbee3935949f6ad6b622a40468d77a7f5d79a50b1854a67ff4`。
- 主包的 SSH detached signature；批准身份 `kwantinyueng@gmail.com`，namespace `ckb-vm-sail-release`。

每个数据资产必须严格小于 2 GiB（2,147,483,648 字节）。主包的 v2 manifest 精确绑定工具包的
名称、字节数、SHA-256，以及 `install/manifest.json` 的 SHA-256
`ac7b468e6715e6a4b956376a0ded0ee6e4d9cfc632d4323b439877916e74708e`。
该 manifest 随主包一起被签名。工具包旧发布位置不构成正式交付：即使字节完全相同，也必须上传到
**同一条最终 release**。发布验收检查实时 API、唯一 asset id / 名称 / URL、immutable 状态、大小、
远端 digest 和两个实际独立下载副本。缺件、替换、重复、跨 release 引用均不能验收。

09-24 真实材料预检的单包为 2,846,612,237 字节，不能上传为单资产；拆分后的主包预览为
1,045,191,491 字节，工具包为上述 1,801,059,088 字节。预览混有明确标记的历史证据，
不是正式发布包；未来主包必须对最终真实内容重新测量，不能复用预览大小/哈希作为发布身份。

## 制作当前候选输入

在干净冻结候选上创建 capsule，输出必须在 checkout 外或既有 ignored evidence 目录中：

```sh
python3 scripts/week6_source_capsule.py create --root "$CHECKOUT" \
  --candidate "$CANDIDATE_COMMIT" --out "$NEW_CAPSULE_DIRECTORY"
```

`CANDIDATE_COMMIT` 是完整 Git OID。capsule 包含根仓库及两个固定 submodule 的完整 Git bundle、
逐文件源码、权限和自校验 snapshot。恢复只用本地 file transport、禁用 Git hook/global config，
检查三个 HEAD/gitlink、独立 Git 对象和精确恢复后的源码快照。若工作树有改动，capsule 会如实绑定
HEAD 加逐字节 overlay，**不把它称为干净 commit**；正式冻结流程须另外核对根仓库无改动。
原 `restore_fixed_inputs.py` 的历史 handoff SHA 不改变，也不冒充当前候选恢复入口。

`scripts/week6_release_package.py build` 接受 `release-package-inputs-v2` JSON。顶层字段是
`schema_version: 2`、`kind`、`candidate`、`version`、`delivery_profile: "A"`、`source_snapshot`、
`coverage`、`non_goals`、`members`、`external_assets`。`source_snapshot` 用 `{path, sha256}`
引用 capsule 中的 `source-snapshot.json` 文件；`members` 每项为 `{path, source, sha256}`，
其中 `source` 相对 `--input-root`，`path` 是包内名。禁止链接、路径逃逸、重复和未声明成员。

必须包含以下包内路径（以及当前真实 evidence、coverage、non-goals 文件）：

```text
source/source-capsule.tar.gz
install/manifest.json
install/rebuilt-decoder-candidate.tar.gz
install/cmake-downloads.tar.gz
install/cmake-downloads-manifest.json
docs/RESTORE.md                 <- 本文的交付副本
```

`external_assets` 必须且只能有 `extra-installations.tar.xz` 一项，值为 `{source, sha256}`，
其字节必须匹配仓库政策。工具包不得重复塞进主包。打包器验证 decoder/CMake 固定输入哈希、
capsule 和**当前 checkout 的完整 snapshot 一致**，然后独立重读归档验证成员。
不能将旧 VM/CI 报告重命名为新候选证据；发布包 build 不替代十二槽聚合及证据语义验收。

## 签名和不可变发布

持有批准私钥的发布者在审查最终包后生成签名；不要把私钥交给自动化代理。签名命令形如：

```sh
ssh-keygen -Y sign -f "$SIGNER_PRIVATE_KEY" -n ckb-vm-sail-release "$PRIMARY_ARCHIVE"
```

先创建 draft，将两个数据资产和签名全部上传并核对，再发布成为 immutable release。
不能先发布后补工具包或签名。`week6_release_package.py record --help` 的记录入口不上传、不签名，
只读检查已发布 release 并真实下载两个数据资产。具体生成物和 current-output 五件套仍需明确审批；
布局/身份批准不是对尚未产生的内容预先签字。

## 从已认证双资产恢复

从经独立渠道核对的候选 checkout 运行以下脚本，使用该 checkout 自带的受信公钥和政策，
不要先运行未验证包内脚本或采纳包内自称的公钥。三个路径分别指实际下载的主包、签名和工具包：

```sh
python3 scripts/week6_restore_release.py \
  --candidate "$CANDIDATE_COMMIT" --archive "$PRIMARY_ARCHIVE" \
  --signature "$PRIMARY_SIGNATURE" --tool-archive "$TOOL_ARCHIVE" \
  --mode staging --out "$NEW_RESTORE_DIRECTORY"
```

脚本先验签和输入身份，再解包；恢复当前源码、五个工具安装根、decoder 安装及独立校验、
CMake 输入 staging，最后确认源码没有变化。`report.json` 记录身份、安装位置和实际命令日志。
输出目录必须不存在，失败会保留诊断中间结果且不自动重用；现有 checkout 不会被覆盖。
本地恢复证明签名/字节闭包；**同一不可变 release 的远端发布事实另由 `record` 验证**，不能互相替代。

`staging` 仅验证字节恢复，不能宣称工具可在任意路径工作。实际执行环境须在全新 VM 中使用
`--mode canonical`，目标固定为 `/home/clair/tinyueng_workplace/ckb-vm-sail-verify`，该目标必须不存在。
脚本不安装宿主 apt 依赖、不提供 OS 隔离、不运行完整证明/测试、不把工具安装记作 clean-room 成功。
基础 OS/主机依赖遵循候选 `week6_clean_room.py` 的固定执行合同；恢复报告提供 `decoder_inputs` 和
`cmake_inputs`，后者含离线 CMake 配置选项。完整重放必须保存真实命令及结果，走原有十阶段第三方验收。

## 边界

冻结前的集成测试使用临时测试签名者、微型工具 fixture 或明确标记的真实材料演练；测试签名
不属于批准发布者，不得作为正式 release / 第三方证据。冻结后新 VM 仍从既有固定输入准备环境，
完整正式双资产包在新 VM/CI 证据形成后制作，不以旧证据绕过这一顺序。
独立复现者暂缺；第三方信任清单保持为空。布局采用、恢复成功、本机模拟或维护者重复运行都不关闭
第三方槽。Lean 保留条件性 ADD 边界，Rocq 保留 NO-GO，不增加证明覆盖。
