import json
import tempfile
import unittest
from pathlib import Path

from app.snapshot_watcher import SnapshotWatcher


class SnapshotWatcherTests(unittest.TestCase):
    def test_new_snapshot_triggers_one_api_pull_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "incoming"
            archive = root / "archive"
            db = root / "memeos.sqlite3"
            incoming.mkdir()
            (incoming / "solana-pool_2026-09-28_19-21-02.png").write_bytes(b"png")
            calls = []

            def fake_fetch(wallet, chain, limit, max_pages):
                calls.append((wallet, chain, limit, max_pages))
                return [{
                    "wallet": wallet,
                    "chain": chain,
                    "tx_hash": "tx-1",
                    "timestamp": 1790600000,
                    "event_type": "buy",
                    "token": {"address": "mint-1", "symbol": "TEST"},
                    "token_amount": "1",
                    "cost_usd": "10",
                    "quote_amount": "0.1",
                }]

            watcher = SnapshotWatcher(db, incoming, archive, "wallet-1", fetcher=fake_fetch)
            first = watcher.process_once()
            second = watcher.process_once()

            self.assertEqual(first["new_snapshots"], 1)
            self.assertEqual(first["api_pulls"], 1)
            self.assertEqual(first["new_activities"], 1)
            self.assertEqual(second["new_snapshots"], 0)
            self.assertEqual(second["api_pulls"], 0)
            self.assertEqual(len(calls), 1)
            self.assertTrue((incoming / "solana-pool_2026-09-28_19-21-02.png").exists())

    def test_no_snapshot_means_no_api_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "incoming"
            incoming.mkdir()
            calls = []

            def fake_fetch(*args):
                calls.append(args)
                return []

            watcher = SnapshotWatcher(root / "db.sqlite3", incoming, root / "archive", "wallet", fetcher=fake_fetch)
            result = watcher.process_once()

            self.assertEqual(result, {"new_snapshots": 0, "api_pulls": 0, "new_activities": 0})
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
