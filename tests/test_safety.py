"""The safety level: fair to services without two-step verification, strict about passwords."""
from datetime import datetime, timedelta

from conftest import FAST_KDF
from kinko.core.model import is_empty, same_service_item, twofa_state, twofa_value
from kinko.core.vault import Vault
from kinko.services.index import Index
from kinko.services.safety import assess

STRONG = "Kp7#vR2!mQ9x@Lw4"  # scores 4


def test_levels():
    assert assess(score=4, twofa="on").level == "high"
    # a service that has no 2FA is not marked down for it
    sf = assess(score=4, twofa="none", category="finance")
    assert sf.level == "high" and sf.reasons == []
    # not checked: no effect, except for finance, where nearly every service offers it
    assert assess(score=4, twofa="unknown", category="service").level == "high"
    sf = assess(score=4, twofa="unknown", category="finance")
    assert (sf.level, sf.reasons) == ("mid", ["twofa_check"])
    # offered but not switched on
    assert assess(score=4, twofa="off").reasons == ["twofa_off"]
    assert assess(score=2, twofa="on").reasons == ["fair"]
    assert assess(score=3, old=True, twofa="on").level == "mid"
    # passwords decide "low", whatever 2FA does
    assert assess(score=1, twofa="on").level == "low"
    sf = assess(score=4, reused=2, twofa="on")
    assert (sf.level, sf.reasons, sf.reused) == ("low", ["reused"], 2)
    # an account type without a 2FA field: 2FA does not count
    sf = assess(score=4, twofa="unknown", category="finance", has_twofa=False)
    assert (sf.level, sf.twofa) == ("high", "na")


def test_twofa_values_stay_readable_by_1_0_0():
    assert twofa_state(None) == "unknown"
    assert twofa_state({"on": True, "app": "Authy"}) == "on"  # written by 1.0.0
    assert twofa_state({"on": False}) == "unknown"
    for st in ("on", "off", "none"):
        v = twofa_value(st, "Authy")
        assert twofa_state(v) == st and not is_empty(v)
        # 1.0.0 shows 2FA as used only when "on" is True, and hides the field otherwise
        assert v["on"] is (st == "on")
    assert twofa_value("on", "Authy")["app"] == "Authy" and "app" not in twofa_value("none", "Authy")
    assert twofa_value("unknown") is None and is_empty(None)


def test_same_service_copies_no_credentials():
    src = {"title": "ひかり銀行", "category": "finance", "sub": "bank", "tags": ["給与"], "favorite": True,
           "extra": [{"key": "f_x", "label": "お客様番号", "type": "text"}],
           "fields": {"username": "taro", "password": STRONG, "pin": "1234", "branch": "101",
                      "url": "https://hikari.example/login", "notes": "メモ", "f_x": "998877",
                      "twofa": twofa_value("on", "Google Authenticator"),
                      "secret_qa": [{"q": "母の旧姓", "a": "山田"}]}}
    d = same_service_item(src)
    assert (d["title"], d["category"], d["sub"], d["tags"]) == ("ひかり銀行", "finance", "bank", ["給与"])
    assert d["extra"] == src["extra"] and not d["favorite"]
    assert set(d["fields"]) == {"url", "twofa"}
    assert twofa_state(d["fields"]["twofa"]) == "off"  # the bank offers 2FA; the new account has not set it up
    src["fields"]["twofa"] = twofa_value("none")
    assert twofa_state(same_service_item(src)["fields"]["twofa"]) == "none"
    del src["fields"]["twofa"]
    assert "twofa" not in same_service_item(src)["fields"]


def test_index_levels_and_counts(tmp_path):
    v, _ = Vault.create(tmp_path / "p.kinko", "p", "pw", kdf=FAST_KDF)
    ids = {
        "on": v.add_item({"title": "a", "category": "service", "fields": {"password": STRONG + "1",
                                                                         "twofa": twofa_value("on")}}),
        "none": v.add_item({"title": "b", "category": "finance", "sub": "bank",
                            "fields": {"password": STRONG + "2", "twofa": twofa_value("none")}}),
        "unchecked_finance": v.add_item({"title": "c", "category": "finance", "fields": {"password": STRONG + "3"}}),
        "off": v.add_item({"title": "d", "category": "game", "fields": {"password": STRONG + "4",
                                                                       "twofa": twofa_value("off")}}),
        "reused1": v.add_item({"title": "e", "category": "service", "fields": {"password": STRONG}}),
        "reused2": v.add_item({"title": "f", "category": "shopping", "fields": {"password": STRONG}}),
        "weak": v.add_item({"title": "g", "category": "service", "fields": {"password": "abc"}}),
        "no_password": v.add_item({"title": "h", "category": "government", "sub": "pension",
                                   "fields": {"pension_number": "1234-567890"}}),
        "closed": v.add_item({"title": "i", "category": "service", "status": "closed",
                              "fields": {"password": "abc"}}),
    }
    old = (datetime.now().astimezone() - timedelta(days=400)).isoformat(timespec="seconds")
    data = dict(v.items[ids["on"]].data)
    v.update_item(ids["on"], data)
    v.items[ids["on"]].data["pw_changed_at"] = old  # in memory only: the index reads it from here
    idx = Index(v)
    level = {k: idx.safety[i].level for k, i in ids.items() if i in idx.safety}
    assert level == {"on": "mid", "none": "high", "unchecked_finance": "mid", "off": "mid",
                     "reused1": "low", "reused2": "low", "weak": "low"}
    assert idx.issues[ids["on"]] == ["old"]
    assert idx.issues[ids["unchecked_finance"]] == ["twofa_check"]
    assert ids["none"] not in idx.issues and ids["no_password"] not in idx.safety
    assert ids["closed"] not in idx.safety
    assert dict(idx.level_counts) == {"high": 1, "mid": 3, "low": 3}
    assert set(idx.ids_for(("health",))) == set(idx.issues)
