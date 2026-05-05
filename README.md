# qubes-proxy-gateway

Qubes OS 透明代理网关，基于 sing-box，支持 vmess/ss/trojan/vless 协议。

## 功能

- 一键部署 sing-box 透明代理网关
- 支持 vmess、shadowsocks、trojan、vless 协议
- TUI 管理工具 (singctl)
- 多订阅源支持
- 自动测速选节点
- IP 地理位置检测（国旗显示）
- 多种代理模式（智能分流、全部代理、仅代理被墙、全局代理、直连）
- 持久化配置（重启不丢失）

## 前提条件

- Qubes OS 4.1+
- 一个 Debian/Ubuntu based 的 AppVM 作为 NetVM
- 该 AppVM 需要能访问互联网

## 快速开始

### 1. 创建 NetVM

在 dom0 中创建一个 AppVM 作为代理网关：

```bash
# 创建 AppVM
qvm-create --class AppVM --template debian-12 sys-proxy
qvm-prefs sys-proxy netvm sys-firewall
qvm-prefs sys-proxy provides_network True

# 或者使用已有的 AppVM
qvm-prefs your-vm provides_network True
```

### 2. 部署到 NetVM

在 dom0 中执行：

```bash
# 复制项目到 NetVM
qvm-copy-to-vm sys-proxy /path/to/qubes-proxy-gateway

# 或者直接在 NetVM 中克隆（如果能访问 GitHub）
qvm-run --pass-io sys-proxy 'cd /home/user && git clone https://github.com/your-user/qubes-proxy-gateway.git'
```

在 NetVM 中执行：

```bash
cd /home/user/qubes-proxy-gateway
sudo bash install.sh
```

### 3. 配置订阅

安装完成后，运行 singctl 配置订阅：

```bash
singctl
```

选择 `订阅管理` → `添加订阅`，输入你的订阅 URL。

### 4. 设置 AppVM 使用代理网关

在 dom0 中，将需要翻墙的 AppVM 的 NetVM 设置为 sys-proxy：

```bash
qvm-prefs your-app-vm netvm sys-proxy
```

### 5. 测试连通性

在 AppVM 中测试：

```bash
curl -s https://www.google.com
curl -s https://api.ipify.org
```

## singctl 使用

```bash
singctl
```

### 代理模式

- **智能分流** — 中国直连，国外代理
- **全部代理** — 所有流量走代理
- **仅代理被墙** — 只代理被墙站点
- **全局代理** — 指定节点转发全部
- **直连** — 不走代理

### 节点管理

- 查看全部节点（带测速和国旗）
- 按订阅分组切换节点
- 一键清空节点

### 订阅管理

- 添加/删除订阅
- 更新单个/全部订阅
- 自动同步到 sing-box 配置

## 更新订阅

```bash
# 通过 singctl 更新
singctl → 订阅管理 → 更新全部

# 或者命令行更新
sudo update-singbox-config
```

## 项目结构

```
qubes-proxy-gateway/
├── install.sh              # 安装脚本
├── uninstall.sh            # 卸载脚本
├── README.md               # 本文档
├── scripts/
│   ├── setup-netvm.sh      # NetVM 初始化脚本
│   ├── update-config.sh    # 更新配置脚本
│   └── test-connectivity.sh # 连通性测试脚本
├── config/
│   ├── sing-box.service    # systemd 服务文件
│   └── nftables.rules      # nftables 规则
└── singctl/
    ├── __init__.py
    ├── __main__.py
    ├── config.py
    ├── data.py
    ├── proxy.py
    ├── nodes.py
    ├── subs.py
    └── ui.py
```

## 工作原理

```
AppVM → NetVM (sys-proxy) → nftables mark → policy routing → TUN → sing-box
                                                                  ├→ CN: direct
                                                                  └→ Foreign: proxy
```

1. AppVM 的流量通过 vif 接口进入 NetVM
2. nftables 标记新连接（fwmark 0x1）
3. 策略路由将标记的流量转发到 TUN 接口
4. sing-box 通过 TUN 接收流量
5. 根据规则决定直连或走代理

## 故障排除

### sing-box 无法启动

```bash
# 查看日志
sudo journalctl -u sing-box -f

# 检查配置
sudo sing-box check -c /rw/config/sing-box/config.json
```

### AppVM 无法上网

```bash
# 检查 NetVM 是否运行
systemctl is-active sing-box

# 检查 nftables 规则
sudo nft list ruleset | grep singbox

# 检查 IP 转发
cat /proc/sys/net/ipv4/ip_forward
```

### DNS 解析失败

```bash
# 检查 DNS 配置
cat /etc/resolv.conf

# 测试 DNS 解析
nslookup google.com 8.8.8.8
```

## 许可证

待定

## 致谢

- [sing-box](https://github.com/SagerNet/sing-box)
- [Qubes OS](https://www.qubes-os.org/)
