# 公开 ADD 解码提取输入包（本地验证）

2026-09-11。这是现有批准输入的可搬迁分发组件，不是新的证明政策、完整工具环境
或已经发布的 release。主 `proof-check` 已迁移至独立安装布局并完成全量实跑及独立
验收；见[正式迁移记录](PUBLIC_INPUT_MIGRATION.md)。这不等于完整环境 clean-room。

这是 v1 历史记录。2026-09-13 当前主入口已切换至 [v2 公开输入政策](REBUILT_GATE_MIGRATION.md)，
新完整门禁正在运行；安装要求见 [v2 输入准入](REBUILT_INPUT_ADMISSION.md)。

## 内容与校验边界

[打包/安装脚本](../../scripts/decoder_input_bundle.py) 固定 68 个输入文件：
公开 Aeneas/Charon/driver、两份工具补丁、两份 LLBC、Rust harness 源码与锁文件、
三个下层 Lean 源文件、标准库身份报告、七份工具资格证据、46 个 full-MIR 库文件，
以及两个独立 Git 源码 bundle。没有 `.olean`。

标准库原来的外链已物化为普通文件（合计 279,554,691 字节）。安装后两个工具源码
固定至政策指定 commit，应用指定补丁，拥有完整独立 Git 对象，不使用本机 alternates。
这不证明打包二进制由这些源码正确构建，也不消除提取工具的可信边界。

安装要求调用方明确提供归档 SHA-256；解包拒绝链接、路径穿越、重复条目、不安全权限
和超额内容。文件集合与哈希再次对照仓库政策及固定资格报告，而非只相信包内清单。
输出目录必须不存在；失败目录和旧报告不会被自动删除或覆盖。

## 已实跑的安装与使用

以下在仓库根执行。接收方必须事先具备 Python 3.11+、Git、固定
`nightly-2026-08-18` Rust 工具链及工具所需系统动态库；这不是全环境安装命令。
归档目前仅在本地，未上传或发布。`--output` 示例须选择尚不存在的目录。

```bash
python3 scripts/decoder_input_bundle.py install \
  --archive artifacts/boundary-check/public-inputs-package-v3/public-decoder-inputs.tar.gz \
  --sha256 e69b2d11f9161b0baa9fcb177acb046a09b1409eb489c3512b2bde708cdda8bc \
  --output artifacts/boundary-check/public-inputs-installed-new
python3 scripts/decoder_input_bundle.py verify \
  artifacts/boundary-check/public-inputs-installed-new/payload
python3 scripts/probes/probe_decoder_relocation.py \
  --installed-inputs artifacts/boundary-check/public-inputs-installed-new
```

维护者可用 `python3 scripts/decoder_input_bundle.py build --output NEW_DIRECTORY`
重新制作包。制作仍读取本机既有批准输入，并从固定上游 commit 获取独立 Git 历史；
不是接收方从源码重新构建全部工具的命令。Git 打包字节可能变化，重制包应记录其实际
归档哈希，不能沿用旧归档哈希。

本次实测安装目录为 `artifacts/boundary-check/public-inputs-installed-v2`。

| 本地证据 | SHA-256 |
| --- | --- |
| [制作报告](../../artifacts/boundary-check/public-inputs-package-v3/build-report.json) | `b6aba3e509149fefdae924f0a4c98f7e52ba19a27c152c09d8199ff8174be3f7` |
| 归档（160,360,791 字节） | `e69b2d11f9161b0baa9fcb177acb046a09b1409eb489c3512b2bde708cdda8bc` |
| 包内清单 | `a2598bdb19600e56840c856e8cc66c540e9ce44be5b6d9a692ca609f807e26d2` |
| [安装报告](../../artifacts/boundary-check/public-inputs-installed-v2/install-report.json) | `9dbe4262f1719236f499daba06deae080cf7e55ef9767df61fa38717526bcbb2` |
| [公开主模型重提取报告](../../artifacts/boundary-check/decoder-relocation-8r4cdxxr/report.json) | `af2d177b5ec065768bc6bcf6f1261e169983221d60ada0933cbc0e34e4bc9698` |

主模型重提取于 08:42:12–08:43:20 UTC 完成七个阶段，实际调用安装包中的二进制和
物化 sysroot；使用新生产源码 checkout 和新 Cargo target。
[位置检查器](../../scripts/decoder_input_locations.py) 先核验整个安装输入，才允许
LLBC 元数据中的 sysroot 所在地和输出路径变化；其他提取选项保持不变。
原始 Lean 输出 SHA-256 为
`a4463d191cb91e02d63e48d7434b352a3ba9225397ce0f6b26b36ba9cd80f5d5`，
仅映射 373 处生成来源注释前缀后仍为批准模型
`b5333f7d0be08339e4029cd8e38d6068704d0fdee6cc19b84b2cdcf97d8a7061`。
没有改写生成文件。该次七阶段报告不包含迭代器重提取或 Lean kernel 新运行。

