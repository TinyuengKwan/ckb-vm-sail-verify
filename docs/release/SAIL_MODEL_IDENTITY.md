# 新 Sail 的完整模型与 ELF 身份审查

本项承接 [Sail 独立重建](ISOLATED_SAIL.md)。目标是审查新工具的差异和完整生成物，
不是通过更新政策哈希把“同版本”直接当作同一工具，也不是证明编译器正确。

## 完整生成物比较入口

```sh
python3 scripts/probes/probe_sail_model_identity.py
python3 -m unittest discover -s scripts/tests -p test_sail_model_identity.py
python3 -O -m unittest discover -s scripts/tests -p test_sail_model_identity.py
```

入口固定读取上一项源码重建报告及 SHA-256，先重算新 OPAM 安装清单、
新/旧 Sail 完整安装清单和固定编译器源码清单，再建立独立 sail-riscv Git clone。
模型 commit、源码字节/权限、配置和原 Lean 生成物必须匹配现有政策。
旧、新编译器各自使用一个空 CMake 构建目录，不复制旧生成文件或 SMT 缓存。

由固定上游 CMake 文件提供命令，不另手写一份截断版模型：

| 目标 | 比较范围 |
| --- | --- |
| `generated_sail_riscv_model` | 完整 C++ 实现、头文件、配置 schema |
| `generated_lean_rv64d` | 生成目录中的全部原始文件，包括 Lean 源码及项目配置 |
| `generated_rocq_rv64d` | 生成目录中的全部文件，含模型及类型定义 |

C++ 目标使用上游动态配置模型；Lean / Rocq 使用政策绑定的完整合并配置。
该配置从原工作区复制并校验哈希，本项没有重新运行 emulator 来合并配置。
两侧均显式选择各自安装前缀中的支持文件及插件。

原始输出逐文件按相对名称和 SHA-256 比较，不替换路径或改写函数体。
另从各自原始 Lean 输出复制一个兼容目录，只应用既有
`sail-defs-computable.patch` 和固定 `lean-toolchain`；全部 `.lean` 与工具链文件
再对照现有主政策的 `generated_sha256.sail`，不是只检查 ADD 单个函数。
原工作区生成物、原工具安装和原政策均保持不动。

本项只生成模型，没有编译这些 C++ / Lean / Rocq 模型；CMake 配置时的宿主编译器
特性探测不算模型编译。即便所有模型比较一致，入口也返回 2，状态为
`full_model_generation_identical_tool_admission_pending`，不自动采纳工具或冒称新 kernel PASS。
构建失败、生成物差异或输入漂移返回 1。所有阶段日志及原始输出保留。

## ELF 只读核对

```sh
python3 scripts/sail_elf_identity.py \
  --install-report artifacts/boundary-check/isolated-sail-nrdi23ds/report.json \
  --output /absolute/path/to/a-new-audit.json
```

输出文件必须不存在，父目录须已存在；不会修改任何 ELF。比较绑定上述安装报告，
检查实际主程序及所有 10 个 `.cmxs` 原生插件的哈希，拒绝漏掉插件。

[实际 ELF 审查报告](../../artifacts/boundary-check/sail-model-identity-v1weq3h5/elf-audit.json)
SHA-256：`4b2e177360d6101253f0fa96144d8284092d1fe4b188a17b047fa2243a0b72d6`。
报告已由只读审查器重新生成并逐字段独立对照。

结果如下：

- 主程序 `.text` 的 6,613,842 字节完全相同，SHA-256 为
  `1a75ae7c3064ed2312eb9cef72a644cc80c16745442679da969cf3ad7a13c8fd`。
- 主程序所有已分配段的布局相同。文件内容有差异的已分配段只有 `.data` 与
  `.note.gnu.build-id`。`.data` 的全部差异严格落在三个固定 4,096 字节的安装字段：
  Sail 插件目录、OCaml 标准库目录和硬编码 OCaml 搜索路径。
  旧/新完整 payload、长度标记、空格 padding、位置及哈希均已核对；其他数据字节相同。
- 10 个原生插件的代码段均相同。C、Rocq、Lean、Lem、output、SMT、SV 七个插件
  **整份文件**相同；doc、latex、OCaml 三个插件的已分配文件内容仅构建标识不同，
  另观察到 `.debug_info`、`.debug_str` 差异。
