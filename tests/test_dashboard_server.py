import json
import tempfile
import unittest
from pathlib import Path

from app.dashboard_server import build_dashboard_state
from app.snapshot_manager import SnapshotManager
from app.storage import RefreshStore


class DashboardServerTests(unittest.TestCase):
    def _seed(self, tmp: str) -> Path:
        root = Path(tmp)
        db = root / "memeos.sqlite3"
        payload = json.loads(Path("data/wallet_refresh_m1.json").read_text())
        RefreshStore(db).save_activities(payload["activities"])
        incoming = root / "incoming"
        archive = root / "archive"
        incoming.mkdir()
        sample = incoming / "solana-example_2026-09-27_19-21-02.png"
        sample.write_bytes(b"fixture")
        SnapshotManager(db, incoming, archive).ingest(sample)
        return db

    def test_unmatched_sell_is_not_counted_as_pnl(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = build_dashboard_state(self._seed(tmp))

        self.assertEqual(state["trade_count"], 3)
        self.assertEqual(state["unmatched_count"], 1)
        self.assertAlmostEqual(state["confirmed_mechanical_net_usd"], -74.94919718453, places=6)
        unmatched = next(t for t in state["trades"] if t["status"] == "unmatched_sell")
        self.assertIsNone(unmatched["gross_pnl_usd"])
        self.assertIsNone(unmatched["net_pnl_usd"])

    def test_dashboard_state_exposes_pending_snapshot_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = build_dashboard_state(self._seed(tmp))

        self.assertEqual(state["snapshot_count"], 1)
        self.assertEqual(state["pending_snapshot_count"], 1)
        self.assertEqual(state["snapshots"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
