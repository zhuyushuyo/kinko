import hashlib
import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from conftest import FAST_KDF
from kinko.core import crypto
from kinko.core.model import default_config, item_fields
from kinko.core.vault import Vault, VaultChanged, WrongPassword, restore_from_backup
from kinko.services import generator
from kinko.services.index import Index
from kinko.services.search import normalize, tokens
from kinko.services.strength import estimate
from kinko.storage import backup, migrate_v2


def make_vault(tmp_path, pw="マスター-pass-1"):
    return Vault.create(tmp_path / "personal.kinko", "個人用保管庫", pw, hint="猫の名前", kdf=FAST_KDF)


def test_recovery_key_roundtrip():
    text, raw = crypto.new_recovery_key()
    assert len(text) == 39 and text.count("-") == 7
    assert crypto.parse_recovery_key(text) == raw
    assert crypto.parse_recovery_key(text.lower().replace("-", " ")) == raw
    with pytest.raises(ValueError):
        crypto.parse_recovery_key("ABCD")


def test_create_unlock_and_wrong_password(tmp_path):
    v, rk = make_vault(tmp_path)
    iid = v.add_item({"title": "ひかり銀行", "category": "finance", "sub": "bank",
                      "fields": {"username": "taro", "password": "S3cret!pw"}})
    v.lock()
    v2 = Vault(tmp_path / "personal.kinko")
    assert v2.name == "個人用保管庫" and v2.hint == "猫の名前"
    with pytest.raises(WrongPassword):
        v2.unlock("違う")
    v2.unlock("マスター-pass-1")
    assert v2.items[iid].data["fields"]["password"] == "S3cret!pw"
    v2.lock()
    v3 = Vault(tmp_path / "personal.kinko")
    v3.unlock_with_recovery(rk.lower())
    assert v3.items[iid].data["title"] == "ひかり銀行"


def test_no_plaintext_on_disk(tmp_path):
    v, _ = make_vault(tmp_path)
    v.add_item({"title": "UniqueServiceName", "fields": {"username": "uniqueuser42", "notes": "secretnote"}})
    v.lock()
    raw = (tmp_path / "personal.kinko").read_bytes()
    for word in (b"UniqueServiceName", b"uniqueuser42", b"secretnote"):
        assert word not in raw


def test_random_salt_per_vault(tmp_path):
    a, _ = Vault.create(tmp_path / "a.kinko", "a", "same", kdf=FAST_KDF)
    b, _ = Vault.create(tmp_path / "b.kinko", "b", "same", kdf=FAST_KDF)
    assert bytes(a._meta["pw_salt"]) != bytes(b._meta["pw_salt"])


def test_change_password_and_recovery_reset(tmp_path):
    v, rk = make_vault(tmp_path)
    iid = v.add_item({"title": "x", "fields": {"password": "p1"}})
    v.change_password("新しいパスワード")
    v.lock()
    v = Vault(tmp_path / "personal.kinko")
    with pytest.raises(WrongPassword):
        v.unlock("マスター-pass-1")
    v.unlock("新しいパスワード")
    new_rk = v.regenerate_recovery_key()
    v.lock()
    v = Vault(tmp_path / "personal.kinko")
    with pytest.raises(WrongPassword):
        v.unlock_with_recovery(rk)
    v.unlock_with_recovery(new_rk)
    assert v.items[iid].data["fields"]["password"] == "p1"


def test_history_trash_and_purge(tmp_path):
    v, _ = make_vault(tmp_path)
    iid = v.add_item({"title": "a", "category": "finance", "sub": "bank",
                      "fields": {"password": "one", "pin": "1111"}})
    first_changed = v.items[iid].data["pw_changed_at"]
    data = json.loads(json.dumps(v.items[iid].data))
    data["fields"]["password"] = "two"
    data["fields"]["pin"] = "2222"
    v.update_item(iid, data)
    hist = v.secret_history(iid)
    assert {h["field"]: h["value"] for h in hist} == {"password": "one", "pin": "1111"}
    assert v.items[iid].data["pw_changed_at"] >= first_changed
    v.trash_item(iid)
    assert v.items[iid].trashed
    v.restore_item(iid)
    assert not v.items[iid].trashed
    v.trash_item(iid)
    v.items[iid].deleted_at = (datetime.now().astimezone() - timedelta(days=40)).isoformat()
    assert v.purge_expired(30) == 1
    assert iid not in v.items


