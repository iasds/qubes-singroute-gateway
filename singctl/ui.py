"""TUI interface - clean and minimal"""
import sys
import os
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
    find_selector_outbound, get_current_dns, apply_dns_preset,
    load_custom_rules, add_custom_rule, remove_custom_rule
)
from .nodes import (
    parse_nodes, speedtest_all, format_node_line, sort_nodes, group_by_sub
)
from .subs import (
    add_subscription, remove_subscription, update_subscription,
    update_all_subscriptions
)
from .i18n import t, get_region_name

# Module-level cache for speedtest results (run once at startup)
_cached_nodes = None


def clear():
    print("\033[2J\033[H", end="")


def header(title):
    print(f"\n  {C_CYAN}{title}{C_RESET}")
    print(f"  {'─' * (BOX_W - 4)}")


def info(label, value):
    print(f"  {C_DIM}{label}:{C_RESET} {value}")


def make_menu(options, title=None):
    if title is None:
        title = f"  {t('tui_select')}"
    menu = TerminalMenu(
        options,
        title=title,
        menu_cursor="▸ ",
        menu_cursor_style=("fg_cyan",),
        menu_highlight_style=("fg_cyan",),
    )
    return menu.show()


def pause():
    input(f"\n  {C_DIM}{t('tui_press_enter')}{C_RESET}")


# ─── Node cache (speedtest once at startup) ─────────────

def get_nodes_cached(config, force_refresh=False):
    """Get nodes with speedtest results, cached from startup.
    Call with force_refresh=True to re-test (e.g. after updating subscriptions).
    """
    global _cached_nodes
    if _cached_nodes is None or force_refresh:
        nodes = parse_nodes(config)
        if nodes:
            print(f"\n  {C_DIM}{t('node_testing')}{C_RESET}")
            nodes = speedtest_all(nodes)
        _cached_nodes = nodes
    return _cached_nodes

def invalidate_node_cache():
    """Clear cached nodes so next get_nodes_cached() re-tests."""
    global _cached_nodes
    _cached_nodes = None


# ─── Main Menu ───────────────────────────────────────────

