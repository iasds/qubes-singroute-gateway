# qubes-singroute-gateway

> Qubes OS transparent proxy gateway — zero-config, multi-protocol, smart routing

[![Qubes OS](https://img.shields.io/badge/Qubes%20OS-4.3-3f51b5?logo=qubesos)](https://www.qubes-os.org/)
[![sing-box](https://img.shields.io/badge/sing--box-1.13+-ff6b00)](https://sing-box.sagernet.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ⚠️ Known Issues

**TUN transparent proxy mode has critical unresolved issues.** See [Issues](https://github.com/iasds/qubes-singroute-gateway/issues) for details.

**SOCKS proxy mode works reliably** — use `127.0.0.1:7890` instead. For transparent proxy on Qubes, consider [qubes-clash-gateway](https://github.com/iasds/qubes-clash-gateway) (mihomo-based).

---

## What It Does

Runs [sing-box](https://sing-box.sagernet.org/) on a Qubes OS NetVM. Using **TUN transparent proxy + nftables traffic marking + policy routing**, it automatically routes all traffic (TCP/UDP, all ports) from every AppVM connected to that NetVM through the proxy.

**Zero config on AppVM side** — no software to install, no settings to change. Just point the AppVM's NetVM to the proxy gateway and you're done.

## Why Use It

| Pain Point | This Project's Solution |
|------------|------------------------|
| Each VM needs its own proxy config | ❌ Not needed — change NetVM once, all VMs covered |
| Manual PAC/SOCKS env var setup | ❌ Doesn't exist — transparent proxy is invisible |
| Proxy only handles TCP, UDP leaks | ❌ TUN mode covers TCP+UDP completely |
| Switching nodes requires config edits & restart | ❌ singctl TUI one-click switch, auto speedtest |
| Subscription expires unnoticed | ❌ Auto-updates every 6h, dead nodes auto-removed |
| DNS pollution / leaks | ✅ Three-tier DNS split (system / proxy / direct) |

## Key Advantages

**🔒 Full transparent proxy** — TUN mode + gvisor userspace TCP/IP stack, covers TCP/UDP/ICMP, no traffic leaks

**⚡ Smart routing** — Domain/IP rules auto-determine direct vs proxy, no manual switching needed

**🎯 Multi-protocol support** — vmess / vless / shadowsocks / trojan / hysteria / tuic / wireguard, with WebSocket / gRPC / HTTP/2 transport

**🛡️ Qubes native isolation** — Proxy runs in an isolated NetVM, AppVMs remain fully isolated, Qubes security model preserved

**🖥️ TUI management tool** — singctl terminal UI: subscription management, node speedtest, mode switching, DNS selection, custom rules — all in one interface

**🔄 Automated operations** — Subscription auto-update (6h), node health monitoring (5min checks, auto-remove after 3 consecutive failures), config persists across reboots

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Qubes OS                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  AppVM   │  │  AppVM   │  │  AppVM   │  ← Application   │
│  │  (work)  │  │(personal)│  │  (dev)   │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │              │              │                       │
│       └──────────────┼──────────────┘                       │
│                      ▼                                      │
│  ┌───────────────────────────────────────────┐              │
│  │           NetVM (this project)             │  ← Network  │
│  │                                           │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  nftables                           │  │              │
│  │  │  - Mark new connections fwmark      │  │              │
│  │  │  - NAT forwarding                   │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  Policy Routing (table 2022)        │  │              │
│  │  │  - Matched fwmark → TUN             │  │              │
│  │  │  - Other traffic → default route    │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  TUN device (tun0)                  │  │              │
│  │  │  - Address: 198.18.0.1/30           │  │              │
│  │  │  - MTU: 9000                        │  │              │
│  │  │  - Stack: gvisor (userspace)        │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │  ┌─────────────────────────────────────┐  │              │
│  │  │  sing-box core                      │  │              │
│  │  │  ├ DNS split:                       │  │              │
│  │  │  │  - Matched domain → system DNS   │  │              │
│  │  │  │  - Other → proxy DNS             │  │              │
│  │  │  ├ Route rules:                     │  │              │
│  │  │  │  - Matched IP → direct           │  │              │
│  │  │  │  - Private IP → direct           │  │              │
│  │  │  │  - Other → auto (best node)      │  │              │
│  │  │  └ Outbound: vmess/vless/ss/trojan  │  │              │
│  │  └──────────────┬──────────────────────┘  │              │
│  │                 ▼                         │              │
│  │         sys-firewall → Internet           │              │
│  └───────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Key Technical Points

#### 1. Traffic Marking (nftables)

```bash
# nftables rule: mark new connections from AppVMs
nft add rule inet singbox mark meta mark set 0x2022
```

`fwmark` (firewall mark) is a Linux kernel field that tags packets, working with policy routing to split traffic.

#### 2. Policy Routing (ip rule)

```bash
# Create custom routing table
echo "2022 singroute" >> /etc/iproute2/rt_tables

# Policy routing: matched fwmark uses table 2022
ip rule add fwmark 0x2022 lookup 2022

# Table 2022 default route points to TUN device
ip route add default dev tun0 table 2022
```

Policy routing selects different routing tables based on packet attributes (like fwmark), achieving "same destination, different path".

#### 3. TUN Device

```json
{
    "type": "tun",
    "interface_name": "tun0",
    "address": ["198.18.0.1/30"],
    "auto_route": true,
    "strict_route": true,
    "stack": "gvisor",
    "mtu": 9000
}
```

TUN is a Linux kernel virtual network device operating at layer 3 (IP packets). sing-box uses it to receive all marked traffic.

#### 4. DNS Split

```json
"servers": [
    {"tag": "dns-system", "server": "10.139.1.1", "detour": "direct"},
    {"tag": "dns-proxy", "server": "8.8.8.8", "detour": "auto"},
    {"tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"}
],
"rules": [
    {"domain_suffix": [".cn"], "server": "dns-system"}
]
```

DNS splitting ensures matched domains resolve via local DNS (fast) and other domains via proxy DNS (accurate).

---

## Features

### Proxy Protocol Support
- vmess / vless / shadowsocks / trojan
- WebSocket / gRPC / HTTP/2 transport
- TLS / REALITY encryption

### Traffic Management
- **Smart routing** — Rule-based split (matched → direct, rest → proxy)
- **Proxy all** — All traffic through proxy (except LAN)
- **Proxy specific sites** — Only proxy listed domains
- **Global proxy** — Single node for all traffic
- **Direct** — No proxy (for debugging)

### Management Tool (singctl)
- TUI interactive interface
- Multi-subscription management
- Node speedtest + latency display
- IP geolocation detection
- DNS provider selection (Google/Cloudflare/Quad9/AdGuard/Mullvad)
- Custom routing rules

### Automation
- **Auto subscription update** — Every 6 hours
- **Node health monitoring** — Check every 5 min, auto-remove after 3 failures
- **Config persistence** — Survives reboots

---

## Quick Start

### Prerequisites

- Qubes OS 4.3 (other versions untested)
- A Debian 12/13 AppVM as NetVM
- The VM must have internet access (via sys-firewall)

### One-Command Install

Run in your NetVM:

```bash
# Option 1: Clone and install (recommended)
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway
sudo bash install.sh

# Option 2: Direct download
sudo bash <(curl -fsSL https://raw.githubusercontent.com/iasds/qubes-singroute-gateway/master/install.sh)
```

The installer automatically:
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

### Set AppVM to Use Proxy Gateway

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

In an AppVM:

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

Run the installer again — it auto-detects the installed version and shows options:

```bash
sudo bash install.sh
```

```
╔══════════════════════════════════════════════════════════╗
║   Qubes Proxy Gateway — Install / Update / Uninstall    ║
╚══════════════════════════════════════════════════════════╝

Status: Installed v1.2.0 → Update available v1.3.0

────────────────────────────────────────────────────────
  [1] Update to v1.3.0
  [2] Uninstall
  [3] Exit
```

Also supports CLI arguments:

```bash
sudo bash install.sh install    # Install directly
sudo bash install.sh update     # Update directly
sudo bash install.sh uninstall  # Uninstall directly
```

---

## singctl Details

### Main Menu

```
╔══════════════════════════════════════════════════════════╗
║                    singctl v1.2.0                        ║
║              Qubes Singroute Gateway Manager             ║
╚══════════════════════════════════════════════════════════╝

  Mode: Smart Routing    DNS: Google DNS
  Node: US-Node-01 (45ms)    Subs: 2, 37 nodes

  [1] Proxy Mode     Switch routing strategy
  [2] Node Manager   View/switch nodes
  [3] Subscriptions  Add/update subscriptions
  [4] DNS Settings   Select DNS provider
  [5] Custom Rules   Add routing rules
  [6] Status Panel   Service status monitor
  [7] Exit
```

### Proxy Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Smart Routing | Rule-based split | Daily use |
| Proxy All | All through proxy (except LAN) | Full proxy needed |
| Proxy Specific | Only listed sites | Save proxy traffic |
| Global Proxy | Single node for all | Debug / special needs |
| Direct | No proxy | Testing / troubleshooting |

### Node Management

```
Node List (grouped by subscription)
────────────────────────────────────────
Subscription: MyProvider (25 nodes)

  #  Region       Node Name              Latency
  1  US           US-Node-01             45ms
  2  Japan        JP-Node-02             67ms
  3  Singapore    SG-Node-03             89ms
  4  Hong Kong    HK-Node-04             32ms
  5  Taiwan       TW-Node-05             55ms

Subscription: BackupProvider (12 nodes)

  6  US           US-Backup-01           120ms
  7  Japan        JP-Backup-02           95ms

Actions:
  [number] Switch to node
  [a] Auto-select best node
  [t] Speedtest all nodes
  [q] Back
```

### DNS Settings

| DNS Provider | Highlights | Best For |
|-------------|------------|----------|
| Google DNS | Classic, reliable | General use |
| Cloudflare | Fast, no logs | Speed-focused |
| Quad9 | Security-first, blocks malicious domains | Security-focused |
| AdGuard | Privacy + ad blocking | Ad-free browsing |
| Mullvad | Strict no-log, Swedish privacy law | Maximum privacy |

---

## Systemd Services

The installer enables these services automatically:

| Service | Description | Frequency |
|---------|-------------|-----------|
| `sing-box.service` | Proxy core service | Always running |
| `singbox-monitor.service` | Node health monitoring | Every 5 min |
| `update-subscriptions.timer` | Auto subscription update | Every 6 hours |

Management commands:

```bash
# Check sing-box status
systemctl status sing-box

# Check monitoring service
systemctl status singbox-monitor

# Check auto-update timer
systemctl status update-subscriptions.timer

# Manual subscription update
update-singbox-config

# View logs
journalctl -u sing-box -f
journalctl -u singbox-monitor -f
```

---

## Configuration Files

All configs stored in `/rw/config/sing-box/` (Qubes persistent storage):

| File | Description |
|------|-------------|
| `config.json` | sing-box main config |
| `singctl-subscriptions.json` | Subscription sources |
| `singctl-preferences.json` | User preferences (mode, DNS, selected node) |
| `singctl-custom-rules.json` | Custom routing rules |

Backup:

```bash
tar czf ~/backup-singroute-$(date +%Y%m%d).tar.gz /rw/config/sing-box/
```

Restore:

```bash
tar xzf ~/backup-singroute-20260506.tar.gz -C /
systemctl restart sing-box
```

---

## Troubleshooting

### AppVM Can't Access Internet

```bash
# Check in NetVM
systemctl is-active sing-box          # Is it running?
nft list ruleset | grep singbox       # nftables rules
ip route show table 2022              # Policy routing
ip addr show tun0                     # TUN interface
journalctl -u sing-box --no-pager -n 50  # Recent logs
```

### DNS Resolution Fails

```bash
# In AppVM
cat /etc/resolv.conf                  # DNS config
nslookup google.com 8.8.8.8          # Test DNS

# In NetVM
singctl → DNS Settings → Switch DNS provider
```

### All Nodes Timeout

```bash
# Update subscriptions for fresh nodes
update-singbox-config

# Or via singctl
singctl → Subscriptions → Update all
```

### Installation Fails

```bash
# Check sing-box installation
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
├── install.sh                          # One-click install/update/uninstall
├── uninstall.sh                        # Uninstall script
├── README.md                           # This file (English)
├── README_zh.md                        # 中文文档
├── scripts/
│   ├── setup-netvm.sh                  # NetVM network config (nftables + routing)
│   ├── auto-update-subscriptions.sh    # Subscription auto-update script
│   ├── update-subscriptions.service    # systemd service
│   ├── update-subscriptions.timer      # systemd timer
│   ├── singbox-monitor.service         # Node health monitor
│   └── test-connectivity.sh            # Connectivity test
└── singctl/
    ├── __init__.py                     # Version
    ├── __main__.py                     # Entry point
    ├── cli.py                          # CLI entry
    ├── config.py                       # Constants, paths, presets
    ├── data.py                         # Data storage
    ├── nodes.py                        # Node parsing, speedtest, geolocation
    ├── proxy.py                        # Proxy mode, config generation
    ├── subs.py                         # Subscription management
    ├── monitor.py                      # Node health monitor
    └── ui.py                           # TUI interface
```

---

## FAQ

### Q: Which proxy protocols are supported?

A: All protocols supported by sing-box: vmess, vless, shadowsocks, trojan, hysteria, tuic, wireguard, etc. This project has been primarily tested with vmess and shadowsocks.

### Q: How is this different from Qubes VPN?

A: Qubes VPN operates at the VPN layer, requiring per-VM configuration or a VPN ProxyVM. This project operates at the proxy layer via TUN transparent proxy — AppVMs are completely unaware.

### Q: Will this affect Qubes isolation?

A: No. Each AppVM still accesses the NetVM through its own network stack. Qubes' network isolation mechanism is fully preserved.

### Q: How to reset to default config?

A: Delete the config directory and reinstall:
```bash
sudo rm -rf /rw/config/sing-box
sudo bash install.sh
```

### Q: Is IPv6 supported?

A: Not currently. Qubes OS doesn't use IPv6 by default, and most proxy nodes don't provide IPv6.

---

## Development

### Local Development

```bash
git clone https://github.com/iasds/qubes-singroute-gateway.git
cd qubes-singroute-gateway

# Install dependencies
pip3 install simple-term-menu pyyaml

# Run directly (without installing)
python3 -m singctl
```

### Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
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

- [Qubes OS Documentation](https://www.qubes-os.org/doc/)
- [sing-box Configuration](https://sing-box.sagernet.org/configuration/)
- [Linux Policy Routing Guide](https://www.policyrouting.org/)
- [nftables wiki](https://wiki.nftables.org/)
- [TUN/TAP Device Details](https://www.kernel.org/doc/Documentation/networking/tuntap.txt)
