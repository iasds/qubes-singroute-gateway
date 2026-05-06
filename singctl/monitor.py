"""Node health monitor — background service that checks proxy nodes periodically.

Features:
- Checks all proxy nodes every CHECK_INTERVAL seconds
- Removes nodes that fail consecutive health checks
- Logs status changes to syslog
- Does NOT restart sing-box on every check (only when nodes are removed)

Requires: running inside the singctl package directory context.
"""
import socket
import time
import json
import syslog
import signal
import sys
import os

# Add parent dir to path so we can import singctl
sys.path.insert(0, "/usr/local/lib")
from singctl.data import load_config, save_config
from singctl.config import SPEEDTEST_TIMEOUT

# --- Configuration ---
CHECK_INTERVAL = 300        # 5 minutes between full checks
NODE_TIMEOUT = 3            # seconds per node TCP connect test
MAX_FAIL_COUNT = 3          # consecutive failures before removing node
CHECK_WORKERS = 10          # parallel TCP checks
MONITOR_LOG_TAG = "singbox-monitor"
PID_FILE = "/tmp/singbox-monitor.pid"

# --- State ---
node_fail_counts = {}  # tag -> consecutive failure count
running = True


def log(msg):
    """Log to syslog and stderr"""
    syslog.syslog(syslog.LOG_INFO, msg)
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def signal_handler(sig, frame):
    global running
    log("收到停止信号，退出...")
    running = False


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def check_node(node, timeout=NODE_TIMEOUT):
    """Check if a node is reachable via TCP connect. Returns (tag, alive, latency_ms)."""
    tag = node.get("tag", "")
    server = node.get("server", "")
    port = node.get("server_port", 0)
    if not server or not port:
        return tag, False, None
    if server in ("127.0.0.1", "localhost", "0.0.0.0"):
        return tag, False, None
    try:
        start = time.monotonic()
        sock = socket.create_connection((server, port), timeout=timeout)
        latency = int((time.monotonic() - start) * 1000)
        sock.close()
        return tag, True, latency
    except Exception:
        return tag, False, None


def get_proxy_nodes(config):
    """Get proxy nodes from config (skip system outbounds)."""
    skip = {"selector", "urltest", "direct", "dns", "block"}
    return [o for o in config.get("outbounds", []) if o.get("type") not in skip]


def check_all_nodes(nodes):
    """Check all nodes using thread pool."""
    import concurrent.futures
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
        futures = {pool.submit(check_node, n): n for n in nodes}
        for fut in concurrent.futures.as_completed(futures):
            tag, alive, latency = fut.result()
            results[tag] = (alive, latency)
    return results


def remove_dead_nodes(config, dead_tags):
    """Remove dead nodes from config outbounds and urltest/selector lists."""
    if not dead_tags:
        return False

    dead_set = set(dead_tags)
    new_outbounds = []
    for o in config.get("outbounds", []):
        if o.get("tag") in dead_set and o.get("type") not in ("selector", "urltest", "direct", "dns", "block"):
            continue
        # Clean up urltest/selector references
        if o.get("type") in ("urltest", "selector") and "outbounds" in o:
            o["outbounds"] = [t for t in o["outbounds"] if t not in dead_set]
        new_outbounds.append(o)

    config["outbounds"] = new_outbounds
    save_config(config)
    return True


def restart_singbox():
    """Restart sing-box service."""
    import subprocess
    try:
        subprocess.run(["systemctl", "restart", "sing-box"], timeout=10, check=True)
        return True
    except Exception as e:
        log(f"重启 sing-box 失败: {e}")
        return False


def run_check():
    """Run a single health check cycle."""
    global node_fail_counts

    config = load_config()
    nodes = get_proxy_nodes(config)
    if not nodes:
        log("没有代理节点，跳过检查")
        return

    log(f"检查 {len(nodes)} 个节点...")
    results = check_all_nodes(nodes)

    alive_count = sum(1 for tag, (alive, _) in results.items() if alive)
    dead_count = len(results) - alive_count

    # Track consecutive failures
    nodes_to_remove = []
    for tag, (alive, latency) in results.items():
        if alive:
            node_fail_counts[tag] = 0
        else:
            node_fail_counts[tag] = node_fail_counts.get(tag, 0) + 1
            if node_fail_counts[tag] >= MAX_FAIL_COUNT:
                nodes_to_remove.append(tag)

    # Log summary
    log(f"检查完成: {alive_count} 在线, {dead_count} 离线, {len(nodes_to_remove)} 待移除")

    # Remove dead nodes
    if nodes_to_remove:
        log(f"移除死节点: {', '.join(nodes_to_remove)}")
        if remove_dead_nodes(config, nodes_to_remove):
            if restart_singbox():
                log(f"sing-box 已重启, 剩余 {len(config['outbounds'])} 个 outbounds")
            # Clean up fail counts for removed nodes
            for tag in nodes_to_remove:
                node_fail_counts.pop(tag, None)

    # Check if all nodes are dead
    if alive_count == 0:
        log("⚠️ 警告: 所有代理节点都离线!")


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    syslog.openlog(MONITOR_LOG_TAG)
    write_pid()
    log(f"节点健康监控启动 (间隔 {CHECK_INTERVAL}s, 连续 {MAX_FAIL_COUNT} 次失败后移除)")

    # Initial check after 30s (let sing-box start first)
    time.sleep(30)

    while running:
        try:
            run_check()
        except Exception as e:
            log(f"检查异常: {e}")

        # Sleep in small increments so we can respond to signals
        for _ in range(CHECK_INTERVAL):
            if not running:
                break
            time.sleep(1)

    cleanup_pid()
    log("节点健康监控已停止")


if __name__ == "__main__":
    main()
