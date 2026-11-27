"""Drives the real widgets offscreen through the main flows."""
import os
import tempfile

import pytest

os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="kinko-test-config-")
pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtGui import QGuiApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from conftest import FAST_KDF  # noqa: E402
from kinko.core import vault as vault_mod  # noqa: E402
from kinko.core.vault import Vault  # noqa: E402
from kinko.i18n import set_language  # noqa: E402
from kinko.settings import Settings  # noqa: E402
from kinko.ui import theme  # noqa: E402

PW = "gui-test-password-1"


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    a.setStyle("Fusion")
    return a


@pytest.fixture
def env(app, tmp_path, monkeypatch):
    monkeypatch.setattr(vault_mod, "DEFAULT_KDF", FAST_KDF)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    settings = Settings(tmp_path / "settings.json")
    settings.set("vault_dir", str(tmp_path / "AppData" / "KINKO"))
    set_language("ja")
    theme.apply(app, settings)
    return settings, tmp_path


def pump(n=3):
    for _ in range(n):
        QApplication.processEvents()


def make_window(settings, path):
    v, _ = Vault.create(path, "テスト保管庫", PW, kdf=FAST_KDF)
    v.add_item({"title": "ひかり銀行", "category": "finance", "sub": "bank",
                "fields": {"username": "hikari", "password": "Pass-one-111"}})
    v.add_item({"title": "動画配信", "category": "service", "fields": {"email": "a@example.jp", "password": "abc"}})
    v.lock()
    settings.remember_vault(str(path))
    from kinko.ui.main_window import MainWindow

    win = MainWindow(settings)
    win.show()
    pump()
    return win


def test_unlock_edit_history_trash_and_lock(env):
    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock("wrong")
    assert not win.vault.unlocked and win.lock_screen.error.isVisible()
    win.unlock(PW)
    pump()
    view = win.view
    assert view is not None and win.statusBar().isVisible()
    bank = next(i for i, r in win.vault.items.items() if r.data["title"] == "ひかり銀行")
    view.list.select_id(bank)
    pump()
    view.edit_item(bank)
    pw_type, pw_edit = view.editor._editors["password"]
    pw_edit.setText("Pass-two-222")
    assert view.editor.is_dirty()
    view.editor.save()
    pump()
    assert win.vault.items[bank].data["fields"]["password"] == "Pass-two-222"
    assert win.vault.secret_history(bank)[0]["value"] == "Pass-one-111"
    # copy goes to the clipboard and is cleared later
    settings.set("clipboard_seconds", 1)
    view.copy_quick(bank, "password")
    assert QGuiApplication.clipboard().text() == "Pass-two-222"
    win.clipboard.clear_if_ours()
    assert QGuiApplication.clipboard().text() == ""
    # trash and undo
    view.trash_item(bank)
    pump()
    assert win.vault.items[bank].trashed
    win.toast._run()
    pump()
    assert not win.vault.items[bank].trashed
    # new item through the editor
    view.new_item()
    view.editor.title.setText("新しいサービス")
    view.editor._editors["username"][1].setText("newuser")
    view.editor.save()
    pump()
    assert any(r.data["title"] == "新しいサービス" for r in win.vault.items.values())
    # search
    view.list.search.setText("ｼﾝｷ")
    pump()
    view.list.search.setText("新しい")
    pump()
    assert view.list.model.rowCount() == 1
    # lock while editing discards with a notice
    view.list.search.clear()
    view.edit_item(bank)
    view.editor.title.setText("changed")
    win.lock("idle")
    pump()
    assert not win.vault.unlocked and win.view is None
    win.unlock(PW)
    pump()
    assert win.vault.items[bank].data["title"] == "ひかり銀行"
    win.close()


def test_backup_restore_change_password_and_recovery(env, monkeypatch):
    settings, tmp = env
    path = tmp / "AppData" / "KINKO" / "personal.kinko"
    win = make_window(settings, path)
    win.unlock(PW)
    pump()
    first = win.backups.run_now()
    assert first is not None and first.exists()
    win.view.new_item()
    win.view.editor.title.setText("after backup")
    win.view.editor.save()
    pump()
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(first), "")))
    win.restore_backup()
    pump()
    assert not win.vault.unlocked
    win.unlock(PW)
    pump()
    assert not any(r.data["title"] == "after backup" for r in win.vault.items.values())
    # change password (vault level) and re-issue recovery key
    win.vault.change_password("next-password-2")
    key = win.vault.regenerate_recovery_key()
    win.lock("manual")
    win.unlock("next-password-2")
    assert win.vault.unlocked
    win.lock("manual")
    from kinko.ui.wizards import RecoveryUnlockDialog

    dlg = RecoveryUnlockDialog(win, win.vault)
    dlg.key.setText(key.lower())
    dlg.form.pw.setText("after-recovery-3")
    dlg.form.confirm.setText("after-recovery-3")
    dlg._ok()
    assert win.vault.unlocked
    win.vault.lock()
    win.vault.unlock("after-recovery-3")
    win.close()


