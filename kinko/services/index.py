"""Derived facts about the unlocked items: search text, strength, reuse, issues, counts."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ..core.model import (category_path, closed_label, display_name, find_category, find_sub, item_fields,
                          parse_iso)
from .search import matches, normalize, tokens
from .strength import Strength, estimate

OLD_DAYS = 365


class Index:
    def __init__(self, vault):
        self.vault = vault
        cfg = vault.config
        self.search_text: dict[str, str] = {}
        self.strength: dict[str, Strength] = {}
        self.reused: dict[str, int] = {}
        self.issues: dict[str, list[str]] = {}
        self.tags: Counter = Counter()
        self.cat_counts: Counter = Counter()
        self.sub_counts: Counter = Counter()
        self.fav_count = 0
        self.trash_count = 0
        self.active_count = 0
        self.closed_count = 0
        self.total = 0

        by_pw: dict[str, list[str]] = defaultdict(list)
        now = datetime.now().astimezone()
        for iid, rec in vault.items.items():
            d = rec.data
            if rec.trashed:
                self.trash_count += 1
                continue
            self.total += 1
            self.cat_counts[d["category"]] += 1
            if d.get("sub"):
                self.sub_counts[(d["category"], d["sub"])] += 1
            if d.get("favorite"):
                self.fav_count += 1
            for t in d.get("tags", []):
                self.tags[t] += 1
            if d["status"] == "closed":
                self.closed_count += 1
            else:
                self.active_count += 1
            pw = d["fields"].get("password") or ""
            if pw:
                self.strength[iid] = estimate(pw)
                if d["status"] == "active":
                    by_pw[pw].append(iid)
            parts = [d.get("title", ""), category_path(cfg, d), " ".join(d.get("tags", []))]
            for f in item_fields(cfg, d):
                if f["type"] in ("text", "email", "url", "multiline", "date", "number"):
                    parts.append(str(d["fields"].get(f["key"], "")))
                elif f["type"] == "qa":
                    parts.extend(q.get("q", "") for q in d["fields"].get(f["key"], []) if isinstance(q, dict))
                elif f["type"] == "twofa":
                    parts.append((d["fields"].get(f["key"]) or {}).get("app", ""))
            if d["status"] == "closed":
                parts.append(closed_label(cfg, d))
            self.search_text[iid] = normalize(" ".join(parts))

        for ids in by_pw.values():
            if len(ids) > 1:
                for iid in ids:
                    self.reused[iid] = len(ids) - 1

        limit = now - timedelta(days=OLD_DAYS)
        for iid, rec in vault.items.items():
            d = rec.data
            if rec.trashed or d["status"] != "active":
                continue
            found = []
            if iid in self.reused:
                found.append("reused")
            st = self.strength.get(iid)
            if st is not None and st.score <= 1:
                found.append("weak")
            changed = parse_iso(d.get("pw_changed_at") or rec.created_at)
            if d["fields"].get("password") and changed and changed < limit:
                found.append("old")
            if d["category"] == "finance" and not (d["fields"].get("twofa") or {}).get("on"):
                found.append("no2fa")
            if found:
                self.issues[iid] = found

    # ---------------------------------------------------------------- queries
    def ids_for(self, spec: tuple, status: str = "all", query: str = "") -> list[str]:
        vault = self.vault
        toks = tokens(query)
        out = []
        kind = spec[0] if spec else "all"
        for iid, rec in vault.items.items():
            d = rec.data
            if kind == "trash":
                if not rec.trashed:
                    continue
            elif rec.trashed:
                continue
            if toks:
                if not matches(self.search_text.get(iid, normalize(d.get("title", ""))), toks):
                    continue
            elif kind == "fav" and not d.get("favorite"):
                continue
            elif kind == "recent" and not rec.used_at:
                continue
            elif kind == "cat" and d["category"] != spec[1]:
                continue
            elif kind == "sub" and (d["category"] != spec[1] or d.get("sub") != spec[2]):
                continue
            elif kind == "tag" and spec[1] not in d.get("tags", []):
                continue
            elif kind == "health" and iid not in self.issues:
                continue
            if status == "active" and d["status"] != "active":
                continue
            if status == "closed" and d["status"] != "closed":
                continue
            out.append(iid)
        return out

    def sort(self, ids: list[str], mode: str) -> list[str]:
        items = self.vault.items

        def name_key(i):
            return normalize(items[i].data.get("title", ""))

        if mode == "name":
            return sorted(ids, key=name_key)
        if mode == "updated":
            return sorted(sorted(ids, key=name_key), key=lambda i: items[i].updated_at or "", reverse=True)
        return sorted(sorted(ids, key=name_key), key=lambda i: items[i].used_at or "", reverse=True)

    def subtitle(self, iid: str, mode: str) -> str:
        d = self.vault.items[iid].data
        f = d["fields"]
        if mode == "none":
            return ""
        if mode == "email":
            return f.get("email") or f.get("username") or ""
        if mode == "url":
            return f.get("url") or ""
        if f.get("username"):
            return f["username"]
        if f.get("email"):
            return f["email"]
        cfg = self.vault.config
        sub = find_sub(cfg, d["category"], d.get("sub", ""))
        cat = find_category(cfg, d["category"])
        return display_name(sub) if sub else (display_name(cat) if cat else "")
