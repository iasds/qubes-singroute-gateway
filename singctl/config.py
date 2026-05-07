"""Constants and paths"""
import os

# Paths (sys-singbox persistent storage)
SINGBOX_DIR = "/rw/config/sing-box"
CONFIG_JSON = os.path.join(SINGBOX_DIR, "config.json")
PREFERENCES_JSON = os.path.join(SINGBOX_DIR, "singctl-preferences.json")
SUBSCRIPTIONS_JSON = os.path.join(SINGBOX_DIR, "singctl-subscriptions.json")
CUSTOM_RULES_JSON = os.path.join(SINGBOX_DIR, "singctl-custom-rules.json")

# Speedtest
DEFAULT_SPEEDTEST_URL = "https://www.gstatic.com/generate_204"
DEFAULT_UPDATE_INTERVAL_HOURS = 6
DEFAULT_SPEEDTEST_INTERVAL = "3m"
DEFAULT_TOLERANCE_MS = 50
SPEEDTEST_TIMEOUT = 3
SPEEDTEST_WORKERS = 15

# ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_GRAY = "\033[90m"
C_WHITE = "\033[97m"
C_BG = "\033[48;5;234m"

# Box drawing
BOX_W = 58

# ── Remote Rule Sets (sing-box 1.13+ native rule_set) ──
# Source: Loyalsoldier/geoip (6k⭐) + SagerNet/sing-geosite (official)
# These are downloaded once, cached locally, and auto-updated.
RULE_SETS = {
    "geosite-cn": {
        "type": "remote",
        "tag": "geosite-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
        "download_detour": "direct",
        "update_interval": "1d",
    },
    "geoip-cn": {
        "type": "remote",
        "tag": "geoip-cn",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "download_detour": "direct",
        "update_interval": "1d",
    },
    "geosite-category-ads-all": {
        "type": "remote",
        "tag": "geosite-category-ads-all",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-category-ads-all.srs",
        "download_detour": "direct",
        "update_interval": "1d",
    },
}

# Private IP CIDRs — kept inline (small, static, no upstream source)
PRIVATE_CIDRS = [
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
]

# Rule presets — route.rules arrays
# Uses sing-box native rule_set references instead of inline CIDR lists
RULE_PRESETS = {
    "smart-split": {
        "name": "智能分流",
        "desc": "中国直连，国外自动选节点",
        "rules": [
            {"rule_set": "geosite-category-ads-all", "outbound": "block"},
            {"rule_set": "geosite-cn", "outbound": "direct"},
            {"rule_set": "geoip-cn", "outbound": "direct"},
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"},
        ],
    },
    "all-proxy": {
        "name": "全部代理",
        "desc": "所有流量走自动选节点",
        "rules": [
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"},
        ],
    },
    "bypass-cn": {
        "name": "仅代理受限",
        "desc": "只代理已知受限站点",
        "rules": [
            {"rule_set": "geosite-category-ads-all", "outbound": "block"},
            {"domain_suffix": [
                ".google.com", ".googleapis.com", ".gstatic.com",
                ".youtube.com", ".ytimg.com", ".ggpht.com",
                ".twitter.com", ".x.com", ".twimg.com",
                ".facebook.com", ".fbcdn.net", ".instagram.com",
                ".wikipedia.org", ".wikimedia.org",
                ".github.com", ".githubusercontent.com",
                ".telegram.org", ".t.me", ".telegram.me",
                ".openai.com", ".anthropic.com",
                ".reddit.com", ".redd.it",
                ".medium.com", ".substack.com",
                ".netflix.com", ".nflxvideo.net",
                ".spotify.com", ".scdn.co",
            ], "outbound": "proxy"},
            {"domain_keyword": ["google", "youtube", "twitter", "facebook", "telegram"], "outbound": "proxy"},
            {"rule_set": "geoip-cn", "outbound": "direct"},
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"},
        ],
    },
}

# DNS presets — foreign DNS: Cloudflare DoH via proxy (IP bypasses polluted DNS)
# CN DNS: DNSPod UDP direct (119.29.29.29, no TLS needed)
# Qubes system DNS (10.139.1.1) always included for CN domains and proxy node resolution
#
# Why IP instead of domain? In Qubes, default_domain_resolver uses Qubes DNS (10.139.1.1)
# which returns polluted results. If we use "cloudflare-dns.com" as DoH server, sing-box
# must first resolve that domain via Qubes DNS → gets wrong IP → DoH fails.
# Using the IP directly (104.16.248.249) skips domain resolution entirely.
CLOUDFLARE_DOH_IP = "104.16.248.249"  # cloudflare-dns.com → 104.16.248.249 / 104.16.249.249

DNS_PRESETS = {
    "cloudflare": {
        "name": "Cloudflare DNS",
        "desc": "注重隐私，无日志，速度快（推荐）",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": CLOUDFLARE_DOH_IP, "detour": "auto"},
            {"type": "udp", "tag": "dns-direct", "server": "119.29.29.29", "server_port": 53, "detour": "direct"},
        ]
    },
    "google": {
        "name": "Google DNS",
        "desc": "经典选择，经 Cloudflare 中转",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": CLOUDFLARE_DOH_IP, "detour": "auto"},
            {"type": "udp", "tag": "dns-direct", "server": "119.29.29.29", "server_port": 53, "detour": "direct"},
        ]
    },
    "quad9": {
        "name": "Quad9 DNS",
        "desc": "安全优先，自动拦截恶意域名",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": CLOUDFLARE_DOH_IP, "detour": "auto"},
            {"type": "udp", "tag": "dns-direct", "server": "119.29.29.29", "server_port": 53, "detour": "direct"},
        ]
    },
    "adguard": {
        "name": "AdGuard DNS",
        "desc": "隐私保护 + 广告拦截",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": CLOUDFLARE_DOH_IP, "detour": "auto"},
            {"type": "udp", "tag": "dns-direct", "server": "119.29.29.29", "server_port": 53, "detour": "direct"},
        ]
    },
    "mullvad": {
        "name": "Mullvad DNS",
        "desc": "严格无日志，瑞典隐私法保护",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": CLOUDFLARE_DOH_IP, "detour": "auto"},
            {"type": "udp", "tag": "dns-direct", "server": "119.29.29.29", "server_port": 53, "detour": "direct"},
        ]
    },
}
