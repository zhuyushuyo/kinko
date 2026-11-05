"""Builds a fake Account Manager Ver2 accounts.db (same schema and encryption) with fictional data."""
import base64
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

V2_PASSWORD = "old-master-パス"

_CREATE = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, service_name TEXT NOT NULL,
    username TEXT, password_encrypted BLOB NOT NULL, previous_password_encrypted BLOB,
    url TEXT, notes TEXT, updated_at TEXT)
"""
_MIGRATIONS = [
    "ALTER TABLE accounts ADD COLUMN email TEXT",
    "ALTER TABLE accounts ADD COLUMN finance_type TEXT",
    "ALTER TABLE accounts ADD COLUMN pin_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN transaction_password_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN secret_q1 TEXT",
    "ALTER TABLE accounts ADD COLUMN secret_a1_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN secret_q2 TEXT",
    "ALTER TABLE accounts ADD COLUMN secret_a2_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN secret_q3 TEXT",
    "ALTER TABLE accounts ADD COLUMN secret_a3_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN gov_subcategory TEXT",
    "ALTER TABLE accounts ADD COLUMN full_name TEXT",
    "ALTER TABLE accounts ADD COLUMN pension_number_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN branch_number TEXT",
    "ALTER TABLE accounts ADD COLUMN account_number_encrypted BLOB",
    "ALTER TABLE accounts ADD COLUMN requires_auth INTEGER DEFAULT 0",
    "ALTER TABLE accounts ADD COLUMN authenticator_type TEXT",
    "ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'",
]


def fernet(password: str) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"account_manager_minimal_salt_2026",
                     iterations=600000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8"))))


def build(path: Path, password: str = V2_PASSWORD) -> Path:
    f = fernet(password)
    e = lambda s: f.encrypt(s.encode("utf-8")) if s else None  # noqa: E731
    conn = sqlite3.connect(path)
    conn.execute(_CREATE)
    for m in _MIGRATIONS:
        conn.execute(m)
    rows = [
        dict(category="finance", service_name="ひかり銀行", username="hikari_taro01", email="taro@example.jp",
             finance_type="bank", password_encrypted=e("Bank#Pass-2024"),
             previous_password_encrypted=e("OldBank#2019"), pin_encrypted=e("4812"),
             transaction_password_encrypted=e("Trade!77"), branch_number="101 本店営業部",
             account_number_encrypted=e("1234567"), url="https://hikari-bank.example/login",
             notes="キャッシュカードは2027年3月まで", requires_auth=1, authenticator_type="Google Authenticator",
             secret_q1="母親の旧姓は？", secret_a1_encrypted=e("やまだ"), status="active",
             updated_at="2025-03-12T10:00:00"),
        dict(category="finance", service_name="あおばカード", username="aoba-user", finance_type="credit_card",
             password_encrypted=e("Card-pass-1"), status="cancelled", updated_at="2024-01-05T09:30:00"),
        dict(category="government", service_name="ねんきんネット", username="yamada.t", gov_subcategory="年金",
             full_name="山田 太郎", pension_number_encrypted=e("1234-567890"), password_encrypted=e("Nenkin*2025"),
             updated_at="2026-02-01T12:00:00"),
        dict(category="government", service_name="区の図書館", username="lib-001", gov_subcategory="図書館",
             password_encrypted=e("Library2026"), updated_at="2026-05-01T08:00:00"),
        dict(category="government", service_name="マイナポータル", gov_subcategory="MyNumber Related",
             password_encrypted=e("Myna-portal-9"), updated_at="2026-04-01T08:00:00"),
        dict(category="service", service_name="動画配信 Kino", email="taro@example.jp",
             password_encrypted=e("password1"), updated_at="2026-06-01T08:00:00"),
        dict(category="shopping", service_name="ネットショップ マルシェ", email="taro@example.jp",
             password_encrypted=e("password1"), url="https://marche.example", updated_at="2026-07-01T08:00:00"),
        dict(category="game", service_name="星のRPGオンライン", username="hoshi_taro",
             password_encrypted=e("Hoshi-RPG-2026"), secret_q2="最初のペットの名前は？",
             secret_a2_encrypted=e("ポチ"), updated_at="2026-08-01T08:00:00"),
        dict(category="work", service_name="研究室チャット", email="taro@lab.example.ac.jp",
             password_encrypted=e("Lab-chat-2026!"), updated_at="2026-09-01T08:00:00"),
    ]
    for r in rows:
        cols = ", ".join(r)
        conn.execute(f"INSERT INTO accounts ({cols}) VALUES ({', '.join('?' * len(r))})", list(r.values()))
    conn.commit()
    conn.close()
    return path
