"""UI text in Japanese and English.

Wording can be customized without touching the code: put a JSON file such as
{"lock.unlock": "開ける"} at <settings folder>/i18n/ja.json (or en.json).
"""
from __future__ import annotations

import json

from .messages import M

LANGUAGES = ("ja", "en")
_lang = "ja"
_overrides: dict[str, str] = {}


def set_language(lang: str) -> None:
    global _lang, _overrides
    _lang = lang if lang in LANGUAGES else "ja"
    _overrides = {}
    try:
        from ..paths import config_dir

        path = config_dir() / "i18n" / f"{_lang}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _overrides = {str(k): str(v) for k, v in data.items()}
    except (OSError, ValueError):
        _overrides = {}


def language() -> str:
    return _lang


def tr(key: str, **kwargs) -> str:
    if not key:
        return ""
    text = _overrides.get(key)
    if text is None:
        pair = M.get(key)
        if pair is None:
            return key
        text = pair[1] if _lang == "en" else pair[0]
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
