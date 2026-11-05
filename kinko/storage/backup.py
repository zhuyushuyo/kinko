"""Generational backups: keep the latest N copies plus the newest copy of each of the last D days."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from .store import Store

_STAMP = "%Y%m%d_%H%M%S"


def backup_dir_for(vault_path: Path, configured: str = "") -> Path:
    return Path(configured) if configured else Path(vault_path).parent / "backups"


def _pattern(vault_path: Path) -> re.Pattern:
    stem = re.escape(Path(vault_path).stem)
    suffix = re.escape(Path(vault_path).suffix or ".kinko")
    return re.compile(rf"^{stem}_(\d{{8}}_\d{{6}})(?:_\d+)?{suffix}$")


def make_backup(store: Store, vault_path: Path, backup_dir: Path, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    vault_path = Path(vault_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    base = f"{vault_path.stem}_{now.strftime(_STAMP)}"
    dest = backup_dir / f"{base}{vault_path.suffix}"
    n = 1
    while dest.exists():
        dest = backup_dir / f"{base}_{n}{vault_path.suffix}"
        n += 1
    store.backup_to(dest)
    return dest


def list_backups(vault_path: Path, backup_dir: Path) -> list[tuple[datetime, Path]]:
    pat = _pattern(vault_path)
    out = []
    try:
        entries = list(Path(backup_dir).iterdir())
    except OSError:
        return []
    for p in entries:
        m = pat.match(p.name)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), _STAMP)
        except ValueError:
            continue
        out.append((ts, p))
    out.sort(key=lambda t: (t[0], t[1].name), reverse=True)
    return out


def prune(vault_path: Path, backup_dir: Path, keep_latest: int, keep_days: int,
          now: datetime | None = None) -> list[Path]:
    now = now or datetime.now()
    backups = list_backups(vault_path, backup_dir)
    keep: set[Path] = {p for _, p in backups[:max(keep_latest, 1)]}
    if keep_days > 0:
        since = (now - timedelta(days=keep_days)).date()
        seen_days: set = set()
        for ts, p in backups:  # newest first
            d = ts.date()
            if d >= since and d not in seen_days:
                seen_days.add(d)
                keep.add(p)
    removed = []
    for _, p in backups:
        if p not in keep:
            try:
                p.unlink()
                removed.append(p)
            except OSError:
                pass
    return removed
