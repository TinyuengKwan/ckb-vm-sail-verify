# 非预期宿主变更：LXC 包装脚本触发 Snap 安装

2026-09-13。本次原意是只读查看 clean-room 可用环境，但执行
`lxc remote list --format=json` 前没有先阅读本机包装脚本，因而意外触发宿主安装。
这不是经用户确认的环境迁移，不能作为 clean-room 已完成的证据。

## 已核实事实

- `/usr/sbin/lxc` 是 shell 包装脚本，而不是现成 LXD 客户端。
  SHA-256：`ced5e274aad61faed666527e4d4719efb103c240ae4524f43d87226783e88298`。
  当 `/snap/bin/lxc` 不存在时，它连接 `/run/lxd-installer.socket`，发送触发字节并等待安装。
  当前用户属于 `lxd` 组，因此此触发操作无需交互式 sudo。
- 发现输出 `Installing LXD snap` 后，已终止此次客户端 PID 3733296；工具会话退出 143。
  安装由系统服务独立执行，客户端终止未取消该服务的操作。
- `snap changes` 确认 change **2** 为此次安装：06:01 UTC 开始，06:03 UTC 完成。
  安装目标为 `lxd`，channel `5.21/stable/ubuntu-24.04`。
- 为中止自己的非预期安装，曾执行 `snap abort 2`，结果为 access denied；
  `sudo -n snap abort 2` 返回需要密码。未请求或输入管理员密码。
- 最终 `snap list lxd` 显示版本 `5.21.7-1018661`，revision **40585**，安装已经完成。
- `snap tasks 2` 还记录了依赖 snap **core24 revision 2124**、**snapd revision 27738**
  的安装，snapd 自动重启、LXD 默认配置/安装 hook、服务启动和安全配置步骤。
  因此影响不止于下载一个客户端文件。
- 助手没有执行 `lxd init`、创建容器、配置网络/存储或卸载任何 snap；
  这不等于声称安装 hook 没有初始化内部数据。

## 当前处理边界

停止进一步 LXD/宿主环境操作，向用户披露变更并请求是否保留的指示。
没有自动删除 LXD、其数据或关联依赖；若决定移除，应先由管理员检查实际数据和依赖，
避免把安装后的其他使用一并删除。未声称回滚已完成。

此前已完成的 native、Rocq 和 v9 本地聚合报告保持原始字节。
事件发生时，正式 `proof-check` 在既有会话中进行公开 decoder/冷构建阶段；没有因该事件重新启动它。
该次完整门禁随后于 06:26 UTC 退出 0，06:29 UTC [独立验收通过](FORMAL_MAIN_INTEGRATION.md)。
最终环境审计须显式记录本次宿主变更，不得宣称整段执行中宿主环境完全未变。
