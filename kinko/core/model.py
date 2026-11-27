"""Item model: field types, built-in fields, and the default (customizable) categories and types.

An item is a dict:
    {"title": str, "category": str, "sub": str, "status": "active"|"closed",
     "favorite": bool, "tags": [str], "fields": {key: value}, "extra": [{"key","label","type"}],
     "pw_changed_at": iso str}

Which fields an item shows comes from the type (template) of its category or
sub-category. Values never get lost: anything not covered by the type is still
shown under "その他の項目".
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime
from typing import Any

from ..i18n import tr

FIELD_TYPES = ("text", "email", "secret", "pin", "url", "multiline", "date", "number", "qa", "twofa")
SECRET_TYPES = ("secret", "pin")
COPYABLE_TYPES = ("text", "email", "secret", "pin", "url", "date", "number")

# key: (type, label i18n key)
BUILTIN_FIELDS: dict[str, tuple[str, str]] = {
    "username": ("text", "field.username"),
    "email": ("email", "field.email"),
    "password": ("secret", "field.password"),
    "transaction_password": ("secret", "field.transaction_password"),
    "pin": ("pin", "field.pin"),
    "branch": ("text", "field.branch"),
    "account_number": ("secret", "field.account_number"),
    "full_name": ("text", "field.full_name"),
    "pension_number": ("secret", "field.pension_number"),
    "twofa": ("twofa", "field.twofa"),
    "url": ("url", "field.url"),
    "secret_qa": ("qa", "field.secret_qa"),
    "notes": ("multiline", "field.notes"),
}


def _f(*keys: str, **labels: str) -> list[dict]:
    out = []
    for k in keys:
        d: dict[str, Any] = {"key": k}
        if k in labels:
            d["label_key"] = labels[k]
        out.append(d)
    return out


DEFAULT_TEMPLATES: dict[str, dict] = {
    "login": {"name_key": "template.login",
              "fields": _f("username", "email", "password", "twofa", "url", "secret_qa", "notes")},
    "bank": {"name_key": "template.bank",
             "fields": _f("username", "password", "transaction_password", "pin", "branch", "account_number",
                          "email", "twofa", "url", "secret_qa", "notes", url="field.login_url")},
    "card": {"name_key": "template.card",
             "fields": _f("username", "email", "password", "pin", "transaction_password", "twofa", "url",
                          "secret_qa", "notes", url="field.login_url")},
    "investment": {"name_key": "template.investment",
                   "fields": _f("username", "email", "password", "transaction_password", "pin", "branch",
                                "account_number", "twofa", "url", "secret_qa", "notes", url="field.login_url")},
    "pension": {"name_key": "template.pension",
                "fields": _f("full_name", "pension_number", "username", "email", "password", "twofa", "url",
                             "secret_qa", "notes")},
}

DEFAULT_CATEGORIES: list[dict] = [
    {"id": "shopping", "name_key": "cat.shopping", "icon": "bag", "color": "shop", "template": "login", "subs": []},
    {"id": "service", "name_key": "cat.service", "icon": "globe", "color": "svc", "template": "login", "subs": []},
    {"id": "finance", "name_key": "cat.finance", "icon": "yen", "color": "fin", "template": "login",
     "subs": [
         {"id": "bank", "name_key": "sub.bank", "template": "bank", "closed_key": "status.closed_contract"},
         {"id": "credit_card", "name_key": "sub.credit_card", "template": "card", "closed_key": "status.closed_contract"},
         {"id": "investment", "name_key": "sub.investment", "template": "investment"},
     ]},
    {"id": "game", "name_key": "cat.game", "icon": "game", "color": "game", "template": "login", "subs": []},
    {"id": "government", "name_key": "cat.government", "icon": "building", "color": "gov", "template": "login",
     "closed_key": "status.closed_gov",
     "subs": [
         {"id": "pension", "name_key": "sub.pension", "template": "pension"},
         {"id": "mynumber", "name_key": "sub.mynumber", "template": "login"},
         {"id": "my_license", "name_key": "sub.my_license", "template": "login"},
         {"id": "health_ins", "name_key": "sub.health_ins", "template": "login"},
     ]},
    {"id": "work", "name_key": "cat.work", "icon": "briefcase", "color": "work", "template": "login", "subs": []},
]

CATEGORY_ICONS = ("bag", "cart", "globe", "yen", "card", "game", "building", "briefcase", "home", "heart",
                  "book", "school", "mail", "phone", "plane", "car", "music", "film", "gift", "cloud",
                  "wifi", "key", "user", "star")
CATEGORY_COLORS = ("shop", "svc", "fin", "game", "gov", "work", "teal", "plum", "olive", "rust")

AUTH_APPS = ("Google Authenticator", "Microsoft Authenticator", "Authy", "Apple（パスワード／キーチェーン）",
             "Duo Mobile", "SMS", "メール")


def default_config() -> dict:
    return {"schema": 1, "categories": copy.deepcopy(DEFAULT_CATEGORIES), "templates": copy.deepcopy(DEFAULT_TEMPLATES)}


def normalize_config(cfg: dict | None) -> dict:
    """Fill gaps so older or hand-edited configs stay usable."""
    base = default_config()
    if not isinstance(cfg, dict):
        return base
    cfg = copy.deepcopy(cfg)
    cfg.setdefault("schema", 1)
    if not isinstance(cfg.get("templates"), dict) or not cfg["templates"]:
        cfg["templates"] = base["templates"]
    if "login" not in cfg["templates"]:
        cfg["templates"]["login"] = base["templates"]["login"]
    if not isinstance(cfg.get("categories"), list) or not cfg["categories"]:
        cfg["categories"] = base["categories"]
    for cat in cfg["categories"]:
        cat.setdefault("subs", [])
        cat.setdefault("icon", "star")
        cat.setdefault("color", "work")
        if cat.get("template") not in cfg["templates"]:
            cat["template"] = "login"
        for sub in cat["subs"]:
            if sub.get("template") not in cfg["templates"]:
                sub["template"] = cat["template"]
    return cfg


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def empty_item(category: str = "service", sub: str = "") -> dict:
    return {"title": "", "category": category, "sub": sub, "status": "active", "favorite": False,
            "tags": [], "fields": {}, "extra": [], "pw_changed_at": ""}


def normalize_item(data: dict) -> dict:
    d = empty_item()
    d.update({k: v for k, v in (data or {}).items()})
    d["fields"] = dict(d.get("fields") or {})
    d["extra"] = list(d.get("extra") or [])
    d["tags"] = [t for t in (d.get("tags") or []) if isinstance(t, str) and t.strip()]
    if d.get("status") not in ("active", "closed"):
        d["status"] = "active"
    return d


# Two-step verification, per account:
#   on      - switched on (with the app or method in "app")
#   off     - the service offers it, but it is not switched on yet
#   none    - the service does not offer it
#   unknown - not recorded (stored as no value at all)
# Stored in fields["twofa"] as {"state": ..., "on": bool, "app": str}. "on" is what KINKO 1.0.0 reads:
# 1.0.0 shows an account as using 2FA only when it is True and hides the field otherwise.
TWOFA_STATES = ("unknown", "on", "off", "none")


def twofa_state(value: Any) -> str:
    if not isinstance(value, dict):
        return "unknown"
    state = value.get("state")
    if state in ("on", "off", "none"):
        return state
    return "on" if value.get("on") else "unknown"


def twofa_value(state: str, app: str = "") -> dict | None:
    """What the vault stores for a 2FA state (None for unknown)."""
    if state not in ("on", "off", "none"):
        return None
    out: dict = {"state": state, "on": state == "on"}
    if state == "on" and app.strip():
        out["app"] = app.strip()
    return out


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not any((q.get("q") or q.get("a")) for q in value if isinstance(q, dict))
    if isinstance(value, dict):
        return twofa_state(value) == "unknown"
    return False


def same_service_item(src: dict) -> dict:
    """A new, empty account for the same service as src: its name, category, tags, URL, extra field
    names and whether the service offers 2FA. No ID, password, PIN, answer or note is copied."""
    d = empty_item(src.get("category", "service"), src.get("sub", ""))
    d["title"] = src.get("title", "")
    d["tags"] = list(src.get("tags", []))
    d["extra"] = [dict(e) for e in src.get("extra", []) if isinstance(e, dict)]
    url = (src.get("fields") or {}).get("url")
    if url:
        d["fields"]["url"] = url
    state = twofa_state((src.get("fields") or {}).get("twofa"))
    if state in ("on", "off"):
        d["fields"]["twofa"] = twofa_value("off")  # the service offers it; this account has not set it up
    elif state == "none":
        d["fields"]["twofa"] = twofa_value("none")
    return d


# ---------------------------------------------------------------- lookups

def display_name(obj: dict) -> str:
    return obj.get("name") or tr(obj.get("name_key", "")) or obj.get("id", "")


def find_category(cfg: dict, cat_id: str) -> dict | None:
    for c in cfg["categories"]:
        if c["id"] == cat_id:
            return c
    return None


def find_sub(cfg: dict, cat_id: str, sub_id: str) -> dict | None:
    cat = find_category(cfg, cat_id)
    if not cat or not sub_id:
        return None
    for s in cat["subs"]:
        if s["id"] == sub_id:
            return s
    return None


def template_id_for(cfg: dict, cat_id: str, sub_id: str = "") -> str:
    sub = find_sub(cfg, cat_id, sub_id)
    if sub and sub.get("template") in cfg["templates"]:
        return sub["template"]
    cat = find_category(cfg, cat_id)
    if cat and cat.get("template") in cfg["templates"]:
        return cat["template"]
    return "login"


def template_for(cfg: dict, cat_id: str, sub_id: str = "") -> dict:
    return cfg["templates"][template_id_for(cfg, cat_id, sub_id)]


def field_label(fdef: dict) -> str:
    if fdef.get("label"):
        return fdef["label"]
    if fdef.get("label_key"):
        return tr(fdef["label_key"])
    builtin = BUILTIN_FIELDS.get(fdef.get("key", ""))
    return tr(builtin[1]) if builtin else fdef.get("key", "")


def field_type(fdef: dict) -> str:
    if fdef.get("type") in FIELD_TYPES:
        return fdef["type"]
    builtin = BUILTIN_FIELDS.get(fdef.get("key", ""))
    return builtin[0] if builtin else "text"


def _lookup_def(cfg: dict, item: dict, key: str) -> dict:
    for e in item.get("extra", []):
        if e.get("key") == key:
            return e
    if key in BUILTIN_FIELDS:
        return {"key": key}
    for t in cfg["templates"].values():
        for f in t["fields"]:
            if f.get("key") == key:
                return f
    return {"key": key, "label": key, "type": "text"}


def item_fields(cfg: dict, item: dict, include_empty: bool = False) -> list[dict]:
    """Fields to show for an item, in order: type fields, extra fields, then leftovers."""
    tpl = template_for(cfg, item.get("category", ""), item.get("sub", ""))
    values = item.get("fields", {})
    out: list[dict] = []
    seen: set[str] = set()
    for f in tpl["fields"]:
        k = f["key"]
        seen.add(k)
        if include_empty or not is_empty(values.get(k)):
            out.append({**f, "label": field_label(f), "type": field_type(f), "origin": "template"})
    for e in item.get("extra", []):
        k = e.get("key")
        if not k or k in seen:
            continue
        seen.add(k)
        if include_empty or not is_empty(values.get(k)):
            out.append({**e, "label": field_label(e), "type": field_type(e), "origin": "extra"})
    for k, v in values.items():
        if k in seen or is_empty(v):
            continue
        d = _lookup_def(cfg, item, k)
        out.append({**d, "key": k, "label": field_label(d), "type": field_type(d), "origin": "leftover"})
    return out


def field_type_of(cfg: dict, item: dict, key: str) -> str:
    tpl = template_for(cfg, item.get("category", ""), item.get("sub", ""))
    for f in tpl["fields"]:
        if f["key"] == key:
            return field_type(f)
    return field_type(_lookup_def(cfg, item, key))


def closed_label(cfg: dict, item: dict) -> str:
    sub = find_sub(cfg, item.get("category", ""), item.get("sub", ""))
    cat = find_category(cfg, item.get("category", ""))
    for obj in (sub, cat):
        if obj and obj.get("closed_label"):
            return obj["closed_label"]
        if obj and obj.get("closed_key"):
            return tr(obj["closed_key"])
    return tr("status.closed_default")


def category_path(cfg: dict, item: dict) -> str:
    cat = find_category(cfg, item.get("category", ""))
    if not cat:
        return tr("cat.unknown")
    sub = find_sub(cfg, cat["id"], item.get("sub", ""))
    return f"{display_name(cat)} ／ {display_name(sub)}" if sub else display_name(cat)


def first_letter(title: str) -> str:
    title = (title or "").strip()
    return title[0].upper() if title else "?"
