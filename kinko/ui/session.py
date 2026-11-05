"""Session services while a vault is open: secure clipboard, auto-lock and scheduled backups."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QMimeData, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication

from ..storage import backup
from .native import MacScreenLock


class SecureClipboard(QObject):
    """Copies text and clears it again after N seconds, unless something else was copied meanwhile."""

    cleared = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._last: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear_if_ours)

    def copy(self, text: str) -> int:
        md = QMimeData()
        md.setText(text)
        if sys.platform == "win32":
            # Keep it out of Windows clipboard history (Win+V) and cloud clipboard.
            fmt = 'application/x-qt-windows-mime;value="{}"'
            md.setData(fmt.format("ExcludeClipboardContentFromMonitorProcessing"), QByteArray(b"\x01\x00\x00\x00"))
            md.setData(fmt.format("CanIncludeInClipboardHistory"), QByteArray(b"\x00\x00\x00\x00"))
            md.setData(fmt.format("CanUploadToCloudClipboard"), QByteArray(b"\x00\x00\x00\x00"))
        QGuiApplication.clipboard().setMimeData(md)
        self._last = text
        secs = int(self.settings["clipboard_seconds"] or 0)
        if secs > 0:
            self._timer.start(secs * 1000)
        else:
            self._timer.stop()
        return secs

    def clear_if_ours(self) -> None:
        self._timer.stop()
        if self._last is None:
            return
        cb = QGuiApplication.clipboard()
        if cb.text() == self._last:
            cb.clear()
        self._last = None
        self.cleared.emit()


class AutoLock(QObject):
    """Locks after idle time, and when the OS screen locks (macOS polling / Windows session events)."""

    lock_now = pyqtSignal(str)
    tick = pyqtSignal(int)  # seconds left, -1 when off

    _ACTIVITY = {QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
                 QEvent.Type.Wheel, QEvent.Type.TouchBegin}

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._last = time.monotonic()
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check)
        self._mac = MacScreenLock() if sys.platform == "darwin" else None

    def start(self) -> None:
        self._last = time.monotonic()
        if not self._active:
            QGuiApplication.instance().installEventFilter(self)
        self._active = True
        self._timer.start()
        self._check()

    def stop(self) -> None:
        if self._active:
            QGuiApplication.instance().removeEventFilter(self)
        self._active = False
        self._timer.stop()

    def poke(self) -> None:
        self._last = time.monotonic()

    def eventFilter(self, obj, ev):  # noqa: N802
        if ev.type() in self._ACTIVITY:
            self._last = time.monotonic()
        return False

    def os_locked(self) -> None:
        if self._active and self.settings["lock_on_os_lock"]:
            self.lock_now.emit("os")

    def _check(self) -> None:
        if not self._active:
            return
        if self._mac and self.settings["lock_on_os_lock"] and self._mac.locked():
            self.lock_now.emit("os")
            return
        minutes = int(self.settings["auto_lock_minutes"] or 0)
        if minutes <= 0:
            self.tick.emit(-1)
            return
        left = int(minutes * 60 - (time.monotonic() - self._last))
        if left <= 0:
            self.lock_now.emit("idle")
            return
        self.tick.emit(left)


class BackupScheduler(QObject):
    """Backs up a few seconds after the last change, then prunes old generations."""

    done = pyqtSignal(object)  # datetime
    failed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.vault = None
        self.last: datetime | None = None
        self._pending = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self.run_now)

    def attach(self, vault) -> None:
        self.vault = vault
        self.last = None
        items = backup.list_backups(vault.path, self.backup_dir())
        if items:
            self.last = items[0][0]

    def detach(self) -> None:
        self.flush()
        self.vault = None

    def backup_dir(self) -> Path:
        return backup.backup_dir_for(self.vault.path, self.settings["backup_dir"])

    def schedule(self) -> None:
        if self.vault is None or not self.settings["backup_enabled"]:
            return
        self._pending = True
        self._timer.start()

    def flush(self) -> None:
        if self._pending:
            self.run_now()

    def run_now(self) -> Path | None:
        self._timer.stop()
        self._pending = False
        if self.vault is None or not self.vault.unlocked:
            return None
        try:
            store = self.vault.store_for_backup()
            dest = backup.make_backup(store, self.vault.path, self.backup_dir())
            backup.prune(self.vault.path, self.backup_dir(), int(self.settings["backup_keep_latest"]),
                         int(self.settings["backup_keep_days"]))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return None
        self.last = datetime.now()
        self.done.emit(self.last)
        return dest
