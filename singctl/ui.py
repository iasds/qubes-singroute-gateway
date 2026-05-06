"""TUI interface - clean and minimal"""
import sys
import time
from simple_term_menu import TerminalMenu
from .config import (
    RULE_PRESETS, DNS_PRESETS, BOX_W,
    C_RESET, C_BOLD, C_DIM, C_GREEN, C_RED, C_CYAN, C_WHITE
)
from .data import (
    load_preferences, save_preferences, load_config, save_config,
    load_subscriptions, time_ago, uptime_str
)
from .proxy import (
    is_running, get_uptime_seconds, get_exit_ip, restart,
    detect_current_mode, apply_mode, clear_proxy_nodes,
    find_selector_outbound, get_current_dns, apply_dns_preset
)
from .nodes import (
    parse_nodes, speedtest_all, format_node_line, sort_nodes, group_by_sub
)
from .subs import (
    add_subscription, remove_subscription, update_subscription,
    update_all_subscriptions
)


def clear():
    print("\033[2J\033[H", end="")


def header(title):
    print(f"\n  {C_CYAN}{title}{C_RESET}")
    print(f"  {'─' * (BOX_W - 4)}")


def info(label, value):
    print(f"  {C_DIM}{label}:{C_RESET} {value}")


def make_menu(options, title="  选择:"):
    menu = TerminalMenu(
        options,
        title=title,
        menu_cursor="▸ ",
        menu_cursor_style=("fg_cyan",),
        menu_highlight_style=("fg_cyan",),
    )
    return menu.show()


def pause():
    input(f"\n  {C_DIM}按 Enter 继续...{C_RESET}")


# ─── Main Menu ───────────────────────────────────────────

def show_main():
    while True:
        clear()
        config = load_config()
        prefs = load_preferences()

        running = is_running()
        mode, node, preset = detect_current_mode(config)
        mode_names = {"global": "全局", "rule": "规则", "direct": "直连"}
        mode_str = mode_names.get(mode, mode)
        if preset:
            mode_str += f" ({RULE_PRESETS.get(preset, {}).get('name', preset)})"
        if mode == "global" and node:
            mode_str += f" → {node}"

        nodes = parse_nodes(config)
        subs_data = load_subscriptions()
        sub_count = len(subs_data.get("subscriptions", []))

        status = f"{C_GREEN}●{C_RESET}" if running else f"{C_RED}○{C_RESET}"
        print(f"\n  singctl  {status} {mode_str}")
        print(f"  {'─' * (BOX_W - 4)}")
        info("出口IP", get_exit_ip() if running else "—")
        info("运行", uptime_str(get_uptime_seconds()) if running else "—")
        info("节点", f"{len(nodes)}  |  订阅 {sub_count}  |  更新 {time_ago(prefs.get('last_update'))}")

        idx = make_menu([
            "代理模式",
            "节点管理",
            "订阅管理",
            "设置",
            "退出",
        ], title="")

        if idx is None or idx == 4:
            clear()
            sys.exit(0)
        elif idx == 0:
            show_mode_menu(config, prefs)
        elif idx == 1:
            show_nodes_menu(config)
        elif idx == 2:
            show_subs_menu()
        elif idx == 3:
            show_settings(prefs)


# ─── Mode Menu ───────────────────────────────────────────

