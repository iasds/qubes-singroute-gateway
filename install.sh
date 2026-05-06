#!/bin/bash
# qubes-proxy-gateway installer
# Usage: sudo bash install.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/usr/local/lib/singctl"
BIN_DIR="/usr/local/bin"
CONFIG_DIR="/rw/config/sing-box"
SERVICE_FILE="/etc/systemd/system/sing-box.service"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check root
if [ "$(id -u)" -ne 0 ]; then
    error "请使用 sudo 运行此脚本"
fi

# Check if running in Qubes VM
if [ ! -d /rw/config ]; then
    warn "未检测到 Qubes OS 环境，继续安装..."
fi

info "=== qubes-proxy-gateway 安装 ==="

# Step 1: Install dependencies
info "[1/6] 安装依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip nftables curl

# Install Python packages
pip3 install --break-system-packages simple-term-menu pyyaml 2>/dev/null || \
pip3 install simple-term-menu pyyaml

# Step 2: Install sing-box
info "[2/6] 安装 sing-box..."
if ! command -v sing-box &> /dev/null; then
    # Check for local binary first
    LOCAL_BIN=""
    if [ -f "$SCRIPT_DIR/sing-box" ]; then
        LOCAL_BIN="$SCRIPT_DIR/sing-box"
    elif [ -f "/tmp/sing-box" ]; then
        LOCAL_BIN="/tmp/sing-box"
    fi

    if [ -n "$LOCAL_BIN" ]; then
        info "使用本地二进制: $LOCAL_BIN"
        cp "$LOCAL_BIN" /usr/local/bin/sing-box
        chmod +x /usr/local/bin/sing-box
    else
        # Try downloading from GitHub
        ARCH=$(uname -m)
        case $ARCH in
            x86_64) ARCH="amd64" ;;
            aarch64) ARCH="arm64" ;;
            armv7l) ARCH="armv7" ;;
        esac

        VERSION=$(curl -s --connect-timeout 10 https://api.github.com/repos/SagerNet/sing-box/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
        if [ -n "$VERSION" ]; then
            DOWNLOAD_URL="https://github.com/SagerNet/sing-box/releases/download/v${VERSION}/sing-box-${VERSION}-linux-${ARCH}.tar.gz"
            info "下载 sing-box v${VERSION}..."
            cd /tmp
            if curl -fL --connect-timeout 15 "$DOWNLOAD_URL" -o sing-box.tar.gz 2>/dev/null; then
                tar xzf sing-box.tar.gz
                mv sing-box-*/sing-box /usr/local/bin/
                chmod +x /usr/local/bin/sing-box
                rm -rf sing-box-* sing-box.tar.gz
            else
                error "下载失败。请手动安装 sing-box："
                echo ""
                echo "  方法一: 将 sing-box 二进制放到项目目录下，重新运行 install.sh"
                echo "    cp /path/to/sing-box $SCRIPT_DIR/"
                echo "    sudo bash install.sh"
                echo ""
                echo "  方法二: 手动下载并放到指定位置"
                echo "    从 https://github.com/SagerNet/sing-box/releases 下载"
                echo "    cp sing-box /usr/local/bin/sing-box"
                echo "    chmod +x /usr/local/bin/sing-box"
                echo "    然后重新运行 sudo bash install.sh"
                exit 1
            fi
        else
            error "无法获取 sing-box 版本信息。请手动安装："
            echo ""
            echo "  从 https://github.com/SagerNet/sing-box/releases 下载二进制"
            echo "  放到 $SCRIPT_DIR/sing-box 或 /tmp/sing-box"
            echo "  然后重新运行 sudo bash install.sh"
            exit 1
        fi
    fi

    info "sing-box 安装完成: $(sing-box version | head -1)"
else
    info "sing-box 已安装: $(sing-box version | head -1)"
fi

# Step 3: Create config directory
info "[3/6] 创建配置目录..."
mkdir -p "$CONFIG_DIR"
chown user:user "$CONFIG_DIR"

# Step 4: Install singctl
info "[4/6] 安装 singctl..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/singctl/"* "$INSTALL_DIR/"

# Create singctl launcher
cat > "$BIN_DIR/singctl" << 'EOF'
#!/bin/bash
cd /usr/local/lib
exec python3 -m singctl "$@"
EOF
chmod +x "$BIN_DIR/singctl"

# Create update command
cat > "$BIN_DIR/update-singbox-config" << 'EOF'
#!/bin/bash
cd /usr/local/lib
python3 -c "
from singctl.subs import update_all_subscriptions, sync_nodes_to_config
print('更新订阅...')
results = update_all_subscriptions()
for name, count, err in results:
    if err:
        print(f'  ✗ {name}: {err}')
    else:
        print(f'  ✓ {name}: {count} 个节点')
count = sync_nodes_to_config()
print(f'同步完成: {count} 个节点')
"
EOF
chmod +x "$BIN_DIR/update-singbox-config"

# Step 5: Setup networking
info "[5/6] 配置网络..."
bash "$SCRIPT_DIR/scripts/setup-netvm.sh"

# Step 6: Create systemd service and start
info "[6/6] 配置系统服务..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=sing-box service
Documentation=https://sing-box.sagernet.org
After=network.target nss-lookup.target

[Service]
ExecStart=/usr/local/bin/sing-box run -c /rw/config/sing-box/config.json
Restart=on-failure
RestartSec=10
LimitNOFILE=infinity

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable sing-box

# Generate initial config if not exists
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    info "生成初始配置..."
    python3 -c "
import json
config = {
    'log': {'level': 'info', 'timestamp': True},
    'dns': {
        'servers': [
            {'type': 'udp', 'tag': 'dns-system', 'server': '10.139.1.1', 'server_port': 53, 'detour': 'direct'},
            {'type': 'https', 'tag': 'dns-proxy', 'server': '8.8.8.8', 'detour': 'auto'},
            {'type': 'https', 'tag': 'dns-direct', 'server': '119.29.29.29', 'detour': 'direct'}
        ],
        'rules': [
            {'domain_suffix': ['.cn', 'baidu.com', 'qq.com', 'taobao.com', 'bilibili.com', 'doh.pub', 'gfw250.com', 'iepl', 'mojcn.com', 'cnmjin.net'], 'server': 'dns-system'}
        ],
        'strategy': 'prefer_ipv4',
        'independent_cache': True
    },
    'inbounds': [
        {'type': 'tun', 'tag': 'tun-in', 'interface_name': 'tun0',
         'address': ['172.19.0.1/30', 'fdfe:dcba:9877::1/126'],
         'auto_route': True, 'strict_route': True, 'stack': 'gvisor', 'mtu': 9000},
        {'type': 'mixed', 'tag': 'mixed-local', 'listen': '127.0.0.1', 'listen_port': 7890}
    ],
    'outbounds': [
        {'type': 'direct', 'tag': 'direct', 'domain_resolver': {'server': 'dns-system', 'strategy': 'prefer_ipv4'}},
        {'type': 'urltest', 'tag': 'auto', 'outbounds': [], 'url': 'https://www.gstatic.com/generate_204', 'interval': '3m', 'tolerance': 50}
    ],
    'route': {
        'rules': [
            {'ip_cidr': ['10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16'], 'outbound': 'direct'}
        ],
        'final': 'auto'
    }
}
with open('$CONFIG_DIR/config.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
"
fi

# Start sing-box
systemctl start sing-box

echo ""
info "=== 安装完成 ==="
echo ""
echo "使用方法:"
echo "  singctl                    # 打开管理界面"
echo "  update-singbox-config      # 更新订阅"
echo ""
echo "下一步:"
echo "  1. 运行 singctl 添加订阅"
echo "  2. 在 dom0 中设置 AppVM 的 NetVM 为本机"
echo ""
echo "  qvm-prefs your-app-vm netvm $(hostname)"
echo ""
