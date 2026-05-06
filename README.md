# qubes-singroute-gateway

> Qubes OS 网络架构实践 — 透明代理、流量转发、策略路由学习项目

[![Qubes OS](https://img.shields.io/badge/Qubes%20OS-4.3-3f51b5?logo=qubesos)](https://www.qubes-os.org/)
[![sing-box](https://img.shields.io/badge/sing--box-1.13+-ff6b00)](https://sing-box.sagernet.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 项目简介

本项目是一个 **Qubes OS 网络架构学习与实践项目**，通过搭建透明代理网关，深入理解 Linux 网络子系统的核心技术：

- **nftables** 包过滤与流量标记
- **策略路由**（Policy Routing）与路由表管理
- **TUN/TAP** 虚拟网络设备
- **DNS 分流**与域名解析策略
- **透明代理**流量转发机制
- **Python TUI** 终端界面开发

项目基于 [sing-box](https://sing-box.sagernet.org/) 通用代理平台，实现了完整的网络流量转发链路，适合作为 Qubes OS 网络架构的学习案例。

## 学习目标

通过本项目，你将学到：

### 1. Linux 网络基础
- 网络命名空间与虚拟接口
- IP 转发与路由表
- nftables 防火墙规则编写
- fwmark 标记与策略路由

### 2. 代理技术原理
- SOCKS/HTTP 代理协议
- 透明代理实现方式（TUN/redir）
- 代理协议：vmess/vless/shadowsocks/trojan
- 传输层：WebSocket/gRPC/HTTP/2

### 3. Qubes OS 架构
- AppVM / NetVM / SysVM 隔离模型
- 虚拟机间网络通信
- 持久化存储机制（/rw/config）

### 4. Python 开发实践
- TUI 终端界面开发
- 并发网络编程（测速模块）
- 配置文件管理
- systemd 服务集成

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Qubes OS 架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  AppVM   │  │  AppVM   │  │  AppVM   │  ← 应用层        │
│  │  (work)  │  │(personal)│  │  (dev)   │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │              │              │                       │
│       └──────────────┼──────────────┘                       │
│                      ▼                                      │
│  ┌───────────────────────────────────────────┐              │
│  │           NetVM (本项目)                   │  ← 网络层    │
│  │                                           │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  nftables                           │  │              │
│  │  │  - 新连接标记 fwmark=0x2022         │  │              │
│  │  │  - NAT 转发                         │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  策略路由 (table 2022)              │  │              │
│  │  │  - 匹配 fwmark 的流量 → TUN        │  │              │
│  │  │  - 其他流量 → 默认路由              │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  TUN 设备 (tun0)                    │  │              │
│  │  │  - 地址: 198.18.0.1/30              │  │              │
│  │  │  - MTU: 9000                        │  │              │
│  │  │  - 栈: gvisor (用户态)              │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  sing-box 核心                      │  │              │
│  │  │  ├ DNS 分流:                        │  │              │
│  │  │  │  - 国内域名 → 系统 DNS (直连)    │  │              │
│  │  │  │  - 国外域名 → 代理 DNS           │  │              │
│  │  │  ├ 路由规则:                        │  │              │
│  │  │  │  - 国内 IP → direct (直连)       │  │              │
│  │  │  │  - 私有 IP → direct              │  │              │
│  │  │  │  - 其他 → auto (自动选节点)      │  │              │
│  │  │  └ 出站: vmess/vless/ss/trojan      │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │         sys-firewall → Internet           │              │
│  └───────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心技术点

#### 1. 流量标记 (nftables)

```bash
# nftables 规则：标记来自 AppVM 的新连接
nft add rule inet singbox mark meta mark set 0x2022
```

`fwmark`（防火墙标记）是 Linux 内核的一个字段，用于在数据包上打标签，配合策略路由实现流量分流。

#### 2. 策略路由 (ip rule)

```bash
# 创建自定义路由表
echo "2022 singroute" >> /etc/iproute2/rt_tables

# 策略路由：匹配 fwmark 的流量使用表 2022
ip rule add fwmark 0x2022 lookup 2022

# 表 2022 的默认路由指向 TUN 设备
ip route add default dev tun0 table 2022
```

策略路由允许根据数据包的属性（如 fwmark）选择不同的路由表，实现"同目的不同路径"。

#### 3. TUN 设备

```python
# sing-box 配置中的 TUN 入站
{
    "type": "tun",
    "interface_name": "tun0",
    "address": ["198.18.0.1/30"],
    "auto_route": True,      # 自动添加路由
    "strict_route": True,    # 严格路由模式
    "stack": "gvisor",       # 用户态 TCP/IP 栈
    "mtu": 9000              # 最大传输单元
}
```

TUN 是 Linux 内核提供的虚拟网络设备，工作在三层（IP 包），sing-box 通过它接收所有被标记的流量。

#### 4. DNS 分流

```python
# DNS 服务器配置
"servers": [
    {"tag": "dns-system", "server": "10.139.1.1", "detour": "direct"},  # Qubes 系统 DNS
    {"tag": "dns-proxy", "server": "8.8.8.8", "detour": "auto"},        # 代理 DNS
    {"tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"} # 国内 DNS
]

# DNS 路由规则
"rules": [
    {"domain_suffix": [".cn"], "server": "dns-system"}  # .cn 域名用系统 DNS
]
```

DNS 分流确保国内域名走国内 DNS 解析（快速），国外域名走代理 DNS 解析（准确）。

---

## 功能特性

### 代理协议支持
- vmess / vless / shadowsocks / trojan
- WebSocket / gRPC / HTTP/2 传输层
- TLS / REALITY 加密

### 流量管理
- **智能分流** — 国内直连，国外走代理
- **全部代理** — 所有流量走代理（局域网除外）
- **仅代理受限** — 只代理受限站点
- **全局代理** — 指定节点转发全部流量
- **直连** — 不走代理（调试用）

### 管理工具 (singctl)
- TUI 交互界面
- 多订阅源管理
- 节点测速 + 延迟显示
- IP 地理位置检测（显示区域名称）
- DNS 提供商选择（Google/Cloudflare/Quad9/AdGuard/Mullvad）
- 自定义路由规则

### 自动化
- **订阅自动更新** — 每 6 小时
- **节点健康监控** — 每 5 分钟检测，连续 3 次失败自动剔除
- **配置持久化** — 重启不丢失

---

## 快速开始

### 前提条件

- Qubes OS 4.3（其它版本未测试，不保证兼容）
- 一个 Debian 12/13 的 AppVM 作为 NetVM
- 该 VM 需要能访问互联网（通过 sys-firewall）

### 一行命令安装

在你的 NetVM 中执行：

```bash
# 方法一：先 clone 再安装（推荐）
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway
sudo bash install.sh

# 方法二：直接下载安装脚本
sudo bash <(curl -fsSL https://raw.githubusercontent.com/iasds/qubes-singroute-gateway/master/install.sh)
```

安装脚本会自动完成：
1. ✅ 安装系统依赖（python3、nftables、pip）
2. ✅ 下载安装 sing-box（支持本地二进制 fallback）
3. ✅ 安装 singctl 管理工具
4. ✅ 配置透明代理网络（nftables mark + 策略路由）
5. ✅ 创建系统服务（sing-box + 自动更新 + 监控）
6. ✅ 生成初始配置

### 配置订阅

```bash
singctl
# 选择：订阅管理 → 添加订阅 → 输入你的订阅 URL
```

### 设置 AppVM 使用代理网关

在 dom0 中：

```bash
# 单个 VM
qvm-prefs your-app-vm netvm sys-proxy

# 批量设置
for vm in work personal dev; do
    qvm-prefs $vm netvm sys-proxy
done
```

### 验证

在 AppVM 中：

```bash
# 测试网络访问
curl -s https://www.google.com

# 查看出口 IP
curl -s https://api.ipify.org

# 测试 DNS 解析
nslookup github.com
```

---

## 更新/卸载

再次运行安装脚本，会自动检测已安装版本并提供选项：

```bash
sudo bash install.sh
```

```
╔══════════════════════════════════════════════════════════╗
║   Qubes Proxy Gateway — 安装/更新/卸载工具              ║
╚══════════════════════════════════════════════════════════╝

当前状态: 已安装 v1.2.0 → 有新版本 v1.3.0

────────────────────────────────────────────────────────
  [1] 更新到 v1.3.0
  [2] 卸载
  [3] 退出
```

也支持命令行参数：

```bash
sudo bash install.sh install    # 直接安装
sudo bash install.sh update     # 直接更新
sudo bash install.sh uninstall  # 直接卸载
```

---

## singctl 详解

### 主菜单

```
╔══════════════════════════════════════════════════════════╗
║                    singctl v1.2.0                        ║
║              Qubes Singroute Gateway 管理                ║
╚══════════════════════════════════════════════════════════╝

  当前模式: 智能分流    DNS: Google DNS
  节点: 美国 US-Node-01 (45ms)    订阅: 2 个, 37 个节点

  [1] 代理模式    切换分流策略
  [2] 节点管理    查看/切换节点
  [3] 订阅管理    添加/更新订阅
  [4] DNS 设置    选择 DNS 提供商
  [5] 自定义规则  添加路由规则
  [6] 状态面板    服务状态监控
  [7] 退出
```

### 代理模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| 智能分流 | 国内直连 + 国外代理 | 日常使用 |
| 全部代理 | 全部走代理（局域网除外） | 需要全局代理 |
| 仅代理受限 | 只代理受限站点 | 节省代理流量 |
| 全局代理 | 指定节点转发全部 | 调试/特殊需求 |
| 直连 | 不走代理 | 测试/排除问题 |

### 节点管理

```
节点列表 (按订阅分组)
────────────────────────────────────────
订阅: MyProvider (25 个节点)

  #  区域      节点名称              延迟
  1  美国      US-Node-01            45ms
  2  日本      JP-Node-02            67ms
  3  新加坡    SG-Node-03            89ms
  4  中国香港  HK-Node-04            32ms
  5  中国台湾  TW-Node-05            55ms

订阅: BackupProvider (12 个节点)

  6  美国      US-Backup-01          120ms
  7  日本      JP-Backup-02          95ms

操作:
  [数字] 切换到该节点
  [a] 自动选最优节点
  [t] 测速全部节点
  [q] 返回
```

### DNS 设置

| DNS 提供商 | 特点 | 推荐场景 |
|-----------|------|---------|
| Google DNS | 经典，稳定可靠 | 通用 |
| Cloudflare | 速度快，无日志 | 注重速度 |
| Quad9 | 安全优先，拦截恶意域名 | 注重安全 |
| AdGuard | 隐私保护 + 广告拦截 | 去广告 |
| Mullvad | 严格无日志，瑞典隐私法 | 极致隐私 |

---

## 自动服务

安装后会自动启用以下 systemd 服务：

| 服务 | 说明 | 频率 |
|------|------|------|
| `sing-box.service` | 代理核心服务 | 持续运行 |
| `singbox-monitor.service` | 节点健康监控 | 每 5 分钟检测 |
| `update-subscriptions.timer` | 订阅自动更新 | 每 6 小时 |

管理命令：

```bash
# 查看 sing-box 状态
systemctl status sing-box

# 查看监控服务
systemctl status singbox-monitor

# 查看自动更新定时器
systemctl status update-subscriptions.timer

# 手动触发订阅更新
update-singbox-config

# 查看日志
journalctl -u sing-box -f
journalctl -u singbox-monitor -f
```

---

## 配置文件

所有配置存储在 `/rw/config/sing-box/`（Qubes 持久化存储）：

| 文件 | 说明 |
|------|------|
| `config.json` | sing-box 主配置 |
| `singctl-subscriptions.json` | 订阅源列表 |
| `singctl-preferences.json` | 用户偏好（模式、DNS、选中节点） |
| `singctl-custom-rules.json` | 自定义路由规则 |

备份配置：

```bash
tar czf ~/backup-singroute-$(date +%Y%m%d).tar.gz /rw/config/sing-box/
```

恢复配置：

```bash
tar xzf ~/backup-singroute-20260506.tar.gz -C /
systemctl restart sing-box
```

---

## 故障排除

### AppVM 无法上网

```bash
# 在 NetVM 中检查
systemctl is-active sing-box          # 是否运行
nft list ruleset | grep singbox       # nftables 规则
ip route show table 2022              # 策略路由
ip addr show tun0                     # TUN 接口
journalctl -u sing-box --no-pager -n 50  # 最近日志
```

### DNS 解析失败

```bash
# 在 AppVM 中
cat /etc/resolv.conf                  # DNS 配置
nslookup google.com 8.8.8.8          # 测试 DNS

# 在 NetVM 中
singctl → DNS 设置 → 切换 DNS 提供商
```

### 节点全部超时

```bash
# 更新订阅获取新节点
update-singbox-config

# 或通过 singctl
singctl → 订阅管理 → 更新全部订阅
```

### 安装失败

```bash
# 检查 sing-box 是否安装成功
sing-box version

# 检查 Python 依赖
python3 -c "import simple_term_menu"

# 检查网络连接
curl -s https://api.github.com

# 查看安装日志
sudo bash -x install.sh 2>&1 | tee install.log
```

---

## 项目结构

```
qubes-singroute-gateway/
├── install.sh                          # 一键安装/更新/卸载脚本
├── uninstall.sh                        # 卸载脚本
├── README.md                           # 本文档
├── scripts/
│   ├── setup-netvm.sh                  # NetVM 网络配置 (nftables + 路由)
│   ├── auto-update-subscriptions.sh    # 订阅自动更新脚本
│   ├── update-subscriptions.service    # systemd 服务
│   ├── update-subscriptions.timer      # systemd 定时器
│   ├── singbox-monitor.service         # 节点监控服务
│   └── test-connectivity.sh            # 连通性测试
└── singctl/
    ├── __init__.py                     # 版本号
    ├── __main__.py                     # 入口
    ├── cli.py                          # CLI 入口
    ├── config.py                       # 常量、路径、预设
    ├── data.py                         # 数据存储
    ├── nodes.py                        # 节点解析、测速、地理位置
    ├── proxy.py                        # 代理模式、配置生成
    ├── subs.py                         # 订阅管理
    ├── monitor.py                      # 节点健康监控
    └── ui.py                           # TUI 界面
```

---

## FAQ

### Q: 这个项目的学习价值在哪里？

A: 通过搭建透明代理网关，你可以深入理解：
- Linux 网络子系统（nftables、路由、TUN）
- 代理协议原理（vmess/vless/ss/trojan）
- Qubes OS 安全架构（VM 隔离、网络分层）
- Python 系统编程（TUI、并发、服务管理）

### Q: 支持哪些代理协议？

A: sing-box 支持的所有协议：vmess、vless、shadowsocks、trojan、hysteria、tuic、wireguard 等。本项目主要测试了 vmess 和 shadowsocks。

### Q: 和 Qubes VPN 有什么区别？

A: Qubes VPN 在 VPN 层面工作，需要每个 VM 配置或使用 VPN ProxyVM。本项目在代理层面工作，通过 TUN 透明代理，AppVM 完全无感知。

### Q: 会影响 Qubes 之间的隔离吗？

A: 不会。每个 AppVM 仍然通过自己的网络栈访问 NetVM，Qubes 的网络隔离机制完全保留。

### Q: 如何恢复默认配置？

A: 删除配置目录并重新安装：
```bash
sudo rm -rf /rw/config/sing-box
sudo bash install.sh
```

### Q: 支持 IPv6 吗？

A: 当前不支持。Qubes OS 默认不使用 IPv6，且大部分代理节点不提供 IPv6。

---

## 开发

### 本地开发

```bash
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway

# 安装依赖
pip3 install simple-term-menu pyyaml

# 直接运行（不安装）
python3 -m singctl
```

### 贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

## 致谢

- [sing-box](https://github.com/SagerNet/sing-box) — 通用代理平台
- [Qubes OS](https://www.qubes-os.org/) — 安全操作系统
- [simple-term-menu](https://github.com/IngoMeyer441/simple-term-menu) — Python TUI 库

---

## 延伸阅读

- [Qubes OS 官方文档](https://www.qubes-os.org/doc/)
- [sing-box 配置文档](https://sing-box.sagernet.org/configuration/)
- [Linux 策略路由指南](https://www.policyrouting.org/)
- [nftables wiki](https://wiki.nftables.org/)
- [TUN/TAP 设备详解](https://www.kernel.org/doc/Documentation/networking/tuntap.txt)