def show_mode_menu(config, prefs):
    while True:
        clear()
        mode, node, preset = detect_current_mode(config)
        mode_names = {"global": "全局", "rule": "规则", "direct": "直连"}
        current = mode_names.get(mode, mode)
        if preset:
            current += f" ({RULE_PRESETS.get(preset, {}).get('name', preset)})"

        header("代理模式")
        info("当前", current)
        print()

        idx = make_menu([
            "智能分流  — 中国直连，国外代理",
            "全部代理  — 所有流量走代理",
            "仅代理被墙 — 只代理被墙站点",
            "全局代理  — 指定节点转发全部",
            "直连      — 不走代理",
            "← 返回",
        ])

        if idx is None or idx == 5:
            return
        elif idx == 0:
            _apply_and_save(config, prefs, "rule", rule_preset="smart-split")
            print(f"\n  {C_GREEN}✓{C_RESET} 已切换到智能分流")
            pause()
        elif idx == 1:
            _apply_and_save(config, prefs, "rule", rule_preset="all-proxy")
            print(f"\n  {C_GREEN}✓{C_RESET} 已切换到全部代理")
            pause()
        elif idx == 2:
            _apply_and_save(config, prefs, "rule", rule_preset="bypass-cn")
            print(f"\n  {C_GREEN}✓{C_RESET} 已切换到仅代理被墙")
            pause()
        elif idx == 3:
            show_global_node_select(config, prefs)
        elif idx == 4:
            _apply_and_save(config, prefs, "direct")
            print(f"\n  {C_GREEN}✓{C_RESET} 已切换到直连")
            pause()


