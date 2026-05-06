#!/bin/bash
# ============================================================
#  Qubes Singroute Gateway — One-Click Install/Update/Uninstall
# ============================================================
#  Usage:
#    sudo bash install.sh
#
#  Features:
#    - First run: Full auto-install (sing-box + singctl + network)
#    - Re-run: Auto-detect version, offer update/uninstall/exit
#    - Multi-language support (10 languages)
# ============================================================
set -e

REPO="iasds/qubes-singroute-gateway"
BRANCH="master"
INSTALL_DIR="/usr/local/lib/singctl"
BIN_DIR="/usr/local/bin"
CONFIG_DIR="/rw/config/sing-box"
SERVICE_FILE="/etc/systemd/system/sing-box.service"
WORK_DIR="/tmp/qpg-install-$$"

# ── Colors ──
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

# ── Check root ──
if [ "$(id -u)" -ne 0 ]; then
    error "Please run with sudo / 请使用 sudo 运行"
fi

# ── Cleanup ──
cleanup() {
    rm -rf "$WORK_DIR" 2>/dev/null
}
trap cleanup EXIT

# ============================================================
#  Language Selection
# ============================================================

# Language code to native name mapping
declare -A LANG_NAMES=(
    [zh]="中文"
    [en]="English"
    [ja]="日本語"
    [ko]="한국어"
    [ru]="Русский"
    [es]="Español"
    [pt]="Português"
    [ar]="العربية"
    [tr]="Türkçe"
    [fa]="فارسی"
)

# Language code to number
declare -A LANG_NUMS=(
    [zh]=1
    [en]=2
    [ja]=3
    [ko]=4
    [ru]=5
    [es]=6
    [pt]=7
    [ar]=8
    [tr]=9
    [fa]=10
)

# Number to language code
declare -A NUM_TO_LANG=(
    [1]=zh
    [2]=en
    [3]=ja
    [4]=ko
    [5]=ru
    [6]=es
    [7]=pt
    [8]=ar
    [9]=tr
    [10]=fa
)

# Load language file
load_lang() {
    local lang=$1
    local lang_file=""
    
    # Try installed location
    if [ -f "/usr/local/lib/lang/${lang}.json" ]; then
        lang_file="/usr/local/lib/lang/${lang}.json"
    # Try working directory
    elif [ -f "lang/${lang}.json" ]; then
        lang_file="lang/${lang}.json"
    # Try script directory
    elif [ -f "$(dirname "$0")/lang/${lang}.json" ]; then
        lang_file="$(dirname "$0")/lang/${lang}.json"
    fi
    
    if [ -n "$lang_file" ] && [ -f "$lang_file" ]; then
        # Parse JSON and export as variables
        eval "$(python3 -c "
import json, sys
with open('$lang_file', 'r', encoding='utf-8') as f:
    d = json.load(f)
for k, v in d.items():
    if isinstance(v, str):
        # Escape single quotes
        v = v.replace(\"'\", \"'\\\\''\")
        print(f\"L_{k}='{v}'\")
")"
    fi
}

# Get translation
t() {
    local key="$1"
    shift
    local var="L_${key}"
    local text="${!var}"
    
    if [ -z "$text" ]; then
        text="$key"
    fi
    
    # Replace {key} placeholders from key=value arguments
    for arg in "$@"; do
        local k="${arg%%=*}"
        local v="${arg#*=}"
        text="${text//\{$k\}/$v}"
    done
    
    echo "$text"
}

# Show language selection menu
show_language_menu() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║${NC}   ${CYAN}Qubes Singroute Gateway${NC}                              ${BOLD}║${NC}"
    echo -e "${BOLD}║${NC}   Install / Update / Uninstall                          ${BOLD}║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}  Please select your language / 请选择语言:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC}  中文"
    echo -e "  ${CYAN}[2]${NC}  English"
    echo -e "  ${CYAN}[3]${NC}  日本語"
    echo -e "  ${CYAN}[4]${NC}  한국어"
    echo -e "  ${CYAN}[5]${NC}  Русский"
    echo -e "  ${CYAN}[6]${NC}  Español"
    echo -e "  ${CYAN}[7]${NC}  Português"
    echo -e "  ${CYAN}[8]${NC}  العربية"
    echo -e "  ${CYAN}[9]${NC}  Türkçe"
    echo -e "  ${CYAN}[10]${NC} فارسی"
    echo ""
    
    while true; do
        read -p "  Select [1-10]: " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le 10 ]; then
            SELECTED_LANG="${NUM_TO_LANG[$choice]}"
            break
        fi
        echo -e "  ${RED}Invalid choice / 无效选择${NC}"
    done
}

