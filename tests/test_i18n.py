"""Every key the code uses exists in the catalog, in both languages."""
import re
from pathlib import Path

from kinko.i18n.messages import M

ROOT = Path(__file__).resolve().parent.parent / "kinko"

DYNAMIC = {
    "ftype": ["text", "email", "secret", "pin", "url", "multiline", "date", "number", "qa", "twofa"],
    "gen.sep": ["space", "none"],
    "issue": ["reused", "weak", "fair", "old", "twofa_off", "twofa_check"],
    "safety.level": ["high", "mid", "low"],
    "safety.title": ["high", "mid", "low"],
    "safety.reason": ["reused", "weak", "fair", "old", "twofa_off", "twofa_check"],
    "safety.twofa": ["on", "none", "unknown"],
    "twofa": ["unknown", "on", "off", "none"],
    "sort": ["recent", "name", "updated"],
    "sc": ["search", "new_item", "edit_item", "save_item", "copy_password", "copy_username", "open_url",
           "favorite", "trash_item", "lock", "settings"],
    "settings.palette_role": ["ai", "tokiwa", "kincha", "bengara"],
    "gen": ["random", "words", "pin", "upper", "lower", "digits", "symbols", "avoid_ambiguous", "capitalize",
            "word_digit"],
    "settings.page": ["general", "appearance", "security", "generator", "categories", "backup", "shortcuts", "vault"],
    "settings.subtitle": ["username", "email", "url", "none"],
    "settings": ["show_favorites", "show_recent", "show_tags", "show_health"],
    "strength": ["0", "1", "2", "3", "4"],
}


def used_keys():
    keys = set()
    for f in ROOT.rglob("*.py"):
        s = f.read_text(encoding="utf-8")
        keys |= set(re.findall(r"""\btr\(\s*["']([a-z0-9_.]+)["']""", s))
        keys |= set(re.findall(r'"(?:name_key|label_key|closed_key)"\s*:\s*"([a-z0-9_.]+)"', s))
        keys |= set(re.findall(r'\(\s*"[a-z]+"\s*,\s*"(field\.[a-z_]+)"\s*\)', s))
        keys |= set(re.findall(r'url="(field\.[a-z_]+)"', s))
    for prefix, names in DYNAMIC.items():
        sep = "_" if prefix in ("gen.sep", "settings.page", "settings.subtitle") else "."
        keys |= {f"{prefix}{sep}{n}" for n in names}
    return keys


def test_all_keys_present():
    missing = sorted(k for k in used_keys() if k not in M and not k.endswith("."))
    assert missing == []


def test_both_languages_and_placeholders_match():
    for key, (ja, en) in M.items():
        assert ja and en, key
        assert set(re.findall(r"{(\w+)}", ja)) == set(re.findall(r"{(\w+)}", en)), key
