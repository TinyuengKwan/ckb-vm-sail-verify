# 四项 CMake 下载输入补充包

2026-09-13。**本次打包已保存固定下载内容并完成独立字节验证；打包过程不执行冷配置、编译或发布。**
后续另行完成的[本机真实冷配置与 GMP 构建](FIXED_CMAKE_CONFIGURATION.md)有独立执行/验收报告，
不改写本页打包报告的范围，也不代表完整新环境验收。
[宿主前置条件核验](FIXED_HOST_INPUT_REVIEW.md)发现，冻结 Sail-RISC-V 源码的冷构建还引用
四个网络下载。这些内容不在 handoff v1 的三个归档中；不能从“源码＋工具已恢复”推断
冷构建不需要其他输入。本次从原构建缓存复制精确内容，没有重新下载或更改 CMake 源码。

## 固定来源

关联的 Sail-RISC-V commit 为 `8f91355eee63a85738723603e23d32eecdd763dc`，
源码快照文件 SHA-256 为 `810b71aa1d4002acce1ad0fc52ef1f37019a6e57550d1c5e381c06b68c5b9999`。

| 输入 | 字节数 | 源码规定的校验 |
| --- | ---: | --- |
| GMP 6.3.0 `.tar.xz` | 2,094,196 | SHA256 `a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898` |
| CLI11 2.6.2 `CLI11.hpp` | 473,783 | SHA256 `227a16fe5f9f8ada80c3c409492475536f597e7bd83a6c26eacc3c8c149a9295` |
| jsoncons 1.8.1 `.tar.gz` | 1,664,123 | SHA3_256 `c1f7957049ce756005ce67917ce8b6f09c0cf56e630664edeb272365229baada` |
| asio 1.36.0 `.tar.bz2` | 3,217,022 | SHA3_256 `5979be31450b6e8d09ab7e766f62f4f7e1be85f090f2a9a773e12203922e5ce9` |

外部[清单](../../artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/manifest.json)
同时记录各项 SHA256、源码声明文件身份、原 URL、哈希算法及本机缓存来源。
清单 SHA-256：`792223f4b9773e647805edc4b0b9e1a2064d1a2c498866d14c1a748f405217dd`。
SHA3_256 没有被误当作 SHA256。

## 实际打包与独立验收

08:23:00–08:23:01 UTC 的[打包报告](../../artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/report.json)
退出 0，SHA-256 `cb857cd421e00227e99f12777d5ac3e323166e02fa927ce3e25110d185e7e08b`。
[代码](../../artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/build.py)和原始四文件副本保留。
输入共 7,449,124 字节；[压缩包](../../artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/cmake-downloads.tar.gz)
为 7,031,333 字节，SHA-256
`51589032e8adc0aa6db1420633630e5d83cbbb0e094990d0484dd9f6fc8199c9`。
包仅含四个扁平普通文件；逐条验证类型、权限、长度与摘要后解到新 `roundtrip/`，
原缓存、保存副本和往返副本字节一致且没有共享 inode。没有覆盖原构建缓存。

08:24:39 UTC 的[独立验收](../../artifacts/boundary-check/fixed-cmake-downloads-GyJYxzS7/independent-report.json)
退出 0，SHA-256 `48df839944e87e07e2e851828f68b27cf6e2514423bd6ea14774a96af3e984ef`。
由另一个 Python `-O` 进程重新检查实际压缩包、清单、四份源声明及三处文件副本；
每项的同长度损坏和截断均被拒绝，共 8 个负测。

## 尚未关闭

本包不是完整 build-input 闭包，也不是 release 包。格式为
`fixed-cmake-download-inputs-v1`，不能直接传给安装补充包恢复器来冒充同一种格式。
没有修改 [handoff v1](fixed-input-handoff-20260913-v1.json)、统一恢复器或冻结源码身份，
也没有将本包无声接入旧恢复报告。

后续本机新目录的实际配置已确认三个 FetchContent 本地源码覆盖，GMP 也由预置归档完成
构建；仍须接入正式固定路径的新环境部署和后续交付版本。
宿主工具/头文件/静态库、Cargo 缓存、生成物、完整执行与第三方记录
仍是单独义务。对外分发前还须审查许可证与隐私元数据；本次未上传或发布。