## 补齐迭代器模型重提取

探针现在同时从新 checkout 提取公开入口和函数指针迭代器。
首次九阶段运行 [decoder-relocation-vpr7ubuz](../../artifacts/boundary-check/decoder-relocation-vpr7ubuz/report.json)
在迭代器原始哈希检查处失败，报告 SHA-256 为
`d761b652b00bdfb0bf4e6c51e4c99a44d79d1dd49d6e30ab1c21ad254fafefef`。
逐行复核发现只有 20 处固定 `fnptr_cases.rs` 来源注释路径不同：新路径相对于提取
工作目录，旧批准输出为绝对路径。所有其余字节保持相同。

[身份检查器](../../scripts/decoder_model_identity.py) 对迭代器单独处理这一个固定
源文件的完整 `Source:` 行，路径由实际 checkout 和提取工作目录计算；保留行列号、
可选注释结束符和所有其他字节。不会接受任意源文件或通用路径替换。公开主模型原有
比对规则不变。输出文件从不改写，原始失败报告也不改写。

随后 [decoder-relocation-495a5xcb](../../artifacts/boundary-check/decoder-relocation-495a5xcb/report.json)
于 08:59:34–09:00:48 UTC 从头完成九个阶段，全部退出 0。报告 SHA-256：
`4c9f737d921cf7471220fa417fbd6d296836adbc9dcac3eff9d4c7c7c9c60f8f`。
公开模型 373 处来源路径比对后仍为批准的 `b5333f7d…`；迭代器原始 SHA-256 为
`c5847f862c1edadc74d8d2384cdb2699e3fce5f9cb40c474d0e8c151ee9235b1`，
20 处来源位置比对后为原批准值
`3ea3986975afcd389e5cb1b280b8bff43add33eccdb569a4d585a3ccf2c053e3`。
进程结束后独立重验了九个阶段日志、两份生成物和完整安装输入，均通过。

[新增 10 项迭代器身份测试](../../scripts/tests/test_decoder_iterator_identity.py) 在普通 Python
和 `-O` 下通过：错误工作目录/checkout、文件名、行列号、函数体、公理、注释定界符、
额外文本、其他源文件或非预期路径拼写均不能逃过原身份约束。

```bash
python3 -m unittest discover -s scripts/tests -p 'test_decoder_*identity.py'
python3 -O -m unittest discover -s scripts/tests -p 'test_decoder_*identity.py'
```

这关闭了两份公开提取根的搬迁实测缺口，仍不是新安装布局下完整 Lean kernel 门禁通过。

本轮还执行了检查器全量测试：以下两条命令各运行 189 项，分别耗时 353.947 秒、
356.593 秒，均退出 0、结果为 `OK`。其中包含使用既有 Lean 构建依赖的真实内核负测，
不是新安装环境的全依赖重建。测试中注入的生成失败、错误参数等 `ERROR` 输出是预期
拒绝路径；不把这类输出本身视作运行成功，最终结果以测试断言和进程退出码为准。

```bash
python3 -m unittest discover -s scripts/tests
python3 -O -m unittest discover -s scripts/tests
```

## 保留的失败与测试

- v1 制作失败：旧 Aeneas checkout 缺少历史 Git 对象，不能导出独立 bundle。
  [原始失败记录](../../artifacts/boundary-check/public-inputs-package-v1/failure-report.json)
  保留；改用新目录获取固定上游完整历史，没有修补旧工具 checkout。
- v2 包被安装器拒绝：环境 umask 使 `package.json` 为 0664。
  [拒绝记录](../../artifacts/boundary-check/public-inputs-package-v2/installation-rejection.json)
  保留；制作器明确设为 0644，校验器仍拒绝 0664。v2 包不作为可用安装包。
- 输入包 21 项、位置检查 7 项、harness 10 项及公开模型身份 9 项测试通过普通 Python
  与 `-O`。这些新测试尚未接入主证明门禁的测试列表。

## 仍未关闭

正式调用层、来源政策与验收器已联合迁移，通过差异审计及全套 Lean 依赖构建、
定理类型/定义/合同快照和负测；完成记录单独链接在本页开头。
本页历史提取身份报告本身不替代后续 kernel 检查。
完整 Rust/Sail/Lean/Rocq 环境安装、最终分发许可证/通知审计、发布下载、独立第三方
复现仍待完成，见 [Week6 清单](../WEEK6_STATUS.md)。
