"""Import from Account Manager Ver2 (accounts.db).

The old file is opened read-only and never changed. Every column is carried
over: status (closed accounts), the previous password, secret questions and
the 2FA settings. Fields that cannot be decrypted are reported, not dropped
silently.
"""
from __future__ import annotations

import base64
import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..core.model import find_category, normalize_config
from ..core.vault import Vault, WrongPassword

V2_SALT = b"account_manager_minimal_salt_2026"
V2_ITERATIONS = 600_000

GOV_MAP = {
    "年金": "pension", "pension": "pension",
    "マイナンバー関連": "mynumber", "mynumber related": "mynumber",
    "マイナ免許": "my_license", "myna license": "my_license",
    "健康保険": "health_ins", "health insurance": "health_ins",
}
FINANCE_MAP = {"bank": "bank", "credit_card": "credit_card", "investment": "investment"}
KNOWN_CATEGORIES = ("shopping", "service", "finance", "game", "government", "work")

ENCRYPTED_FIELDS = {
    "password_encrypted": "password",
    "pin_encrypted": "pin",
    "transaction_password_encrypted": "transaction_password",
    "account_number_encrypted": "account_number",
    "pension_number_encrypted": "pension_number",
}


class V2Error(Exception):
    pass


class V2Decryptor:
    def __init__(self, password: str):
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=V2_SALT, iterations=V2_ITERATIONS)
        self._fernet = Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8"))))

    def decrypt(self, blob) -> str:
        if isinstance(blob, str):
            blob = blob.encode("utf-8")
        return self._fernet.decrypt(bytes(blob)).decode("utf-8")


def _connect_ro(path: Path) -> sqlite3.Connection:
    path = Path(path)
    if not path.is_file():
        raise V2Error(f"not found: {path}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(path: Path) -> list[dict]:
    conn = _connect_ro(path)
    try:
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY id")]
        except sqlite3.Error as exc:
            raise V2Error("accounts table not found") from exc
    finally:
        conn.close()


def count_accounts(path: Path) -> int:
    return len(_rows(path))


def verify_password(path: Path, password: str) -> tuple[V2Decryptor, int]:
    """Returns the decryptor and the number of accounts. Raises WrongPassword."""
    rows = _rows(path)
    dec = V2Decryptor(password)
    samples = [r["password_encrypted"] for r in rows if r.get("password_encrypted")][:3]
    if not samples:
        return dec, len(rows)
    for blob in samples:
        try:
            dec.decrypt(blob)
            return dec, len(rows)
        except (InvalidToken, ValueError, UnicodeDecodeError):
            continue
    raise WrongPassword()


@dataclass
class MigrationReport:
    source: str = ""
    total: int = 0
    imported: int = 0
    closed: int = 0
    previous_passwords: int = 0
    by_category: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)  # (title, [fields])
    new_subcategories: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.total == self.imported


def _gov_sub(config: dict, label: str, report: MigrationReport) -> str:
    label = (label or "").strip()
    if not label:
        return ""
    key = GOV_MAP.get(label.lower()) or GOV_MAP.get(label)
    if key:
        return key
    gov = find_category(config, "government")
    sub_id = "s_" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    if gov is not None and not any(s["id"] == sub_id for s in gov["subs"]):
        gov["subs"].append({"id": sub_id, "name": label, "template": "login"})
        report.new_subcategories.append(label)
    return sub_id


def _category(config: dict, cat: str, report: MigrationReport) -> str:
    cat = (cat or "").strip() or "service"
    if find_category(config, cat):
        return cat
    cat_id = "c_" + hashlib.sha1(cat.encode("utf-8")).hexdigest()[:8]
    if not find_category(config, cat_id):
        config["categories"].append({"id": cat_id, "name": cat, "icon": "star", "color": "work",
                                     "template": "login", "subs": []})
    return cat_id


def build_entries(rows: list[dict], dec: V2Decryptor, config: dict, report: MigrationReport) -> list[dict]:
    entries = []
    for r in rows:
        problems = []

        def dec_field(col: str) -> str:
            blob = r.get(col)
            if not blob:
                return ""
            try:
                return dec.decrypt(blob)
            except (InvalidToken, ValueError, UnicodeDecodeError):
                problems.append(col.replace("_encrypted", ""))
                return ""

        title = (r.get("service_name") or "").strip() or "(no name)"
        category = _category(config, r.get("category") or "", report)
        sub = ""
        if category == "finance":
            sub = FINANCE_MAP.get((r.get("finance_type") or "").strip(), "")
        elif category == "government":
            sub = _gov_sub(config, r.get("gov_subcategory") or "", report)

        fields: dict = {}
        for col in ("username", "email", "url", "notes", "full_name"):
            v = (r.get(col) or "").strip() if col != "notes" else (r.get(col) or "")
            if v:
                fields[col] = v
        if (r.get("branch_number") or "").strip():
            fields["branch"] = r["branch_number"].strip()
        for col, key in ENCRYPTED_FIELDS.items():
            v = dec_field(col)
            if v:
                fields[key] = v
        qa = []
        for i in (1, 2, 3):
            q = (r.get(f"secret_q{i}") or "").strip()
            a = dec_field(f"secret_a{i}_encrypted")
            if q or a:
                qa.append({"q": q, "a": a})
        if qa:
            fields["secret_qa"] = qa
        if r.get("requires_auth") or r.get("authenticator_type"):
            fields["twofa"] = {"on": True, "app": r.get("authenticator_type") or ""}

        status = "closed" if (r.get("status") or "active") == "cancelled" else "active"
        updated = _iso(r.get("updated_at") or "")
        history = []
        prev = dec_field("previous_password_encrypted")
        if prev and prev != fields.get("password"):
            history.append({"field": "password", "label": "", "value": prev, "changed_at": updated, "note": "v2"})
            report.previous_passwords += 1

        tags = []
        if problems:
            tags.append("移行要確認")
            report.problems.append((title, problems))
        data = {"title": title, "category": category, "sub": sub, "status": status, "favorite": False,
                "tags": tags, "fields": fields, "extra": [], "pw_changed_at": updated}
        entries.append({"data": data, "created_at": updated, "updated_at": updated, "history": history})
        report.by_category[category] = report.by_category.get(category, 0) + 1
        if status == "closed":
            report.closed += 1
    return entries


def _iso(value: str) -> str:
    from datetime import datetime

    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return ""


def migrate(source: Path, password: str, vault: Vault) -> MigrationReport:
    """Copy every account of an Account Manager Ver2 database into an unlocked KINKO vault."""
    source = Path(source)
    dec, _ = verify_password(source, password)
    rows = _rows(source)
    report = MigrationReport(source=str(source), total=len(rows))
    config = normalize_config(vault.config)
    entries = build_entries(rows, dec, config, report)
    vault.config = config
    vault.save_config()
    ids = vault.import_items(entries)
    report.imported = len(ids)
    return report
