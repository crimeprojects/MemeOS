"""Safe ingestion and lifecycle management for terminal chart snapshots."""

from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FILENAME_RE = re.compile(
    r"^(?P<chain>[^-]+)-(?P<address>.+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2}-\d{2})\.png$"
)


class SnapshotManager:
    def __init__(self, database: str | Path, incoming: str | Path, archive: str | Path):
        self.database = Path(database)
        self.incoming = Path(incoming)
        self.archive = Path(archive)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.incoming.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    archive_path TEXT,
                    sha256 TEXT NOT NULL UNIQUE,
                    chain TEXT,
                    token_or_address TEXT,
                    captured_at TEXT,
                    status TEXT NOT NULL,
                    notion_page_id TEXT,
                    ingested_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _metadata(path: Path) -> tuple[str | None, str | None, str | None]:
        match = FILENAME_RE.match(path.name)
        if not match:
            return None, None, None
        captured = f"{match.group('date')}T{match.group('time').replace('-', ':')}"
        return match.group("chain"), match.group("address"), captured

    def ingest(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        sha256 = self._sha256(source)
        chain, token_or_address, captured_at = self._metadata(source)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM snapshots WHERE sha256 = ?", (sha256,)
            ).fetchone()
            if existing:
                return dict(existing)
            cursor = connection.execute(
                """
                INSERT INTO snapshots
                (filename, source_path, sha256, chain, token_or_address, captured_at,
                 status, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    source.name,
                    str(source),
                    sha256,
                    chain,
                    token_or_address,
                    captured_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            snapshot_id = int(cursor.lastrowid)
        return self.get(snapshot_id)

    def ingest_incoming(self) -> list[dict[str, Any]]:
        snapshots = []
        for path in sorted(self.incoming.glob("*.png")):
            snapshots.append(self.ingest(path))
        return snapshots

    def mark_uploaded(self, snapshot_id: int, notion_page_id: str) -> None:
        snapshot = self.get(snapshot_id)
        if not snapshot:
            raise KeyError(snapshot_id)
        source = Path(snapshot["source_path"])
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = self.archive / snapshot["filename"]
        shutil.copy2(source, destination)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE snapshots
                SET archive_path = ?, status = 'uploaded', notion_page_id = ?
                WHERE snapshot_id = ?
                """,
                (str(destination), notion_page_id, snapshot_id),
            )
        source.unlink()

    def get(self, snapshot_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0])
