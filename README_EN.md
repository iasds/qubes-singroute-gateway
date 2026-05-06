# qubes-singroute-gateway

> Qubes OS Network Architecture Practice — Transparent Proxy, Traffic Forwarding, Policy Routing Learning Project

[![Qubes OS](https://img.shields.io/badge/Qubes%20OS-4.3-3f51b5?logo=qubesos)](https://www.qubes-os.org/)
[![sing-box](https://img.shields.io/badge/sing--box-1.13+-ff6b00)](https://sing-box.sagernet.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Project Introduction

This project is a **Qubes OS network architecture learning and practice project**. By building a transparent proxy gateway, it provides deep understanding of the core technologies of the Linux networking subsystem:

- **nftables** packet filtering and traffic marking
- **Policy Routing** and routing table management
- **TUN/TAP** virtual network devices
- **DNS splitting** and domain resolution strategies
- **Transparent proxy** traffic forwarding mechanisms
- **Python TUI** terminal interface development

The project is based on [sing-box](https://sing-box.sagernet.org/), a universal proxy platform, and implements a complete network traffic forwarding pipeline, making it an ideal learning case for Qubes OS network architecture.

## Learning Objectives

Through this project, you will learn:

### 1. Linux Networking Fundamentals
- Network namespaces and virtual interfaces
- IP forwarding and routing tables
- nftables firewall rule writing
- fwmark marking and policy routing

### 2. Proxy Technology Principles
- SOCKS/HTTP proxy protocols
- Transparent proxy implementation methods (TUN/redir)
- Proxy protocols: vmess/vless/shadowsocks/trojan
- Transport layers: WebSocket/gRPC/HTTP/2

### 3. Qubes OS Architecture
- AppVM / NetVM / SysVM isolation model
- Inter-VM network communication
- Persistent storage mechanism (/rw/config)

### 4. Python Development Practices
- TUI terminal interface development
- Concurrent network programming (speed test module)
- Configuration file management
- systemd service integration

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Qubes OS Architecture                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  AppVM   │  │  AppVM   │  │  AppVM   │  ← Application   │
│  │  (work)  │  │(personal)│  │  (dev)   │    Layer          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │              │              │                       │
│       └──────────────┼──────────────┘                       │
│                      ▼                                      │
│  ┌───────────────────────────────────────────┐              │
│  │           NetVM (this project)            │  ← Network   │
│  │                                           │    Layer      │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  nftables                           │  │              │
│  │  │  - Mark new connections fwmark=0x2022│ │              │
│  │  │  - NAT forwarding                   │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  Policy Routing (table 2022)        │  │              │
│  │  │  - Matched fwmark traffic → TUN     │  │              │
│  │  │  - Other traffic → default route    │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  TUN Device (tun0)                  │  │              │
│  │  │  - Address: 198.18.0.1/30           │  │              │
│  │  │  - MTU: 9000                        │  │              │
│  │  │  - Stack: gvisor (userspace)        │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  sing-box Core                      │  │              │
│  │  │  ├ DNS Splitting:                   │  │              │
│  │  │  │  - Matched domains → system DNS  │  │              │
│  │  │  │    (direct)                       │  │              │
│  │  │  │  - Other domains → proxy DNS     │  │              │
│  │  │  ├ Routing Rules:                   │  │              │
│  │  │  │  - Matched IP → direct           │  │              │
│  │  │  │  - Private IP → direct           │  │              │
│  │  │  │  - Other → auto (auto-select     │  │              │
│  │  │  │    node)                          │  │              │
│  │  │  └ Outbounds: vmess/vless/ss/trojan │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │         sys-firewall → Internet           │              │
│  └───────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Core Technical Points

#### 1. Traffic Marking (nftables)

```bash
# nftables rule: mark new connections from AppVMs
nft add rule inet singbox mark meta mark set 0x2022
```

`fwmark` (firewall mark) is a Linux kernel field used to tag packets, working with policy routing to implement traffic splitting.

#### 2. Policy Routing (ip rule)

```bash
# Create custom routing table
echo "2022 singroute" >> /etc/iproute2/rt_tables

# Policy routing: use table 2022 for traffic matching fwmark
ip rule add fwmark 0x2022 lookup 2022

# Default route in table 2022 points to TUN device
ip route add default dev tun0 table 2022
```

Policy routing allows selecting different routing tables based on packet attributes (such as fwmark), enabling "same destination, different paths."

#### 3. TUN Device

```python
# TUN inbound in sing-box configuration
{
    "type": "tun",
    "interface_name": "tun0",
    "address": ["198.18.0.1/30"],
    "auto_route": True,      # Auto-add routes
    "strict_route": True,    # Strict routing mode
    "stack": "gvisor",       # Userspace TCP/IP stack
    "mtu": 9000              # Maximum Transmission Unit
}
```

TUN is a virtual network device provided by the Linux kernel, operating at Layer 3 (IP packets). sing-box uses it to receive all marked traffic.

#### 4. DNS Splitting

```python
# DNS server configuration
"servers": [
    {"tag": "dns-system", "server": "10.139.1.1", "detour": "direct"},  # Qubes system DNS
    {"tag": "dns-proxy", "server": "8.8.8.8", "detour": "auto"},        # Proxy DNS
    {"tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"} # Local DNS
]

# DNS routing rules
"rules": [
    {"domain_suffix": [".cn"], "server": "dns-system"}  # .cn domains use system DNS
]
```

DNS splitting ensures matched domains use local DNS resolution (fast), while other domains use proxy DNS resolution (accurate).

---

## Features

### Proxy Protocol Support
- vmess / vless / shadowsocks / trojan
- WebSocket / gRPC / HTTP/2 transport layers
- TLS / REALITY encryption

### Traffic Management
- **Smart Splitting** — Rule-based routing (matched domains go direct, others go proxy)
- **Proxy All** — All traffic goes through proxy (except LAN)
- **Proxy Selected Sites Only** — Only proxy specified sites
- **Global Proxy** — Specific node forwards all traffic
- **Direct** — No proxy (for debugging)

### Management Tool (singctl)
- TUI interactive interface
- Multi-subscription source management
- Node speed test + latency display
- IP geolocation detection (shows region names)
- DNS provider selection (Google/Cloudflare/Quad9/AdGuard/Mullvad)
- Custom routing rules

### Automation
- **Auto subscription update** — Every 6 hours
- **Node health monitoring** — Checks every 5 minutes, auto-removes after 3 consecutive failures
- **Configuration persistence** — Survives reboots

---

## Quick Start

### Prerequisites

- Qubes OS 4.3 (other versions untested, compatibility not guaranteed)
- A Debian 12/13 AppVM as NetVM
- The VM must have internet access (via sys-firewall)

### One-Line Install

Run in your NetVM:

```bash
# Method 1: Clone then install (recommended)
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway
sudo bash install.sh

# Method 2: Download and run install script directly
sudo bash <(curl -fsSL https://raw.githubusercontent.com/iasds/qubes-singroute-gateway/master/install.sh)
```

The install script automatically completes:
1. ✅ Installs system dependencies (python3, nftables, pip)
2. ✅ Downloads and installs sing-box (with local binary fallback)
3. ✅ Installs singctl management tool
4. ✅ Configures transparent proxy networking (nftables mark + policy routing)
5. ✅ Creates systemd services (sing-box + auto-update + monitoring)
6. ✅ Generates initial configuration

### Configure Subscription

```bash
singctl
# Select: Subscription Management → Add Subscription → Enter your subscription URL
```

### Set Up AppVMs to Use Proxy Gateway

In dom0:

```bash
# Single VM
qvm-prefs your-app-vm netvm sys-proxy

# Batch setup
for vm in work personal dev; do
    qvm-prefs $vm netvm sys-proxy
done
```

### Verify

In the AppVM:

```bash
# Test network access
curl -s https://www.google.com

# Check exit IP
curl -s https://api.ipify.org

# Test DNS resolution
nslookup github.com
```

---

## Update / Uninstall

Run the install script again to automatically detect the installed version and provide options:

```bash
sudo bash install.sh
```

```
╔══════════════════════════════════════════════════════════╗
║   Qubes Proxy Gateway — Install/Update/Uninstall Tool   ║
╚══════════════════════════════════════════════════════════╝

Current Status: Installed v1.2.0 → New version available v1.3.0

────────────────────────────────────────────────────────
  [1] Update to v1.3.0
  [2] Uninstall
  [3] Exit
```

Also supports command-line arguments:

```bash
sudo bash install.sh install    # Direct install
sudo bash install.sh update     # Direct update
sudo bash install.sh uninstall  # Direct uninstall
```

---

## singctl Details

### Main Menu

```
╔══════════════════════════════════════════════════════════╗
║                    singctl v1.2.0                        ║
║            Qubes Singroute Gateway Management            ║
╚══════════════════════════════════════════════════════════╝

  Current Mode: Smart Splitting    DNS: Google DNS
  Node: US-Node-01 (45ms)    Subscriptions: 2, 37 nodes

  [1] Proxy Mode      Switch splitting strategy
  [2] Node Management  View/switch nodes
  [3] Subscription Mgmt Add/update subscriptions
  [4] DNS Settings     Select DNS provider
  [5] Custom Rules     Add routing rules
  [6] Status Panel     Service status monitoring
  [7] Exit
```

### Proxy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Smart Splitting | Rule-based routing | Daily use |
| Proxy All | All traffic proxied (except LAN) | Full proxy needed |
| Proxy Selected Sites | Only proxy specified sites | Save proxy traffic |
| Global Proxy | Specific node forwards all | Debugging/special needs |
| Direct | No proxy | Testing/troubleshooting |

### Node Management

```
Node List (Grouped by Subscription)
────────────────────────────────────────
Subscription: MyProvider (25 nodes)

  #  Region        Node Name              Latency
  1  US            US-Node-01             45ms
  2  Japan         JP-Node-02             67ms
  3  Singapore     SG-Node-03             89ms
  4  Hong Kong     HK-Node-04             32ms
  5  Taiwan        TW-Node-05             55ms

Subscription: BackupProvider (12 nodes)

  6  US            US-Backup-01           120ms
  7  Japan         JP-Backup-02           95ms

Actions:
  [number] Switch to that node
  [a] Auto-select best node
  [t] Speed test all nodes
  [q] Back
```

### DNS Settings

| DNS Provider | Characteristics | Recommended For |
|-------------|-----------------|-----------------|
| Google DNS | Classic, stable, reliable | General use |
| Cloudflare | Fast, no logs | Speed-focused |
| Quad9 | Security-first, blocks malicious domains | Security-focused |
| AdGuard | Privacy protection + ad blocking | Ad blocking |
| Mullvad | Strict no-logs, Swedish privacy laws | Ultimate privacy |

---

## Automated Services

The following systemd services are automatically enabled after installation:

| Service | Description | Frequency |
|---------|-------------|-----------|
| `sing-box.service` | Proxy core service | Continuous |
| `singbox-monitor.service` | Node health monitoring | Every 5 minutes |
| `update-subscriptions.timer` | Auto subscription update | Every 6 hours |

Management commands:

```bash
# Check sing-box status
systemctl status sing-box

# Check monitoring service
systemctl status singbox-monitor

# Check auto-update timer
systemctl status update-subscriptions.timer

# Manually trigger subscription update
update-singbox-config

# View logs
journalctl -u sing-box -f
journalctl -u singbox-monitor -f
```

---

## Configuration Files

All configuration is stored in `/rw/config/sing-box/` (Qubes persistent storage):

| File | Description |
|------|-------------|
| `config.json` | sing-box main configuration |
| `singctl-subscriptions.json` | Subscription source list |
| `singctl-preferences.json` | User preferences (mode, DNS, selected node) |
| `singctl-custom-rules.json` | Custom routing rules |

Backup configuration:

```bash
tar czf ~/backup-singroute-$(date +%Y%m%d).tar.gz /rw/config/sing-box/
```

Restore configuration:

```bash
tar xzf ~/backup-singroute-20260506.tar.gz -C /
systemctl restart sing-box
```

---

## Troubleshooting

### AppVM Cannot Access Internet

```bash
# Check in NetVM
systemctl is-active sing-box          # Is it running
nft list ruleset | grep singbox       # nftables rules
ip route show table 2022              # Policy routing
ip addr show tun0                     # TUN interface
journalctl -u sing-box --no-pager -n 50  # Recent logs
```

### DNS Resolution Failure

```bash
# In AppVM
cat /etc/resolv.conf                  # DNS configuration
nslookup google.com 8.8.8.8          # Test DNS

# In NetVM
singctl → DNS Settings → Switch DNS provider
```

### All Nodes Timing Out

```bash
# Update subscription to get new nodes
update-singbox-config

# Or through singctl
singctl → Subscription Management → Update all subscriptions
```

### Installation Failure

```bash
# Check if sing-box is installed successfully
sing-box version

# Check Python dependencies
python3 -c "import simple_term_menu"

# Check network connectivity
curl -s https://api.github.com

# View install log
sudo bash -x install.sh 2>&1 | tee install.log
```

---

## Project Structure

```
qubes-singroute-gateway/
├── install.sh                          # One-click install/update/uninstall script
├── uninstall.sh                        # Uninstall script
├── README.md                           # Documentation (Chinese)
├── README_EN.md                        # Documentation (English)
├── scripts/
│   ├── setup-netvm.sh                  # NetVM network config (nftables + routing)
│   ├── auto-update-subscriptions.sh    # Subscription auto-update script
│   ├── update-subscriptions.service    # systemd service
│   ├── update-subscriptions.timer      # systemd timer
│   ├── singbox-monitor.service         # Node monitoring service
│   └── test-connectivity.sh            # Connectivity test
└── singctl/
    ├── __init__.py                     # Version number
    ├── __main__.py                     # Entry point
    ├── cli.py                          # CLI entry
    ├── config.py                       # Constants, paths, presets
    ├── data.py                         # Data storage
    ├── nodes.py                        # Node parsing, speed test, geolocation
    ├── proxy.py                        # Proxy mode, config generation
    ├── subs.py                         # Subscription management
    ├── monitor.py                      # Node health monitoring
    └── ui.py                           # TUI interface
```

---

## FAQ

### Q: What is the learning value of this project?

A: By building a transparent proxy gateway, you can deeply understand:
- Linux networking subsystem (nftables, routing, TUN)
- Proxy protocol principles (vmess/vless/ss/trojan)
- Qubes OS security architecture (VM isolation, network layering)
- Python system programming (TUI, concurrency, service management)

### Q: Which proxy protocols are supported?

A: All protocols supported by sing-box: vmess, vless, shadowsocks, trojan, hysteria, tuic, wireguard, etc. This project has been primarily tested with vmess and shadowsocks.

### Q: How does this differ from Qubes VPN?

A: Qubes VPN operates at the VPN layer and requires each VM to be configured or use a VPN ProxyVM. This project operates at the proxy layer through TUN transparent proxy, making it completely transparent to AppVMs.

### Q: Will this affect Qubes isolation?

A: No. Each AppVM still accesses the NetVM through its own network stack. Qubes' network isolation mechanism is fully preserved.

### Q: How do I restore default configuration?

A: Delete the configuration directory and reinstall:
```bash
sudo rm -rf /rw/config/sing-box
sudo bash install.sh
```

### Q: Is IPv6 supported?

A: Not currently. Qubes OS does not use IPv6 by default, and most proxy nodes do not provide IPv6.

---

## Development

### Local Development

```bash
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway

# Install dependencies
pip3 install simple-term-menu pyyaml

# Run directly (without installation)
python3 -m singctl
```

### Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE)

## Acknowledgments

- [sing-box](https://github.com/SagerNet/sing-box) — Universal proxy platform
- [Qubes OS](https://www.qubes-os.org/) — Security-focused operating system
- [simple-term-menu](https://github.com/IngoMeyer441/simple-term-menu) — Python TUI library

---

## Further Reading

- [Qubes OS Official Documentation](https://www.qubes-os.org/doc/)
- [sing-box Configuration Documentation](https://sing-box.sagernet.org/configuration/)
- [Linux Policy Routing Guide](https://www.policyrouting.org/)
- [nftables wiki](https://wiki.nftables.org/)
- [TUN/TAP Device Details](https://www.kernel.org/doc/Documentation/networking/tuntap.txt)
