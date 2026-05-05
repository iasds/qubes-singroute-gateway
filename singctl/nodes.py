"""Node parsing, speedtest, and IP geolocation"""
import socket
import time
import json
import urllib.request
import ssl
import concurrent.futures
from collections import defaultdict
from .config import SPEEDTEST_TIMEOUT, SPEEDTEST_WORKERS, C_GREEN, C_RED, C_GRAY, C_RESET, C_DIM

_geo_cache = {}


def country_flag(code):
    if not code or len(code) != 2:
        return "🌐"
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))


def lookup_ip_geo(ip):
    if not ip or ip in ("127.0.0.1", "localhost", ""):
        return None, None
    if ip in _geo_cache:
        return _geo_cache[ip]
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"http://ip-api.com/json/{ip}?fields=countryCode,country&lang=zh-CN"
        req = urllib.request.Request(url, headers={"User-Agent": "singctl/0.1"})
        with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            code = data.get("countryCode", "")
            name = data.get("country", "")
            result = (code, name)
            _geo_cache[ip] = result
            return result
    except Exception:
        return None, None


def parse_nodes(config):
    """Parse proxy nodes, extract subscription source from tag"""
    skip = {"selector", "urltest", "direct", "dns", "block"}
    nodes = []
    for o in config.get("outbounds", []):
        if o.get("type") in skip:
            continue
        tag = o.get("tag", "")
        if not tag:
            continue
        
        # Extract sub source: n000-sub1-xxx -> sub1
        sub_source = "other"
        parts = tag.split("-", 2)
        if len(parts) >= 2 and parts[1] in ("sub1", "sub2"):
            sub_source = parts[1]
        
        nodes.append({
            "tag": tag,
            "type": o.get("type", "unknown"),
            "server": o.get("server", ""),
            "port": o.get("server_port", 0),
            "latency": None,
            "online": None,
            "country_code": None,
            "country_name": None,
            "flag": "🌐",
            "sub_source": sub_source,
            "outbound": o
        })
    return nodes


def _resolve_and_test(node, timeout=SPEEDTEST_TIMEOUT):
    server = node.get("server", "")
    port = node.get("port", 0)
    if not server or not port:
        return None, None, None

    ip = None
    try:
        ip = socket.gethostbyname(server)
    except Exception:
        pass

    code, name = None, None
    if ip:
        code, name = lookup_ip_geo(ip)

    latency = None
    try:
        start = time.monotonic()
        sock = socket.create_connection((server, port), timeout=timeout)
        latency = int((time.monotonic() - start) * 1000)
        sock.close()
    except Exception:
        pass

    return latency, code, name


def speedtest_all(nodes, max_workers=SPEEDTEST_WORKERS):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(_resolve_and_test, n): n for n in nodes}
        for fut in concurrent.futures.as_completed(future_map):
            node = future_map[fut]
            try:
                latency, code, name = fut.result()
                node["latency"] = latency
                node["online"] = latency is not None
                if code:
                    node["country_code"] = code
                    node["country_name"] = name
                    node["flag"] = country_flag(code)
            except Exception:
                node["latency"] = None
                node["online"] = False
    return nodes


def group_by_sub(nodes):
    """Group nodes by subscription source"""
    groups = defaultdict(list)
    for n in nodes:
        groups[n.get("sub_source", "other")].append(n)
    
    # Sort nodes within each group by latency
    result = []
    for source in ("sub1", "sub2", "other"):
        if source in groups:
            ns = groups[source]
            ns.sort(key=lambda x: x["latency"] if x["latency"] else 99999)
            result.append((source, ns))
    return result


def format_latency(latency):
    if latency is None:
        return f"{C_GRAY}---{C_RESET}"
    if latency < 100:
        return f"{C_GREEN}{latency}ms{C_RESET}"
    if latency < 300:
        return f"{latency}ms"
    return f"{C_RED}{latency}ms{C_RESET}"


def format_node_line(node, name_width=30):
    """Format node line: flag + name + latency"""
    flag = node.get("flag", "🌐")
    # Clean up tag: remove n000-sub1- prefix
    tag = node["tag"]
    parts = tag.split("-", 2)
    if len(parts) >= 3:
        tag = parts[2]  # Remove n000-sub1- prefix
    name = tag[:name_width].ljust(name_width)
    lat = format_latency(node["latency"])
    return f"    {flag} {name} {lat:>14s}"


def sort_nodes(nodes, by="latency"):
    def key(n):
        online = 0 if n["online"] else 1
        lat = n["latency"] if n["latency"] is not None else 99999
        return (online, lat)
    return sorted(nodes, key=key)
