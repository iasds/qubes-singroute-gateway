"""Internationalization (i18n) module for singctl"""
import json
import os

# Current language code
_current_lang = "en"

# Translation cache
_translations = {}

# Available languages
AVAILABLE_LANGUAGES = {
    "zh": {"name": "中文", "native": "中文"},
    "en": {"name": "English", "native": "English"},
    "ja": {"name": "日本語", "native": "日本語"},
    "ko": {"name": "한국어", "native": "한국어"},
    "ru": {"name": "Русский", "native": "Русский"},
    "es": {"name": "Español", "native": "Español"},
    "pt": {"name": "Português", "native": "Português"},
    "ar": {"name": "العربية", "native": "العربية"},
    "tr": {"name": "Türkçe", "native": "Türkçe"},
    "fa": {"name": "فارسی", "native": "فارسی"},
}


def get_lang_dir():
    """Get the language directory path"""
    # Try installed location first
    installed = "/usr/local/lib/lang"
    if os.path.isdir(installed):
        return installed
    
    # Try relative to this file
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(module_dir)
    local = os.path.join(project_dir, "lang")
    if os.path.isdir(local):
        return local
    
    # Try current working directory
    cwd = os.path.join(os.getcwd(), "lang")
    if os.path.isdir(cwd):
        return cwd
    
    return None


def load_language(lang_code):
    """Load language translations from JSON file"""
    global _current_lang, _translations
    
    if lang_code not in AVAILABLE_LANGUAGES:
        lang_code = "en"
    
    lang_dir = get_lang_dir()
    if not lang_dir:
        _current_lang = lang_code
        _translations = {}
        return
    
    lang_file = os.path.join(lang_dir, f"{lang_code}.json")
    if not os.path.exists(lang_file):
        lang_file = os.path.join(lang_dir, "en.json")
    
    try:
        with open(lang_file, "r", encoding="utf-8") as f:
            _translations = json.load(f)
        _current_lang = lang_code
    except (json.JSONDecodeError, IOError):
        _translations = {}


def get_current_lang():
    """Get current language code"""
    return _current_lang


def t(key, **kwargs):
    """Translate a key to current language
    
    Usage:
        t("menu_mode")  # Returns translated string
        t("status_update_available", local="1.0.0", remote="1.1.0")  # With format args
    """
    text = _translations.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def get_region_name(code):
    """Get region name in current language"""
    key = f"region_{code}"
    return _translations.get(key, code)


def get_language_list():
    """Get list of available languages with their display names"""
    return [
        (code, info["native"])
        for code, info in AVAILABLE_LANGUAGES.items()
    ]
