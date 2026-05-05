#!/bin/bash
# qubes-proxy-gateway uninstaller
# Usage: sudo bash uninstall.sh
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} 请使用 sudo 运行此脚本"
    exit 1
fi

info "=== qubes-proxy-gateway 卸载 ==="

# Stop and disable service
info "停止服务..."
systemctl stop sing-box 2>/dev/null || true
systemctl disable sing-box 2>/dev/null || true

# Remove service file
info "删除服务文件..."
rm -f /etc/systemd/system/sing-box.service
systemctl daemon-reload

# Remove binaries
info "删除程序文件..."
rm -f /usr/local/bin/sing-box
rm -f /usr/local/bin/singctl
rm -f /usr/local/bin/update-singbox-config
rm -rf /usr/local/lib/singctl

# Remove nftables rules
info "删除 nftables 规则..."
nft delete table inet singbox-mark 2>/dev/null || true

# Remove policy routing
info "删除策略路由..."
ip rule del fwmark 0x1 table 2022 2>/dev/null || true

# Remove rc.local entries (keep other entries)
if [ -f /rw/config/rc.local ]; then
    info "清理 rc.local..."
    sed -i '/qubes-proxy-gateway/,/^RCLOCAL$/d' /rw/config/rc.local 2>/dev/null || true
fi

echo ""
info "=== 卸载完成 ==="
echo ""
echo "配置文件保留在 /rw/config/sing-box/"
echo "如需完全删除，执行: sudo rm -rf /rw/config/sing-box"
