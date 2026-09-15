# 统一固定输入恢复（非规范路径暂存）

2026-09-13。恢复入口已经实现并从三个实际归档完成本机暂存。
**这是源码与安装输入恢复，不是可运行工具链、clean-room、第三方复现或 Week6 PASS。**
不修改正式政策、冻结交付清单、原安装报告中的绝对路径或当前生产 checkout。

## 实跑身份与范围

[恢复入口](../../scripts/restore_fixed_inputs.py)固定接收
[交付准备清单 v1](fixed-input-handoff-20260913-v1.json)，可信 SHA-256 为
`7a88d4eaa88c83a2317401ac64d9b8dc1c74e6125d40a539645e75f5f103a015`。
它先校验全部九个文件引用和源码/安装/decoder 交叉身份，再创建新输出目录。
源码传输格式与安装包格式分别验证，不把两种清单互相改名以通过检查。

07:50:34–07:56:34 UTC 的 [恢复报告](../../artifacts/boundary-check/unified-fixed-restore-L5xCOnDq/run/report.json)
记录终态 `fixed_inputs_staged_noncanonical_full_verification_not_claimed`。
报告 SHA-256：`f3ef0562b6d4be513ef2014a36084e24dc8e1feee1c23eb7f74b071a1b2b69b8`。
16 个命令阶段全部退出 0：三个 bundle 引用、主仓库 clone/checkout、两个子模块本地 URL、
实际递归 submodule checkout、三个仓库各自的根目录/fsck，以及恢复副本自己的
decoder 安装与另一个进程中的 `--verify`。

此外逐项恢复和校验了：

- 冻结源码：主项目 435、CKB-VM 489、sail-riscv 859 个源文件，含精确工作树覆盖层。
- 安装补充包：56,702 项、8,404,146,606 普通文件字节，分别安装到五个固定相对目录。
- 已批准 rebuilt-v2 decoder 输入：使用恢复副本中的原准入政策与原安装器，没有政策刷新。

快照文件 SHA-256 仍为
`810b71aa1d4002acce1ad0fc52ef1f37019a6e57550d1c5e381c06b68c5b9999`。
恢复入口及本文是该快照之后的新增内容，**不属于冻结候选**，也未接入正式证明政策。
入口 SHA-256 为 `794001f2b357f74c50da2f85829de2dd10ed5df9cb6faccbd55c6187015a7def`；
报告另固定它依赖的三个本地辅助模块身份。

补充安装目录从本次 `extra-staged/` 移入本次 `checkout/` 后，前者不再是完整暂存树。
后续文件核验必须使用报告的 `extra_installation_current_root`，不能继续把已搬空的
中间目录当作安装证据。原安装树和原归档没有被移动或覆盖。

## 使用入口

需要 Python 3.11 或更高版本、Git 和足够的磁盘空间；这些前置条件不是完整宿主依赖锁定。
在持有清单中全部输入、保持其相对目录布局的当前工作区，只做新目录暂存：

```bash
python3 -O scripts/restore_fixed_inputs.py \
  --mode staging \
  --handoff docs/release/fixed-input-handoff-20260913-v1.json \
  --input-root . \
  --out artifacts/boundary-check/fixed-input-restoration-new
```

`--out` 必须不存在；示例目录用过后应换一个新路径，不删除旧证据。
输出包括日志、终态报告、源码素材和新的 `checkout/`。暂存模式不调用正式工具解析器，
因为旧安装报告中的绝对路径可能指向原工作区；也不运行生成器或 proof-check。
本机 file transport 和收窄的进程环境不构成操作系统隔离或原目录访问禁用。

`--mode canonical` 仅允许目标为
`/home/clair/tinyueng_workplace/ckb-vm-sail-verify` 且该目录不存在的新环境。
本机已有该目录，因此[真实保护测试](../../artifacts/boundary-check/unified-fixed-restore-L5xCOnDq/canonical-guard-report.json)
在读取大归档或创建输出前拒绝，退出 1，正式验收范围的源码快照前后相同。
没有在本机搬走原 checkout 来制造“空目录”，也没有实测 canonical 部署成功。
即使未来 canonical 恢复成功，状态也只允许 `full_verification_pending`，不自动关闭 clean-room。

## 四文件 bootstrap