def test_settings_categories_and_language(env):
    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock(PW)
    pump()
    from kinko.ui.category_editor import CategoryEditor
    from kinko.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(win, 0)
    for i in range(dlg.nav.count()):
        dlg.nav.setCurrentRow(i)
        pump(1)
    ed = dlg.findChild(CategoryEditor)
    assert ed is not None
    # move the finance account away by deleting the finance category
    ed.cat_list.setCurrentRow(2)
    from PyQt6.QtWidgets import QInputDialog

    orig = QInputDialog.getItem
    QInputDialog.getItem = staticmethod(lambda *a, **k: (a[3][0], True))
    try:
        ed._cat_delete()
    finally:
        QInputDialog.getItem = orig
    assert all(c["id"] != "finance" for c in win.vault.config["categories"])
    assert all(r.data["category"] != "finance" for r in win.vault.items.values())
    # remove a field from a type: the value stays on the item
    tpl = win.vault.config["templates"]["login"]
    ed.seg.set_value("types", emit=True)
    ed.tpl_list.setCurrentRow(list(win.vault.config["templates"]).index("login"))
    ed.field_list.setCurrentRow([f["key"] for f in tpl["fields"]].index("email"))
    ed._field_delete()
    from kinko.core.model import item_fields

    video = next(r for r in win.vault.items.values() if r.data["title"] == "動画配信")
    assert "email" in [f["key"] for f in item_fields(win.vault.config, video.data)]
    # appearance + language switch rebuild the views without restarting
    settings.set("theme", "dark")
    settings.set("density", "compact")
    win.apply_appearance()
    settings.set("language", "en")
    win.apply_language()
    pump()
    assert win.view is not None and win.view.sidebar.nav.count() > 0
    settings.set("language", "ja")
    win.apply_language()
    dlg.close()
    win.close()


def test_migration_wizard(env, monkeypatch):
    settings, tmp = env
    from v2_fixture import V2_PASSWORD, build

    src = build(tmp / "accounts.db")
    from kinko.ui.wizards import VaultWizard

    wiz = VaultWizard(None, settings, "migrate")
    wiz.src_combo.insertItem(0, "fixture", str(src))
    wiz.src_combo.setCurrentIndex(0)
    wiz.old_pw.setText(V2_PASSWORD)
    wiz._verify_source()
    assert wiz._decryptor_ok
    wiz._next()  # -> place
    wiz.file_edit.setText("migrated")
    wiz._next()  # -> password
    wiz.pwform.pw.setText("new-master-pass-123")
    wiz.pwform.confirm.setText("new-master-pass-123")
    wiz._next()  # creates + migrates -> report
    assert wiz.vault is not None and wiz.report.imported == 9
    wiz._next()  # -> recovery
    assert not wiz.next_btn.isEnabled()
    wiz.recovery.saved.setChecked(True)
    assert wiz.next_btn.isEnabled()
    assert len(wiz.vault.items) == 9
    wiz.vault.lock()


def test_emergency_kit_pdf(env, tmp_path):
    from kinko.ui import emergency_kit

    out = emergency_kit.save_pdf(tmp_path / "kit.pdf", "テスト", "/x/personal.kinko", "abc", "ABCD-EFGH-JKMN-PQRS-TVWX-YZ01-2345-6789")
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 2000


