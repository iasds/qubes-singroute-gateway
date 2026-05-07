"""Subscription management"""
import base64
import json
import urllib.request
import ssl
import re
from datetime import datetime
from .config import SUBSCRIPTIONS_JSON
from .data import load_json, save_json, load_subscriptions, save_subscriptions


def fetch_raw(url, timeout=15):
    """Fetch raw content from a subscription URL"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "singctl/0.1",
        "Accept": "*/*"
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def parse_uri_nodes(raw_data):
    """Parse proxy URIs (ss://, vmess://, vless://, trojan://, hysteria2://)"""
    text = raw_data
    # Try base64 decode first
    try:
        text = base64.b64decode(raw_data).decode("utf-8")
    except Exception:
        try:
            # Some providers use url-safe base64
            text = base64.urlsafe_b64decode(raw_data + "==").decode("utf-8")
        except Exception:
            pass

    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")

    nodes = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(ss|vmess|vless|trojan|hysteria2|hysteria|tuic|anytls)://', line)
        if m:
            proto = m.group(1)
            name = ""
            if "#" in line:
                line, name = line.rsplit("#", 1)
                name = urllib.request.unquote(name)
            nodes.append({
                "uri": line,
                "protocol": proto,
                "name": name or f"{proto}-{len(nodes)+1}"
            })
    return nodes


def parse_json_nodes(raw_data):
    """Parse sing-box or clash JSON format"""
    try:
        data = json.loads(raw_data)
    except Exception:
        return []

    nodes = []
    # sing-box format: {"outbounds": [...]}
    if isinstance(data, dict) and "outbounds" in data:
        for o in data["outbounds"]:
            if o.get("type") in ("selector", "urltest", "direct", "dns", "block"):
                continue
            nodes.append({
                "outbound": o,
                "protocol": o.get("type", "unknown"),
                "name": o.get("tag", f"node-{len(nodes)+1}")
            })
        return nodes

    # List of outbounds
    if isinstance(data, list):
        for o in data:
            if isinstance(o, dict) and o.get("type") not in (
                "selector", "urltest", "direct", "dns", "block"
            ):
                nodes.append({
                    "outbound": o,
                    "protocol": o.get("type", "unknown"),
                    "name": o.get("tag", f"node-{len(nodes)+1}")
                })
    return nodes


def fetch_subscription(url, timeout=15):
    """Fetch and parse a subscription, returns (nodes_list, raw_data)"""
    raw = fetch_raw(url, timeout)

    # Try JSON first
    json_nodes = parse_json_nodes(raw)
    if json_nodes:
        return json_nodes, raw

    # Try URI format
    uri_nodes = parse_uri_nodes(raw)
    if uri_nodes:
        return uri_nodes, raw

    return [], raw


def add_subscription(url, name=None):
    """Add a new subscription"""
    subs = load_subscriptions()
    # Check duplicate
    for s in subs["subscriptions"]:
        if s["url"] == url:
            return None, "订阅已存在"

    try:
        nodes, raw = fetch_subscription(url)
    except Exception as e:
        return None, f"获取失败: {e}"

    sub = {
        "url": url,
        "name": name or f"sub{len(subs['subscriptions'])+1}",
        "node_count": len(nodes),
        "last_update": datetime.now().isoformat(),
        "nodes": nodes
    }
    subs["subscriptions"].append(sub)
    save_subscriptions(subs)
    
    # Sync to config.json
    sync_nodes_to_config()
    
    return sub, None


def remove_subscription(index):
    """Remove a subscription by index (0-based)"""
    subs = load_subscriptions()
    if 0 <= index < len(subs["subscriptions"]):
        removed = subs["subscriptions"].pop(index)
        save_subscriptions(subs)
        return removed
    return None


def update_subscription(index):
    """Update a single subscription"""
    subs = load_subscriptions()
    if 0 <= index < len(subs["subscriptions"]):
        sub = subs["subscriptions"][index]
        try:
            nodes, raw = fetch_subscription(sub["url"])
            sub["nodes"] = nodes
            sub["node_count"] = len(nodes)
            sub["last_update"] = datetime.now().isoformat()
            save_subscriptions(subs)
            
            # Sync to config.json
            sync_nodes_to_config()
            
            return sub, None
        except Exception as e:
            return None, str(e)
    return None, "索引无效"


def update_all_subscriptions():
    """Update all subscriptions"""
    subs = load_subscriptions()
    results = []
    for i, sub in enumerate(subs["subscriptions"]):
        try:
            nodes, raw = fetch_subscription(sub["url"])
            sub["nodes"] = nodes
            sub["node_count"] = len(nodes)
            sub["last_update"] = datetime.now().isoformat()
            results.append((sub["name"], len(nodes), None))
        except Exception as e:
            results.append((sub["name"], 0, str(e)))
    save_subscriptions(subs)
    
    # Sync to config.json
    sync_nodes_to_config()
    
    return results


def get_all_nodes_from_subs():
    """Get all nodes from all subscriptions, merged"""
    subs = load_subscriptions()
    all_nodes = []
    for sub in subs["subscriptions"]:
        for node in sub.get("nodes", []):
            node["subscription"] = sub["name"]
            all_nodes.append(node)
    return all_nodes


def sync_nodes_to_config():
    """Sync subscription nodes to config.json"""
    from .data import load_config, save_config
    import json
    import base64
    
    subs = load_subscriptions()
    config = load_config()
    
    # Collect all nodes from subscriptions
    all_outbounds = []
    node_tags = []
    skip_types = {"selector", "urltest", "direct", "dns", "block"}
    
    # Keep system outbounds
    system_outbounds = []
    for o in config.get("outbounds", []):
        if o.get("type") in skip_types:
            system_outbounds.append(o)
    
    # Add nodes from subscriptions
    sub_idx = 0
    for sub in subs.get("subscriptions", []):
        sub_idx += 1
        for i, node in enumerate(sub.get("nodes", [])):
            # Generate tag
            tag = f"n{len(all_outbounds):03d}-sub{sub_idx}-{node.get('name', f'node{i+1}')}"
            tag = tag[:50]
            
            ob = None
            
            # If node has outbound config, use it directly
            if "outbound" in node and node["outbound"]:
                ob = node["outbound"]
                ob["tag"] = tag
            # If node has URI, parse it
            elif "uri" in node:
                uri = node["uri"]
                proto = node.get("protocol", "")
                
                if proto == "vmess":
                    ob = _parse_vmess_uri(uri, tag)
                elif proto == "ss":
                    ob = _parse_ss_uri(uri, tag)
                elif proto == "trojan":
                    ob = _parse_trojan_uri(uri, tag)
                elif proto in ("hysteria2", "hysteria"):
                    ob = _parse_hy2_uri(uri, tag)
                elif proto == "vless":
                    ob = _parse_vless_uri(uri, tag)
                elif proto == "tuic":
                    ob = _parse_tuic_uri(uri, tag)
                elif proto == "anytls":
                    ob = _parse_anytls_uri(uri, tag)
            
            if ob:
                # Skip dead nodes (e.g. 127.0.0.1)
                server = ob.get("server", "")
                if server in ("127.0.0.1", "localhost", "0.0.0.0"):
                    continue
                all_outbounds.append(ob)
                node_tags.append(tag)
    
    # Update config
    config["outbounds"] = all_outbounds + system_outbounds
    
    # Ensure route.default_domain_resolver exists (sing-box 1.13+ requirement)
    if "route" not in config:
        config["route"] = {}
    if "default_domain_resolver" not in config["route"]:
        config["route"]["default_domain_resolver"] = {"server": "dns-system", "strategy": "prefer_ipv4"}

    # Sync rule_sets (reuse proxy module's logic)
    from .proxy import _sync_rule_sets
    _sync_rule_sets(config)

    # Update urltest outbound
    for o in config["outbounds"]:
        if o.get("type") == "urltest":
            o["outbounds"] = node_tags

    save_config(config)
    return len(node_tags)


def _parse_vmess_uri(uri, tag):
    """Parse vmess:// URI to outbound config"""
    import json
    import base64
    try:
        b64 = uri.replace("vmess://", "")
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        data = json.loads(base64.b64decode(b64))
        
        ob = {
            "type": "vmess",
            "tag": tag,
            "server": data.get("add", ""),
            "server_port": int(data.get("port", 443)),
            "uuid": data.get("id", ""),
            "alter_id": int(data.get("aid", 0)),
            "security": data.get("scy", "auto"),
            "transport": {"type": data.get("net", "tcp")}
        }
        
        if data.get("tls") == "tls":
            ob["tls"] = {
                "enabled": True,
                "server_name": data.get("sni") or data.get("host") or data.get("add", "")
            }
        
        if data.get("net") == "ws":
            ob["transport"] = {"type": "ws", "path": data.get("path", "/")}
            if data.get("host"):
                ob["transport"]["headers"] = {"Host": data["host"]}
        
        return ob
    except Exception:
        return None


def _parse_ss_uri(uri, tag):
    """Parse ss:// URI to outbound config"""
    import base64
    try:
        # ss://method:password@server:port#name
        uri = uri.replace("ss://", "")
        if "@" in uri:
            # New format: method:password@server:port
            auth, server = uri.rsplit("@", 1)
            if ":" in auth:
                method, password = auth.split(":", 1)
            else:
                # Base64 encoded auth
                decoded = base64.b64decode(auth + "==").decode()
                method, password = decoded.split(":", 1)
            
            if "#" in server:
                server = server.split("#")[0]
            
            if ":" in server:
                host, port = server.rsplit(":", 1)
                port = int(port)
            else:
                host = server
                port = 443
            
            return {
                "type": "shadowsocks",
                "tag": tag,
                "server": host,
                "server_port": port,
                "method": method,
                "password": password
            }
        else:
            # Old format: base64encoded
            decoded = base64.b64decode(uri + "==").decode()
            if "@" in decoded:
                auth, server = decoded.rsplit("@", 1)
                method, password = auth.split(":", 1)
                host, port = server.rsplit(":", 1)
                return {
                    "type": "shadowsocks",
                    "tag": tag,
                    "server": host,
                    "server_port": int(port),
                    "method": method,
                    "password": password
                }
    except Exception:
        return None


def _parse_trojan_uri(uri, tag):
    """Parse trojan:// URI to outbound config"""
    try:
        # trojan://password@server:port?sni=xxx#name
        uri = uri.replace("trojan://", "")
        if "@" in uri:
            password, rest = uri.split("@", 1)
            server_part = rest.split("?")[0]
            if "#" in server_part:
                server_part = server_part.split("#")[0]
            
            if ":" in server_part:
                host, port = server_part.rsplit(":", 1)
                port = int(port)
            else:
                host = server_part
                port = 443
            
            # Extract SNI from query params
            sni = host
            if "?" in rest:
                params = rest.split("?")[1]
                for p in params.split("&"):
                    if p.startswith("sni="):
                        sni = p[4:]
                        break
            
            return {
                "type": "trojan",
                "tag": tag,
                "server": host,
                "server_port": port,
                "password": password,
                "tls": {"enabled": True, "server_name": sni}
            }
    except Exception:
        return None


def _parse_hy2_uri(uri, tag):
    """Parse hysteria2:// URI to outbound config.

    Format: hysteria2://password@server:port?sni=xxx&insecure=1#name
    Also handles: hysteria:// (legacy alias)
    """
    try:
        # Strip scheme
        uri = re.sub(r'^hysteria2?://', '', uri)

        # Extract fragment (name)
        if "#" in uri:
            uri, _ = uri.rsplit("#", 1)

        # Split query params
        params = {}
        if "?" in uri:
            uri, qs = uri.split("?", 1)
            for p in qs.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = urllib.request.unquote(v)

        # password@server:port
        if "@" not in uri:
            return None
        password, server_part = uri.rsplit("@", 1)

        if ":" in server_part:
            host, port = server_part.rsplit(":", 1)
            port = int(port)
        else:
            host = server_part
            port = 443

        ob = {
            "type": "hysteria2",
            "tag": tag,
            "server": host,
            "server_port": port,
            "password": password,
        }

        # TLS config
        sni = params.get("sni") or params.get("peer") or host
        insecure = params.get("insecure", "0") == "1"
        ob["tls"] = {
            "enabled": True,
            "server_name": sni,
            "insecure": insecure,
        }

        # Optional: obfs
        obfs_type = params.get("obfs")
        if obfs_type:
            ob["obfs"] = {
                "type": obfs_type,
                "password": params.get("obfs-password", ""),
            }

        # Optional: pinSHA256
        pin = params.get("pinSHA256")
        if pin:
            ob["tls"]["certificate_path"] = pin

        return ob
    except Exception:
        return None


def _parse_vless_uri(uri, tag):
    """Parse vless:// URI to outbound config.

    Format: vless://uuid@server:port?encryption=none&security=tls&sni=xxx&type=ws&path=/path&host=xxx#name
    """
    try:
        # Strip scheme
        uri = uri.replace("vless://", "")

        # Extract fragment (name)
        if "#" in uri:
            uri, _ = uri.rsplit("#", 1)

        # Split query params
        params = {}
        if "?" in uri:
            uri, qs = uri.split("?", 1)
            for p in qs.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = urllib.request.unquote(v)

        # uuid@server:port
        if "@" not in uri:
            return None
        uuid, server_part = uri.rsplit("@", 1)

        if ":" in server_part:
            host, port = server_part.rsplit(":", 1)
            port = int(port)
        else:
            host = server_part
            port = 443

        ob = {
            "type": "vless",
            "tag": tag,
            "server": host,
            "server_port": port,
            "uuid": uuid,
        }

        # TLS
        security = params.get("security", "none")
        if security in ("tls", "reality"):
            tls_cfg = {"enabled": True}
            sni = params.get("sni") or params.get("peer") or host
            tls_cfg["server_name"] = sni

            if security == "reality":
                tls_cfg["reality"] = {
                    "enabled": True,
                    "public_key": params.get("pbk", ""),
                    "short_id": params.get("sid", ""),
                }
                if params.get("fp"):
                    tls_cfg["utls"] = {
                        "enabled": True,
                        "fingerprint": params["fp"],
                    }
            ob["tls"] = tls_cfg

        # Transport
        transport_type = params.get("type", "tcp")
        if transport_type == "ws":
            ob["transport"] = {"type": "ws"}
            if params.get("path"):
                ob["transport"]["path"] = params["path"]
            if params.get("host"):
                ob["transport"]["headers"] = {"Host": params["host"]}
        elif transport_type == "grpc":
            ob["transport"] = {"type": "grpc"}
            if params.get("serviceName"):
                ob["transport"]["service_name"] = params["serviceName"]
        elif transport_type == "h2":
            ob["transport"] = {"type": "http"}
            if params.get("path"):
                ob["transport"]["path"] = params["path"]
            if params.get("host"):
                ob["transport"]["host"] = [params["host"]]
        # tcp: no transport config needed

        return ob
    except Exception:
        return None


def _parse_tuic_uri(uri, tag):
    """Parse tuic:// URI to outbound config.

    Format: tuic://uuid:password@server:port?congestion_control=bbr&sni=xxx&alpn=h3#name
    """
    try:
        uri = uri.replace("tuic://", "")

        # Extract fragment
        if "#" in uri:
            uri, _ = uri.rsplit("#", 1)

        # Split query params
        params = {}
        if "?" in uri:
            uri, qs = uri.split("?", 1)
            for p in qs.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = urllib.request.unquote(v)

        # uuid:password@server:port
        if "@" not in uri:
            return None
        auth, server_part = uri.rsplit("@", 1)

        if ":" in auth:
            uuid, password = auth.split(":", 1)
        else:
            return None

        if ":" in server_part:
            host, port = server_part.rsplit(":", 1)
            port = int(port)
        else:
            host = server_part
            port = 443

        ob = {
            "type": "tuic",
            "tag": tag,
            "server": host,
            "server_port": port,
            "uuid": uuid,
            "password": password,
        }

        # Congestion control
        cc = params.get("congestion_control", "bbr")
        ob["congestion_control"] = cc

        # TLS
        sni = params.get("sni") or host
        alpn = params.get("alpn", "h3").split(",")
        ob["tls"] = {
            "enabled": True,
            "server_name": sni,
            "alpn": alpn,
            "insecure": params.get("insecure", "0") == "1",
        }

        # UDP relay mode
        relay_mode = params.get("udp_relay_mode", "native")
        ob["udp_relay_mode"] = relay_mode

        return ob
    except Exception:
        return None


def _parse_anytls_uri(uri, tag):
    """Parse anytls:// URI to outbound config.

    Format: anytls://password@server:port?sni=xxx&insecure=1#name
    Note: anytls requires sing-box 1.12+
    """
    try:
        uri = uri.replace("anytls://", "")

        # Extract fragment
        if "#" in uri:
            uri, _ = uri.rsplit("#", 1)

        # Split query params
        params = {}
        if "?" in uri:
            uri, qs = uri.split("?", 1)
            for p in qs.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = urllib.request.unquote(v)

        # password@server:port
        if "@" not in uri:
            return None
        password, server_part = uri.rsplit("@", 1)

        if ":" in server_part:
            host, port = server_part.rsplit(":", 1)
            port = int(port)
        else:
            host = server_part
            port = 443

        sni = params.get("sni") or host
        insecure = params.get("insecure", "0") == "1"

        ob = {
            "type": "anytls",
            "tag": tag,
            "server": host,
            "server_port": port,
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": sni,
                "insecure": insecure,
            },
        }

        return ob
    except Exception:
        return None
