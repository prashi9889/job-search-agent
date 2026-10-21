"""Append-only audit history stored in a local SQLite database."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    subject TEXT NOT NULL,
    details TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
"""


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def record(self, action: str, subject: str, details: dict | None = None, actor: str = "agent") -> int:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO audit (ts, actor, action, subject, details) VALUES (?, ?, ?, ?, ?)",
                (ts, actor, action, subject, json.dumps(details or {}, sort_keys=True)),
            )
        return cur.lastrowid

    def recent(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{**dict(r), "details": json.loads(r["details"])} for r in rows]

    def close(self) -> None:
        self._conn.close()
