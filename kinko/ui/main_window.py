"""Main window: welcome / lock screen / three-pane vault view, plus shortcuts, auto-lock and backups."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                             QSplitter, QStackedWidget, QWidget)

from .. import VAULT_SUFFIX
from ..core.model import same_service_item
from ..core.vault import NotAVault, Vault, VaultChanged, VaultLocked, WrongPassword, restore_from_backup
from ..i18n import set_language, tr
from ..paths import find_v2_databases, reveal_in_file_manager
from ..services.index import Index
from ..settings import DEFAULT_SHORTCUTS
from . import icons, native, theme
from .history_dialog import HistoryDialog
from .item_detail import DetailView, EmptyDetail
from .item_editor import EditorView
from .item_list import ListPane
from .lock_screen import LockScreen, WelcomeScreen, vault_menu
from .session import AutoLock, BackupScheduler, SecureClipboard
from .settings_dialog import SettingsDialog
from .sidebar import Sidebar
from .widgets import ClickableLabel, Toast
from .wizards import (ChangePasswordDialog, RecoveryKeyDialog, RecoveryUnlockDialog, VaultWizard, busy)

_MAC = sys.platform == "darwin"


class VaultView(QWidget):
    """Sidebar | list | detail-or-editor for an unlocked vault."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.vault = main.vault
        self.settings = main.settings
        self.index = Index(self.vault)
        self.editing = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.sidebar = Sidebar(self.settings)
        self.sidebar.setMinimumWidth(200)
        self.sidebar.set_refresher(self.refresh)
        self.list = ListPane(self.settings, main.passthrough_sequences())
        self.list.setMinimumWidth(300)
        self.detail_stack = QStackedWidget()
        self.detail_stack.setObjectName("DetailPane")
        self.empty = EmptyDetail()
        self.detail = DetailView(self.settings, lambda: int(self.settings["trash_days"]))
        self.editor = EditorView(self.settings)
        for w in (self.empty, self.detail, self.editor):
            self.detail_stack.addWidget(w)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.list)
        self.splitter.addWidget(self.detail_stack)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([228, 372, 680])
        state = self.settings["splitter_state"]
        if state:
            self.splitter.restoreState(QByteArray.fromBase64(state.encode()))
        self.splitter.splitterMoved.connect(self._save_splitter)
        lay.addWidget(self.splitter)

        self.sidebar.filter_changed.connect(self._filter_changed)
        self.sidebar.settings_requested.connect(main.open_settings)
        self.sidebar.lock_requested.connect(lambda: main.lock("manual"))
        self.sidebar.vault_menu_requested.connect(main.show_vault_menu)
        self.list.current_changed.connect(self._current_changed)
        self.list.copy_requested.connect(self.copy_quick)
        self.list.new_requested.connect(self.new_item)
        self.list.edit_requested.connect(self.edit_item)
        d = self.detail
        d.edit_requested.connect(self.edit_item)
        d.favorite_toggled.connect(self.set_favorite)
        d.trash_requested.connect(self.trash_item)
        d.restore_requested.connect(self.restore_item)
        d.purge_requested.connect(self.purge_item)
        d.duplicate_requested.connect(self.add_same_service)
        d.new_requested.connect(self.new_item)
        d.copy_requested.connect(self.copy_field)
        d.open_url_requested.connect(self.open_url)
        d.history_requested.connect(self.show_history)
        self.editor.saved.connect(self.save_item)
        self.editor.cancelled.connect(self.cancel_edit)
        self._shown: str | None = None

        self.sidebar.refresh(self.vault, self.index)
        self.list.set_vault(self.vault, self.index)
        self.list.set_spec(self.sidebar.spec)

    def _save_splitter(self, *_):
        self.settings.set("splitter_state", bytes(self.splitter.saveState().toBase64()).decode())

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> None:
        self.index = Index(self.vault)
        self.sidebar.refresh(self.vault, self.index)
        self.list.set_vault(self.vault, self.index)
        self.list.spec = self.sidebar.spec
        keep = self.list.current_id()
        self.list.reload(keep=keep)
        if not self.editing and self._shown and self._shown in self.vault.items:
            self.detail.show_item(self.vault, self.index, self._shown)

    def refresh_light(self) -> None:
        """Only "last used" changed: re-sort the list, keep the detail pane as it is."""
        self.index = Index(self.vault)
        self.list.set_vault(self.vault, self.index)
        self.list.blockSignals(True)
        self.list.view.selectionModel().blockSignals(True)
        try:
            self.list.reload(keep=self._shown)
        finally:
            self.list.view.selectionModel().blockSignals(False)
            self.list.blockSignals(False)

    def _filter_changed(self, spec: tuple) -> None:
        if self.editing and not self._leave_editor():
            self.sidebar._select_spec(self.list.spec, emit=False)
            return
        self.list.set_spec(spec)

    def _current_changed(self, iid) -> None:
        if self.editing:
            if iid == self.editor.iid:
                return
            if not self._leave_editor():
                if self.editor.iid:
                    self.list.view.blockSignals(True)
                    self.list.select_id(self.editor.iid)
                    self.list.view.blockSignals(False)
                return
        self.show(iid)

    def show(self, iid) -> None:
        self._shown = iid
        if iid and iid in self.vault.items:
            self.detail.show_item(self.vault, self.index, iid)
            self.detail_stack.setCurrentWidget(self.detail)
        else:
            self.detail_stack.setCurrentWidget(self.empty)

    def current_id(self) -> str | None:
        return self._shown

    def _leave_editor(self) -> bool:
        """True when it is OK to leave the editor (saved or discarded)."""
        if not self.editor.is_dirty():
            self._set_editing(False)
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("editor.cancel_title"))
        box.setText(tr("editor.leave_prompt"))
        save = box.addButton(tr("editor.save"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("editor.discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is save:
            data = self.editor.collect()
            if not data["title"]:
                return False
            return self._do_save(self.editor.iid, data, select=False)
        if box.clickedButton() is discard:
            self._set_editing(False)
            return True
        return False

    def _set_editing(self, editing: bool) -> None:
        self.editing = editing
        self.main.update_actions()

    # ---------------------------------------------------------------- edit
    def new_item(self) -> None:
        if self.editing and not self._leave_editor():
            return
        spec = self.sidebar.spec
        preset = None
        if spec[0] == "cat":
            preset = (spec[1], "")
        elif spec[0] == "sub":
            preset = (spec[1], spec[2])
        self.editor.start(self.vault, self.index, None, preset)
        self.detail_stack.setCurrentWidget(self.editor)
        self._set_editing(True)

    def edit_item(self, iid: str | None = None) -> None:
        iid = iid or self._shown
        if not iid or iid not in self.vault.items or self.vault.items[iid].trashed:
            return
        if self.editing and iid != self.editor.iid and not self._leave_editor():
            return
        self.editor.start(self.vault, self.index, self.vault.items[iid])
        self.detail_stack.setCurrentWidget(self.editor)
        self._set_editing(True)

    def add_same_service(self, iid: str) -> None:
        """A new account for the same service: name, category, URL and tags carried over, no ID or password."""
        if self.editing and not self._leave_editor():
            return
        data = same_service_item(self.vault.items[iid].data)
        self.editor.start(self.vault, self.index, None, template_data=data)
        self.detail_stack.setCurrentWidget(self.editor)
        self._set_editing(True)

    def save_item(self, iid, data: dict) -> None:
        self._do_save(iid, data, select=True)

    def _do_save(self, iid, data: dict, select: bool) -> bool:
        try:
            if iid:
                self.vault.update_item(iid, data)
            else:
                iid = self.vault.add_item(data)
        except VaultChanged:
            self.main.toast.show_message(tr("toast.reloaded_retry"), ms=7000)
            return False
        except VaultLocked:
            return False
        self.editor.mark_saved()
        self._set_editing(False)
        self.refresh()
        if select:
            self.list.select_id(iid)
            self.show(iid)
        self.main.toast.show_message(tr("toast.saved"))
        return True

    def cancel_edit(self) -> None:
        self._set_editing(False)
        self.show(self.list.current_id())

    # ---------------------------------------------------------------- actions
    def _guard(self, fn, *args) -> None:
        try:
            fn(*args)
        except VaultChanged:
            self.main.toast.show_message(tr("toast.reloaded"), ms=6000)
            self.refresh()

    def set_favorite(self, iid: str, value: bool) -> None:
        self._guard(self.vault.set_favorite, iid, value)

    def trash_item(self, iid: str | None = None) -> None:
        iid = iid or self._shown
        if not iid or self.editing or iid not in self.vault.items or self.vault.items[iid].trashed:
            return
        title = self.vault.items[iid].data.get("title", "")
        self._guard(self.vault.trash_item, iid)
        self.main.toast.show_message(tr("toast.trashed", title=title), tr("toast.undo"),
                                     lambda: self._guard(self.vault.restore_item, iid), ms=6000)

    def restore_item(self, iid: str) -> None:
        self._guard(self.vault.restore_item, iid)
        self.main.toast.show_message(tr("toast.restored"))

    def purge_item(self, iid: str) -> None:
        title = self.vault.items[iid].data.get("title", "")
        if QMessageBox.question(self, tr("detail.purge"), tr("detail.purge_confirm", title=title)) \
                == QMessageBox.StandardButton.Yes:
            self._guard(self.vault.purge_item, iid)

    def copy_value(self, iid: str, value: str, what: str) -> int:
        secs = self.main.clipboard.copy(value)
        self.vault.mark_used(iid)
        msg = tr("toast.copied_clear", what=what, s=secs) if secs > 0 else tr("toast.copied", what=what)
        self.main.toast.show_message(msg)
        return secs

    def copy_field(self, iid: str, key: str, value: str, lab: str) -> None:
        secs = self.copy_value(iid, value, lab)
        self.detail.mark_copied(key, secs)

    def copy_quick(self, iid: str, which: str) -> None:
        f = self.vault.items[iid].data["fields"]
        if which == "password":
            if not f.get("password"):
                self.main.toast.show_message(tr("toast.no_password"))
                return
            self.copy_value(iid, f["password"], tr("field.password"))
            if iid == self._shown:
                self.detail.mark_copied("password", int(self.settings["clipboard_seconds"]))
        else:
            value = f.get("username") or f.get("email")
            if not value:
                self.main.toast.show_message(tr("toast.no_username"))
                return
            key = "username" if f.get("username") else "email"
            self.copy_value(iid, value, tr("field.username"))
            if iid == self._shown:
                self.detail.mark_copied(key, int(self.settings["clipboard_seconds"]))

    def open_url(self, iid: str, url: str = "") -> None:
        url = url or self.vault.items[iid].data["fields"].get("url", "")
        if not url:
            self.main.toast.show_message(tr("toast.no_url"))
            return
        if "://" not in url:
            url = "https://" + url
        QDesktopServices.openUrl(QUrl(url))
        self.vault.mark_used(iid)

    def show_history(self, iid: str) -> None:
        HistoryDialog(self, self.vault, iid, lambda v, n: self.copy_value(iid, v, n)).exec()

    def focus_search(self) -> None:
        if self.editing and not self._leave_editor():
            return
        if self.sidebar.spec == ("trash",):
            self.sidebar.select(("all",))
        self.list.focus_search()


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.vault: Vault | None = None
        self.view: VaultView | None = None
        self._discarded_edit = False
        self._refresh_pending = False
        self._refresh_full = False
        self.setWindowTitle("KINKO")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(980, 640)
        self.resize(1280, 800)
        geo = settings["window_geometry"]
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.toast = Toast(self)
        self.clipboard = SecureClipboard(settings, self)
        self.autolock = AutoLock(settings, self)
        self.autolock.lock_now.connect(self.lock)
        self.autolock.tick.connect(self._tick)
        self.backups = BackupScheduler(settings, self)
        self.backups.done.connect(self._backup_done)
        self.backups.failed.connect(lambda e: self.toast.show_message(tr("toast.backup_failed", error=e), ms=8000))
        self._build_status()
        self._build_actions()
        QApplication.instance().applicationStateChanged.connect(self._app_state)
        self._win_filter = native.make_windows_lock_filter(lambda: self.autolock.os_locked())
        if self._win_filter is not None:
            QApplication.instance().installNativeEventFilter(self._win_filter)
        QTimer.singleShot(0, self._start)

    # ---------------------------------------------------------------- chrome
    def _build_status(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        left = QWidget()
        ll = QHBoxLayout(left)
        ll.setContentsMargins(10, 0, 0, 0)
        ll.setSpacing(6)
        self.st_icon = QLabel()
        ll.addWidget(self.st_icon)
        self.st_name = QLabel()
        f = self.st_name.font()
        f.setBold(True)
        self.st_name.setFont(f)
        ll.addWidget(self.st_name)
        self.st_path = ClickableLabel()
        self.st_path.setProperty("role", "faint")
        self.st_path.clicked.connect(lambda: self.vault and reveal_in_file_manager(self.vault.path))
        ll.addWidget(self.st_path)
        ll.addStretch(1)
        sb.addWidget(left, 1)
        self.st_lock = QLabel()
        self.st_backup = QLabel()
        sb.addPermanentWidget(self.st_lock)
        sb.addPermanentWidget(self.st_backup)
        sb.setVisible(False)

    def _update_status(self) -> None:
        v = self.vault
        if not v or not v.unlocked:
            self.statusBar().setVisible(False)
            return
        self.statusBar().setVisible(True)
        self.st_icon.setPixmap(icons.pixmap("lock", theme.t("ink2"), 13))
        self.st_name.setText(v.name)
        p = str(v.path)
        self.st_path.setText(self.st_path.fontMetrics().elidedText(p, Qt.TextElideMode.ElideMiddle, 420))
        self.st_path.setToolTip(tr("status.reveal", path=p))
        self._backup_done(self.backups.last)

    def _tick(self, left: int) -> None:
        if left < 0:
            self.st_lock.setText(tr("status.autolock_off") + "   ")
        else:
            self.st_lock.setText(tr("status.autolock", t=f"{left // 60}:{left % 60:02d}") + "   ")

    def _backup_done(self, when) -> None:
        if when is None:
            self.st_backup.setText(tr("status.no_backup") + "  ")
        else:
            self.st_backup.setText(tr("status.backup", t=when.strftime("%H:%M" if when.date() == when.today().date()
                                                                       else "%m/%d %H:%M")) + "  ")

    def _build_actions(self) -> None:
        self.actions_by_name: dict[str, QAction] = {}

        def act(name, slot, text_key):
            a = QAction(tr(text_key), self)
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            a.triggered.connect(slot)
            self.addAction(a)
            self.actions_by_name[name] = a
            return a

        act("search", lambda: self.view and self.view.focus_search(), "sc.search")
        act("new_item", lambda: self.view and self.view.new_item(), "sc.new_item")
        act("edit_item", lambda: self.view and self.view.edit_item(), "sc.edit_item")
        act("save_item", lambda: self.view and self.view.editing and self.view.editor.save(), "sc.save_item")
        act("copy_password", lambda: self._copy_current("password"), "sc.copy_password")
        act("copy_username", lambda: self._copy_current("username"), "sc.copy_username")
        act("open_url", lambda: self.view and self.view.current_id() and self.view.open_url(self.view.current_id()),
            "sc.open_url")
        act("favorite", self._toggle_favorite, "sc.favorite")
        act("trash_item", lambda: self.view and self.view.trash_item(), "sc.trash_item")
        act("lock", lambda: self.lock("manual"), "sc.lock")
        settings_action = act("settings", lambda: self.open_settings(), "sc.settings")
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.esc_action = QAction(self)
        self.esc_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        self.esc_action.triggered.connect(lambda: self.view and self.view.editing and self.view.editor.cancel())
        self.addAction(self.esc_action)
        if _MAC:
            self._build_mac_menu()
        self.apply_shortcuts()
        self.update_actions()

    def _build_mac_menu(self) -> None:
        mb = self.menuBar()
        mb.clear()
        a = self.actions_by_name
        file_m = mb.addMenu(tr("menu.file"))
        file_m.addAction(a["new_item"])
        file_m.addSeparator()
        file_m.addAction(tr("menu.open_vault"), self.open_vault_dialog)
        file_m.addAction(tr("menu.create_vault"), lambda: self.run_wizard("create"))
        file_m.addAction(tr("menu.migrate"), lambda: self.run_wizard("migrate"))
        file_m.addSeparator()
        file_m.addAction(a["lock"])
        file_m.addAction(a["settings"])
        edit_m = mb.addMenu(tr("menu.edit"))
        for name in ("copy_password", "copy_username", "open_url", "edit_item", "save_item", "favorite", "trash_item"):
            edit_m.addAction(a[name])
        view_m = mb.addMenu(tr("menu.view"))
        view_m.addAction(a["search"])

    def passthrough_sequences(self) -> list[QKeySequence]:
        sc = dict(DEFAULT_SHORTCUTS)
        sc.update(self.settings["shortcuts"])
        return [QKeySequence(sc["copy_password"]), QKeySequence(sc["copy_username"])]

    def apply_shortcuts(self) -> None:
        sc = dict(DEFAULT_SHORTCUTS)
        sc.update(self.settings["shortcuts"])
        for name, a in self.actions_by_name.items():
            a.setShortcut(QKeySequence(sc.get(name, "")))
        if self.view is not None:
            self.view.list.search.passthrough = self.passthrough_sequences()
            self.view.list.view.passthrough = self.passthrough_sequences()

    def update_actions(self) -> None:
        unlocked = bool(self.vault and self.vault.unlocked and self.view)
        editing = bool(self.view and self.view.editing)
        self.esc_action.setEnabled(unlocked and editing)
        for name, a in self.actions_by_name.items():
            if name == "settings":
                a.setEnabled(True)
            elif name == "save_item":
                a.setEnabled(unlocked and editing)
            elif name in ("new_item", "search", "lock"):
                a.setEnabled(unlocked)
            else:
                a.setEnabled(unlocked and not editing)

    def _copy_current(self, which: str) -> None:
        if not self.view or self.view.editing:
            return
        iid = self.view.current_id()
        if iid and iid in self.vault.items and not self.vault.items[iid].trashed:
            self.view.copy_quick(iid, which)

    def _toggle_favorite(self) -> None:
        if self.view and not self.view.editing:
            iid = self.view.current_id()
            if iid and iid in self.vault.items:
                self.view.set_favorite(iid, not self.vault.items[iid].data.get("favorite"))

    # ---------------------------------------------------------------- pages
    def _set_page(self, w: QWidget) -> None:
        old = self.stack.currentWidget()
        self.stack.addWidget(w)
        self.stack.setCurrentWidget(w)
        if old is not None and old is not w:
            self.stack.removeWidget(old)
            old.deleteLater()

    def _start(self) -> None:
        last = self.settings["last_vault"]
        if self.settings["open_last_vault"] and last and Path(last).is_file():
            self.open_vault(last)
        else:
            self.show_welcome()

    def show_welcome(self) -> None:
        self.vault = None
        self.view = None
        self.setWindowTitle("KINKO")
        self._update_status()
        w = WelcomeScreen(self.settings["recent_vaults"], bool(find_v2_databases(1)))
        w.create_requested.connect(lambda: self.run_wizard("create"))
        w.migrate_requested.connect(lambda: self.run_wizard("migrate"))
        w.open_requested.connect(self.open_vault_dialog)
        w.recent_requested.connect(self.open_vault)
        self._set_page(w)
        self.update_actions()

    def open_vault(self, path: str) -> None:
        if self.vault and self.vault.unlocked:
            self.lock("switch")
        try:
            v = Vault(path)
        except NotAVault:
            QMessageBox.warning(self, tr("open.title"), tr("open.not_vault", path=path))
            if not self.vault:
                self.show_welcome()
            return
        self.vault = v
        self.settings.remember_vault(str(v.path))
        self.show_lock()

    def open_vault_dialog(self) -> None:
        start = self.settings["vault_dir"] or (str(self.vault.path.parent) if self.vault else str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, tr("open.title"), start, f"KINKO (*{VAULT_SUFFIX});;* (*)")
        if path:
            self.open_vault(path)

    def show_lock(self) -> None:
        self.view = None
        self.setWindowTitle("KINKO")
        lock = LockScreen()
        lock.set_vault(self.vault.name, self.vault.path, self.vault.hint)
        lock.unlock_requested.connect(self.unlock)
        lock.recovery_requested.connect(self.recover)
        lock.switch_requested.connect(lambda: self.show_vault_menu(lock.vault_path))
        self.lock_screen = lock
        self._set_page(lock)
        self._update_status()
        self.update_actions()
        lock.focus()

    def show_vault_menu(self, anchor: QWidget) -> None:
        m = vault_menu(self, self.settings["recent_vaults"], str(self.vault.path) if self.vault else "",
                       self.open_vault, self.open_vault_dialog, lambda: self.run_wizard("create"),
                       lambda: self.run_wizard("migrate"))
        m.exec(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)))

    def unlock(self, password: str) -> None:
        lock = self.lock_screen
        lock.set_busy(True)
        try:
            with busy():
                self.vault.reload_meta()
                self.vault.unlock(password)
        except WrongPassword:
            lock.set_busy(False)
            lock.show_error(tr("lock.wrong"))
            return
        except NotAVault:
            lock.set_busy(False)
            lock.show_error(tr("open.not_vault", path=self.vault.path))
            return
        lock.set_busy(False)
        self._after_unlock()

    def recover(self) -> None:
        dlg = RecoveryUnlockDialog(self, self.vault)
        if dlg.exec() and self.vault.unlocked:
            self._after_unlock()
            self.toast.show_message(tr("toast.recovered"), ms=7000)

    def _after_unlock(self) -> None:
        v = self.vault
        try:
            n = v.purge_expired(int(self.settings["trash_days"]))
        except VaultChanged:
            n = 0
        self.settings.remember_vault(str(v.path))
        v.listeners.append(self._vault_changed)
        self.backups.attach(v)
        self.autolock.start()
        self.view = VaultView(self)
        self._set_page(self.view)
        self.setWindowTitle(f"KINKO ― {v.name}")
        self._update_status()
        self.update_actions()
        native.register_windows_session_events(self)
        if self._discarded_edit:
            self.toast.show_message(tr("toast.edit_discarded"), ms=7000)
            self._discarded_edit = False
        elif n:
            self.toast.show_message(tr("toast.trash_purged", n=n))
        if v.broken:
            QMessageBox.warning(self, tr("open.title"), tr("open.broken", n=len(v.broken)))
        QTimer.singleShot(0, self.view.list.focus_search)

    def lock(self, reason: str = "manual") -> None:
        v = self.vault
        if not v or not v.unlocked:
            return
        if self.view is not None and self.view.editing and self.view.editor.is_dirty():
            if reason in ("manual", "switch"):
                if not self.view._leave_editor():
                    return
            else:
                self._discarded_edit = True
        QApplication.activeModalWidget() and QApplication.activeModalWidget().close()
        self.clipboard.clear_if_ours()
        self.backups.detach()
        self.autolock.stop()
        if self._vault_changed in v.listeners:
            v.listeners.remove(self._vault_changed)
        v.lock()
        self.show_lock()

    def _vault_changed(self, kind: str) -> None:
        if kind in ("items", "config", "meta", "reload"):
            self.backups.schedule()
        if kind == "meta":
            self.setWindowTitle(f"KINKO ― {self.vault.name}")
            self._update_status()
        if kind != "used":
            self._refresh_full = True
        if not self._refresh_pending:
            self._refresh_pending = True
            QTimer.singleShot(0, self._do_refresh)

    def _do_refresh(self) -> None:
        self._refresh_pending = False
        full, self._refresh_full = self._refresh_full, False
        if self.view is not None and self.vault and self.vault.unlocked:
            if full:
                self.view.refresh()
            else:
                self.view.refresh_light()

    # ---------------------------------------------------------------- wizards & dialogs
    def run_wizard(self, mode: str) -> None:
        previous = self.vault
        if previous and previous.unlocked:
            self.lock("switch")
            if previous.unlocked:
                return
        wiz = VaultWizard(self, self.settings, mode)
        wiz.exec()
        if wiz.vault is not None:
            self.vault = wiz.vault
            self._after_unlock()
            if wiz.report is not None:
                self.toast.show_message(tr("toast.migrated", n=wiz.report.imported), ms=7000)
        elif previous is None:
            self.show_welcome()

    def open_settings(self, page: int = 0) -> None:
        dlg = SettingsDialog(self, page)
        dlg.reopen.connect(lambda p: (dlg.done(0), QTimer.singleShot(0, lambda: self.open_settings(p))))
        dlg.exec()

    def change_password(self) -> None:
        if self.vault and self.vault.unlocked and ChangePasswordDialog(self.activeModal(), self.vault).exec():
            self.toast.show_message(tr("toast.password_changed"), ms=6000)

    def regenerate_recovery(self) -> None:
        if not (self.vault and self.vault.unlocked):
            return
        parent = self.activeModal()
        if QMessageBox.question(parent, tr("recovery.new_title"), tr("recovery.regenerate_confirm")) \
                != QMessageBox.StandardButton.Yes:
            return
        key = self.vault.regenerate_recovery_key()
        RecoveryKeyDialog(parent, self.vault, key).exec()

    def restore_backup(self) -> None:
        if not (self.vault and self.vault.unlocked):
            return
        parent = self.activeModal()
        bdir = self.backups.backup_dir()
        path, _ = QFileDialog.getOpenFileName(parent, tr("restore.title"), str(bdir), f"KINKO (*{VAULT_SUFFIX})")
        if not path:
            return
        if QMessageBox.question(parent, tr("restore.title"), tr("restore.confirm", name=Path(path).name)) \
                != QMessageBox.StandardButton.Yes:
            return
        vault_path = self.vault.path
        if parent is not self:
            parent.close()
        self.lock("switch")
        if self.vault.unlocked:
            return
        try:
            safety = restore_from_backup(vault_path, Path(path), bdir)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("restore.title"), tr("restore.failed", error=exc))
            return
        self.open_vault(str(vault_path))
        self.toast.show_message(tr("restore.done", name=safety.name), ms=9000)

    def activeModal(self) -> QWidget:
        return QApplication.activeModalWidget() or self

    # ---------------------------------------------------------------- appearance
    def apply_appearance(self) -> None:
        theme.apply(QApplication.instance(), self.settings)
        self._apply_title_bar()
        self._rebuild_page()

    def _apply_title_bar(self) -> None:
        mode = self.settings["theme"]
        if mode == "system" and not getattr(self, "_title_forced", False):
            return  # the OS already matches; only touch it after an explicit choice
        self._title_forced = mode != "system"
        native.set_dark_title_bar(self, None if mode == "system" else mode == "dark")

    def apply_language(self) -> None:
        set_language(self.settings["language"])
        for name, a in self.actions_by_name.items():
            a.setText(tr(f"sc.{name}"))
        if _MAC:
            self._build_mac_menu()
        self._rebuild_page()

    def refresh_views(self, rebuild: bool = False) -> None:
        if self.view is not None:
            if rebuild:
                self._rebuild_page()
            else:
                self.view.refresh()

    def _rebuild_page(self) -> None:
        if self.vault and self.vault.unlocked and self.view is not None:
            spec = self.view.sidebar.spec
            current = self.view.current_id()
            editing = self.view.editing and self.view.editor.is_dirty()
            if editing:
                self.view.refresh()
                return
            self.view = VaultView(self)
            self._set_page(self.view)
            self.view.sidebar.select(spec)
            if current:
                self.view.list.select_id(current)
            self._update_status()
        elif self.vault is not None:
            self.show_lock()
        else:
            self.show_welcome()
        self.update_actions()

    # ---------------------------------------------------------------- window events
    def changeEvent(self, e):  # noqa: N802
        if e.type() == QEvent.Type.WindowStateChange and self.isMinimized() and self.settings["lock_on_minimize"]:
            QTimer.singleShot(0, lambda: self.lock("minimize"))
        super().changeEvent(e)

    def _app_state(self, state) -> None:
        if state != Qt.ApplicationState.ApplicationActive and self.settings["lock_on_app_switch"]:
            if QApplication.activeModalWidget() is None:
                self.lock("app_switch")
        if state == Qt.ApplicationState.ApplicationHidden and self.settings["lock_on_minimize"]:
            self.lock("hidden")

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.reposition()

    def showEvent(self, e):  # noqa: N802
        super().showEvent(e)
        self._apply_title_bar()

    def closeEvent(self, e):  # noqa: N802
        if self.view is not None and self.view.editing and self.view.editor.is_dirty():
            if not self.view._leave_editor():
                e.ignore()
                return
        self.settings.set("window_geometry", bytes(self.saveGeometry().toBase64()).decode())
        if self.vault and self.vault.unlocked:
            self.clipboard.clear_if_ours()
            self.backups.detach()
            self.autolock.stop()
            self.vault.lock()
        super().closeEvent(e)