def test_copy_shortcut_from_list_and_search(env):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock(PW)
    win.activateWindow()
    pump()
    view = win.view
    QGuiApplication.clipboard().setText("before")
    view.list.search.setFocus()
    view.list.search.setText("ひかり")
    pump()
    QTest.keyClick(view.list.search, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    pump()
    assert QGuiApplication.clipboard().text() == "Pass-one-111"
    QGuiApplication.clipboard().setText("before")
    view.list.view.setFocus()
    QTest.keyClick(view.list.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    pump()
    assert QGuiApplication.clipboard().text() == "Pass-one-111"
    QTest.keyClick(view.list.view, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    pump()
    assert QGuiApplication.clipboard().text() == "hikari"
    win.close()


def test_add_button_and_same_service_account(env):
    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock(PW)
    pump()
    view = win.view
    bank = next(i for i, r in win.vault.items.items() if r.data["title"] == "ひかり銀行")
    # the add button is always there, next to the search field
    assert view.list.add_btn.isVisibleTo(win) and view.list.add_btn.text() == "追加"
    view.list.add_btn.click()
    pump()
    assert view.editing and view.editor.iid is None and view.editor.title.text() == ""
    view.editor.cancel()
    pump()
    # the detail menu offers both: a new account, and another account for the same service
    view.list.select_id(bank)
    pump()
    from PyQt6.QtWidgets import QMenu, QToolButton

    menus = [b.menu() for b in view.detail.findChildren(QToolButton) if b.menu() is not None]
    texts = [a.text() for m in menus for a in m.actions() if isinstance(m, QMenu)]
    assert "新しいアカウントを追加" in texts and "同じサービスの別アカウントを追加" in texts
    win.vault.update_item(bank, {**win.vault.items[bank].data,
                                 "fields": {**win.vault.items[bank].data["fields"], "url": "https://hikari.example"}})
    view.refresh()
    view.add_same_service(bank)
    pump()
    ed = view.editor
    assert ed.iid is None and ed.title.text() == "ひかり銀行"
    assert ed._editors["username"][1].text() == "" and ed._editors["password"][1].text() == ""
    assert ed._editors["url"][1].text() == "https://hikari.example"
    assert ed.cat.currentData() == "finance" and ed.sub.currentData() == "bank"
    ed._editors["username"][1].setText("hikari-2")
    ed.save()
    pump()
    assert sum(1 for r in win.vault.items.values() if r.data["title"] == "ひかり銀行") == 2
    win.close()


def test_twofa_states_and_safety_level(env):
    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock(PW)
    pump()
    view = win.view
    bank = next(i for i, r in win.vault.items.items() if r.data["title"] == "ひかり銀行")
    from kinko.core.model import twofa_state
    from kinko.ui.item_detail import SafetyBox

    # finance account, 2FA not checked yet: "medium", asks to check
    view.list.select_id(bank)
    pump()
    view.edit_item(bank)
    view.editor._editors["password"][1].setText("Kp7#vR2!mQ9x@Lw4")
    view.editor.save()
    pump()
    assert view.index.safety[bank].level == "mid" and view.index.issues[bank] == ["twofa_check"]
    box = view.detail.findChild(SafetyBox)
    assert box is not None and box.title.text().startswith("安全度：中")
    # the bank has no 2FA: no longer marked down
    view.edit_item(bank)
    tf = view.editor._editors["twofa"][1]
    tf.set_state("none")
    assert not tf.app.isVisibleTo(view.editor)
    view.editor.save()
    pump()
    data = win.vault.items[bank].data
    assert twofa_state(data["fields"]["twofa"]) == "none" and data["fields"]["twofa"]["on"] is False
    assert view.index.safety[bank].level == "high" and bank not in view.index.issues
    assert view.detail.findChild(SafetyBox).title.text().startswith("安全度：高")
    # switched on, with an app
    view.edit_item(bank)
    tf = view.editor._editors["twofa"][1]
    tf.set_state("on")
    tf.app.setCurrentText("Authy")
    view.editor.save()
    pump()
    assert win.vault.items[bank].data["fields"]["twofa"] == {"state": "on", "on": True, "app": "Authy"}
    # the weak, reused or old ones come first in the security check
    view.sidebar.select(("health",))
    pump()
    first = view.list.model.ids[0]
    assert view.index.safety[first].level == "low"
    assert view.list.caption.text().startswith("安全度")
    win.close()


def test_palette_in_settings_and_both_modes(env):
    settings, tmp = env
    win = make_window(settings, tmp / "AppData" / "KINKO" / "personal.kinko")
    win.unlock(PW)
    pump()
    from PyQt6.QtWidgets import QLabel

    from kinko.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(win, 1)
    pump(1)
    assert any(lb.text() == "藤 Fuji（KINKO 版）" for lb in dlg.findChildren(QLabel))
    for mode, bg in (("dark", "#1A1927"), ("light", "#FFFFFF")):
        settings.set("theme", mode)
        win.apply_appearance()
        pump()
        assert theme.t("paper") == bg
    dlg.close()
    win.close()