- 新旧 Sail 安装文件均为 1,099 项，无增删，295 项条目不同，原始差异清单保留。
  主要是编译产物、调试信息和安装元数据。唯一变化的 `.ml` 文件为生成的
  `lib/libsail/Libsail_sites.ml` 目录定位模块；没有把全部安装清单宣布为相同。

4,096 字节槽位不是任意文本替换：审查器逐一查找唯一的完整旧/新字段，
检查原位和不重叠，并拒绝槽外任意字节变化。长度前缀及 NUL 分隔搜索路径的解释
可在本次新 OPAM 安装的 `lib/dune-site/helpers.ml` 中核对。
这只是内存中的对照计算，不保存“归一化二进制”或绕过原执行文件身份检查。

本项没有证明 ELF 文件头、程序头、所有填充、调试信息等其余字节等价，
没有重新认证宿主动态库/Z3 或证明翻译器正确。不同安装路径也会选择不同依赖闭包，
因此这些观察不能单独替代完整生成/提取与正式工具采纳审计。
15 项模型比较测试及 20 项 ELF 测试在普通 Python 和 `-O` 下通过。

## 当前边界

原运行已结束并失败于旧编译器的政策清单核对：干净重生成没有原目录残留的
`Specialization.lean`，共同文件无差异，详见[旧生成文件审查与隔离演练](SAIL_STALE_GENERATED_FILE.md)。
原失败报告保留；新编译器侧另行比较已完成，Lean 165 项和 Rocq 两项原始输出一致，
但 C++ 源码与头文件不同，整项比较失败；该原比较运行没有进入候选适配阶段或采纳新工具。
ELF 审查本身不计为完整模型比较成功。
新工具尚未进入正式政策，未跑新工具下的完整 ADD 门禁。
原批准工具下已单独接入[精确安装及旧文件清单迁移](SAIL_INSTALL_MIGRATION.md)，
正式主/公开 `proof-check` 已于 2026-09-12 17:36:37 UTC 完成；这不豁免候选 C++ 差异。
后续新工具的[实际联合提取](REBUILT_EXTRACTION_CHAIN.md)和
[公开候选源码级 kernel 链](REBUILT_PUBLIC_KERNEL.md)已完成，后者实际适配候选 Sail Lean，
检查 162 项政策文件并重建全依赖。这不是把原三后端比较失败改成成功，也不是新工具
正式准入。第三方与完整发布门槛仍待完成。

## C++ 原始差异的进一步只读清点

在核验[候选比较报告](../../artifacts/boundary-check/sail-candidate-model-rjsls7ks/report.json)
绑定的两份 `.cpp` / `.h` 原始哈希后，逐行及声明清点得到：两份头文件均为 14,673 行，
两份 C++ 均为 992,190 行，但不只是行顺序不同。642 个形如 `z0zE…` 的成员名称集合
相同，其中六个同名声明的类型不同：

| 生成名称 | 原输出 | 新输出 |
| --- | --- | --- |
| `z0zE177` | `sail_int` | `bool` |
| `z0zE185` | `bool` | `sail_int` |
| `z0zE265` | `enum zExtContextPolicy` | `bool` |
| `z0zE277` | `bool` | `enum zExtContextPolicy` |
| `z0zE363` | `bool` | `sail_int` |
| `z0zE371` | `sail_int` | `bool` |

C++ 还存在大量控制流 label 编号变化。上述表不证明同名成员应具有同一语义，
也不证明架构寄存器类型真的发生变化：这些是生成名称，不能仅按同名判断语义。
不能仅按名称、行重排或大小相近放行，更不能把整个文件随意规范化后更新正式哈希。
后续[受限 C++ 标记对应审查](SAIL_CPP_CORRESPONDENCE.md)已完成：642 个字段建立覆盖
实现和头文件的全局一一映射，对应类型全部一致；3,675 个方法区域及全部间隙均已比较。
六个同名类型差异在该映射下得到解释，声明顺序未改变。未写回任何生成源码；仍未证明
宏展开/名称绑定、形式化 alpha 等价或一般运行等价。
后续[新模拟器冷构建](REBUILT_SAIL_CPP.md)已在另一独立源码副本中实际生成、编译完整
模型并重新物化相同配置，10 阶段通过。新一次生成字节仍有受限名称变化，不称为
字节可复现；后续[实际双端差分与重放](REBUILT_SAIL_RUNTIME.md)也已完成 38 阶段，
32 个案例、188 项适用 mutation 和 32 个实际重放通过。有限执行证据不等于一般
语义等价，正式工具准入仍未关闭。
