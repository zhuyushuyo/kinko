"""Create a vault, migrate from Account Manager Ver2, recovery key, password change dialogs."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QStackedWidget,
                             QVBoxLayout, QWidget)

from .. import VAULT_SUFFIX
from ..core.vault import Vault, WrongPassword
from ..i18n import tr
from ..paths import default_vault_dir, find_v2_databases
from ..services.strength import estimate
from ..storage import migrate_v2
from . import emergency_kit, theme
from .widgets import Banner, SecretEdit, StrengthMeter, button, hline, label


class busy:
    def __enter__(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

    def __exit__(self, *exc):
        QApplication.restoreOverrideCursor()


def save_emergency_kit(parent, vault_name: str, vault_path: Path, vault_id: str, key: str) -> bool:
    desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation) or str(Path.home())
    stamp = datetime.now().strftime("%Y%m%d")
    default = str(Path(desktop) / f"KINKO_{tr('kit.file')}_{stamp}.pdf")
    path, _ = QFileDialog.getSaveFileName(parent, tr("kit.save_title"), default, "PDF (*.pdf)")
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    try:
        emergency_kit.save_pdf(path, vault_name, str(vault_path), vault_id, key)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(parent, tr("kit.save_title"), tr("kit.save_failed", error=exc))
        return False
    box = QMessageBox(parent)
    box.setWindowTitle(tr("kit.save_title"))
    box.setText(tr("kit.saved"))
    box.setInformativeText(tr("kit.saved_note"))
    open_btn = box.addButton(tr("kit.open"), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(tr("common.close"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    return True


class PasswordForm(QWidget):
    """New master password + confirmation + strength + optional hint."""

    def __init__(self, note: str = "", with_hint: bool = True, hint: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if note:
            lay.addWidget(label(note, "muted", wrap=True))
            lay.addSpacing(6)
        lay.addWidget(label(tr("pwform.new"), "fieldkey"))
        self.pw = SecretEdit(generator=False)
        self.pw.edit.setProperty("size", "large")
        lay.addWidget(self.pw)
        row = QHBoxLayout()
        self.meter = StrengthMeter()
        row.addWidget(self.meter)
        self.meter_label = label("", "small")
        row.addWidget(self.meter_label)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(6)
        lay.addWidget(label(tr("pwform.confirm"), "fieldkey"))
        self.confirm = SecretEdit(generator=False)
        self.confirm.edit.setProperty("size", "large")
        lay.addWidget(self.confirm)
        self.pw.textChanged.connect(self._update)
        self.hint = None
        if with_hint:
            lay.addSpacing(10)
            lay.addWidget(label(tr("pwform.hint"), "fieldkey"))
            self.hint = QLineEdit(hint)
            self.hint.setPlaceholderText(tr("pwform.hint_placeholder"))
            lay.addWidget(self.hint)
            lay.addWidget(label(tr("pwform.hint_note"), "smallfaint", wrap=True))
        lay.addWidget(label(tr("pwform.no_reset_note"), "smallfaint", wrap=True))
        self._update("")

    def _update(self, text: str) -> None:
        if not text:
            self.meter.set_score(None)
            self.meter_label.setText(tr("pwform.tip"))
            return
        st = estimate(text)
        self.meter.set_score(st.score)
        self.meter_label.setText(f"{tr(st.label_key)}（{tr('common.chars', n=len(text))}）")

    def validate(self, parent) -> str | None:
        pw, cf = self.pw.text(), self.confirm.text()
        if not pw:
            QMessageBox.warning(parent, tr("pwform.title"), tr("pwform.empty"))
            return None
        if pw != cf:
            QMessageBox.warning(parent, tr("pwform.title"), tr("pwform.mismatch"))
            return None
        if self.hint is not None and self.hint.text().strip() and self.hint.text().strip() in pw:
            QMessageBox.warning(parent, tr("pwform.title"), tr("pwform.hint_contains"))
            return None
        if estimate(pw).score <= 1:
            r = QMessageBox.question(parent, tr("pwform.title"), tr("pwform.weak_confirm"))
            if r != QMessageBox.StandardButton.Yes:
                return None
        return pw

    def hint_text(self) -> str:
        return self.hint.text().strip() if self.hint is not None else ""


class RecoveryPanel(QWidget):
    """Shows a recovery key once, with the emergency-kit PDF button and a 'saved it' checkbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label(tr("recovery.lead"), "muted", wrap=True))
        self.key = QLabel()
        self.key.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key.setFont(theme.mono_font(theme.font_px() + 6))
        self.key.setStyleSheet(f"background: {theme.t('ai_tint')}; color: {theme.t('ai')}; border: 1px solid "
                               f"{theme.t('ai_line')}; border-radius: 10px; padding: 16px; font-weight: 700;")
        self.key.setWordWrap(True)
        lay.addWidget(self.key)
        row = QHBoxLayout()
        self.kit_btn = button(tr("recovery.save_kit"), "primary", "download")
        row.addWidget(self.kit_btn)
        self.copy_btn = button(tr("recovery.copy"), None, "copy")
        row.addWidget(self.copy_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(Banner("warn", tr("recovery.warn")))
        self.saved = QCheckBox(tr("recovery.saved_check"))
        lay.addWidget(self.saved)
        self._ctx = None
        self.kit_btn.clicked.connect(self._save_kit)
        self.copy_btn.clicked.connect(self._copy)

    def set_key(self, key: str, vault_name: str, vault_path: Path, vault_id: str) -> None:
        self.key.setText(key)
        self._ctx = (vault_name, vault_path, vault_id, key)
        self.saved.setChecked(False)

    def _save_kit(self) -> None:
        if self._ctx and save_emergency_kit(self, *self._ctx):
            self.saved.setChecked(True)

    def _copy(self) -> None:
        if self._ctx:
            QGuiApplication.clipboard().setText(self._ctx[3])
            self.copy_btn.setText(tr("recovery.copied"))


class VaultWizard(QDialog):
    """mode = "create" or "migrate"."""

    def __init__(self, parent, settings, mode: str = "create"):
        super().__init__(parent)
        self.settings = settings
        self.mode = mode
        self.vault: Vault | None = None
        self.report = None
        self._decryptor_ok = False
        self.setWindowTitle(tr("wizard.migrate_title") if mode == "migrate" else tr("wizard.create_title"))
        self.setMinimumSize(600, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)
        self.step = label("", "smallfaint")
        lay.addWidget(self.step)
        self.title = label("", "h1")
        lay.addWidget(self.title)
        lay.addWidget(hline())
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        lay.addWidget(hline())
        nav = QHBoxLayout()
        self.back_btn = button(tr("common.back"), slot=self._back)
        self.next_btn = button(tr("common.next"), "primary", slot=self._next)
        self.cancel_btn = button(tr("common.cancel"), "ghost", slot=self.reject)
        nav.addWidget(self.cancel_btn)
        nav.addStretch(1)
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        lay.addLayout(nav)

        self.pages: list[tuple[str, QWidget]] = []
        if mode == "migrate":
            self.pages.append((tr("wizard.page_source"), self._page_source()))
        self.pages.append((tr("wizard.page_place"), self._page_place()))
        self.pages.append((tr("wizard.page_password"), self._page_password()))
        if mode == "migrate":
            self.pages.append((tr("wizard.page_report"), self._page_report()))
        self.pages.append((tr("wizard.page_recovery"), self._page_recovery()))
        for _, w in self.pages:
            self.stack.addWidget(w)
        self._go(0)

    # ---------------------------------------------------------------- pages
    def _page_source(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(label(tr("migrate.lead"), "muted", wrap=True))
        lay.addSpacing(4)
        lay.addWidget(label(tr("migrate.file"), "fieldkey"))
        row = QHBoxLayout()
        self.src_combo = QComboBox()
        for p in find_v2_databases():
            self.src_combo.addItem(self._src_label(p), str(p))
        if self.src_combo.count() == 0:
            self.src_combo.addItem(tr("migrate.none_found"), "")
        self.src_combo.currentIndexChanged.connect(self._src_changed)
        row.addWidget(self.src_combo, 1)
        row.addWidget(button(tr("common.browse"), slot=self._browse_src))
        lay.addLayout(row)
        self.src_path = label("", "smallfaint", wrap=True, selectable=True)
        lay.addWidget(self.src_path)
        lay.addSpacing(8)
        lay.addWidget(label(tr("migrate.old_password"), "fieldkey"))
        row2 = QHBoxLayout()
        self.old_pw = SecretEdit(generator=False)
        self.old_pw.edit.returnPressed.connect(self._verify_source)
        row2.addWidget(self.old_pw, 1)
        row2.addWidget(button(tr("migrate.check"), slot=self._verify_source))
        lay.addLayout(row2)
        self.src_result = label("", "small", wrap=True)
        lay.addWidget(self.src_result)
        lay.addStretch(1)
        lay.addWidget(label(tr("migrate.readonly_note"), "smallfaint", wrap=True))
        self._src_changed()
        return w

    @staticmethod
    def _src_label(p: Path) -> str:
        try:
            ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            ts = "?"
        parent = p.parent.parent.name if p.parent.name == "data" else p.parent.name
        return f"{parent} / {p.name}（{tr('migrate.modified')} {ts}）"

    def _src_changed(self) -> None:
        self.src_path.setText(self.src_combo.currentData() or "")
        self._decryptor_ok = False
        self.src_result.setText("")
        self._update_nav()

    def _browse_src(self) -> None:
        start = self.src_combo.currentData() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, tr("migrate.file"), start, "accounts.db (*.db);;* (*)")
        if path:
            self.src_combo.insertItem(0, self._src_label(Path(path)), path)
            self.src_combo.setCurrentIndex(0)

    def _verify_source(self) -> None:
        src = self.src_combo.currentData()
        if not src:
            self.src_result.setText(tr("migrate.choose_file"))
            return
        if not self.old_pw.text():
            self.src_result.setText(tr("migrate.enter_password"))
            return
        try:
            with busy():
                _, n = migrate_v2.verify_password(Path(src), self.old_pw.text())
        except WrongPassword:
            self._set_src_result(False, tr("migrate.wrong_password"))
            return
        except Exception as exc:  # noqa: BLE001
            self._set_src_result(False, tr("migrate.cannot_read", error=exc))
            return
        self._decryptor_ok = True
        self._set_src_result(True, tr("migrate.found", n=n))
        self._update_nav()

    def _set_src_result(self, ok: bool, text: str) -> None:
        self.src_result.setProperty("role", "ok" if ok else "error")
        self.src_result.style().unpolish(self.src_result)
        self.src_result.style().polish(self.src_result)
        self.src_result.setText(("✓ " if ok else "") + text)
        self._decryptor_ok = ok
        self._update_nav()

    def _page_place(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(label(tr("place.name"), "fieldkey"))
        self.name_edit = QLineEdit(tr("place.default_name"))
        lay.addWidget(self.name_edit)
        lay.addWidget(label(tr("place.name_note"), "smallfaint", wrap=True))
        lay.addSpacing(10)
        lay.addWidget(label(tr("place.folder"), "fieldkey"))
        row = QHBoxLayout()
        self.folder_edit = QLineEdit(self.settings["vault_dir"] or str(default_vault_dir()))
        self.folder_edit.setReadOnly(True)
        row.addWidget(self.folder_edit, 1)
        row.addWidget(button(tr("common.change"), slot=self._choose_folder))
        lay.addLayout(row)
        lay.addSpacing(6)
        lay.addWidget(label(tr("place.file"), "fieldkey"))
        row2 = QHBoxLayout()
        self.file_edit = QLineEdit("personal")
        row2.addWidget(self.file_edit, 1)
        row2.addWidget(label(VAULT_SUFFIX, "muted"))
        lay.addLayout(row2)
        lay.addSpacing(8)
        lay.addWidget(Banner("info", tr("place.drive_note"), "shield_check"))
        lay.addStretch(1)
        return w

    def _choose_folder(self) -> None:
        start = Path(self.folder_edit.text())
        while not start.exists() and start != start.parent:
            start = start.parent
        path = QFileDialog.getExistingDirectory(self, tr("place.folder"), str(start))
        if path:
            self.folder_edit.setText(path)

    def _target_path(self) -> Path:
        name = self.file_edit.text().strip() or "personal"
        if not name.endswith(VAULT_SUFFIX):
            name += VAULT_SUFFIX
        return Path(self.folder_edit.text()) / name

    def _page_password(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        note = tr("pwform.migrate_note") if self.mode == "migrate" else tr("pwform.create_note")
        self.pwform = PasswordForm(note)
        lay.addWidget(self.pwform)
        lay.addStretch(1)
        return w

    def _page_report(self) -> QWidget:
        w = QWidget()
        self.report_lay = QVBoxLayout(w)
        self.report_lay.setContentsMargins(0, 8, 0, 0)
        self.report_lay.setSpacing(8)
        return w

    def _fill_report(self) -> None:
        r = self.report
        lay = self.report_lay
        kind = "ok" if r.ok and not r.problems else "warn"
        text = tr("report.ok", n=r.imported) if r.ok else tr("report.partial", n=r.imported, total=r.total)
        lay.addWidget(Banner(kind, text, "check" if kind == "ok" else "alert"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        rows = [
            (tr("report.source"), r.source),
            (tr("report.count"), tr("report.count_value", imported=r.imported, total=r.total)),
            (tr("report.closed"), str(r.closed)),
            (tr("report.prev"), str(r.previous_passwords)),
        ]
        if r.new_subcategories:
            rows.append((tr("report.new_subs"), "、".join(r.new_subcategories)))
        for i, (k, v) in enumerate(rows):
            grid.addWidget(label(k, "fieldkey"), i, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(label(v, None, wrap=True, selectable=True), i, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        if r.problems:
            lay.addSpacing(6)
            lay.addWidget(label(tr("report.problems"), "warn", wrap=True))
            box = QPlainTextEdit("\n".join(f"・{t}：{', '.join(f)}" for t, f in r.problems))
            box.setReadOnly(True)
            box.setMaximumHeight(110)
            lay.addWidget(box)
        lay.addStretch(1)
        lay.addWidget(label(tr("report.untouched"), "smallfaint", wrap=True))

    def _page_recovery(self) -> QWidget:
        self.recovery = RecoveryPanel()
        self.recovery.saved.toggled.connect(lambda _: self._update_nav())
        return self.recovery

    # ---------------------------------------------------------------- navigation
    def _index_of(self, page_title: str) -> int:
        for i, (t, _) in enumerate(self.pages):
            if t == page_title:
                return i
        return -1

    def _go(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        title = self.pages[i][0]
        self.title.setText(title)
        self.step.setText(tr("wizard.step", i=i + 1, n=len(self.pages)))
        self._update_nav()

    def _current_title(self) -> str:
        return self.pages[self.stack.currentIndex()][0]

    def _update_nav(self) -> None:
        if not hasattr(self, "next_btn") or self.stack.currentIndex() < 0 or self.stack.count() != len(self.pages):
            return
        cur = self._current_title()
        last = self.stack.currentIndex() == len(self.pages) - 1
        self.next_btn.setText(tr("common.finish") if last else (
            tr("wizard.create_now") if cur == tr("wizard.page_password") else tr("common.next")))
        enabled = True
        if cur == tr("wizard.page_source"):
            enabled = self._decryptor_ok
        if last:
            enabled = self.recovery.saved.isChecked()
        self.next_btn.setEnabled(enabled)
        self.back_btn.setVisible(self.vault is None and self.stack.currentIndex() > 0)
        self.cancel_btn.setVisible(self.vault is None)

    def _back(self) -> None:
        if self.stack.currentIndex() > 0 and self.vault is None:
            self._go(self.stack.currentIndex() - 1)

    def _next(self) -> None:
        cur = self._current_title()
        i = self.stack.currentIndex()
        if cur == tr("wizard.page_place"):
            target = self._target_path()
            if not self.name_edit.text().strip():
                QMessageBox.warning(self, cur, tr("place.need_name"))
                return
            if target.exists():
                QMessageBox.warning(self, cur, tr("place.exists", path=target))
                return
        if cur == tr("wizard.page_password"):
            pw = self.pwform.validate(self)
            if pw is None:
                return
            if not self._create(pw):
                return
        if i == len(self.pages) - 1:
            self.accept()
            return
        self._go(i + 1)

    def _create(self, password: str) -> bool:
        target = self._target_path()
        try:
            with busy():
                vault, key = Vault.create(target, self.name_edit.text().strip(), password, self.pwform.hint_text())
                if self.mode == "migrate":
                    self.report = migrate_v2.migrate(Path(self.src_combo.currentData()), self.old_pw.text(), vault)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("wizard.create_title"), tr("wizard.create_failed", error=exc))
            return False
        self.vault = vault
        self.settings.set("vault_dir", str(target.parent))
        if self.report is not None:
            self._fill_report()
        self.recovery.set_key(key, vault.name, vault.path, vault.vault_id)
        return True

    def reject(self) -> None:
        if self.vault is not None:
            r = QMessageBox.question(self, self.windowTitle(), tr("recovery.close_without"))
            if r != QMessageBox.StandardButton.Yes:
                return
            self.accept()
            return
        super().reject()


class ChangePasswordDialog(QDialog):
    def __init__(self, parent, vault: Vault):
        super().__init__(parent)
        self.vault = vault
        self.new_password = None
        self.setWindowTitle(tr("changepw.title"))
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(8)
        lay.addWidget(label(tr("changepw.title"), "h1"))
        lay.addWidget(label(tr("changepw.lead"), "muted", wrap=True))
        lay.addWidget(label(tr("changepw.current"), "fieldkey"))
        self.current = SecretEdit(generator=False)
        lay.addWidget(self.current)
        lay.addSpacing(6)
        self.form = PasswordForm(with_hint=True, hint=vault.hint)
        lay.addWidget(self.form)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("common.cancel"), "ghost", slot=self.reject))
        row.addWidget(button(tr("changepw.do"), "primary", slot=self._ok))
        lay.addLayout(row)

    def _ok(self) -> None:
        try:
            with busy():
                self.vault.check_password(self.current.text())
        except WrongPassword:
            QMessageBox.warning(self, tr("changepw.title"), tr("changepw.wrong_current"))
            return
        pw = self.form.validate(self)
        if pw is None:
            return
        with busy():
            self.vault.change_password(pw)
            if self.form.hint_text() != self.vault.hint:
                self.vault.set_meta_text("hint", self.form.hint_text())
        self.new_password = pw
        self.accept()


class RecoveryUnlockDialog(QDialog):
    """Enter the recovery key, then choose a new master password."""

    def __init__(self, parent, vault: Vault):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle(tr("recover.title"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(8)
        lay.addWidget(label(tr("recover.title"), "h1"))
        lay.addWidget(label(tr("recover.lead"), "muted", wrap=True))
        lay.addWidget(label(tr("recover.key"), "fieldkey"))
        self.key = QLineEdit()
        self.key.setFont(theme.mono_font(theme.font_px() + 2))
        self.key.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        lay.addWidget(self.key)
        lay.addSpacing(6)
        self.form = PasswordForm(with_hint=True, hint=vault.hint)
        lay.addWidget(self.form)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(button(tr("common.cancel"), "ghost", slot=self.reject))
        row.addWidget(button(tr("recover.do"), "primary", slot=self._ok))
        lay.addLayout(row)

    def _ok(self) -> None:
        pw = self.form.validate(self)
        if pw is None:
            return
        try:
            with busy():
                self.vault.unlock_with_recovery(self.key.text())
        except WrongPassword:
            QMessageBox.warning(self, tr("recover.title"), tr("recover.wrong_key"))
            return
        with busy():
            self.vault.change_password(pw)
            if self.form.hint_text() != self.vault.hint:
                self.vault.set_meta_text("hint", self.form.hint_text())
        self.accept()


class RecoveryKeyDialog(QDialog):
    """Shown after re-issuing the recovery key."""

    def __init__(self, parent, vault: Vault, key: str):
        super().__init__(parent)
        self.setWindowTitle(tr("recovery.new_title"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(label(tr("recovery.new_title"), "h1"))
        self.panel = RecoveryPanel()
        self.panel.set_key(key, vault.name, vault.path, vault.vault_id)
        lay.addWidget(self.panel)
        row = QHBoxLayout()
        row.addStretch(1)
        self.ok = button(tr("common.finish"), "primary", slot=self.accept)
        self.ok.setEnabled(False)
        self.panel.saved.toggled.connect(self.ok.setEnabled)
        row.addWidget(self.ok)
        lay.addLayout(row)

    def reject(self) -> None:
        if not self.panel.saved.isChecked():
            r = QMessageBox.question(self, self.windowTitle(), tr("recovery.close_without"))
            if r != QMessageBox.StandardButton.Yes:
                return
        super().reject()
