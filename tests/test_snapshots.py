import tempfile
import unittest
from pathlib import Path

from app.snapshot_manager import SnapshotManager


class SnapshotManagerTests(unittest.TestCase):
    def test_ingests_snapshot_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming"
            archive = root / "archive"
            incoming.mkdir()
            source = incoming / "solana-TOKEN_2026-09-27_19-21-02.png"
            source.write_bytes(b"fake png")
            manager = SnapshotManager(root / "snapshots.sqlite3", incoming, archive)

            snapshot = manager.ingest(source)

            self.assertEqual(snapshot["status"], "pending")
            self.assertTrue(source.exists())
            self.assertFalse((archive / source.name).exists())

    def test_marks_uploaded_only_after_copying_to_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming"
            archive = root / "archive"
            incoming.mkdir()
            source = incoming / "solana-TOKEN_2026-09-27_19-21-02.png"
            source.write_bytes(b"fake png")
            manager = SnapshotManager(root / "snapshots.sqlite3", incoming, archive)
            snapshot = manager.ingest(source)

            manager.mark_uploaded(snapshot["snapshot_id"], "notion-page-1")

            self.assertFalse(source.exists())
            self.assertTrue((archive / source.name).exists())
            saved = manager.get(snapshot["snapshot_id"])
            self.assertEqual(saved["status"], "uploaded")
            self.assertEqual(saved["notion_page_id"], "notion-page-1")

    def test_same_file_is_not_ingested_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming"
            archive = root / "archive"
            incoming.mkdir()
            source = incoming / "solana-TOKEN_2026-09-27_19-21-02.png"
            source.write_bytes(b"fake png")
            manager = SnapshotManager(root / "snapshots.sqlite3", incoming, archive)

            first = manager.ingest(source)
            second = manager.ingest(source)

            self.assertEqual(first["snapshot_id"], second["snapshot_id"])
            self.assertEqual(manager.count(), 1)


if __name__ == "__main__":
    unittest.main()
