"""Renders the main screens with fictional sample data (offscreen) for visual checks.

    python tools/screenshots.py [out_dir] [--lang en]

Uses a temporary settings folder and vault; nothing on this PC is touched.
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TMP = Path(tempfile.mkdtemp(prefix="kinko-shots-"))
os.environ["XDG_CONFIG_HOME"] = str(TMP / "config")

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtGui import QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from kinko.core.model import twofa_value  # noqa: E402
from kinko.core.vault import Vault  # noqa: E402
from kinko.i18n import set_language  # noqa: E402
from kinko.settings import Settings  # noqa: E402
from kinko.ui import theme  # noqa: E402

FAST = {"alg": "argon2id", "t": 1, "m": 8192, "p": 1}
PW = "sample-master-pass"


def iso(days_ago: float = 0) -> str:
    return (datetime.now().astimezone() - timedelta(days=days_ago)).isoformat(timespec="seconds")


def sample_vault(path: Path) -> Vault:
    v, _ = Vault.create(path, "個人用保管庫", PW, hint="好きな本の一節", kdf=FAST)
    add = v.add_item
    bank = add({"title": "ひかり銀行", "category": "finance", "sub": "bank", "favorite": True, "tags": ["給与口座"],
                "fields": {"username": "hikari_taro01", "password": "OldBank#2019-pass", "transaction_password": "Trade!77x",
                           "pin": "4812", "branch": "101　本店営業部", "account_number": "1234567",
                           "twofa": twofa_value("on", "Google Authenticator"),
                           "url": "https://hikari-bank.example/login",
                           "secret_qa": [{"q": "母親の旧姓は？", "a": "やまだ"}, {"q": "最初のペットの名前は？", "a": "ぽち"}],
                           "notes": "キャッシュカードの有効期限は2027年3月。\n住所変更は本店の窓口で手続き済み。"}})
    d = copy.deepcopy(v.items[bank].data)
    d["fields"]["password"] = "q7#Rv-2mXk!pLw9T"
    v.update_item(bank, d)
    v.items[bank].data["pw_changed_at"] = iso(600)
    v.update_item(bank, copy.deepcopy(v.items[bank].data))
    v.items[bank].data["pw_changed_at"] = iso(600)
    v.update_item(bank, v.items[bank].data)
    add({"title": "マイナポータル", "category": "government", "sub": "mynumber",
         "fields": {"username": "", "notes": "マイナンバーカードでログイン", "password": "Myna-portal-9z"}})
    shop = add({"title": "ネットショップ マルシェ", "category": "shopping",
                "fields": {"email": "taro.yamada@example.jp", "password": "password1", "url": "https://marche.example"}})
    add({"title": "みどり証券", "category": "finance", "sub": "investment",
         "fields": {"username": "mdr-458213", "password": "password1", "transaction_password": "Mdr#5521"}})
    add({"title": "動画配信 Kino", "category": "service",
         "fields": {"email": "taro.yamada@example.jp", "password": "kino2024"}})
    add({"title": "ねんきんネット", "category": "government", "sub": "pension",
         "fields": {"username": "yamada.t", "full_name": "山田 太郎", "pension_number": "1234-567890",
                    "password": "Nenkin*2025-ok"}})
    add({"title": "研究室チャット", "category": "work", "tags": ["研究"],
         "fields": {"email": "taro@lab.example.ac.jp", "password": "Lab-chat-2026!x",
                    "twofa": twofa_value("on", "Microsoft Authenticator")}})
    add({"title": "星のRPGオンライン", "category": "game",
         "fields": {"username": "hoshi_taro", "password": "Hoshi-RPG-2026!sky", "twofa": twofa_value("none")}})
    add({"title": "フリマアプリ ぽけっと", "category": "shopping",
         "fields": {"email": "taro.yamada@example.jp", "password": "Poket#Furima-2026x", "twofa": twofa_value("off")}})
    add({"title": "クラウド保存 Nuage", "category": "service", "tags": ["研究"],
         "fields": {"email": "taro.yamada@example.jp", "password": "kamosu-renoki-tabaru-mise7",
                    "twofa": twofa_value("on", "Google Authenticator")}})
    add({"title": "あおばカード", "category": "finance", "sub": "credit_card", "status": "closed",
         "fields": {"email": "taro.yamada@example.jp", "password": "Aoba-card-01"}})
    old = add({"title": "古い通販サイト", "category": "shopping", "fields": {"username": "olduser"}})
    v.trash_item(old)
    for i, iid in enumerate([bank, shop]):
        v.items[iid].used_at = iso(i * 0.1)
        v._store.item_set_used(iid, v.items[iid].used_at)
    return v


def grab(w) -> QPixmap:
    QApplication.processEvents()
    return w.grab()


def composite(win, popup, anchor) -> QPixmap:
    """Offscreen screens are tiny, so place the popup under its field by hand."""
    base = grab(win)
    pm = popup.grab()
    pos = anchor.mapTo(win, QPoint(0, anchor.height() + 4))
    pos.setX(min(pos.x(), win.width() - pm.width() - 12))
    p = QPainter(base)
    p.drawPixmap(pos, pm)
    p.end()
    return base


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "screenshots"
    lang = "en" if "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en" else "ja"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle("Fusion")
    settings = Settings(TMP / "settings.json")
    settings.set("language", lang)
    set_language(lang)
    settings.set("theme", "light")
    theme.apply(app, settings)
    vault = sample_vault(TMP / "マイドライブ" / "App Development" / "AppData" / "KINKO" / "personal.kinko")
    vault.lock()
    settings.remember_vault(str(vault.path))

    from kinko.ui.main_window import MainWindow
    from kinko.ui.settings_dialog import SettingsDialog
    from kinko.ui.wizards import VaultWizard

    win = MainWindow(settings)
    win.resize(1280, 800)
    win.show()
    QApplication.processEvents()
    QApplication.processEvents()
    grab(win).save(str(out / "01_lock.png"))

    win.unlock(PW)
    QApplication.processEvents()
    view = win.view
    bank = next(i for i, r in win.vault.items.items() if r.data["title"] == "ひかり銀行")
    view.list.select_id(bank)
    view.copy_quick(bank, "username")
    QApplication.processEvents()
    grab(win).save(str(out / "02_main_light.png"))
    settings.set("theme", "dark")
    win.apply_appearance()
    win.view.list.select_id(bank)
    QApplication.processEvents()
    grab(win).save(str(out / "02b_main_dark.png"))
    settings.set("theme", "light")
    win.apply_appearance()
    view = win.view
    view.list.select_id(bank)
    QApplication.processEvents()

    view.list.search.setText("ﾏﾙｼｪ")
    QApplication.processEvents()
    grab(win).save(str(out / "03_search.png"))
    view.list.search.clear()

    view.sidebar.select(("health",))
    QApplication.processEvents()
    grab(win).save(str(out / "04_health.png"))
    view.sidebar.select(("all",))

    settings.set("theme", "dark")
    win.apply_appearance()
    view = win.view
    view.list.select_id(bank)
    view.edit_item(bank)
    QApplication.processEvents()
    pw_editor = view.editor._editors["password"][1]
    view.editor._generate(pw_editor, None)
    QApplication.processEvents()
    composite(win, view.editor._popup, pw_editor).save(str(out / "05_edit_dark.png"))
    view.editor._popup.close()
    view.editor.cancel()

    settings.set("theme", "light")
    win.apply_appearance()
    dlg = SettingsDialog(win, 1)
    dlg.show()
    QApplication.processEvents()
    grab(dlg).save(str(out / "06_settings_appearance.png"))
    dlg.nav.setCurrentRow(4)
    QApplication.processEvents()
    grab(dlg).save(str(out / "07_settings_categories.png"))
    dlg.nav.setCurrentRow(2)
    QApplication.processEvents()
    grab(dlg).save(str(out / "08_settings_security.png"))
    dlg.close()

    wiz = VaultWizard(win, settings, "migrate")
    wiz.show()
    QApplication.processEvents()
    grab(wiz).save(str(out / "09_wizard_source.png"))
    wiz.recovery.set_key("ABCD-EFGH-JKMN-PQRS-TVWX-YZ01-2345-6789", "個人用保管庫", vault.path, vault.vault_id)
    wiz._go(len(wiz.pages) - 1)
    QApplication.processEvents()
    grab(wiz).save(str(out / "10_wizard_recovery.png"))
    wiz.vault = None
    wiz.done(0)

    win.lock("manual")
    settings.set("theme", "dark")
    win.apply_appearance()
    QApplication.processEvents()
    grab(win).save(str(out / "01b_lock_dark.png"))
    settings.set("theme", "light")
    win.apply_appearance()
    win.show_welcome()
    QApplication.processEvents()
    grab(win).save(str(out / "11_welcome.png"))

    from kinko.ui import emergency_kit
    emergency_kit.save_pdf(out / "12_emergency_kit.pdf", "個人用保管庫", str(vault.path), vault.vault_id,
                           "ABCD-EFGH-JKMN-PQRS-TVWX-YZ01-2345-6789")
    print("saved to", out)


if __name__ == "__main__":
    main()
