# 下层 Option.map 差异：显式 sysroot 对照

2026-09-12。在新旧 Aeneas 对同一 LLBC 输出一致之后，继续对同一个实际最小共享闭包
源码进行四次新提取：原批准 / 新构建 base Charon × 已安装 Rust std / 新 full-MIR。
四份 LLBC 均用同一个新 join-only Aeneas 翻译，根、include 和检查选项不变。

## 实测结果

```sh
python3 -O scripts/probes/probe_lower_sysroot_matrix.py
```

[报告](../../artifacts/boundary-check/lower-sysroot-matrix-9vbqg674/report.json)：
19:16:50–19:18:22 UTC，10 阶段全部退出 0，外层退出 2，
`sysroot_matrix_completed_no_adoption`。SHA-256：
`2ad13e449c49593a2d5e5c8f86fc4df3f4a2b3b2f709e668ca3c5453da81b121`。

| 显式 sysroot | 原 Charon | 新 Charon |
| --- | --- | --- |
| `default`，指向已验私有 Rust 安装 | 原 map 形状；按既有规则匹配原 MiniComplete 政策 | 整份原始输出与左侧相同 |
| 新 full-MIR 的绝对目录 | 新 map 形状；重现此前身份不符的模型 | 整份原始输出与左侧相同 |

已安装 std 两份原始模型哈希为
`56205ec91e57742586a5a035131619a2fe35136d53657323bc4867f795fef164`；其既有规范化哈希
为原政策 `d74c806ad263565153fed59538426c442f948774b18c6c025b0c95c97673791a`。
full-MIR 两份原始模型均为
`6f65774afd345abc9b3e058f9c47db450057984d4e054838986fb65ae863fd4b`，与前一轮新模型逐字节相同。
没有修改生成文件或新增身份规范化规则。

同一 sysroot 下切换 Charon 二进制不改变输出；切换 sysroot 则重现 map 的函数体变化。
这是本次固定最小模型、两个固定翻译器和两套固定库的对照结果，不能推广为整个 Charon
或标准库的等价证明。旧报告没有记录实际选择的隐式 sysroot；**本次不追认旧运行的库身份**。

只读 LLBC 检查还显示，原 map 有 7 个局部变量，新 map 有 9 个，并多出布尔状态赋值；
生成 Lean 中对应 `(o, b)` 和末尾 `if b then ok o else ok o`。单看这些形状不足以放行
精确定义审计；后续[实际 kernel 等价与原 raw 定理连接](LOWER_MAP_EQUIVALENCE.md)另有记录。

## 保证边界

两套库依赖独立 Rust / full-MIR 报告及完整安装清单核验；实际选择由 `--sysroot` 明确
给出，清除环境中的隐式 Miri / Charon / Aeneas 选择。原工具继续按正式二进制哈希绑定，
新工具按独立构建记录绑定。这不是工具采纳、历史来源补证、完整 clean-room 或新 kernel。
五项检查器测试在普通 Python 与 `-O` 下通过。
完成后独立复核十阶段日志、精确 argv/cwd、工具/库安装身份、源码、四份 LLBC/模型及
两对结果通过，原政策未改变。
