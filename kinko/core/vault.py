"""A KINKO vault: one .kinko file, unlocked with the master password or the recovery key.

Only timestamps and internal IDs are stored in plain text. Every item, the
vault's own settings (categories and types) and the password history are
sealed with AES-256-GCM under the vault's data key.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from .. import __version__
from . import crypto
from .crypto import DEFAULT_KDF, CryptoError
from .model import (SECRET_TYPES, default_config, field_type_of, item_fields, new_id, normalize_config,
                    normalize_item, now_iso, parse_iso)
from ..storage.store import FORMAT, Store, StoreError

FORMAT_VERSION = 1


class VaultError(Exception):
    pass


class WrongPassword(VaultError):
    pass


class NotAVault(VaultError):
    pass


class VaultLocked(VaultError):
    pass


class VaultChanged(VaultError):
    """The file was changed elsewhere (another PC via Drive). It has been reloaded."""


@dataclass
class Record:
    id: str
    created_at: str
    updated_at: str
    used_at: str | None
    deleted_at: str | None
    data: dict

    @property
    def trashed(self) -> bool:
        return bool(self.deleted_at)


def _aad(vault_id: str, kind: str, *parts: str) -> bytes:
    return "/".join(("kinko", kind, vault_id, *parts)).encode("utf-8")


def _dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _text(v) -> str:
    if v is None:
        return ""
    return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)


class Vault:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._dek: bytes | None = None
        self._store: Store | None = None
        self._stat: tuple[int, int] | None = None
        self.config: dict | None = None
        self.items: dict[str, Record] = {}
        self.broken: list[str] = []
        self.listeners: list[Callable[[str], None]] = []
        self._meta: dict = {}
        self.reload_meta()

    # ---------------------------------------------------------------- meta
    def reload_meta(self) -> None:
        if not self.path.is_file():
            raise NotAVault(str(self.path))
        store = None
        try:
            store = Store(self.path)
            if not store.is_vault():
                raise NotAVault(str(self.path))
            self._meta = store.meta_all()
        except (sqlite3.Error, StoreError) as exc:
            raise NotAVault(str(self.path)) from exc
        finally:
            if store:
                store.close()
        if int(_text(self._meta.get("format_version")) or 0) > FORMAT_VERSION:
            raise NotAVault("newer format")

    @property
    def vault_id(self) -> str:
        return _text(self._meta.get("vault_id"))

    @property
    def name(self) -> str:
        return _text(self._meta.get("name")) or self.path.stem

    @property
    def hint(self) -> str:
        return _text(self._meta.get("hint"))

    @property
    def kdf(self) -> dict:
        return json.loads(_text(self._meta.get("kdf")) or "{}") or dict(DEFAULT_KDF)

    @property
    def created_at(self) -> str:
        return _text(self._meta.get("created_at"))

    @property
    def unlocked(self) -> bool:
        return self._dek is not None

    def _aad(self, kind: str, *parts: str) -> bytes:
        return _aad(self.vault_id, kind, *parts)

    # ---------------------------------------------------------------- create / unlock
    @classmethod
    def create(cls, path: str | Path, name: str, password: str, hint: str = "",
               kdf: dict | None = None, config: dict | None = None) -> tuple["Vault", str]:
        path = Path(path)
        kdf = dict(kdf or DEFAULT_KDF)
        vault_id = new_id()
        dek = crypto.new_data_key()
        pw_salt = crypto.random_bytes(crypto.SALT_LEN)
        kek = crypto.derive_password_key(password, pw_salt, kdf)
        rk_text, rk_raw = crypto.new_recovery_key()
        rk_salt = crypto.random_bytes(crypto.SALT_LEN)
        rkek = crypto.derive_recovery_key(rk_raw, rk_salt)
        now = now_iso()
        store = Store.create(path)
        try:
            with store.tx():
                for k, v in {
                    "format": FORMAT, "format_version": str(FORMAT_VERSION), "vault_id": vault_id,
                    "name": name, "hint": hint, "created_at": now, "app_version": __version__,
                    "kdf": json.dumps(kdf), "pw_salt": pw_salt,
                    "pw_wrap": crypto.seal(kek, dek, _aad(vault_id, "dek", "pw")),
                    "rk_salt": rk_salt, "rk_wrap": crypto.seal(rkek, dek, _aad(vault_id, "dek", "rk")),
                    "rk_created_at": now,
                    "config": crypto.seal(dek, _dump(normalize_config(config) if config else default_config()),
                                          _aad(vault_id, "config")),
                }.items():
                    store.meta_set(k, v)
        finally:
            store.close()
        vault = cls(path)
        vault._open(dek)
        return vault, rk_text

    def check_password(self, password: str) -> bytes:
        kek = crypto.derive_password_key(password, bytes(self._meta["pw_salt"]), self.kdf)
        try:
            return crypto.unseal(kek, self._meta["pw_wrap"], self._aad("dek", "pw"))
        except CryptoError as exc:
            raise WrongPassword() from exc

    def unlock(self, password: str) -> None:
        self._open(self.check_password(password))

    def unlock_with_recovery(self, recovery_key: str) -> None:
        try:
            raw = crypto.parse_recovery_key(recovery_key)
        except ValueError as exc:
            raise WrongPassword() from exc
        rkek = crypto.derive_recovery_key(raw, bytes(self._meta["rk_salt"]))
        try:
            dek = crypto.unseal(rkek, self._meta["rk_wrap"], self._aad("dek", "rk"))
        except CryptoError as exc:
            raise WrongPassword() from exc
        self._open(dek)

    def _open(self, dek: bytes) -> None:
        if self._store:
            self._store.close()
        self._store = Store(self.path)
        self._meta = self._store.meta_all()
        cfg_blob = self._meta.get("config")
        if cfg_blob:
            cfg = json.loads(crypto.unseal(dek, cfg_blob, self._aad("config")))
        else:
            cfg = default_config()
        self.config = normalize_config(cfg)
        self.items = {}
        self.broken = []
        for row in self._store.items_all():
            try:
                data = json.loads(crypto.unseal(dek, row["blob"], self._aad("item", row["id"])))
            except (CryptoError, ValueError):
                self.broken.append(row["id"])
                continue
            self.items[row["id"]] = Record(row["id"], row["created_at"], row["updated_at"], row["used_at"],
                                           row["deleted_at"], normalize_item(data))
        self._dek = dek
        self._remember_stat()

    def lock(self) -> None:
        self._dek = None
        self.items = {}
        self.config = None
        if self._store:
            self._store.close()
            self._store = None

    def reload(self) -> None:
        """Re-read the file with the key in memory (after a change made elsewhere)."""
        if not self._dek:
            raise VaultLocked()
        old_id = self.vault_id
        dek = self._dek
        self._open(dek)
        if self.vault_id != old_id:
            self.lock()
            raise VaultLocked()
        self._notify("reload")

    # ---------------------------------------------------------------- freshness (Drive sync)
    def _file_stat(self) -> tuple[int, int] | None:
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size

    def _remember_stat(self) -> None:
        self._stat = self._file_stat()

    def _before_write(self) -> Store:
        if not self._dek or not self._store:
            raise VaultLocked()
        current = self._file_stat()
        if self._stat is not None and current is not None and current != self._stat:
            self.reload()
            raise VaultChanged()
        return self._store

    def _after_write(self, kind: str) -> None:
        self._remember_stat()
        self._notify(kind)

    def _notify(self, kind: str) -> None:
        for fn in list(self.listeners):
            fn(kind)

    # ---------------------------------------------------------------- keys & meta edits
    def change_password(self, new_password: str, kdf: dict | None = None) -> None:
        store = self._before_write()
        kdf = dict(kdf or self.kdf or DEFAULT_KDF)
        salt = crypto.random_bytes(crypto.SALT_LEN)
        kek = crypto.derive_password_key(new_password, salt, kdf)
        with store.tx():
            store.meta_set("kdf", json.dumps(kdf))
            store.meta_set("pw_salt", salt)
            store.meta_set("pw_wrap", crypto.seal(kek, self._dek, self._aad("dek", "pw")))
            store.meta_set("app_version", __version__)
        self._meta = store.meta_all()
        self._after_write("meta")

    def regenerate_recovery_key(self) -> str:
        store = self._before_write()
        text, raw = crypto.new_recovery_key()
        salt = crypto.random_bytes(crypto.SALT_LEN)
        with store.tx():
            store.meta_set("rk_salt", salt)
            store.meta_set("rk_wrap", crypto.seal(crypto.derive_recovery_key(raw, salt), self._dek,
                                                  self._aad("dek", "rk")))
            store.meta_set("rk_created_at", now_iso())
        self._meta = store.meta_all()
        self._after_write("meta")
        return text

    def set_meta_text(self, key: str, value: str) -> None:
        if key not in ("name", "hint"):
            raise KeyError(key)
        store = self._before_write()
        with store.tx():
            store.meta_set(key, value)
        self._meta = store.meta_all()
        self._after_write("meta")

    def save_config(self) -> None:
        store = self._before_write()
        self.config = normalize_config(self.config)
        with store.tx():
            store.meta_set("config", crypto.seal(self._dek, _dump(self.config), self._aad("config")))
        self._after_write("config")

    # ---------------------------------------------------------------- items
    def _seal_item(self, rec: Record) -> bytes:
        return crypto.seal(self._dek, _dump(rec.data), self._aad("item", rec.id))

    def _put(self, store: Store, rec: Record) -> None:
        store.item_put(rec.id, rec.created_at, rec.updated_at, rec.used_at, rec.deleted_at, self._seal_item(rec))

    def get(self, item_id: str) -> Record:
        return self.items[item_id]

    def add_item(self, data: dict) -> str:
        store = self._before_write()
        data = normalize_item(data)
        now = now_iso()
        if data["fields"].get("password") and not data.get("pw_changed_at"):
            data["pw_changed_at"] = now
        rec = Record(new_id(), now, now, None, None, data)
        with store.tx():
            self._put(store, rec)
        self.items[rec.id] = rec
        self._after_write("items")
        return rec.id

    def update_item(self, item_id: str, data: dict) -> None:
        store = self._before_write()
        rec = self.items[item_id]
        old = rec.data
        new = normalize_item(data)
        now = now_iso()
        labels = {f["key"]: f["label"] for f in item_fields(self.config, old, include_empty=True)}
        replaced = []
        for key, old_val in old["fields"].items():
            if not isinstance(old_val, str) or not old_val:
                continue
            if field_type_of(self.config, old, key) not in SECRET_TYPES:
                continue
            if new["fields"].get(key) != old_val:
                replaced.append((key, old_val))
        new_pw = new["fields"].get("password")
        if new_pw and new_pw != old["fields"].get("password"):
            new["pw_changed_at"] = now
        else:
            new["pw_changed_at"] = old.get("pw_changed_at", "")
        updated = Record(item_id, rec.created_at, now, rec.used_at, rec.deleted_at, new)
        with store.tx():
            for key, old_val in replaced:
                hid = new_id()
                entry = {"field": key, "label": labels.get(key, key), "value": old_val}
                store.hist_add(hid, item_id, now, crypto.seal(self._dek, _dump(entry),
                                                              self._aad("hist", item_id, hid)))
            self._put(store, updated)
        self.items[item_id] = updated
        self._after_write("items")

    def set_favorite(self, item_id: str, favorite: bool) -> None:
        data = dict(self.items[item_id].data)
        data["favorite"] = bool(favorite)
        store = self._before_write()
        rec = self.items[item_id]
        updated = Record(rec.id, rec.created_at, rec.updated_at, rec.used_at, rec.deleted_at, data)
        with store.tx():
            self._put(store, updated)
        self.items[item_id] = updated
        self._after_write("items")

    def trash_item(self, item_id: str) -> None:
        self._set_deleted(item_id, now_iso())

    def restore_item(self, item_id: str) -> None:
        self._set_deleted(item_id, None)

    def _set_deleted(self, item_id: str, ts: str | None) -> None:
        store = self._before_write()
        with store.tx():
            store.item_set_deleted(item_id, ts)
        self.items[item_id].deleted_at = ts
        self._after_write("items")

    def purge_item(self, item_id: str) -> None:
        store = self._before_write()
        with store.tx():
            store.item_delete(item_id)
        self.items.pop(item_id, None)
        self._after_write("items")

    def empty_trash(self) -> int:
        ids = [i for i, r in self.items.items() if r.trashed]
        if not ids:
            return 0
        store = self._before_write()
        with store.tx():
            for i in ids:
                store.item_delete(i)
        for i in ids:
            self.items.pop(i, None)
        self._after_write("items")
        return len(ids)

    def purge_expired(self, days: int) -> int:
        if days <= 0:
            return 0
        limit = datetime.now().astimezone() - timedelta(days=days)
        ids = [i for i, r in self.items.items()
               if r.trashed and (parse_iso(r.deleted_at) or limit) < limit]
        if not ids:
            return 0
        store = self._before_write()
        with store.tx():
            for i in ids:
                store.item_delete(i)
        for i in ids:
            self.items.pop(i, None)
        self._after_write("items")
        return len(ids)

    def mark_used(self, item_id: str) -> None:
        if not self._dek or not self._store or item_id not in self.items:
            return
        try:
            store = self._before_write()
        except VaultChanged:
            return
        ts = now_iso()
        with store.tx():
            store.item_set_used(item_id, ts)
        self.items[item_id].used_at = ts
        self._after_write("used")

    def secret_history(self, item_id: str) -> list[dict]:
        if not self._dek or not self._store:
            raise VaultLocked()
        out = []
        for row in self._store.hist_for(item_id):
            try:
                entry = json.loads(crypto.unseal(self._dek, row["blob"], self._aad("hist", item_id, row["id"])))
            except (CryptoError, ValueError):
                continue
            entry["changed_at"] = row["changed_at"]
            out.append(entry)
        return out

    def import_items(self, entries: list[dict]) -> list[str]:
        """Bulk insert for migration. entry = {data, created_at, updated_at, history: [{field,label,value,changed_at,note}]}"""
        store = self._before_write()
        ids = []
        with store.tx():
            for e in entries:
                data = normalize_item(e["data"])
                created = e.get("created_at") or now_iso()
                updated = e.get("updated_at") or created
                rec = Record(new_id(), created, updated, None, None, data)
                self._put(store, rec)
                for h in e.get("history", []):
                    hid = new_id()
                    entry = {k: h[k] for k in ("field", "label", "value", "note") if k in h}
                    store.hist_add(hid, rec.id, h.get("changed_at") or updated,
                                   crypto.seal(self._dek, _dump(entry), self._aad("hist", rec.id, hid)))
                self.items[rec.id] = rec
                ids.append(rec.id)
        self._after_write("items")
        return ids

    # ---------------------------------------------------------------- backups
    def store_for_backup(self) -> Store | None:
        return self._store


def restore_from_backup(vault_path: Path, backup_path: Path, safety_dir: Path) -> Path:
    """Replace the vault file with a backup of the same vault. Returns the safety copy of the current file."""
    vault_path, backup_path = Path(vault_path), Path(backup_path)
    current = Vault(vault_path)
    candidate = Vault(backup_path)
    if candidate.vault_id != current.vault_id:
        raise NotAVault("backup belongs to a different vault")
    safety_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety = safety_dir / f"{vault_path.stem}_before_restore_{stamp}{vault_path.suffix}"
    shutil.copy2(vault_path, safety)
    tmp = vault_path.with_suffix(vault_path.suffix + ".restoring")
    shutil.copy2(backup_path, tmp)
    os.replace(tmp, vault_path)
    return safety
