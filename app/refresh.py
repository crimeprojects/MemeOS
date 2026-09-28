#!/usr/bin/env python3
"""Fetch read-only GMGN activity and produce grouped candidate trades."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.trade_review import group_activities
from app.storage import RefreshStore


def fetch_activity(wallet: str, chain: str, limit: int, max_pages: int) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []
    cursor = ""
    for _ in range(max_pages):
        command = [
            "gmgn-cli", "portfolio", "activity",
            "--chain", chain,
            "--wallet", wallet,
            "--limit", str(limit),
            "--raw",
        ]
        if cursor:
            command.extend(["--cursor", cursor])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "GMGN request failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GMGN returned invalid JSON: {exc}") from exc
        if payload.get("code") not in (None, 0):
            raise RuntimeError(payload.get("message") or f"GMGN error code {payload['code']}")
        page = payload.get("activities", [])
        activities.extend(page)
        cursor = payload.get("next") or ""
        if not cursor or not page:
            break
    return activities


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", required=True, help="Public wallet address")
    parser.add_argument("--chain", default="sol")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--since", type=int, help="Only include events at/after Unix timestamp")
    parser.add_argument("--until", type=int, help="Only include events before Unix timestamp")
    parser.add_argument("--output", type=Path, default=Path("data/latest_refresh.json"))
    parser.add_argument("--db", type=Path, default=Path("data/memeos.sqlite3"))
    args = parser.parse_args()

    activities = fetch_activity(args.wallet, args.chain, args.limit, args.max_pages)
    if args.since is not None:
        activities = [a for a in activities if int(a.get("timestamp", 0)) >= args.since]
    if args.until is not None:
        activities = [a for a in activities if int(a.get("timestamp", 0)) < args.until]

    store = RefreshStore(args.db)
    inserted = store.save_activities(activities)
    session_activities = store.activities_between(args.wallet, args.chain, args.since, args.until)
    trades = group_activities(session_activities)
    store.record_refresh(
        wallet=args.wallet,
        chain=args.chain,
        session_start=args.since,
        session_end=args.until,
        activity_count=len(activities),
        next_cursor=None,
    )
    result = {
        "wallet": args.wallet,
        "chain": args.chain,
        "refreshed_at": int(time.time()),
        "activity_count": len(session_activities),
        "new_activity_count": inserted,
        "trade_count": len(trades),
        "activities": session_activities,
        "trades": trades,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")

    closed = sum(t["status"] == "closed" for t in trades)
    open_count = sum(t["status"] == "open" for t in trades)
    unmatched = sum(t["status"] == "unmatched_sell" for t in trades)
    net_pnl = sum(t["net_pnl_usd"] for t in trades)
    print(f"Fetched {len(activities)} activities ({inserted} new)")
    print(f"Session contains {len(session_activities)} stored activities")
    print(f"Grouped {len(trades)} candidate trades ({closed} closed, {open_count} open, {unmatched} unmatched)")
    print(f"Candidate net P&L: ${net_pnl:.2f}")
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("Interrupted")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
