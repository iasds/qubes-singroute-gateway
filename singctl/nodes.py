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

# 国家/地区代码 → 中文名称（特殊地区需标注所属）
_REGION_NAMES = {
    # 亚洲
    "CN": "中国", "HK": "中国香港", "MO": "中国澳门", "TW": "中国台湾",
    "JP": "日本", "KR": "韩国", "SG": "新加坡", "MY": "马来西亚",
    "TH": "泰国", "VN": "越南", "PH": "菲律宾", "ID": "印度尼西亚",
    "IN": "印度", "PK": "巴基斯坦", "BD": "孟加拉", "LK": "斯里兰卡",
    "MM": "缅甸", "KH": "柬埔寨", "LA": "老挝", "NP": "尼泊尔",
    "MN": "蒙古", "KZ": "哈萨克斯坦", "UZ": "乌兹别克斯坦",
    # 中东
    "AE": "阿联酋", "SA": "沙特", "IL": "以色列", "TR": "土耳其",
    "IR": "伊朗", "IQ": "伊拉克", "QA": "卡塔尔", "BH": "巴林",
    "KW": "科威特", "OM": "阿曼", "JO": "约旦", "LB": "黎巴嫩",
    # 欧洲
    "GB": "英国", "DE": "德国", "FR": "法国", "NL": "荷兰",
    "BE": "比利时", "CH": "瑞士", "AT": "奥地利", "SE": "瑞典",
    "NO": "挪威", "DK": "丹麦", "FI": "芬兰", "IT": "意大利",
    "ES": "西班牙", "PT": "葡萄牙", "PL": "波兰", "CZ": "捷克",
    "RO": "罗马尼亚", "HU": "匈牙利", "BG": "保加利亚", "HR": "克罗地亚",
    "GR": "希腊", "UA": "乌克兰", "BY": "白俄罗斯", "LT": "立陶宛",
    "LV": "拉脱维亚", "EE": "爱沙尼亚", "RS": "塞尔维亚", "SK": "斯洛伐克",
    "IE": "爱尔兰", "IS": "冰岛", "LU": "卢森堡", "MT": "马耳他",
    "CY": "塞浦路斯", "MC": "摩纳哥", "AD": "安道尔", "LI": "列支敦士登",
    # 北美
    "US": "美国", "CA": "加拿大", "MX": "墨西哥",
    # 南美
    "BR": "巴西", "AR": "阿根廷", "CL": "智利", "CO": "哥伦比亚",
    "PE": "秘鲁", "VE": "委内瑞拉", "EC": "厄瓜多尔", "UY": "乌拉圭",
    # 大洋洲
    "AU": "澳大利亚", "NZ": "新西兰",
    # 非洲
    "ZA": "南非", "EG": "埃及", "NG": "尼日利亚", "KE": "肯尼亚",
    "MA": "摩洛哥", "TN": "突尼斯", "GH": "加纳", "ET": "埃塞俄比亚",
}


def region_text(code):
    """返回地区中文名称，未知返回代码或🌐"""
    if not code or len(code) != 2:
        return "🌐"
    return _REGION_NAMES.get(code, code)


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
            "region": "🌐",
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
                    node["region"] = region_text(code)
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
    """Format node line: region + name + latency"""
    region = node.get("region", "🌐")
    # Clean up tag: remove n000-sub1- prefix
    tag = node["tag"]
    parts = tag.split("-", 2)
    if len(parts) >= 3:
        tag = parts[2]  # Remove n000-sub1- prefix
    name = tag[:name_width].ljust(name_width)
    lat = format_latency(node["latency"])
    return f"    {region:<6s} {name} {lat:>14s}"


def sort_nodes(nodes, by="latency"):
    def key(n):
        online = 0 if n["online"] else 1
        lat = n["latency"] if n["latency"] is not None else 99999
        return (online, lat)
    return sorted(nodes, key=key)
