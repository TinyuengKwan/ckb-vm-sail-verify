# Sail C++ 生成名称的受限对应审查

承接[完整模型身份审查](SAIL_MODEL_IDENTITY.md)。本项关闭两份已留存 C++ 输出的
**受限标记对应**检查，不关闭编译器准入、一般运行等价或 Week6 发布门槛。

```sh
python3 scripts/sail_cpp_correspondence.py
python3 -m unittest discover -s scripts/tests -p test_sail_cpp_correspondence.py
python3 -O -m unittest discover -s scripts/tests -p test_sail_cpp_correspondence.py
```

## 实际结果

[报告](../../artifacts/boundary-check/sail-cpp-correspondence-12524i33/report.json)
SHA-256：`f84f9104f8823640b7149ce8cb1083a66adcb201993213cccb6ffda48bbb341b`。
[完整名称映射](../../artifacts/boundary-check/sail-cpp-correspondence-12524i33/correspondence.json)
SHA-256：`29392d8a4bb61e323e0490b325f5dd288575046813f336d24fc01a5fca388d47`。
2026-09-12 22:18:28–22:19:34 UTC，外层退出 2，状态
`scoped_token_correspondence_checked_semantics_pending`。20 项测试在普通 Python 与 `-O` 下通过。
审查器源码 SHA-256：`a98fbe33d38890d2bb22af905a1377c6a1d56ea9f20823a2a151788f46ea6f08`。

输入是原候选生成报告绑定的旧、新 `.cpp` 与 `.h`，没有重新生成、排序或写回任何模型：

| 范围 | 实测结果 |
| --- | --- |
| 全局生成字段 | 642 个，一套覆盖整个实现和头文件的一一映射；130 个名称改变 |
| 单独识别的 Model 方法区域 | 3,675 个，含构造/析构；名称和顺序相同 |
| 方法外间隙 | 3,676 段全部比较，未跳过文件头、尾或未单独识别的函数 |
| 局部变量名称 | 检查 58,637 个方法内名称，其中 18,230 个改变 |
| 局部 label 名称 | 检查 26,634 个，其中 20,856 个改变；要求本方法内有唯一声明 |
| 保守固定名称 | 在头文件或方法外出现的 86 个合成局部名称在方法内也不得改变 |
| 头文件 | 原声明顺序、对应类型、初始化器及其余标记全部保留，不按名称排序 |

另有 20 个 `create_letbind_*` / `kill_letbind_*` 方法因首行同时含语句，未落入单独
方法识别格式；它们作为间隙中的文本受到更严格比较，**不是漏检或被丢弃**。
因此不能把报告的 `method_count` 写成全部 3,695 个 Model 方法均作了局部映射。

此前六个“相同原始名称而类型不同”的声明，在全局对应下得到以下结果：

| 旧名称 | 对应新名称 | 两侧对应类型 |
| --- | --- | --- |
| `z0zE177` | `z0zE185` | `sail_int` |
| `z0zE185` | `z0zE163` | `bool` |
| `z0zE265` | `z0zE277` | `enum zExtContextPolicy` |
| `z0zE277` | `z0zE273` | `bool` |
| `z0zE363` | `z0zE367` | `bool` |
| `z0zE371` | `z0zE363` | `sail_int` |

## 检查规则与边界

空白、常量、运算符、普通名称、字符串/字符字面量、普通注释都必须逐标记相同。
只允许同族生成名称的一一替换；不变名称的出现也参与映射，防止与已有名称合并。
仅 `/* lifted zz50zE… */` 和 `// register zz50zE…` 两种精确生成注释可随同一字段映射改变。
方法边界用词法花括号配平，字面量和注释中的花括号不参与配平。
不支持的原始字符串、未闭合字面量或注释直接拒绝。

后续只读复核重算了全部报告输入和映射文件哈希，并直接使用已保存的映射在内存中重建
完整旧实现/头文件：结果逐字等于新文件，不写回源码。该复核不调用 `compare()`、
`Bijection` 或映射推导，但共享受限词法器及区域识别，因此不算独立 C++ 解析器验证。
另补充未单独识别方法的间隙变异、已存在名称捕获，以及真实字段声明交换的拒绝测试。

这不是完整 C++ 解析器，没有证明宏展开、词法嵌套作用域中的名称绑定、外部引用、
ABI 或执行等价，也未解释生成器 fresh-name 编号变化的根因。不能单凭此项称为形式化
alpha 等价证明。配置 schema 不在本审查器的输入范围；其一致性属于原生成比较报告。
本项不重新认证完整 Sail 安装或宿主工具闭包。

原[候选三后端比较](../../artifacts/boundary-check/sail-candidate-model-rjsls7ks/report.json)
仍是原始字节比较失败，未回写为通过；四份正式证明政策在本项前后哈希不变。
接下来仍需实际候选 C++ 编译、运行差分及独立的正式工具身份/资格准入审查。

## 保留的失败尝试

首轮[失败报告](../../artifacts/boundary-check/sail-cpp-correspondence-ami1h4um/report.json)
SHA-256：`8109977f3c8988ef11a4550a07eb258ed80d7d9c9f1d76717a4e68382641e896`。
旧扫描器误以为方法闭括号必须位于第 0 列，构造函数实际采用缩进闭括号，导致区域跨过
析构函数，报 `tokens after the method body`。已保留当时的 `probe-source.py`
（SHA-256 `5ec9a9e428d7a2964488560a7fa2f32b3809c689a45035410b0e6d4b8227f8cf`），
只修正边界识别并补充构造/析构、尾部间隙及注释/字面量花括号测试。
失败记录不改写，也不将扫描器格式错误解释为模型语义错误。
