"""SQLite layer for .kinko vault files. Knows nothing about encryption."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

APPLICATION_ID = 0x4B494E4B  # "KINK"
FORMAT = "kinko-vault"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value BLOB
);
CREATE TABLE IF NOT EXISTS items (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    used_at    TEXT,
    deleted_at TEXT,
    blob       BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id         TEXT PRIMARY KEY,
    item_id    TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    blob       BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS history_item ON history(item_id);
"""


class StoreError(Exception):
    pass


class Store:
    def __init__(self, path: str | Path, readonly: bool = False):
        self.path = Path(path)
        if readonly:
            uri = self.path.resolve().as_uri() + "?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
        else:
            self.conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
            self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.row_factory = sqlite3.Row
        self._depth = 0

    @classmethod
    def create(cls, path: str | Path) -> "Store":
        path = Path(path)
        if path.exists():
            raise StoreError(f"{path} already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        store = cls(path)
        store.conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
        store.conn.execute("PRAGMA user_version=1")
        store.conn.executescript(_SCHEMA)
        return store

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    def is_vault(self) -> bool:
        try:
            app_id = self.conn.execute("PRAGMA application_id").fetchone()[0]
            if app_id != APPLICATION_ID:
                return False
            return self.meta_get("format") == FORMAT
        except sqlite3.Error:
            return False

    @contextmanager
    def tx(self) -> Iterator[None]:
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")
        finally:
            self._depth = 0

    # ---------------------------------------------------------------- meta
    def meta_get(self, key: str):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return None if row is None else row[0]

    def meta_set(self, key: str, value) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value))

    def meta_all(self) -> dict:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT key, value FROM meta")}

    # ---------------------------------------------------------------- items
    def items_all(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM items"))

    def item_put(self, item_id: str, created_at: str, updated_at: str, used_at: str | None,
                 deleted_at: str | None, blob: bytes) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO items(id, created_at, updated_at, used_at, deleted_at, blob) "
            "VALUES(?, ?, ?, ?, ?, ?)", (item_id, created_at, updated_at, used_at, deleted_at, blob))

    def item_set_used(self, item_id: str, ts: str) -> None:
        self.conn.execute("UPDATE items SET used_at=? WHERE id=?", (ts, item_id))

    def item_set_deleted(self, item_id: str, ts: str | None) -> None:
        self.conn.execute("UPDATE items SET deleted_at=? WHERE id=?", (ts, item_id))

    def item_delete(self, item_id: str) -> None:
        self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.execute("DELETE FROM history WHERE item_id=?", (item_id,))

    # ---------------------------------------------------------------- history
    def hist_add(self, hist_id: str, item_id: str, changed_at: str, blob: bytes) -> None:
        self.conn.execute("INSERT INTO history(id, item_id, changed_at, blob) VALUES(?, ?, ?, ?)",
                          (hist_id, item_id, changed_at, blob))

    def hist_for(self, item_id: str) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM history WHERE item_id=? ORDER BY changed_at DESC", (item_id,)))

    # ---------------------------------------------------------------- backup
    def backup_to(self, dest: str | Path) -> None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(dest))
        try:
            self.conn.backup(target)
        finally:
            target.close()
