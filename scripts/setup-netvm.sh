#!/bin/bash
# Setup NetVM for transparent proxy
# This script configures nftables and IP forwarding
set -e

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/99-singbox.conf

# Load nftables rules: mark AppVM traffic for TUN routing
nft -f - << 'EOF'
table inet singbox-mark {
    chain forward {
        type filter hook forward priority mangle - 1; policy accept;
        iifname "vif*" ct state new meta l4proto tcp ct mark set 0x1 meta mark set 0x1
        iifname "vif*" ct state new udp dport != 53 ct mark set 0x1 meta mark set 0x1
    }
}
EOF

# Bypass TUN for sing-box own outbound traffic (prevent routing loop)
# sing-box TUN auto_route creates ip rules that capture ALL traffic,
# including sing-box's own direct outbound packets → loop.
# Fix: mark sing-box process packets and route them via main table.
nft -f - << 'EOF'
table inet singbox-bypass {
    chain output {
        type route hook output priority mangle - 1; policy accept;
        meta skuid 0 meta mark set 0x2
    }
}
EOF

# Add policy routing for marked packets
if ! ip rule show | grep -q "fwmark 0x1"; then
    ip rule add fwmark 0x1 table 2022
fi

# Bypass TUN for sing-box outbound (fwmark 0x2 → main table)
if ! ip rule show | grep -q "fwmark 0x2"; then
    ip rule add fwmark 0x2 lookup main priority 100
fi

# Add route to TUN via table 2022
if ! ip route show table 2022 | grep -q "172.19.0.2"; then
    ip route add default via 172.19.0.2 dev tun0 table 2022 2>/dev/null || true
fi

# Create rc.local for persistence
cat > /rw/config/rc.local << 'RCLOCAL'
#!/bin/bash
# qubes-singroute-gateway startup script

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Load nftables rules: mark AppVM traffic for TUN routing
nft -f - << 'NFT'
table inet singbox-mark {
    chain forward {
        type filter hook forward priority mangle - 1; policy accept;
        iifname "vif*" ct state new meta l4proto tcp ct mark set 0x1 meta mark set 0x1
        iifname "vif*" ct state new udp dport != 53 ct mark set 0x1 meta mark set 0x1
    }
}
NFT

# Bypass TUN for sing-box own outbound traffic (prevent routing loop)
nft -f - << 'NFT'
table inet singbox-bypass {
    chain output {
        type route hook output priority mangle - 1; policy accept;
        meta skuid 0 meta mark set 0x2
    }
}
NFT

# Add policy routing
ip rule add fwmark 0x1 table 2022 2>/dev/null || true
ip rule add fwmark 0x2 lookup main priority 100 2>/dev/null || true
ip route add default via 172.19.0.2 dev tun0 table 2022 2>/dev/null || true

# Start sing-box
systemctl start sing-box
RCLOCAL
chmod +x /rw/config/rc.local

# Create nftables persistence
mkdir -p /rw/config
cat > /rw/config/qubes-firewall-user-script << 'FWSCRIPT'
#!/bin/bash
# Load singbox nftables rules
nft -f - << 'NFT'
table inet singbox-mark {
    chain forward {
        type filter hook forward priority mangle - 1; policy accept;
        iifname "vif*" ct state new meta l4proto tcp ct mark set 0x1 meta mark set 0x1
        iifname "vif*" ct state new udp dport != 53 ct mark set 0x1 meta mark set 0x1
    }
}
NFT

nft -f - << 'NFT'
table inet singbox-bypass {
    chain output {
        type route hook output priority mangle - 1; policy accept;
        meta skuid 0 meta mark set 0x2
    }
}
NFT
FWSCRIPT
chmod +x /rw/config/qubes-firewall-user-script

echo "NetVM 配置完成"