def _apply_and_save(config, prefs, mode, **kwargs):
    apply_mode(config, mode, **kwargs)
    prefs["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_preferences(prefs)


def show_global_node_select(config, prefs):
    """Select node for global mode: first pick sub, then pick node"""
    clear()
    header("全局代理 — 选择节点")
    print(f"\n  {C_DIM}正在测速...{C_RESET}")

    nodes = parse_nodes(config)
    if not nodes:
        print(f"\n  没有可用节点")
        pause()
        return

    nodes = speedtest_all(nodes)
    groups = group_by_sub(nodes)

    # Step 1: Select subscription
    clear()
    header("全局代理 — 选择订阅")
    sub_names = []
    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        sub_names.append(f"{source}  ({online}/{len(ns)} 在线)")
    sub_names.append("← 返回")

    idx = make_menu(sub_names, title="  选择订阅来源:")
    if idx is None or idx == len(groups):
        return

    # Step 2: Select node within subscription
    source, sub_nodes = groups[idx]
    clear()
    header(f"全局代理 — {source}")

    options = [format_node_line(n) for n in sub_nodes]
    options.append("← 返回")

    idx = make_menu(options, title="  选择节点:")
    if idx is None or idx == len(sub_nodes):
        return

    node = sub_nodes[idx]
    _apply_and_save(config, prefs, "global", node_tag=node["tag"])
    print(f"\n  {C_GREEN}✓{C_RESET} 已切换到: {node['tag']}")
    pause()


# ─── Nodes Menu ──────────────────────────────────────────

def show_nodes_menu(config):
    while True:
        clear()
        header("节点管理")

        nodes = parse_nodes(config)
        
        sel = find_selector_outbound(config)
        if sel:
            current = sel.get("default", sel.get("outbounds", [None])[0])
            info("当前选中", current or "—")
        info("节点数", str(len(nodes)))
        print()

        idx = make_menu([
            "查看全部节点",
            "切换节点（按订阅）",
            "清空全部节点",
            "← 返回",
        ])

        if idx is None or idx == 3:
            return
        elif idx == 0:
            show_all_nodes(nodes)
        elif idx == 1:
            if not nodes:
                print(f"\n  没有可用节点")
                pause()
            else:
                show_node_selector_by_sub(config, nodes)
        elif idx == 2:
            show_clear_nodes(config)


def show_all_nodes(nodes):
    """Show all nodes with speedtest"""
    clear()
    header("全部节点")
    print(f"\n  {C_DIM}正在测速...{C_RESET}")

    nodes = speedtest_all(nodes)
    groups = group_by_sub(nodes)

    clear()
    header("全部节点")

    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        print(f"\n  {source} ({online}/{len(ns)} 在线)")
        print(f"  {'─' * (BOX_W - 6)}")
        for n in ns:
            print(format_node_line(n))

    pause()


def show_clear_nodes(config):
    """Clear all proxy nodes"""
    nodes = parse_nodes(config)
    if not nodes:
        print(f"\n  已经没有节点了")
        pause()
        return
    
    clear()
    header("清空节点")
    print(f"\n  当前有 {len(nodes)} 个节点")
    print(f"  清空后需要重新添加订阅才能使用代理")
    
    idx = make_menu([
        "确认清空",
        "← 返回",
    ], title="")
    
    if idx == 0:
        clear_proxy_nodes(config)
        print(f"\n  {C_GREEN}✓{C_RESET} 已清空全部节点")
        pause()


def show_node_selector_by_sub(config, nodes):
    """Select node: first pick sub, then pick node"""
    clear()
    header("切换节点")
    print(f"\n  {C_DIM}正在测速...{C_RESET}")

    nodes = speedtest_all(nodes)
    groups = group_by_sub(nodes)

    # Step 1: Select subscription
    clear()
    header("切换节点 — 选择订阅")
    sub_names = []
    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        sub_names.append(f"{source}  ({online}/{len(ns)} 在线)")
    sub_names.append("← 返回")

    idx = make_menu(sub_names, title="  选择订阅来源:")
    if idx is None or idx == len(groups):
        return

    # Step 2: Select node within subscription
    source, sub_nodes = groups[idx]
    clear()
    header(f"切换节点 — {source}")

    options = [format_node_line(n) for n in sub_nodes]
    options.append("← 返回")

    idx = make_menu(options, title="  选择节点:")
    if idx is None or idx == len(sub_nodes):
        return

    node = sub_nodes[idx]
    sel = find_selector_outbound(config)
    if sel:
        obs = sel.get("outbounds", [])
        if node["tag"] in obs:
            obs.remove(node["tag"])
            obs.insert(0, node["tag"])
            sel["outbounds"] = obs
            sel["default"] = node["tag"]
            save_config(config)
            restart()
            print(f"\n  {C_GREEN}✓{C_RESET} 已切换到: {node['tag']}")
    pause()


# ─── Subscription Menu ───────────────────────────────────

def show_subs_menu():
    while True:
        clear()
        header("订阅管理")

        subs_data = load_subscriptions()
        subs = subs_data.get("subscriptions", [])

        if subs:
            print()
            for i, s in enumerate(subs):
                name = s.get("name", f"sub{i+1}")
                count = s.get("node_count", len(s.get("nodes", [])))
                updated = time_ago(s.get("last_update"))
                print(f"  {i+1}. {name}  {count}个节点  {updated}")
            print()

        idx = make_menu([
            "添加订阅",
            "删除订阅",
            "更新全部",
            "更新单个",
            "← 返回",
        ])

        if idx is None or idx == 4:
            return
        elif idx == 0:
            sub_add()
        elif idx == 1:
            sub_remove(subs)
        elif idx == 2:
            sub_update_all()
        elif idx == 3:
            sub_update_single(subs)


def sub_add():
    clear()
    header("添加订阅")
    url = input(f"\n  订阅URL: ").strip()
    if not url:
        return
    name = input(f"  名称 (可选): ").strip() or None

    print(f"\n  {C_DIM}获取中...{C_RESET}")
    sub, err = add_subscription(url, name)
    if err:
        print(f"  {C_RED}✗{C_RESET} {err}")
    else:
        print(f"  {C_GREEN}✓{C_RESET} {sub['name']} ({sub['node_count']} 个节点)")
    pause()


def sub_remove(subs):
    if not subs:
        print(f"\n  没有订阅")
        pause()
        return

    clear()
    header("删除订阅")
    options = [f"{s.get('name', f'sub{i+1}')} ({s.get('node_count', 0)}个)" for i, s in enumerate(subs)]
    options.append("← 返回")

    idx = make_menu(options, title="  选择:")
    if idx is None or idx == len(subs):
        return

    removed = remove_subscription(idx)
    if removed:
        print(f"\n  {C_GREEN}✓{C_RESET} 已删除: {removed.get('name', '')}")
    pause()


def sub_update_all():
    clear()
    header("更新全部订阅")
    print(f"\n  {C_DIM}更新中...{C_RESET}")

    results = update_all_subscriptions()
    print()
    for name, count, err in results:
        if err:
            print(f"  {C_RED}✗{C_RESET} {name}: {err}")
        else:
            print(f"  {C_GREEN}✓{C_RESET} {name}: {count} 个节点")
    pause()


def sub_update_single(subs):
    if not subs:
        print(f"\n  没有订阅")
        pause()
        return

    clear()
    header("更新单个订阅")
    options = [s.get('name', f'sub{i+1}') for i, s in enumerate(subs)]
    options.append("← 返回")

    idx = make_menu(options, title="  选择:")
    if idx is None or idx == len(subs):
        return

    print(f"\n  {C_DIM}更新中...{C_RESET}")
    sub, err = update_subscription(idx)
    if err:
        print(f"  {C_RED}✗{C_RESET} {err}")
    else:
        print(f"  {C_GREEN}✓{C_RESET} {sub['name']} ({sub['node_count']} 个节点)")
    pause()


# ─── Settings ────────────────────────────────────────────

def show_settings(prefs):
    while True:
        clear()
        header("设置")
        print()
        # Show current DNS
        config = load_config()
        current_dns = get_current_dns(config)
        dns_name = DNS_PRESETS.get(current_dns, {}).get("name", "未知") if current_dns else "未知"
        info("DNS", dns_name)
        info("更新间隔", f"{prefs.get('update_interval_hours', 6)} 小时")
        info("测速URL", prefs.get("speedtest_url", "默认"))
        info("延迟容差", f"{prefs.get('tolerance_ms', 50)} ms")

        idx = make_menu([
            "DNS 设置",
            "修改更新间隔",
            "修改测速URL",
            "修改延迟容差",
            "← 返回",
        ])

        if idx is None or idx == 4:
            return
        elif idx == 0:
            show_dns_menu(config)
        elif idx == 1:
            val = input(f"\n  更新间隔 (小时): ").strip()
            if val.isdigit() and int(val) > 0:
                prefs["update_interval_hours"] = int(val)
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()
        elif idx == 2:
            val = input(f"\n  测速URL: ").strip()
            if val:
                prefs["speedtest_url"] = val
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()
        elif idx == 3:
            val = input(f"\n  延迟容差 (ms): ").strip()
            if val.isdigit():
                prefs["tolerance_ms"] = int(val)
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()


def show_dns_menu(config):
    """DNS provider selection menu"""
    clear()
    header("DNS 设置")

    current = get_current_dns(config)
    current_name = DNS_PRESETS.get(current, {}).get("name", "未知") if current else "未知"
    print()
    info("当前 DNS", current_name)
    print()

    options = []
    keys = []
    for key, preset in DNS_PRESETS.items():
        marker = " ✓" if key == current else ""
        options.append(f"{preset['name']}{marker}  — {preset['desc']}")
        keys.append(key)
    options.append("← 返回")

    idx = make_menu(options, title="  选择 DNS:")
    if idx is None or idx == len(keys):
        return

    selected_key = keys[idx]
    print(f"\n  {C_DIM}切换中...{C_RESET}")
    apply_dns_preset(config, selected_key)
    print(f"  {C_GREEN}✓{C_RESET} 已切换到 {DNS_PRESETS[selected_key]['name']}")
    pause()


# ─── Entry Point ─────────────────────────────────────────

def main():
    try:
        show_main()
    except KeyboardInterrupt:
        clear()
        sys.exit(0)
    except EOFError:
        # Terminal closed or piped input ended
        clear()
        sys.exit(0)
    except Exception as e:
        clear()
        print(f"\n  Error: {e}")
        sys.exit(1)
