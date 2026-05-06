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

# China IP CIDRs (major ranges) - replaces geoip:cn
CHINA_CIDRS = [
    "1.0.1.0/24", "1.0.2.0/23", "1.0.8.0/21", "1.0.32.0/19",
    "1.1.0.0/24", "1.1.2.0/23", "1.1.4.0/22", "1.1.8.0/24",
    "1.2.0.0/23", "1.2.2.0/24", "1.4.1.0/24", "1.4.2.0/23",
    "1.8.0.0/16", "1.10.0.0/21", "1.12.0.0/14", "1.16.0.0/12",
    "1.32.0.0/11", "1.48.0.0/13", "1.56.0.0/13", "1.64.0.0/10",
    "1.128.0.0/9", "14.0.0.0/11", "14.104.0.0/13", "14.112.0.0/12",
    "27.8.0.0/13", "27.16.0.0/12", "27.36.0.0/14", "27.40.0.0/13",
    "27.50.128.0/17", "27.54.192.0/18", "27.64.0.0/10", "27.128.0.0/9",
    "36.0.0.0/10", "36.96.0.0/11", "36.128.0.0/10", "36.192.0.0/11",
    "36.248.0.0/14", "39.0.0.0/11", "39.64.0.0/10", "39.128.0.0/10",
    "42.0.0.0/8", "43.224.0.0/13", "43.236.0.0/14", "43.240.0.0/14",
    "45.112.0.0/14", "49.0.0.0/11", "49.32.0.0/11", "49.64.0.0/10",
    "49.128.0.0/11", "58.0.0.0/9", "59.32.0.0/11", "59.64.0.0/10",
    "60.0.0.0/10", "60.160.0.0/11", "60.194.0.0/15", "60.200.0.0/13",
    "60.208.0.0/12", "60.252.0.0/16", "61.0.0.0/12", "61.28.0.0/15",
    "61.45.128.0/17", "61.48.0.0/13", "61.128.0.0/10", "100.64.0.0/10",
    "101.0.0.0/11", "101.32.0.0/12", "101.48.0.0/14", "101.52.0.0/15",
    "101.54.0.0/16", "101.64.0.0/10", "101.128.0.0/14", "101.132.0.0/14",
    "101.200.0.0/14", "101.224.0.0/11", "103.0.0.0/14", "103.4.0.0/15",
    "103.8.0.0/14", "106.0.0.0/9", "106.224.0.0/12", "110.0.0.0/8",
    "111.0.0.0/8", "112.0.0.0/8", "113.0.0.0/8", "114.16.0.0/12",
    "114.48.0.0/12", "114.64.0.0/10", "114.128.0.0/10", "114.192.0.0/11",
    "114.224.0.0/11", "115.0.0.0/11", "115.32.0.0/11", "115.84.0.0/18",
    "115.96.0.0/11", "115.148.0.0/14", "115.152.0.0/15", "115.168.0.0/14",
    "115.192.0.0/10", "116.0.0.0/8", "117.0.0.0/9", "117.128.0.0/10",
    "118.16.0.0/12", "118.64.0.0/10", "118.132.0.0/14", "118.180.0.0/14",
    "118.192.0.0/10", "119.0.0.0/9", "119.128.0.0/10", "119.232.0.0/13",
    "119.248.0.0/14", "120.0.0.0/10", "120.64.0.0/11", "120.128.0.0/11",
    "121.0.0.0/11", "121.32.0.0/11", "121.60.0.0/14", "121.64.0.0/10",
    "121.192.0.0/10", "122.0.0.0/9", "122.128.0.0/13", "122.192.0.0/10",
    "123.0.0.0/10", "123.64.0.0/10", "123.128.0.0/10", "123.196.0.0/14",
    "123.232.0.0/13", "123.240.0.0/12", "124.0.0.0/12", "124.16.0.0/13",
    "124.64.0.0/10", "124.128.0.0/11", "124.160.0.0/11", "124.192.0.0/11",
    "124.224.0.0/11", "125.0.0.0/11", "125.32.0.0/11", "125.64.0.0/10",
    "125.160.0.0/11", "125.208.0.0/12", "125.224.0.0/12", "125.240.0.0/13"
]

# Private IP CIDRs - replaces geoip:private
PRIVATE_CIDRS = [
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16"
]

# Rule presets — route.rules arrays
# Note: In sing-box 1.13, dns-out outbound is removed.
# DNS is handled by the DNS inbound configuration, not route rules.
RULE_PRESETS = {
    "smart-split": {
        "name": "智能分流",
        "desc": "中国直连，国外自动选节点",
        "rules": [
            {"domain_suffix": [".cn"], "outbound": "direct"},
            {"domain_suffix": [
                ".baidu.com", ".qq.com", ".taobao.com", ".tmall.com",
                ".jd.com", ".weibo.com", ".zhihu.com", ".bilibili.com",
                ".douyin.com", ".xiaomi.com", ".huawei.com", ".alipay.com",
                ".163.com", ".126.com", ".sina.com", ".sohu.com",
                ".csdn.net", ".cnblogs.com", ".jianshu.com", ".segmentfault.com",
                ".gitee.com", ".aliyun.com", ".tencent.com", ".csdn.net"
            ], "outbound": "direct"},
            {"ip_cidr": CHINA_CIDRS, "outbound": "direct"},
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"}
        ]
    },
    "all-proxy": {
        "name": "全部代理",
        "desc": "所有流量走自动选节点",
        "rules": [
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"}
        ]
    },
    "bypass-cn": {
        "name": "仅代理被墙",
        "desc": "只代理已知被墙站点",
        "rules": [
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
                ".spotify.com", ".scdn.co"
            ], "outbound": "proxy"},
            {"domain_keyword": ["google", "youtube", "twitter", "facebook", "telegram"], "outbound": "proxy"},
            {"ip_cidr": CHINA_CIDRS, "outbound": "direct"},
            {"ip_cidr": PRIVATE_CIDRS, "outbound": "direct"}
        ]
    }
}

# DNS presets — foreign DNS detour: "auto" (via proxy), CN DNS detour: "direct"
# Qubes system DNS (10.139.1.1) always included for CN domains and proxy node resolution
DNS_PRESETS = {
    "google": {
        "name": "Google DNS",
        "desc": "经典选择，稳定可靠",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": "8.8.8.8", "detour": "auto"},
            {"type": "https", "tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"},
        ]
    },
    "cloudflare": {
        "name": "Cloudflare DNS",
        "desc": "注重隐私，无日志，速度快",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": "1.1.1.1", "detour": "auto"},
            {"type": "https", "tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"},
        ]
    },
    "quad9": {
        "name": "Quad9 DNS",
        "desc": "安全优先，自动拦截恶意域名",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": "9.9.9.9", "detour": "auto"},
            {"type": "https", "tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"},
        ]
    },
    "adguard": {
        "name": "AdGuard DNS",
        "desc": "隐私保护 + 广告拦截",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": "94.140.14.14", "detour": "auto"},
            {"type": "https", "tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"},
        ]
    },
    "mullvad": {
        "name": "Mullvad DNS",
        "desc": "严格无日志，瑞典隐私法保护",
        "servers": [
            {"type": "https", "tag": "dns-proxy", "server": "100.64.0.1", "detour": "auto"},
            {"type": "https", "tag": "dns-direct", "server": "119.29.29.29", "detour": "direct"},
        ]
    },
}