def test_external_change_is_detected(tmp_path):
    v, _ = make_vault(tmp_path)
    iid = v.add_item({"title": "a"})
    other = Vault(tmp_path / "personal.kinko")
    other.unlock("マスター-pass-1")
    other.add_item({"title": "from another pc"})
    other.lock()
    with pytest.raises(VaultChanged):
        v.update_item(iid, {"title": "b"})
    assert any(r.data["title"] == "from another pc" for r in v.items.values())
    v.update_item(iid, {"title": "b"})  # works after the reload
    assert v.items[iid].data["title"] == "b"


def test_backup_retention_and_restore(tmp_path):
    v, _ = make_vault(tmp_path)
    bdir = tmp_path / "backups"
    base = datetime(2026, 11, 1, 9, 0, 0)
    for i in range(30):
        backup.make_backup(v.store_for_backup(), v.path, bdir, now=base - timedelta(hours=12 * i))
    removed = backup.prune(v.path, bdir, keep_latest=5, keep_days=7, now=base)
    kept = backup.list_backups(v.path, bdir)
    assert len(kept) + len(removed) == 30
    days = {ts.date() for ts, _ in kept}
    assert len(kept) <= 5 + 8 and len(days) >= 7
    newest = kept[0][1]
    iid = v.add_item({"title": "after backup"})
    v.lock()
    restore_from_backup(v.path, newest, tmp_path / "safety")
    v = Vault(tmp_path / "personal.kinko")
    v.unlock("マスター-pass-1")
    assert iid not in v.items


def test_search_normalization():
    assert normalize("ＡＢＣ　カタカナ") == "abc かたかな"
    assert tokens("ﾋｶﾘ 銀行") == ["ひかり", "銀行"]


def test_generator_and_strength():
    pw = generator.random_password(20, avoid_ambiguous=True)
    assert len(pw) == 20 and not (set(pw) & generator.AMBIGUOUS)
    assert estimate(pw).score >= 3
    assert estimate("password1").score == 0
    p = generator.pin(4)
    assert len(p) == 4 and p.isdigit() and p not in ("1234", "0000")
    words = generator.passphrase(4, "-")
    assert words.count("-") == 3


def test_item_fields_keep_unknown_values():
    cfg = default_config()
    item = {"title": "x", "category": "service", "sub": "", "fields": {"username": "u", "branch": "101",
            "f_custom": "v"}, "extra": [{"key": "f_custom", "label": "会員番号", "type": "text"}]}
    keys = [f["key"] for f in item_fields(cfg, item)]
    assert keys == ["username", "f_custom", "branch"]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_migrate_from_v2(tmp_path):
    from v2_fixture import V2_PASSWORD, build

    src = build(tmp_path / "accounts.db")
    before = _sha(src)
    with pytest.raises(WrongPassword):
        migrate_v2.verify_password(src, "wrong")
    v, _ = make_vault(tmp_path)
    report = migrate_v2.migrate(src, V2_PASSWORD, v)
    assert _sha(src) == before  # the old file is untouched
    assert report.ok and report.imported == 9 and report.closed == 1 and report.previous_passwords == 1
    assert report.problems == [] and report.new_subcategories == ["図書館"]
    items = {r.data["title"]: r for r in v.items.values()}
    bank = items["ひかり銀行"].data
    assert bank["sub"] == "bank" and bank["fields"]["transaction_password"] == "Trade!77"
    assert bank["fields"]["account_number"] == "1234567" and bank["fields"]["branch"] == "101 本店営業部"
    assert bank["fields"]["twofa"] == {"on": True, "app": "Google Authenticator"}
    assert bank["fields"]["secret_qa"] == [{"q": "母親の旧姓は？", "a": "やまだ"}]
    hist = v.secret_history(items["ひかり銀行"].id)
    assert hist[0]["value"] == "OldBank#2019"
    assert items["あおばカード"].data["status"] == "closed"
    pension = items["ねんきんネット"].data
    assert pension["sub"] == "pension" and pension["fields"]["pension_number"] == "1234-567890"
    assert items["マイナポータル"].data["sub"] == "mynumber"
    idx = Index(v)
    kino = items["動画配信 Kino"].id
    assert "reused" in idx.issues[kino] and "weak" in idx.issues[kino]
    assert idx.ids_for(("all",), query="ﾏﾙｼｪ") == [items["ネットショップ マルシェ"].id]
    v.lock()
    v = Vault(tmp_path / "personal.kinko")
    v.unlock("マスター-pass-1")
    assert len(v.items) == 9


def test_v2_file_never_written(tmp_path):
    from v2_fixture import V2_PASSWORD, build

    src = build(tmp_path / "accounts.db")
    conn = migrate_v2._connect_ro(src)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM accounts")
    conn.close()
    dec, n = migrate_v2.verify_password(src, V2_PASSWORD)
    assert n == 9
