#!/usr/bin/env python3
"""Watch terminal snapshots and pull matching wallet activity locally."""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from app.refresh import fetch_activity
from app.snapshot_manager import SnapshotManager
from app.storage import RefreshStore

DEFAULT_WALLET = os.environ.get("MEMEOS_WALLET", "")
DEFAULT_INCOMING = Path.home() / "Downloads" / "trade snapshots"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = PROJECT_ROOT / "data" / "processed-snapshots"
DEFAULT_DB = PROJECT_ROOT / "data" / "memeos.sqlite3"
Fetcher = Callable[[str, str, int, int], list[dict[str, Any]]]


class SnapshotWatcher:
    def __init__(
        self,
        database: str | Path,
        incoming: str | Path,
        archive: str | Path,
        wallet: str,
        chain: str = "sol",
        fetcher: Fetcher = fetch_activity,
        limit: int = 50,
        max_pages: int = 10,
    ) -> None:
        self.database = Path(database)
        self.incoming = Path(incoming)
        self.archive = Path(archive)
        self.wallet = wallet
        self.chain = chain
        self.fetcher = fetcher
        self.limit = limit
        self.max_pages = max_pages
        self.manager = SnapshotManager(self.database, self.incoming, self.archive)
        self.store = RefreshStore(self.database)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _known_hashes(self) -> set[str]:
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute("SELECT sha256 FROM snapshots").fetchall()
        return {row[0] for row in rows}

    def _new_files(self) -> list[Path]:
        known = self._known_hashes()
        return [path for path in sorted(self.incoming.glob("*.png")) if self._sha256(path) not in known]

    def process_once(self) -> dict[str, int]:
        new_files = self._new_files()
        if not new_files:
            return {"new_snapshots": 0, "api_pulls": 0, "new_activities": 0}

        # Pull before registering the files so a transient GMGN failure leaves
        # the PNG eligible for retry on the next loop.
        # One wallet pull serves the whole newly detected batch. Raw activity is
        # deduplicated by SQLite; no AI or Notion call occurs here.
        activities = self.fetcher(self.wallet, self.chain, self.limit, self.max_pages)
        for path in new_files:
            self.manager.ingest(path)
        inserted = self.store.save_activities(activities)
        return {"new_snapshots": len(new_files), "api_pulls": 1, "new_activities": inserted}

    def watch(self, interval: float = 5.0) -> None:
        print(f"Watching {self.incoming}")
        print(f"Wallet: {self.wallet} | chain: {self.chain}")
        print("Mode: local collection only; no AI, Notion writes, or file deletes")
        while True:
            try:
                result = self.process_once()
                if result["new_snapshots"]:
                    print(result)
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nStopping snapshot watcher")
                return
            except Exception as exc:  # keep the watcher alive after transient API errors
                print(f"Watcher error: {exc}")
                time.sleep(max(interval, 60.0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--chain", default="sol")
    parser.add_argument("--incoming", type=Path, default=DEFAULT_INCOMING)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()
    watcher = SnapshotWatcher(args.db, args.incoming, args.archive, args.wallet, args.chain, limit=args.limit, max_pages=args.max_pages)
    if args.once:
        print(watcher.process_once())
    else:
        watcher.watch(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
