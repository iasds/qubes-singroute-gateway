"""sing-box service control and config manipulation"""
import subprocess
import time
import urllib.request
import ssl
import json
from .config import CONFIG_JSON, SINGBOX_DIR
from .data import load_config, save_config


def is_running():
    """Check if sing-box service is active"""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "sing-box"],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


def get_uptime_seconds():
    """Get sing-box uptime in seconds"""
    try:
        r = subprocess.run(
            ["systemctl", "show", "sing-box", "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5
        )
        line = r.stdout.strip()
        if "=" not in line:
            return -1
        ts_str = line.split("=", 1)[1].strip()
        # Parse systemd timestamp: "Tue 2026-05-05 20:00:00 CST"
        from datetime import datetime
        # Try common formats
        for fmt in ["%a %Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"]:
            try:
                start = datetime.strptime(ts_str, fmt)
                return int((datetime.now() - start).total_seconds())
            except ValueError:
                continue
        return -1
    except Exception:
        return -1


def restart():
    """Restart sing-box service"""
    subprocess.run(["systemctl", "restart", "sing-box"], check=True, timeout=10)
    time.sleep(1)  # Give it a moment to start


def get_exit_ip():
    """Get current exit IP address"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": "singctl/0.1"}
        )
        with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
            return resp.read().decode().strip()
    except Exception:
        return "N/A"


def get_outbound_tags(config, skip_types=None):
    """Get all outbound tags, optionally filtering by type"""
    if skip_types is None:
        skip_types = {"selector", "urltest", "direct", "dns", "block"}
    return [
        o["tag"] for o in config.get("outbounds", [])
        if o.get("tag") and o.get("type") not in skip_types
    ]


def get_route_final(config):
    """Get current route.final value"""
    return config.get("route", {}).get("final", "proxy")


def set_route_final(config, tag):
    """Set route.final to a specific outbound tag"""
    if "route" not in config:
        config["route"] = {}
    config["route"]["final"] = tag


def get_route_rules(config):
    """Get current route rules"""
    return config.get("route", {}).get("rules", [])


def set_route_rules(config, rules):
    """Replace route rules"""
    if "route" not in config:
        config["route"] = {}
    config["route"]["rules"] = rules


def find_selector_outbound(config):
    """Find the first selector-type outbound"""
    for o in config.get("outbounds", []):
        if o.get("type") == "selector":
            return o
    return None


def find_urltest_outbound(config):
    """Find the first urltest-type outbound"""
    for o in config.get("outbounds", []):
        if o.get("type") == "urltest":
            return o
    return None


def get_proxy_outbounds(config):
    """Get proxy-type outbounds (not selector/urltest/direct/dns/block)"""
    skip = {"selector", "urltest", "direct", "dns", "block"}
    return [o for o in config.get("outbounds", []) if o.get("type") not in skip]


def detect_current_mode(config):
    """Detect current proxy mode from config"""
    final = get_route_final(config)
    rules = get_route_rules(config)

    if final == "direct":
        return "direct", None, None

    # Check if final points to a proxy node directly (global mode)
    proxy_tags = set()
    for o in get_proxy_outbounds(config):
        proxy_tags.add(o.get("tag", ""))

    if final in proxy_tags:
        return "global", final, None

    # Rule mode — detect preset by analyzing rules
    rule_outbounds = {r.get("outbound") for r in rules if "outbound" in r}
    has_domain_rules = any("domain_suffix" in r or "domain_keyword" in r for r in rules)
    
    # Check if there are IP CIDR rules (China direct)
    has_ip_cidr_rules = any("ip_cidr" in r for r in rules)
    
    # Count domain rules for proxy outbound
    proxy_domain_rules = sum(
        1 for r in rules 
        if r.get("outbound") == "proxy" and ("domain_suffix" in r or "domain_keyword" in r)
    )
    
    # Count total domain rules
    total_domain_rules = sum(
        1 for r in rules 
        if "domain_suffix" in r or "domain_keyword" in r
    )

    # Detect preset based on rule patterns
    if has_domain_rules and proxy_domain_rules > 0:
        # Has proxy domain rules -> bypass-cn
        return "rule", None, "bypass-cn"
    elif has_domain_rules and has_ip_cidr_rules:
        # Has domain rules and IP CIDR rules -> smart-split
        return "rule", None, "smart-split"
    elif has_ip_cidr_rules:
        # Has IP CIDR rules but no domain rules -> all-proxy
        return "rule", None, "all-proxy"
    else:
        # Minimal rules -> smart-split (default)
        return "rule", None, "smart-split"


def apply_mode(config, mode, node_tag=None, rule_preset=None, rules_data=None):
    """Apply a proxy mode to the config and restart sing-box"""
    from .config import RULE_PRESETS

    if mode == "direct":
        set_route_final(config, "direct")
        # Keep rules minimal
        set_route_rules(config, [
            {"protocol": "dns", "outbound": "dns-out"},
            {"ip_cidr": ["10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16"], "outbound": "direct"}
        ])

    elif mode == "global":
        if not node_tag:
            raise ValueError("Global mode requires a node tag")
        set_route_final(config, node_tag)
        set_route_rules(config, [
            {"protocol": "dns", "outbound": "dns-out"},
            {"ip_cidr": ["10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16"], "outbound": "direct"}
        ])

    elif mode == "rule":
        # Restore selector/urltest as final
        selector = find_selector_outbound(config)
        urltest = find_urltest_outbound(config)
        if selector:
            set_route_final(config, selector["tag"])
        elif urltest:
            set_route_final(config, urltest["tag"])
        else:
            set_route_final(config, "proxy")

        # Apply rule preset
        if rules_data:
            set_route_rules(config, rules_data)
        elif rule_preset and rule_preset in RULE_PRESETS:
            set_route_rules(config, RULE_PRESETS[rule_preset]["rules"])

        # If a specific node is selected in rule mode, update selector
        if node_tag and selector:
            obs = selector.get("outbounds", [])
            if node_tag in obs:
                obs.remove(node_tag)
                obs.insert(0, node_tag)
                selector["outbounds"] = obs
                selector["default"] = node_tag

    save_config(config)
    restart()
    return config


def clear_proxy_nodes(config):
    """Remove all proxy nodes from config, keep system outbounds"""
    skip_types = {"selector", "urltest", "direct", "dns", "block"}
    
    # Filter out proxy nodes
    new_outbounds = []
    for o in config.get("outbounds", []):
        if o.get("type") in skip_types:
            # Keep system outbounds, but clear their outbounds list
            if o.get("type") in ("selector", "urltest"):
                o["outbounds"] = []
                o.pop("default", None)
            new_outbounds.append(o)
    
    config["outbounds"] = new_outbounds
    
    # Reset route.final to direct
    if "route" in config:
        config["route"]["final"] = "direct"
        config["route"]["rules"] = [
            {"ip_cidr": ["10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", 
                         "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16"], 
             "outbound": "direct"}
        ]
    
    save_config(config)
    restart()
    return config
