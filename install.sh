#!/bin/bash
# ============================================================
#  Qubes Proxy Gateway — 一键安装/更新/卸载
# ============================================================
#  用法:
#    bash <(curl -fsSL https://raw.githubusercontent.com/iasds/qubes-singroute-gateway/master/install.sh)
#
#  功能:
#    - 首次运行: 全自动安装 sing-box + singctl + 网络配置
#    - 再次运行: 自动检测版本，提供 更新/卸载/退出 选项
#    - 已是最新: 提示无需操作
# ============================================================
set -e

REPO="iasds/qubes-singroute-gateway"
BRANCH="master"
INSTALL_DIR="/usr/local/lib/singctl"
BIN_DIR="/usr/local/bin"
CONFIG_DIR="/rw/config/sing-box"
SERVICE_FILE="/etc/systemd/system/sing-box.service"
WORK_DIR="/tmp/qpg-install-$$"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step()  { echo -e "${CYAN}[→]${NC} $1"; }

# ── 检查 root ──
if [ "$(id -u)" -ne 0 ]; then
    error "请使用 sudo 运行此脚本"
fi

# ── 清理函数 ──
cleanup() {
    rm -rf "$WORK_DIR" 2>/dev/null
}
trap cleanup EXIT

# ============================================================
#  版本检测
# ============================================================
get_local_version() {
    if [ -f "$INSTALL_DIR/__init__.py" ]; then
        grep -oP '__version__\s*=\s*"\K[^"]+' "$INSTALL_DIR/__init__.py" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

get_remote_version() {
    # 方法1: raw 文件（公开仓库）
    local ver
    ver=$(curl -fsSL --connect-timeout 10 \
        "https://raw.githubusercontent.com/$REPO/$BRANCH/singctl/__init__.py" 2>/dev/null \
        | grep -oP '__version__\s*=\s*"\K[^"]+' || echo "")
    if [ -n "$ver" ]; then
        echo "$ver"
        return
    fi

    # 方法2: GitHub API（私有仓库需要 token，公开仓库免费）
    ver=$(curl -s --connect-timeout 10 \
        "https://api.github.com/repos/$REPO/contents/singctl/__init__.py?ref=$BRANCH" 2>/dev/null \
        | grep -oP '"content"\s*:\s*"\K[^"]+' \
        | base64 -d 2>/dev/null \
        | grep -oP '__version__\s*=\s*"\K[^"]+' || echo "")
    if [ -n "$ver" ]; then
        echo "$ver"
        return
    fi

    # 方法3: 无法获取（私有仓库 + 无 token）
    echo ""
}

version_gt() {
    # 比较版本号: $1 > $2
    [ "$(printf '%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ] && [ "$1" != "$2" ]
}

# ============================================================
#  状态检测
# ============================================================
detect_status() {
    LOCAL_VER=$(get_local_version)
    REMOTE_VER=$(get_remote_version)

    if [ -z "$LOCAL_VER" ]; then
        STATUS="not_installed"
    elif [ -z "$REMOTE_VER" ]; then
        STATUS="installed_no_remote"
        STATUS_MSG="已安装 v${LOCAL_VER} (无法检查远程版本)"
    elif [ "$LOCAL_VER" = "$REMOTE_VER" ]; then
        STATUS="up_to_date"
        STATUS_MSG="已安装 v${LOCAL_VER} (已是最新)"
    elif version_gt "$REMOTE_VER" "$LOCAL_VER"; then
        STATUS="update_available"
        STATUS_MSG="已安装 v${LOCAL_VER} → 有新版本 v${REMOTE_VER}"
    else
        STATUS="ahead"
        STATUS_MSG="已安装 v${LOCAL_VER} (比远程 v${REMOTE_VER} 更新)"
    fi
}

# ============================================================
#  显示标题
# ============================================================
show_header() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║${NC}   ${CYAN}Qubes Proxy Gateway${NC} — 安装/更新/卸载工具            ${BOLD}║${NC}"
    echo -e "${BOLD}║${NC}   ${DIM}Qubes OS 透明代理网关 (sing-box)${NC}                     ${BOLD}║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ============================================================
#  安装教程
# ============================================================
show_install_tutorial() {
    echo -e "${BOLD}📖 安装说明${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  本脚本将自动完成以下步骤:"
    echo -e ""
    echo -e "  ${CYAN}1.${NC} 安装系统依赖 (python3, nftables, pip)"
    echo -e "  ${CYAN}2.${NC} 下载并安装 sing-box 代理核心"
    echo -e "  ${CYAN}3.${NC} 安装 singctl 管理工具"
    echo -e "  ${CYAN}4.${NC} 配置透明代理网络 (nftables + 路由)"
    echo -e "  ${CYAN}5.${NC} 创建系统服务 (sing-box + 自动更新 + 监控)"
    echo -e ""
    echo -e "  ${DIM}安装完成后，运行 ${BOLD}singctl${NC}${DIM} 打开管理界面${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""
}

# ============================================================
#  更新教程
# ============================================================
show_update_tutorial() {
    echo -e "${BOLD}📖 更新说明${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  更新将执行以下操作:"
    echo -e ""
    echo -e "  ${CYAN}1.${NC} 拉取最新代码 (git pull)"
    echo -e "  ${CYAN}2.${NC} 更新 singctl 管理工具"
    echo -e "  ${CYAN}3.${NC} 重启相关服务"
    echo -e ""
    echo -e "  ${DIM}你的配置和订阅数据不会被覆盖${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""
}

# ============================================================
#  安装函数
# ============================================================
do_install() {
    show_install_tutorial

    # Step 0: 安装 git 并克隆仓库
    step "[0/7] 准备安装文件..."
    apt-get update -qq
    apt-get install -y -qq git curl

    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"
    step "克隆仓库..."
    git clone --depth 1 -b "$BRANCH" "https://github.com/$REPO.git" "$WORK_DIR"

    cd "$WORK_DIR"
    SCRIPT_DIR="$WORK_DIR"

    # Step 1: 安装依赖
    step "[1/7] 安装系统依赖..."
    apt-get install -y -qq python3 python3-pip nftables

    # Python 包
    pip3 install --break-system-packages simple-term-menu pyyaml 2>/dev/null || \
        pip3 install simple-term-menu pyyaml

    # Step 2: 安装 sing-box
    step "[2/7] 安装 sing-box..."
    if ! command -v sing-box &> /dev/null; then
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
            ARCH=$(uname -m)
            case $ARCH in
                x86_64) ARCH="amd64" ;;
                aarch64) ARCH="arm64" ;;
                armv7l) ARCH="armv7" ;;
            esac

            SING_VER=$(curl -s --connect-timeout 10 https://api.github.com/repos/SagerNet/sing-box/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
            if [ -n "$SING_VER" ]; then
                DL_URL="https://github.com/SagerNet/sing-box/releases/download/v${SING_VER}/sing-box-${SING_VER}-linux-${ARCH}.tar.gz"
                step "下载 sing-box v${SING_VER}..."
                cd /tmp
                if curl -fL --connect-timeout 15 "$DL_URL" -o sing-box.tar.gz 2>/dev/null; then
                    tar xzf sing-box.tar.gz
                    mv sing-box-*/sing-box /usr/local/bin/
                    chmod +x /usr/local/bin/sing-box
                    rm -rf sing-box-* sing-box.tar.gz
                else
                    warn "下载失败，请手动安装 sing-box"
                    echo "  从 https://github.com/SagerNet/sing-box/releases 下载"
                    echo "  放到项目目录下，重新运行此脚本"
                    exit 1
                fi
            else
                warn "无法获取 sing-box 版本，请手动安装"
                exit 1
            fi
        fi
        info "sing-box 安装完成: $(sing-box version | head -1)"
    else
        info "sing-box 已安装: $(sing-box version | head -1)"
    fi

    cd "$WORK_DIR"

    # Step 3: 创建配置目录
    step "[3/7] 创建配置目录..."
    mkdir -p "$CONFIG_DIR"
    chown user:user "$CONFIG_DIR"

    # Step 4: 安装 singctl
    step "[4/7] 安装 singctl 管理工具..."
    mkdir -p "$INSTALL_DIR"
    cp -r singctl/* "$INSTALL_DIR/"

    # 创建 singctl 启动器
    cat > "$BIN_DIR/singctl" << 'LAUNCHER'
#!/bin/bash
cd /usr/local/lib
exec python3 -m singctl "$@"
LAUNCHER
    chmod +x "$BIN_DIR/singctl"

    # 创建 update-singbox-config 命令
    cat > "$BIN_DIR/update-singbox-config" << 'UPDATER'
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
UPDATER
    chmod +x "$BIN_DIR/update-singbox-config"

    # Step 5: 配置网络
    step "[5/7] 配置透明代理网络..."
    if [ -f "$SCRIPT_DIR/scripts/setup-netvm.sh" ]; then
        bash "$SCRIPT_DIR/scripts/setup-netvm.sh"
    else
        warn "未找到 setup-netvm.sh，跳过网络配置"
    fi

    # Step 6: 配置系统服务
    step "[6/7] 配置系统服务..."
    cat > "$SERVICE_FILE" << 'SVC'
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
SVC

    systemctl daemon-reload
    systemctl enable sing-box

    # 生成初始配置
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        step "生成初始配置..."
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

    systemctl start sing-box

    # Step 7: 安装辅助服务
    step "[7/7] 安装辅助服务..."
    if [ -f "$SCRIPT_DIR/scripts/auto-update-subscriptions.sh" ]; then
        cp "$SCRIPT_DIR/scripts/auto-update-subscriptions.sh" /usr/local/bin/auto-update-subscriptions
        chmod +x /usr/local/bin/auto-update-subscriptions
    fi
    if [ -f "$SCRIPT_DIR/scripts/update-subscriptions.service" ]; then
        cp "$SCRIPT_DIR/scripts/update-subscriptions.service" /etc/systemd/system/
    fi
    if [ -f "$SCRIPT_DIR/scripts/update-subscriptions.timer" ]; then
        cp "$SCRIPT_DIR/scripts/update-subscriptions.timer" /etc/systemd/system/
    fi
    if [ -f "$SCRIPT_DIR/scripts/singbox-monitor.service" ]; then
        cp "$SCRIPT_DIR/scripts/singbox-monitor.service" /etc/systemd/system/
    fi

    systemctl daemon-reload
    systemctl enable --now update-subscriptions.timer 2>/dev/null || true
    systemctl enable singbox-monitor 2>/dev/null || true

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ 安装完成！${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}快速开始:${NC}"
    echo -e "    singctl                     打开管理界面"
    echo -e "    update-singbox-config       手动更新订阅"
    echo ""
    echo -e "  ${BOLD}自动服务:${NC}"
    echo -e "    订阅自动更新    每 6 小时"
    echo -e "    节点健康监控    持续运行"
    echo ""
    echo -e "  ${BOLD}下一步:${NC}"
    echo -e "    1. 运行 ${CYAN}singctl${NC} 添加你的订阅"
    echo -e "    2. 在 dom0 设置 AppVM 的 NetVM:"
    echo -e "       ${DIM}qvm-prefs your-app-vm netvm $(hostname)${NC}"
    echo ""
}

# ============================================================
#  更新函数
# ============================================================
do_update() {
    show_update_tutorial

    step "拉取最新代码..."
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"
    git clone --depth 1 -b "$BRANCH" "https://github.com/$REPO.git" "$WORK_DIR"
    cd "$WORK_DIR"

    step "更新 singctl..."
    cp -r singctl/* "$INSTALL_DIR/"

    # 更新辅助脚本
    if [ -f "scripts/auto-update-subscriptions.sh" ]; then
        cp scripts/auto-update-subscriptions.sh /usr/local/bin/auto-update-subscriptions
    fi
    if [ -f "scripts/update-subscriptions.service" ]; then
        cp scripts/update-subscriptions.service /etc/systemd/system/
    fi
    if [ -f "scripts/update-subscriptions.timer" ]; then
        cp scripts/update-subscriptions.timer /etc/systemd/system/
    fi
    if [ -f "scripts/singbox-monitor.service" ]; then
        cp scripts/singbox-monitor.service /etc/systemd/system/
    fi

    step "重启服务..."
    systemctl daemon-reload
    systemctl restart sing-box 2>/dev/null || true

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ 更新完成！${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  已从 v${LOCAL_VER} 更新到 v${REMOTE_VER}"
    echo ""
}

# ============================================================
#  卸载函数
# ============================================================
do_uninstall() {
    echo ""
    echo -e "${YELLOW}${BOLD}⚠ 即将卸载 qubes-singroute-gateway${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  将执行以下操作:"
    echo -e "    - 停止并删除 sing-box 服务"
    echo -e "    - 停止并删除辅助服务 (monitor, auto-update)"
    echo -e "    - 删除 singctl 工具"
    echo -e "    - 删除 sing-box 二进制"
    echo -e "    - ${RED}保留${NC} 配置目录 $CONFIG_DIR"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""

    read -p "确认卸载? (y/N) " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "取消卸载"
        return
    fi

    step "停止服务..."
    systemctl stop sing-box 2>/dev/null || true
    systemctl stop singbox-monitor 2>/dev/null || true
    systemctl stop update-subscriptions.timer 2>/dev/null || true

    step "删除服务..."
    systemctl disable sing-box 2>/dev/null || true
    systemctl disable singbox-monitor 2>/dev/null || true
    systemctl disable update-subscriptions.timer 2>/dev/null || true
    rm -f /etc/systemd/system/sing-box.service
    rm -f /etc/systemd/system/singbox-monitor.service
    rm -f /etc/systemd/system/update-subscriptions.service
    rm -f /etc/systemd/system/update-subscriptions.timer
    systemctl daemon-reload

    step "删除 singctl..."
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/singctl"
    rm -f "$BIN_DIR/update-singbox-config"
    rm -f "$BIN_DIR/auto-update-subscriptions"

    step "删除 sing-box..."
    rm -f /usr/local/bin/sing-box

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ 卸载完成！${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${DIM}配置目录已保留: $CONFIG_DIR${NC}"
    echo -e "  ${DIM}如需彻底清理: sudo rm -rf $CONFIG_DIR${NC}"
    echo ""
}

# ============================================================
#  交互菜单
# ============================================================
show_menu() {
    echo -e "${BOLD}当前状态:${NC} $STATUS_MSG"
    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"

    case "$STATUS" in
        not_installed)
            echo -e "  ${CYAN}[1]${NC} 安装"
            echo -e "  ${DIM}[2]${NC} 退出"
            echo ""
            read -p "请选择 [1-2]: " choice
            case "$choice" in
                1) do_install ;;
                2) echo "退出"; exit 0 ;;
                *) warn "无效选择"; exit 1 ;;
            esac
            ;;
        update_available)
            echo -e "  ${CYAN}[1]${NC} 更新到 v${REMOTE_VER}"
            echo -e "  ${DIM}[2]${NC} 卸载"
            echo -e "  ${DIM}[3]${NC} 退出"
            echo ""
            read -p "请选择 [1-3]: " choice
            case "$choice" in
                1) do_update ;;
                2) do_uninstall ;;
                3) echo "退出"; exit 0 ;;
                *) warn "无效选择"; exit 1 ;;
            esac
            ;;
        up_to_date|ahead)
            echo -e "  ${DIM}[1]${NC} 重新安装 (修复)"
            echo -e "  ${DIM}[2]${NC} 卸载"
            echo -e "  ${DIM}[3]${NC} 退出"
            echo ""
            read -p "请选择 [1-3]: " choice
            case "$choice" in
                1) do_install ;;
                2) do_uninstall ;;
                3) echo "退出"; exit 0 ;;
                *) warn "无效选择"; exit 1 ;;
            esac
            ;;
        installed_no_remote)
            echo -e "  ${DIM}[1]${NC} 重新安装"
            echo -e "  ${DIM}[2]${NC} 卸载"
            echo -e "  ${DIM}[3]${NC} 退出"
            echo ""
            read -p "请选择 [1-3]: " choice
            case "$choice" in
                1) do_install ;;
                2) do_uninstall ;;
                3) echo "退出"; exit 0 ;;
                *) warn "无效选择"; exit 1 ;;
            esac
            ;;
    esac
}

# ============================================================
#  主流程
# ============================================================
show_header

# 如果传了参数，直接执行
case "${1:-}" in
    install)   do_install; exit 0 ;;
    update)    detect_status; do_update; exit 0 ;;
    uninstall) do_uninstall; exit 0 ;;
esac

# 交互模式
detect_status
show_menu
