import tempfile
import unittest
from pathlib import Path

from app.storage import RefreshStore


class RefreshStoreTests(unittest.TestCase):
    def test_activity_insert_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RefreshStore(Path(directory) / "review.sqlite3")
            activity = {
                "wallet": "wallet",
                "chain": "sol",
                "tx_hash": "tx1",
                "timestamp": 100,
                "event_type": "buy",
                "token": {"address": "token", "symbol": "TEST"},
            }

            self.assertEqual(store.save_activities([activity]), 1)
            self.assertEqual(store.save_activities([activity]), 0)
            self.assertEqual(store.count_activities(), 1)

    def test_session_window_returns_only_matching_activities(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RefreshStore(Path(directory) / "review.sqlite3")
            activities = [
                {
                    "wallet": "wallet",
                    "chain": "sol",
                    "tx_hash": f"tx{i}",
                    "timestamp": i,
                    "event_type": "buy",
                    "token": {"address": "token", "symbol": "TEST"},
                }
                for i in range(1, 5)
            ]
            store.save_activities(activities)

            result = store.activities_between("wallet", "sol", 2, 4)

            self.assertEqual([row["timestamp"] for row in result], [2, 3])

    def test_refresh_record_and_checkpoint_are_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RefreshStore(Path(directory) / "review.sqlite3")
            refresh_id = store.record_refresh(
                wallet="wallet",
                chain="sol",
                session_start=100,
                session_end=200,
                activity_count=3,
                next_cursor="cursor-1",
            )

            self.assertIsInstance(refresh_id, int)
            checkpoint = store.latest_checkpoint("wallet", "sol")
            self.assertEqual(checkpoint["next_cursor"], "cursor-1")
            self.assertEqual(checkpoint["session_start"], 100)


if __name__ == "__main__":
    unittest.main()
