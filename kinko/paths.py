"""Where KINKO keeps things: app settings on this PC, vaults on Google Drive."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Folder that holds main.py (…/KINKO/Ver1.0.0 on Drive).
APP_DIR = Path(__file__).resolve().parent.parent

DRIVE_ROOT_NAMES = ("マイドライブ", "My Drive")


def config_dir() -> Path:
    """Per-PC settings folder (never inside the app folder, see B8)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "KINKO"


def drive_roots() -> list[Path]:
    """Google Drive for desktop "My Drive" folders found on this PC."""
    roots: list[Path] = []
    if sys.platform == "darwin":
        cloud = Path.home() / "Library" / "CloudStorage"
        try:
            accounts = sorted(cloud.glob("GoogleDrive-*"))
        except OSError:
            accounts = []
        candidates = [acc / n for acc in accounts for n in DRIVE_ROOT_NAMES]
        candidates += [Path("/Volumes/GoogleDrive") / n for n in DRIVE_ROOT_NAMES]
    elif sys.platform == "win32":
        candidates = [Path(f"{d}:\\") / n for d in "GHIJKLMNOPQRSTUVWXYZDEF" for n in DRIVE_ROOT_NAMES]
    else:
        candidates = [Path.home() / n for n in DRIVE_ROOT_NAMES]
    for c in candidates:
        try:
            if c.is_dir():
                roots.append(c)
        except OSError:
            pass
    return roots


def app_development_root(start: Path | None = None) -> Path | None:
    """The "App Development" folder: above the app itself, or inside My Drive."""
    start = start or APP_DIR
    for p in (start, *start.parents):
        if p.name == "App Development":
            return p
    for root in drive_roots():
        cand = root / "App Development"
        if cand.is_dir():
            return cand
    return None


def default_vault_dir() -> Path:
    """My Drive/App Development/AppData/KINKO, or ~/Documents/KINKO as a fallback."""
    root = app_development_root()
    if root is not None:
        return root / "AppData" / "KINKO"
    return Path.home() / "Documents" / "KINKO"


def find_v2_databases(limit: int = 8) -> list[Path]:
    """Account Manager (Ver2) accounts.db files under App Development, newest first."""
    root = app_development_root()
    if root is None:
        return []
    patterns = (
        "*/*/Personal/Tools/Acc*unt Manager/**/accounts.db",
        "*/*/Personal/Acc*unt Manager/**/accounts.db",
    )
    found: dict[str, Path] = {}
    for pattern in patterns:
        try:
            for p in root.glob(pattern):
                if "backups" not in p.parts:
                    found[str(p)] = p
        except OSError:
            continue

    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    return sorted(found.values(), key=mtime, reverse=True)[:limit]


def reveal_in_file_manager(path: Path) -> None:
    """Show a file in Finder / Explorer."""
    import subprocess

    path = Path(path)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)] if path.exists() else ["open", str(path.parent)])
        elif sys.platform == "win32":
            if path.exists():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass
