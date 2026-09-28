#!/usr/bin/env python3
"""Local, read-only MemeOS dashboard server."""
from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.storage import RefreshStore
from app.trade_review import group_activities

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "memeos.sqlite3"
DEFAULT_HTML = PROJECT_ROOT / "dashboard" / "index.html"
DEFAULT_SNAPSHOT_DIR = Path.home() / "Downloads" / "trade snapshots"


def _snapshot_rows(db: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM snapshots ORDER BY snapshot_id DESC").fetchall()
    return [dict(row) for row in rows]


def _safe_trade(trade: dict[str, Any]) -> dict[str, Any]:
    result = dict(trade)
    # An unmatched sell has no cost basis. Sale proceeds are not P&L.
    if result.get("status") == "unmatched_sell":
        result["gross_pnl_usd"] = None
        result["net_pnl_usd"] = None
        result["data_quality"] = "unmatched"
    return result


def build_dashboard_state(db: str | Path = DEFAULT_DB) -> dict[str, Any]:
    db_path = Path(db)
    store = RefreshStore(db_path)
    with sqlite3.connect(db_path) as connection:
        wallet_row = connection.execute("SELECT wallet FROM activities ORDER BY id LIMIT 1").fetchone()
    wallet = wallet_row[0] if wallet_row else None
    activities = store.activities_between(wallet, "sol") if wallet else []
    trades = [_safe_trade(trade) for trade in group_activities(activities)]
    closed = [trade for trade in trades if trade.get("status") == "closed"]
    mechanical_net = sum(float(trade["net_pnl_usd"]) for trade in closed if trade.get("net_pnl_usd") is not None)
    snapshots = _snapshot_rows(db_path) if db_path.exists() else []
    pending = sum(row.get("status") == "pending" for row in snapshots)
    checkpoint = store.latest_checkpoint(wallet, "sol") if wallet else None
    return {
        "wallet": wallet,
        "chain": "sol",
        "activity_count": len(activities),
        "trade_count": len(trades),
        "closed_count": len(closed),
        "unmatched_count": sum(trade.get("status") == "unmatched_sell" for trade in trades),
        "confirmed_mechanical_net_usd": mechanical_net,
        "snapshot_count": len(snapshots),
        "pending_snapshot_count": pending,
        "latest_refresh": checkpoint,
        "trades": trades,
        "snapshots": snapshots,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB
    html_path = DEFAULT_HTML

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = self.html_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/health":
            self._send_json({"ok": True, "mode": "local-read-only", "database": str(self.db_path)})
            return
        if path in ("/api/overview", "/api/state"):
            self._send_json(build_dashboard_state(self.db_path))
            return
        self._send_json({"error": "not found"}, 404)

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8765, db: Path = DEFAULT_DB) -> None:
    DashboardHandler.db_path = db
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"MemeOS dashboard: http://{host}:{port}")
    print("Mode: local read-only; no Notion writes or file deletes")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MemeOS dashboard")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    serve(args.host, args.port, args.db)