# Get saved language
get_saved_lang() {
    if [ -f "$CONFIG_DIR/singctl-preferences.json" ]; then
        python3 -c "
import json
try:
    with open('$CONFIG_DIR/singctl-preferences.json') as f:
        d = json.load(f)
    print(d.get('language', ''))
except:
    print('')
" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# Save language to config
save_lang() {
    local lang=$1
    local prefs_file="$CONFIG_DIR/singctl-preferences.json"
    
    if [ -f "$prefs_file" ]; then
        # Update existing file
        python3 -c "
import json
with open('$prefs_file', 'r') as f:
    d = json.load(f)
d['language'] = '$lang'
with open('$prefs_file', 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
"
    else
        # Create new file
        mkdir -p "$CONFIG_DIR"
        echo "{\"language\": \"$lang\"}" > "$prefs_file"
    fi
}

# ============================================================
#  Header
# ============================================================
show_header() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║${NC}   ${CYAN}$(t install_title)${NC}"
    echo -e "${BOLD}║${NC}   ${DIM}$(t install_subtitle)${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ============================================================
#  Version Detection
# ============================================================
get_local_version() {
    if [ -f "$INSTALL_DIR/__init__.py" ]; then
        grep -oP '__version__\s*=\s*"\K[^"]+' "$INSTALL_DIR/__init__.py" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

get_remote_version() {
    local ver
    ver=$(curl -fsSL --connect-timeout 10 \
        "https://raw.githubusercontent.com/$REPO/$BRANCH/singctl/__init__.py" 2>/dev/null \
        | grep -oP '__version__\s*=\s*"\K[^"]+' || echo "")
    if [ -n "$ver" ]; then
        echo "$ver"
        return
    fi
    
    ver=$(curl -s --connect-timeout 10 \
        "https://api.github.com/repos/$REPO/contents/singctl/__init__.py?ref=$BRANCH" 2>/dev/null \
        | grep -oP '"content"\s*:\s*"\K[^"]+' \
        | base64 -d 2>/dev/null \
        | grep -oP '__version__\s*=\s*"\K[^"]+' || echo "")
    if [ -n "$ver" ]; then
        echo "$ver"
        return
    fi
    
    echo ""
}

version_gt() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ] && [ "$1" != "$2" ]
}

detect_status() {
    LOCAL_VER=$(get_local_version)
    REMOTE_VER=$(get_remote_version)

    if [ -z "$LOCAL_VER" ]; then
        STATUS="not_installed"
        STATUS_MSG=$(t status_not_installed)
    elif [ -z "$REMOTE_VER" ]; then
        STATUS="installed_no_remote"
        STATUS_MSG=$(t status_no_remote version="$LOCAL_VER")
    elif [ "$LOCAL_VER" = "$REMOTE_VER" ]; then
        STATUS="up_to_date"
        STATUS_MSG=$(t status_up_to_date version="$LOCAL_VER")
    elif version_gt "$REMOTE_VER" "$LOCAL_VER"; then
        STATUS="update_available"
        STATUS_MSG=$(t status_update_available local="$LOCAL_VER" remote="$REMOTE_VER")
    else
        STATUS="ahead"
        STATUS_MSG=$(t status_ahead local="$LOCAL_VER" remote="$REMOTE_VER")
    fi
}

# ============================================================
#  Install Function
# ============================================================
do_install() {
    echo ""
    echo -e "${BOLD}$(t tutorial_install_title)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  $(t tutorial_install_desc)"
    echo ""
    echo -e "  ${CYAN}1.${NC} $(t tutorial_install_step1)"
    echo -e "  ${CYAN}2.${NC} $(t tutorial_install_step2)"
    echo -e "  ${CYAN}3.${NC} $(t tutorial_install_step3)"
    echo -e "  ${CYAN}4.${NC} $(t tutorial_install_step4)"
    echo -e "  ${CYAN}5.${NC} $(t tutorial_install_step5)"
    echo ""
    echo -e "  ${DIM}$(t tutorial_install_hint)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""

    # Save language preference
    save_lang "$SELECTED_LANG"

    # Step 0: Clone repo
    step "$(t step_dependencies n=0 total=7)"
    apt-get update -qq
    apt-get install -y -qq git curl

    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"
    step "Cloning repository..."
    git clone --depth 1 -b "$BRANCH" "https://github.com/$REPO.git" "$WORK_DIR"
    cd "$WORK_DIR"

    # Copy language files to installed location
    mkdir -p /usr/local/lib/lang
    cp lang/*.json /usr/local/lib/lang/

    # Step 1: Install dependencies
    step "$(t step_dependencies n=1 total=7)"
    apt-get install -y -qq python3 python3-pip nftables
    pip3 install --break-system-packages simple-term-menu pyyaml 2>/dev/null || \
        pip3 install simple-term-menu pyyaml

    # Step 2: Install sing-box
    step "$(t step_singbox n=2 total=7)"
    if ! command -v sing-box &> /dev/null; then
        LOCAL_BIN=""
        if [ -f "$WORK_DIR/sing-box" ]; then
            LOCAL_BIN="$WORK_DIR/sing-box"
        elif [ -f "/tmp/sing-box" ]; then
            LOCAL_BIN="/tmp/sing-box"
        fi

        if [ -n "$LOCAL_BIN" ]; then
            info "$(t info_using_local path="$LOCAL_BIN")"
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
                info "$(t info_downloading version="$SING_VER")"
                cd /tmp
                if curl -fL --connect-timeout 15 "$DL_URL" -o sing-box.tar.gz 2>/dev/null; then
                    tar xzf sing-box.tar.gz
                    mv sing-box-*/sing-box /usr/local/bin/
                    chmod +x /usr/local/bin/sing-box
                    rm -rf sing-box-* sing-box.tar.gz
                else
                    error "$(t error_download_failed)"
                fi
            else
                error "$(t error_version_check)"
            fi
        fi
        info "$(t info_singbox_installed version="$(sing-box version | head -1)")"
    else
        info "$(t info_singbox_exists version="$(sing-box version | head -1)")"
    fi

    cd "$WORK_DIR"

    # Step 3: Create config directory
    step "$(t step_config_dir n=3 total=7)"
    mkdir -p "$CONFIG_DIR"
    chown user:user "$CONFIG_DIR"

    # Step 4: Install singctl
    step "$(t step_singctl n=4 total=7)"
    mkdir -p "$INSTALL_DIR"
    cp -r singctl/* "$INSTALL_DIR/"

    # Create singctl launcher
    cat > "$BIN_DIR/singctl" << 'LAUNCHER'
#!/bin/bash
cd /usr/local/lib
exec python3 -m singctl "$@"
LAUNCHER
    chmod +x "$BIN_DIR/singctl"

    # Create update-singbox-config command
    cat > "$BIN_DIR/update-singbox-config" << 'UPDATER'
#!/bin/bash
cd /usr/local/lib
python3 -c "
from singctl.subs import update_all_subscriptions, sync_nodes_to_config
print('Updating subscriptions...')
results = update_all_subscriptions()
for name, count, err in results:
    if err:
        print(f'  ✗ {name}: {err}')
    else:
        print(f'  ✓ {name}: {count} nodes')
count = sync_nodes_to_config()
print(f'Sync complete: {count} nodes')
"
UPDATER
    chmod +x "$BIN_DIR/update-singbox-config"

    # Step 5: Configure network
    step "$(t step_network n=5 total=7)"
    if [ -f "$WORK_DIR/scripts/setup-netvm.sh" ]; then
        bash "$WORK_DIR/scripts/setup-netvm.sh"
    else
        warn "setup-netvm.sh not found, skipping network config"
    fi

    # Step 6: Configure system services
    step "$(t step_services n=6 total=7)"
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

    # Generate initial config based on language
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        info "$(t info_generating)"
        
        # Default rules: only private IPs for non-Chinese, full rules for Chinese
        if [ "$SELECTED_LANG" = "zh" ]; then
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
            {'domain_suffix': ['.cn', 'baidu.com', 'qq.com', 'taobao.com', 'bilibili.com'], 'server': 'dns-system'}
        ],
        'strategy': 'prefer_ipv4',
        'independent_cache': True
    },
    'inbounds': [
        {'type': 'tun', 'tag': 'tun-in', 'interface_name': 'tun0',
         'address': ['172.19.0.1/30', 'fdfe:dcba:9877::1/126'],
         'auto_route': True, 'strict_route': False, 'stack': 'gvisor', 'mtu': 9000},
        {'type': 'mixed', 'tag': 'mixed-local', 'listen': '127.0.0.1', 'listen_port': 7890}
    ],
    'outbounds': [
        {'type': 'direct', 'tag': 'direct', 'domain_resolver': {'server': 'dns-system', 'strategy': 'prefer_ipv4'}},
        {'type': 'urltest', 'tag': 'auto', 'outbounds': ['direct'], 'url': 'https://www.gstatic.com/generate_204', 'interval': '3m', 'tolerance': 50}
    ],
    'route': {
        'rules': [
            {'domain_suffix': ['.cn'], 'outbound': 'direct'},
            {'ip_cidr': ['10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16'], 'outbound': 'direct'}
        ],
        'final': 'auto'
    }
}
with open('$CONFIG_DIR/config.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
"
        else
            python3 -c "
import json
config = {
    'log': {'level': 'info', 'timestamp': True},
    'dns': {
        'servers': [
            {'type': 'udp', 'tag': 'dns-system', 'server': '10.139.1.1', 'server_port': 53, 'detour': 'direct'},
            {'type': 'https', 'tag': 'dns-proxy', 'server': '8.8.8.8', 'detour': 'auto'}
        ],
        'rules': [],
        'strategy': 'prefer_ipv4',
        'independent_cache': True
    },
    'inbounds': [
        {'type': 'tun', 'tag': 'tun-in', 'interface_name': 'tun0',
         'address': ['172.19.0.1/30', 'fdfe:dcba:9877::1/126'],
         'auto_route': True, 'strict_route': False, 'stack': 'gvisor', 'mtu': 9000},
        {'type': 'mixed', 'tag': 'mixed-local', 'listen': '127.0.0.1', 'listen_port': 7890}
    ],
    'outbounds': [
        {'type': 'direct', 'tag': 'direct', 'domain_resolver': {'server': 'dns-system', 'strategy': 'prefer_ipv4'}},
        {'type': 'urltest', 'tag': 'auto', 'outbounds': ['direct'], 'url': 'https://www.gstatic.com/generate_204', 'interval': '3m', 'tolerance': 50}
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
    fi

    systemctl start sing-box

    # Step 7: Install auxiliary services
    step "$(t step_auxiliary n=7 total=7)"
    if [ -f "$WORK_DIR/scripts/auto-update-subscriptions.sh" ]; then
        cp "$WORK_DIR/scripts/auto-update-subscriptions.sh" /usr/local/bin/auto-update-subscriptions
        chmod +x /usr/local/bin/auto-update-subscriptions
    fi
    if [ -f "$WORK_DIR/scripts/update-subscriptions.service" ]; then
        cp "$WORK_DIR/scripts/update-subscriptions.service" /etc/systemd/system/
    fi
    if [ -f "$WORK_DIR/scripts/update-subscriptions.timer" ]; then
        cp "$WORK_DIR/scripts/update-subscriptions.timer" /etc/systemd/system/
    fi
    if [ -f "$WORK_DIR/scripts/singbox-monitor.service" ]; then
        cp "$WORK_DIR/scripts/singbox-monitor.service" /etc/systemd/system/
    fi

    systemctl daemon-reload
    systemctl enable --now update-subscriptions.timer 2>/dev/null || true
    systemctl enable singbox-monitor 2>/dev/null || true

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  $(t success_install)${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}$(t quick_start):${NC}"
    echo -e "    singctl                     $(t cmd_singctl)"
    echo -e "    update-singbox-config       $(t cmd_update)"
    echo ""
    echo -e "  ${BOLD}$(t auto_services):${NC}"
    echo -e "    $(t auto_update_desc)    $(t status_active)"
    echo -e "    $(t auto_monitor_desc)    $(t status_active)"
    echo ""
    echo -e "  ${BOLD}$(t next_steps):${NC}"
    echo -e "    1. $(t next_step1)"
    echo -e "    2. $(t next_step2)"
    echo -e "       ${DIM}qvm-prefs your-app-vm netvm $(hostname)${NC}"
    echo ""
}

# ============================================================
#  Update Function
# ============================================================
do_update() {
    echo ""
    echo -e "${BOLD}$(t tutorial_update_title)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  $(t tutorial_update_desc)"
    echo ""
    echo -e "  ${CYAN}1.${NC} $(t tutorial_update_step1)"
    echo -e "  ${CYAN}2.${NC} $(t tutorial_update_step2)"
    echo -e "  ${CYAN}3.${NC} $(t tutorial_update_step3)"
    echo ""
    echo -e "  ${DIM}$(t tutorial_update_hint)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""

    step "$(t tutorial_update_step1)..."
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"
    git clone --depth 1 -b "$BRANCH" "https://github.com/$REPO.git" "$WORK_DIR"
    cd "$WORK_DIR"

    step "$(t tutorial_update_step2)..."
    cp -r singctl/* "$INSTALL_DIR/"
    
    # Update language files
    mkdir -p /usr/local/lib/lang
    cp lang/*.json /usr/local/lib/lang/

    # Update auxiliary scripts
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

    step "$(t tutorial_update_step3)..."
    systemctl daemon-reload
    systemctl restart sing-box 2>/dev/null || true

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  $(t success_update)${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  $(t success_updated_from old="$LOCAL_VER" new="$REMOTE_VER")"
    echo ""
}

# ============================================================
#  Uninstall Function
# ============================================================
do_uninstall() {
    echo ""
    echo -e "${YELLOW}${BOLD}$(t uninstall_title)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo -e "  $(t uninstall_desc)"
    echo -e "    - $(t uninstall_step1)"
    echo -e "    - $(t uninstall_step2)"
    echo -e "    - $(t uninstall_step3)"
    echo -e "    - $(t uninstall_step4)"
    echo -e "    - ${RED}$(t uninstall_step5)${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
    echo ""

    read -p "$(t confirm_uninstall) (y/N) " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Cancelled"
        return
    fi

    step "Stopping services..."
    systemctl stop sing-box 2>/dev/null || true
    systemctl stop singbox-monitor 2>/dev/null || true
    systemctl stop update-subscriptions.timer 2>/dev/null || true

    step "Removing services..."
    systemctl disable sing-box 2>/dev/null || true
    systemctl disable singbox-monitor 2>/dev/null || true
    systemctl disable update-subscriptions.timer 2>/dev/null || true
    rm -f /etc/systemd/system/sing-box.service
    rm -f /etc/systemd/system/singbox-monitor.service
    rm -f /etc/systemd/system/update-subscriptions.service
    rm -f /etc/systemd/system/update-subscriptions.timer
    systemctl daemon-reload

    step "Removing singctl..."
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/singctl"
    rm -f "$BIN_DIR/update-singbox-config"
    rm -f "$BIN_DIR/auto-update-subscriptions"
    rm -rf /usr/local/lib/lang

    step "Removing sing-box..."
    rm -f /usr/local/bin/sing-box

    echo ""
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  $(t success_uninstall)${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${DIM}$(t uninstall_done): $CONFIG_DIR${NC}"
    echo -e "  ${DIM}$(t uninstall_clean_hint path="$CONFIG_DIR")${NC}"
    echo ""
}

# ============================================================
#  Interactive Menu
# ============================================================
show_menu() {
    echo -e "${BOLD}$(t current_status):${NC} $STATUS_MSG"
    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"

    case "$STATUS" in
        not_installed)
            echo -e "  ${CYAN}[1]${NC} $(t menu_install)"
            echo -e "  ${DIM}[2]${NC} $(t menu_exit)"
            echo ""
            read -p "$(t select_prompt max=2)" choice
            case "$choice" in
                1) do_install ;;
                2) exit 0 ;;
                *) warn "$(t error_invalid_choice)"; exit 1 ;;
            esac
            ;;
        update_available)
            echo -e "  ${CYAN}[1]${NC} $(t menu_update) → v${REMOTE_VER}"
            echo -e "  ${DIM}[2]${NC} $(t menu_uninstall)"
            echo -e "  ${DIM}[3]${NC} $(t menu_exit)"
            echo ""
            read -p "$(t select_prompt max=3)" choice
            case "$choice" in
                1) do_update ;;
                2) do_uninstall ;;
                3) exit 0 ;;
                *) warn "$(t error_invalid_choice)"; exit 1 ;;
            esac
            ;;
        up_to_date|ahead)
            echo -e "  ${DIM}[1]${NC} $(t menu_reinstall)"
            echo -e "  ${DIM}[2]${NC} $(t menu_uninstall)"
            echo -e "  ${DIM}[3]${NC} $(t menu_exit)"
            echo ""
            read -p "$(t select_prompt max=3)" choice
            case "$choice" in
                1) do_install ;;
                2) do_uninstall ;;
                3) exit 0 ;;
                *) warn "$(t error_invalid_choice)"; exit 1 ;;
            esac
            ;;
        installed_no_remote)
            echo -e "  ${DIM}[1]${NC} $(t menu_reinstall)"
            echo -e "  ${DIM}[2]${NC} $(t menu_uninstall)"
            echo -e "  ${DIM}[3]${NC} $(t menu_exit)"
            echo ""
            read -p "$(t select_prompt max=3)" choice
            case "$choice" in
                1) do_install ;;
                2) do_uninstall ;;
                3) exit 0 ;;
                *) warn "$(t error_invalid_choice)"; exit 1 ;;
            esac
            ;;
    esac
}

# ============================================================
#  Main Flow
# ============================================================

# Check if language is already saved
SAVED_LANG=$(get_saved_lang)

if [ -n "$SAVED_LANG" ] && [ "$SAVED_LANG" != "" ]; then
    # Use saved language
    SELECTED_LANG="$SAVED_LANG"
else
    # First run - show language selection
    show_language_menu
fi

# Load language
load_lang "$SELECTED_LANG"

# Show header
show_header

# Handle command line arguments
case "${1:-}" in
    install)   do_install; exit 0 ;;
    update)    detect_status; do_update; exit 0 ;;
    uninstall) do_uninstall; exit 0 ;;
esac

# Interactive mode
detect_status
show_menu