[独立副本清单](../../artifacts/boundary-check/unified-fixed-restore-L5xCOnDq/bootstrap/manifest.json)
保存 `restore_fixed_inputs.py`、`fixed_install_bundle.py`、`source_snapshot.py` 和
`ckb_source_baseline.py` 四个模块的逐字节副本；它不是已发布 bootstrap 包。
可信入口和模块身份必须在执行前从外部核对，不能靠未知代码校验自己来建立信任。

Python `-I` 会去掉脚本目录的隐式模块搜索路径，因此直接执行
`python3 -I restore_fixed_inputs.py` 不能导入同目录辅助模块。
如需隔离 Python 环境，应显式只加入已核验的 bootstrap 目录，例如从该目录运行：

```bash
python3 -I -c 'import runpy,sys; from pathlib import Path; p=Path(sys.argv.pop(1)).resolve(); sys.path.insert(0,str(p.parent)); runpy.run_path(str(p),run_name="__main__")' \
  restore_fixed_inputs.py --help
```

bootstrap 的有限测试与完整恢复必须区分：上述完整恢复实跑使用原工作区入口，
没有用四文件副本再做一次完整恢复，更没有从空机器完成宿主准备和全部验证。

## 验收与剩余边界

08:08:08–08:09:32 UTC 的[独立验收](../../artifacts/boundary-check/unified-restore-acceptance-F4vGfaUi/report.json)
以新 Python `-O` 进程完成，退出 0，SHA-256：
`0b8bd4f0f8083c0bc7d865b69d36f214458c3946c53ce7412fd3350a56854ced`。
[验收代码](../../artifacts/boundary-check/unified-restore-acceptance-F4vGfaUi/check.py)及原始日志同目录保存。
核对全部九个输入引用、16 个精确命令及日志哈希、源码素材和冻结 checkout、三个 Git 根
及独立对象，再运行三次 fsck。全部 56,702 项安装内容相符，无额外文件或硬链接；
另有 219 个隐式父目录，每一个均须是清单中某条路径必需的父目录，不接受任意额外目录。
随后用恢复副本中的 decoder 校验器再次加载输入，并独立测试四文件 bootstrap：
直接 `-I` 调用按预期因同目录模块不可见退出 1，显式加载后按预期拒绝已有 canonical
目录、未创建输出；复制的辅助模块也重新核对了恢复副本的完整冻结源码。
没有运行正式工具解析器或 proof-check。v10 聚合所覆盖的源码快照前后保持相同；
这不等于把后来新增的脚本和文档计入原冻结候选。

首轮[失败记录](../../artifacts/boundary-check/unified-restore-acceptance-dyLR3kRv/report.json)
保留，SHA-256 `74ffcec30b79f94ce86118dba13b3c74fc2a2911aaae3135eba6592da5920117`。
它把清单必需的隐式父目录误报为额外安装内容，退出 1；第二轮按既有归档格式校正
父目录判定后另建报告，没有修改恢复副本、包、生产恢复器或首轮记录。

[19 项入口回归](../../scripts/tests/test_restore_fixed_inputs.py)在普通 Python 和 `-O`
均通过；归档库 23 项回归也在两种模式复跑通过，
[四组测试日志](../../artifacts/boundary-check/unified-restore-acceptance-F4vGfaUi/test-report.json)已保存。
测试覆盖输出占用/别名、固定身份、
归档内容/目录/链接、环境恢复、安装目录碰撞及保留无关文件，不替代真实恢复实跑。

仍待完成：新环境中的固定绝对路径部署、兼容宿主工具和动态库核验、同候选的完整生成、
Lean/Rocq/native 链、源码差异与公开结论审计，以及实际 CI 下载重放、发布和第三方记录。
[后续宿主静态记录](FIXED_HOST_INPUT_REVIEW.md)已核对声明输入的 ELF 元数据和宿主库名候选，
并发现冷构建还需四项下载内容；[单独补充包](FIXED_CMAKE_DOWNLOADS.md)已保存并独立校验。
这不改变本页恢复实跑的范围，不代表已完成宿主兼容或已把下载补充包接入 handoff v1。
[v10 聚合](AUDIT_RELEASE.md)的六类缺失义务不因本次输入恢复而变绿。
进一步 LXD/宿主变更仍按[既有事故记录](LXD_WRAPPER_SIDE_EFFECT.md)暂停；本入口不安装宿主软件。
