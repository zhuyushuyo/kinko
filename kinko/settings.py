"""App settings for this PC, stored as editable JSON (settings.json).

Anything about how the app looks or behaves on this PC lives here. Things that
must travel with the data (categories, item types) live inside the vault.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

from .paths import config_dir

_MAC = sys.platform == "darwin"

DEFAULT_SHORTCUTS = {
    "search": "Ctrl+F",
    "new_item": "Ctrl+N",
    "edit_item": "Ctrl+E",
    "save_item": "Ctrl+S",
    "copy_password": "Ctrl+C",
    "copy_username": "Ctrl+B",
    "open_url": "Ctrl+U",
    "favorite": "Ctrl+D",
    "trash_item": "Ctrl+Backspace" if _MAC else "Del",
    "lock": "Ctrl+L",
    "settings": "Ctrl+,",
}

DEFAULT_GENERATOR = {
    "mode": "random",  # random / words / pin
    "length": 16,
    "upper": True,
    "lower": True,
    "digits": True,
    "symbols": True,
    "symbol_set": "!#$%&*+-=?@_",
    "avoid_ambiguous": True,
    "words": 4,
    "separator": "-",
    "capitalize": False,
    "word_digit": True,
    "pin_length": 4,
}

DEFAULTS: dict[str, Any] = {
    "version": 1,
    # 一般
    "language": "ja",
    "open_last_vault": True,
    "last_vault": "",
    "recent_vaults": [],
    "vault_dir": "",  # "" = My Drive/App Development/AppData/KINKO
    "trash_days": 30,
    # 表示
    "theme": "system",  # light / dark / system
    "density": "standard",  # standard / compact
    "font_px": 13,
    "font_family": "",  # "" = OS default Japanese UI font
    "list_subtitle": "username",  # username / email / url / none
    "sort": "recent",  # recent / name / updated
    "show_favorites": True,
    "show_recent": True,
    "show_tags": True,
    "show_health": True,
    "sidebar_expanded": ["finance"],
    # セキュリティ
    "auto_lock_minutes": 5,  # 0 = off
    "lock_on_minimize": True,
    "lock_on_app_switch": False,
    "lock_on_os_lock": True,
    "clipboard_seconds": 30,  # 0 = never clear
    # バックアップ
    "backup_enabled": True,
    "backup_dir": "",  # "" = <vault folder>/backups
    "backup_keep_latest": 20,
    "backup_keep_days": 30,
    # パスワード生成・ショートカット
    "generator": DEFAULT_GENERATOR,
    "shortcuts": DEFAULT_SHORTCUTS,
    # ウィンドウ
    "window_geometry": "",
    "splitter_state": "",
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else config_dir() / "settings.json"
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Keep the broken file for the user and start from defaults.
            try:
                self.path.replace(self.path.with_suffix(".broken.json"))
            except OSError:
                pass
            return
        if isinstance(raw, dict):
            self.data = _merge(DEFAULTS, raw)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    def set_in(self, group: str, key: str, value: Any, save: bool = True) -> None:
        sub = dict(self.data.get(group) or {})
        sub[key] = value
        self.set(group, sub, save)

    def remember_vault(self, path: str) -> None:
        recent = [p for p in self["recent_vaults"] if p != path]
        recent.insert(0, path)
        self.data["recent_vaults"] = recent[:8]
        self.data["last_vault"] = path
        self.save()

    def reset(self, keys: list[str]) -> None:
        for k in keys:
            self.data[k] = copy.deepcopy(DEFAULTS[k])
        self.save()
