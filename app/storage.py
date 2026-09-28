"""SQLite persistence for GMGN refreshes and raw wallet activity."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class RefreshStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY,
                    wallet TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(wallet, chain, tx_hash, token_address, event_type, timestamp)
                );
                CREATE INDEX IF NOT EXISTS idx_activities_window
                    ON activities(wallet, chain, timestamp);
                CREATE TABLE IF NOT EXISTS refreshes (
                    id INTEGER PRIMARY KEY,
                    wallet TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    session_start INTEGER,
                    session_end INTEGER,
                    fetched_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    activity_count INTEGER NOT NULL,
                    next_cursor TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_refreshes_wallet
                    ON refreshes(wallet, chain, fetched_at);
                """
            )

    def save_activities(self, activities: list[dict[str, Any]]) -> int:
        inserted = 0
        with self._connect() as connection:
            for activity in activities:
                token = activity.get("token") or {}
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO activities
                    (wallet, chain, tx_hash, token_address, event_type, timestamp, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        activity.get("wallet", ""),
                        activity.get("chain", ""),
                        activity.get("tx_hash", ""),
                        token.get("address", ""),
                        activity.get("event_type", ""),
                        int(activity.get("timestamp", 0)),
                        json.dumps(activity, separators=(",", ":")),
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def count_activities(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0])

    def activities_between(
        self,
        wallet: str,
        chain: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["wallet = ?", "chain = ?"]
        params: list[Any] = [wallet, chain]
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(start)
        if end is not None:
            clauses.append("timestamp < ?")
            params.append(end)
        query = f"SELECT payload_json FROM activities WHERE {' AND '.join(clauses)} ORDER BY timestamp ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def record_refresh(
        self,
        wallet: str,
        chain: str,
        session_start: int | None,
        session_end: int | None,
        activity_count: int,
        next_cursor: str | None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO refreshes
                (wallet, chain, session_start, session_end, activity_count, next_cursor)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (wallet, chain, session_start, session_end, activity_count, next_cursor),
            )
            return int(cursor.lastrowid)

    def latest_checkpoint(self, wallet: str, chain: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM refreshes
                WHERE wallet = ? AND chain = ?
                ORDER BY fetched_at DESC, id DESC
                LIMIT 1
                """,
                (wallet, chain),
            ).fetchone()
        return dict(row) if row else None