def show_main():
    while True:
        clear()
        config = load_config()
        prefs = load_preferences()

        running = is_running()
        mode, node, preset = detect_current_mode(config)
        mode_names = {
            "global": t("mode_global"),
            "rule": t("mode_rule"),
            "direct": t("mode_direct"),
        }
        mode_str = mode_names.get(mode, mode)
        if preset:
            mode_str += f" ({RULE_PRESETS.get(preset, {}).get('name', preset)})"

        nodes = get_nodes_cached(config)
        subs_data = load_subscriptions()
        sub_count = len(subs_data.get("subscriptions", []))

        # Active node info
        active_node = None
        active_latency = None
        if mode == "global" and node:
            # Find the node and check latency
            for n in nodes:
                if n["tag"] == node:
                    active_node = n
                    break
        elif mode == "rule":
            # urltest auto-select: show first available node as reference
            active_node = nodes[0] if nodes else None

        status = f"{C_GREEN}●{C_RESET}" if running else f"{C_RED}○{C_RESET}"
        print(f"\n  singctl  {status} {mode_str}")
        print(f"  {'─' * (BOX_W - 4)}")

        # Exit IP and uptime
        exit_ip = get_exit_ip() if running else "—"
        uptime = uptime_str(get_uptime_seconds()) if running else "—"
        info(t("tui_exit_ip"), exit_ip)
        info(t("status_uptime"), uptime)

        # Active node
        if active_node and running:
            # Quick latency check for the active node
            from .nodes import _resolve_and_test
            _, _, active_latency = _resolve_and_test(active_node, timeout=2)
            lat_str = f"{active_latency}ms" if active_latency else t("node_timeout")
            node_name = active_node["tag"].split("-", 2)[-1] if "-" in active_node["tag"] else active_node["tag"]
            region = get_region_name(active_node.get("region", "unknown"))
            info(t("tui_current_node"), f"{region} {node_name[:30]}  {lat_str}")
        elif mode == "global" and node:
            node_name = node.split("-", 2)[-1] if "-" in node else node
            info(t("tui_current_node"), node_name)

        # DNS info
        current_dns = get_current_dns(config)
        dns_name = DNS_PRESETS.get(current_dns, {}).get("name", "?") if current_dns else "—"
        info(t("tui_current_dns"), dns_name)

        # Node/sub summary
        online = sum(1 for n in nodes if n.get("online", True))
        info(t("tui_nodes"), t("tui_nodes_summary", count=len(nodes), subs=sub_count, updated=time_ago(prefs.get('last_update'))))

        # Monitor status
        monitor_running = os.path.exists("/tmp/singbox-monitor.pid") and \
            os.path.isfile("/tmp/singbox-monitor.pid")
        if monitor_running:
            try:
                with open("/tmp/singbox-monitor.pid") as f:
                    pid = f.read().strip()
                os.kill(int(pid), 0)
                monitor_str = f"{C_GREEN}●{C_RESET}"
            except (ValueError, ProcessLookupError, PermissionError):
                monitor_str = f"{C_RED}○{C_RESET}"
                monitor_running = False
        else:
            monitor_str = f"{C_RED}○{C_RESET}"
        info(t("status_monitor"), monitor_str)

        idx = make_menu([
            t("menu_mode"),
            t("menu_nodes"),
            t("menu_subs"),
            t("menu_settings"),
            t("menu_exit"),
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
        mode_names = {
            "global": t("mode_global"),
            "rule": t("mode_rule"),
            "direct": t("mode_direct"),
        }
        current = mode_names.get(mode, mode)
        if preset:
            current += f" ({RULE_PRESETS.get(preset, {}).get('name', preset)})"

        header(t("menu_mode"))
        info(t("tui_current"), current)
        print()

        mode_items = [
            ("mode_smart_split", "mode_smart_split_desc", "mode_smart_split_hint"),
            ("mode_all_proxy", "mode_all_proxy_desc", "mode_all_proxy_hint"),
            ("mode_bypass", "mode_bypass_desc", "mode_bypass_hint"),
        ]
        options = []
        for name_key, desc_key, hint_key in mode_items:
            options.append(f"{t(name_key):10s}  {t(desc_key)}\n           {C_DIM}└ {t(hint_key)}{C_RESET}")
        options.append(f"{t('mode_global'):10s}  {t('mode_global_desc')}\n           {C_DIM}└ {t('mode_global_hint')}{C_RESET}")
        options.append(f"{t('mode_direct'):10s}  {t('mode_direct_desc')}\n           {C_DIM}└ {t('mode_direct_hint')}{C_RESET}")
        options.append(t("tui_back"))

        idx = make_menu(options)

        if idx is None or idx == 5:
            return
        elif idx == 0:
            _apply_and_save(config, prefs, "rule", rule_preset="smart-split")
            print(f"\n  {C_GREEN}✓{C_RESET} {t('mode_switched', mode=t('mode_smart_split'))}")
            pause()
        elif idx == 1:
            _apply_and_save(config, prefs, "rule", rule_preset="all-proxy")
            print(f"\n  {C_GREEN}✓{C_RESET} {t('mode_switched', mode=t('mode_all_proxy'))}")
            pause()
        elif idx == 2:
            _apply_and_save(config, prefs, "rule", rule_preset="bypass-cn")
            print(f"\n  {C_GREEN}✓{C_RESET} {t('mode_switched', mode=t('mode_bypass'))}")
            pause()
        elif idx == 3:
            show_global_node_select(config, prefs)
        elif idx == 4:
            _apply_and_save(config, prefs, "direct")
            print(f"\n  {C_GREEN}✓{C_RESET} {t('mode_switched', mode=t('mode_direct'))}")
            pause()


def _apply_and_save(config, prefs, mode, **kwargs):
    apply_mode(config, mode, **kwargs)
    prefs["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_preferences(prefs)


def show_global_node_select(config, prefs):
    """Select node for global mode: first pick sub, then pick node"""
    clear()
    header(f"{t('mode_global')} — {t('tui_select_node')}")
    print(f"\n  {C_DIM}{t('node_testing')}{C_RESET}")

    nodes = get_nodes_cached(config)
    if not nodes:
        print(f"\n  {t('node_no_available')}")
        pause()
        return

    groups = group_by_sub(nodes)

    # Step 1: Select subscription
    clear()
    header(f"{t('mode_global')} — {t('tui_select_sub')}")
    sub_names = []
    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        sub_names.append(f"{source}  ({online}/{len(ns)} {t('node_online')})")
    sub_names.append(t("tui_back"))

    idx = make_menu(sub_names, title=f"  {t('tui_select_sub_source')}")
    if idx is None or idx == len(groups):
        return

    # Step 2: Select node within subscription
    source, sub_nodes = groups[idx]
    clear()
    header(f"{t('mode_global')} — {source}")

    options = [format_node_line(n) for n in sub_nodes]
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select_node')}")
    if idx is None or idx == len(sub_nodes):
        return

    node = sub_nodes[idx]
    _apply_and_save(config, prefs, "global", node_tag=node["tag"])
    print(f"\n  {C_GREEN}✓{C_RESET} {t('node_switched', name=node['tag'])}")
    pause()


# ─── Nodes Menu ──────────────────────────────────────────

def show_nodes_menu(config):
    while True:
        clear()
        header(t("menu_nodes"))

        nodes = get_nodes_cached(config)
        
        sel = find_selector_outbound(config)
        if sel:
            current = sel.get("default", sel.get("outbounds", [None])[0])
            info(t("tui_current_selected"), current or "—")
        info(t("tui_node_count_label"), str(len(nodes)))
        print()

        idx = make_menu([
            t("node_view_all"),
            t("node_switch_by_sub"),
            t("node_clear_all"),
            t("tui_back"),
        ])

        if idx is None or idx == 3:
            return
        elif idx == 0:
            show_all_nodes(nodes)
        elif idx == 1:
            if not nodes:
                print(f"\n  {t('node_no_available')}")
                pause()
            else:
                show_node_selector_by_sub(config, nodes)
        elif idx == 2:
            show_clear_nodes(config)


def show_all_nodes(nodes):
    """Show all nodes with speedtest"""
    clear()
    header(t("node_all_title"))

    groups = group_by_sub(nodes)

    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        print(f"\n  {source} ({online}/{len(ns)} {t('node_online')})")
        print(f"  {'─' * (BOX_W - 6)}")
        for n in ns:
            print(format_node_line(n))

    pause()


def show_clear_nodes(config):
    """Clear all proxy nodes"""
    nodes = parse_nodes(config)
    if not nodes:
        print(f"\n  {t('node_already_empty')}")
        pause()
        return
    
    clear()
    header(t("node_clear_title"))
    print(f"\n  {t('node_clear_count', count=len(nodes))}")
    print(f"  {t('node_clear_hint')}")
    
    idx = make_menu([
        t("node_confirm_clear"),
        t("tui_back"),
    ], title="")
    
    if idx == 0:
        clear_proxy_nodes(config)
        print(f"\n  {C_GREEN}✓{C_RESET} {t('node_cleared')}")
        pause()


def show_node_selector_by_sub(config, nodes):
    """Select node: first pick sub, then pick node"""
    clear()
    header(f"{t('node_switch_title')} — {t('tui_select_sub')}")

    groups = group_by_sub(nodes)

    # Step 1: Select subscription
    sub_names = []
    for source, ns in groups:
        online = sum(1 for n in ns if n["online"])
        sub_names.append(f"{source}  ({online}/{len(ns)} {t('node_online')})")
    sub_names.append(t("tui_back"))

    idx = make_menu(sub_names, title=f"  {t('tui_select_sub_source')}")
    if idx is None or idx == len(groups):
        return

    # Step 2: Select node within subscription
    source, sub_nodes = groups[idx]
    clear()
    header(f"{t('node_switch_title')} — {source}")

    options = [format_node_line(n) for n in sub_nodes]
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select_node')}")
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
            print(f"\n  {C_GREEN}✓{C_RESET} {t('node_switched', name=node['tag'])}")
    pause()


# ─── Subscription Menu ───────────────────────────────────

def show_subs_menu():
    while True:
        clear()
        header(t("menu_subs"))

        subs_data = load_subscriptions()
        subs = subs_data.get("subscriptions", [])

        if subs:
            print()
            for i, s in enumerate(subs):
                name = s.get("name", f"sub{i+1}")
                count = s.get("node_count", len(s.get("nodes", [])))
                updated = time_ago(s.get("last_update"))
                print(f"  {i+1}. {name}  {t('tui_node_count', count=count)}  {updated}")
            print()

        idx = make_menu([
            t("sub_add"),
            t("sub_delete"),
            t("sub_update_all"),
            t("sub_update_one"),
            t("tui_back"),
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
    header(t("sub_add"))
    url = input(f"\n  {t('sub_enter_url')}").strip()
    if not url:
        return
    name = input(f"  {t('sub_enter_name')}").strip() or None

    print(f"\n  {C_DIM}{t('tui_fetching')}{C_RESET}")
    sub, err = add_subscription(url, name)
    if err:
        print(f"  {C_RED}✗{C_RESET} {err}")
    else:
        invalidate_node_cache()
        print(f"  {C_GREEN}✓{C_RESET} {t('sub_added', name=sub['name'], count=sub['node_count'])}")
    pause()


def sub_remove(subs):
    if not subs:
        print(f"\n  {t('sub_no_subs')}")
        pause()
        return

    clear()
    header(t("sub_delete"))
    options = [f"{s.get('name', f'sub{i+1}')} ({s.get('node_count', 0)})" for i, s in enumerate(subs)]
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select')}")
    if idx is None or idx == len(subs):
        return

    removed = remove_subscription(idx)
    if removed:
        invalidate_node_cache()
        print(f"\n  {C_GREEN}✓{C_RESET} {t('sub_deleted', name=removed.get('name', ''))}")
    pause()


def sub_update_all():
    clear()
    header(t("sub_update_all"))
    print(f"\n  {C_DIM}{t('tui_updating')}{C_RESET}")

    results = update_all_subscriptions()
    invalidate_node_cache()
    print()
    for name, count, err in results:
        if err:
            print(f"  {C_RED}✗{C_RESET} {name}: {err}")
        else:
            print(f"  {C_GREEN}✓{C_RESET} {t('sub_updated', name=name, count=count)}")
    pause()


def sub_update_single(subs):
    if not subs:
        print(f"\n  {t('sub_no_subs')}")
        pause()
        return

    clear()
    header(t("sub_update_one"))
    options = [s.get('name', f'sub{i+1}') for i, s in enumerate(subs)]
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select')}")
    if idx is None or idx == len(subs):
        return

    print(f"\n  {C_DIM}{t('tui_updating')}{C_RESET}")
    sub, err = update_subscription(idx)
    if err:
        print(f"  {C_RED}✗{C_RESET} {err}")
    else:
        invalidate_node_cache()
        print(f"  {C_GREEN}✓{C_RESET} {t('sub_updated', name=sub['name'], count=sub['node_count'])}")
    pause()


# ─── Settings ────────────────────────────────────────────

def show_settings(prefs):
    while True:
        clear()
        header(t("menu_settings"))
        print()
        # Show current DNS
        config = load_config()
        current_dns = get_current_dns(config)
        dns_name = DNS_PRESETS.get(current_dns, {}).get("name", t("tui_unknown")) if current_dns else t("tui_unknown")
        info(t("tui_current_dns"), dns_name)
        # Show custom rules count
        custom_data = load_custom_rules()
        custom_count = len(custom_data.get("rules", []))
        info(t("tui_custom_rules"), t("tui_rules_count", count=custom_count))
        info(t("tui_update_interval"), f"{prefs.get('update_interval_hours', 6)} {t('tui_hours')}")
        info(t("tui_speedtest_url"), prefs.get("speedtest_url", t("tui_default")))
        info(t("tui_tolerance"), f"{prefs.get('tolerance_ms', 50)} ms")

        idx = make_menu([
            t("menu_dns"),
            t("menu_rules"),
            t("tui_change_update_interval"),
            t("tui_change_speedtest_url"),
            t("tui_change_tolerance"),
            t("tui_back"),
        ])

        if idx is None or idx == 5:
            return
        elif idx == 0:
            show_dns_menu(config)
        elif idx == 1:
            show_custom_rules_menu()
        elif idx == 2:
            val = input(f"\n  {t('tui_enter_update_interval')}").strip()
            if val.isdigit() and int(val) > 0:
                prefs["update_interval_hours"] = int(val)
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()
        elif idx == 3:
            val = input(f"\n  {t('tui_enter_speedtest_url')}").strip()
            if val:
                prefs["speedtest_url"] = val
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()
        elif idx == 4:
            val = input(f"\n  {t('tui_enter_tolerance')}").strip()
            if val.isdigit():
                prefs["tolerance_ms"] = int(val)
                save_preferences(prefs)
                print(f"  {C_GREEN}✓{C_RESET}")
            pause()


def show_dns_menu(config):
    """DNS provider selection menu"""
    clear()
    header(t("dns_title"))

    current = get_current_dns(config)
    current_name = DNS_PRESETS.get(current, {}).get("name", t("tui_unknown")) if current else t("tui_unknown")
    print()
    info(t("dns_current"), current_name)
    print()

    options = []
    keys = []
    for key, preset in DNS_PRESETS.items():
        marker = " ✓" if key == current else ""
        options.append(f"{preset['name']}{marker}  — {preset['desc']}")
        keys.append(key)
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select_dns')}")
    if idx is None or idx == len(keys):
        return

    selected_key = keys[idx]
    print(f"\n  {C_DIM}{t('tui_switching')}{C_RESET}")
    apply_dns_preset(config, selected_key)
    print(f"  {C_GREEN}✓{C_RESET} {t('dns_switched', name=DNS_PRESETS[selected_key]['name'])}")
    pause()


# ─── Custom Rules Menu ────────────────────────────────────

def show_custom_rules_menu():
    """Custom routing rules management"""
    while True:
        clear()
        header(t("rules_title"))

        data = load_custom_rules()
        rules = data.get("rules", [])

        if rules:
            print()
            for i, r in enumerate(rules):
                out = r["outbound"]
                out_str = t("rules_outbound_direct") if out == "direct" else (t("rules_outbound_proxy") if out == "proxy" else out)
                rtype = t("rules_type_suffix") if r["type"] == "domain_suffix" else t("rules_type_keyword")
                print(f"  {i+1}. [{rtype}] {r['domain']} → {out_str}")
            print()

        idx = make_menu([
            t("rules_add"),
            t("rules_delete"),
            t("tui_back"),
        ])

        if idx is None or idx == 2:
            return
        elif idx == 0:
            show_add_custom_rule()
        elif idx == 1:
            show_remove_custom_rule(rules)


def show_add_custom_rule():
    """Add a custom routing rule"""
    clear()
    header(t("rules_add_title"))

    domain = input(f"\n  {t('rules_enter_domain')}").strip()
    if not domain:
        return

    # Rule type
    type_idx = make_menu([
        t("rules_type_suffix_desc"),
        t("rules_type_keyword_desc"),
        t("tui_back"),
    ], title=f"  {t('rules_match_type')}")
    if type_idx is None or type_idx == 2:
        return
    rule_type = "domain_suffix" if type_idx == 0 else "domain_keyword"

    # Outbound
    out_idx = make_menu([
        t("rules_outbound_direct_desc"),
        t("rules_outbound_proxy_desc"),
        t("tui_back"),
    ], title=f"  {t('rules_outbound')}")
    if out_idx is None or out_idx == 2:
        return
    outbound = "direct" if out_idx == 0 else "proxy"

    rule, err = add_custom_rule(domain, outbound, rule_type)
    if err:
        print(f"\n  {C_RED}✗{C_RESET} {err}")
    else:
        out_str = t("rules_outbound_direct") if outbound == "direct" else t("rules_outbound_proxy")
        print(f"\n  {C_GREEN}✓{C_RESET} {t('rules_added_detail', domain=domain, outbound=out_str)}")
        print(f"  {C_DIM}{t('rules_effect_hint')}{C_RESET}")
    pause()


def show_remove_custom_rule(rules):
    """Remove a custom routing rule"""
    if not rules:
        print(f"\n  {t('rules_empty')}")
        pause()
        return

    clear()
    header(t("rules_delete_title"))
    options = []
    for r in rules:
        out_str = t("rules_outbound_direct") if r["outbound"] == "direct" else t("rules_outbound_proxy")
        options.append(f"{r['domain']} → {out_str}")
    options.append(t("tui_back"))

    idx = make_menu(options, title=f"  {t('tui_select')}")
    if idx is None or idx == len(rules):
        return

    removed = remove_custom_rule(idx)
    if removed:
        print(f"\n  {C_GREEN}✓{C_RESET} {t('rules_deleted_detail', domain=removed['domain'])}")
    pause()


# ─── Entry Point ─────────────────────────────────────────

def main():
    from .i18n import load_language
    from .data import load_preferences
    prefs = load_preferences()
    load_language(prefs.get("lang", "zh"))
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
