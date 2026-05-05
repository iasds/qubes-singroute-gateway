"""JSON file I/O and preferences management"""
import json
import os
from datetime import datetime
from .config import (
    PREFERENCES_JSON, SUBSCRIPTIONS_JSON, CONFIG_JSON,
    DEFAULT_SPEEDTEST_URL, DEFAULT_UPDATE_INTERVAL_HOURS,
    DEFAULT_SPEEDTEST_INTERVAL, DEFAULT_TOLERANCE_MS
)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_preferences():
    defaults = {
        "mode": "rule",
        "rule_preset": "smart-split",
        "global_node": None,
        "last_update": None,
        "update_interval_hours": DEFAULT_UPDATE_INTERVAL_HOURS,
        "speedtest_url": DEFAULT_SPEEDTEST_URL,
        "speedtest_interval": DEFAULT_SPEEDTEST_INTERVAL,
        "tolerance_ms": DEFAULT_TOLERANCE_MS,
        "log_level": "info",
        "history": []
    }
    prefs = load_json(PREFERENCES_JSON, defaults)
    for k, v in defaults.items():
        if k not in prefs:
            prefs[k] = v
    return prefs


def save_preferences(prefs):
    save_json(PREFERENCES_JSON, prefs)


def load_config():
    return load_json(CONFIG_JSON, {})


def save_config(config):
    save_json(CONFIG_JSON, config)


def load_subscriptions():
    return load_json(SUBSCRIPTIONS_JSON, {"subscriptions": []})


def save_subscriptions(subs):
    save_json(SUBSCRIPTIONS_JSON, subs)


def time_ago(iso_str):
    """Convert ISO timestamp to '2h前' style string"""
    if not iso_str:
        return "从未"
    try:
        dt = datetime.fromisoformat(iso_str)
        diff = datetime.now() - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return f"{secs}秒前"
        if secs < 3600:
            return f"{secs // 60}分钟前"
        if secs < 86400:
            return f"{secs // 3600}h前"
        return f"{secs // 86400}天前"
    except Exception:
        return "未知"


def uptime_str(secs):
    """Convert seconds to '3h22m' style string"""
    if secs < 0:
        return "N/A"
    h, m = divmod(secs // 60, 60)
    if h > 0:
        return f"{h}h{m}m"
    return f"{m}m"
