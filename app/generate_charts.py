#!/usr/bin/env python3
"""Fetch market candles and render charts for candidate trades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.charting import render_trade_chart
from app.market_data import fetch_birdeye_candles, fetch_candles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/wallet_refresh.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/charts"))
    parser.add_argument("--source", choices=["gmgn", "birdeye"], default="gmgn")
    parser.add_argument("--resolution", default="30s", choices=["1s", "15s", "30s", "1m", "5m", "15m"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--padding", type=int, default=120, help="Seconds around the trade")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    rendered = 0
    skipped = 0
    for trade in payload.get("trades", [])[: args.limit]:
        if trade.get("status") != "closed" or not trade.get("closed_at"):
            skipped += 1
            continue
        start = max(0, int(trade["opened_at"]) - args.padding)
        end = int(trade["closed_at"]) + args.padding
        try:
            fetcher = fetch_birdeye_candles if args.source == "birdeye" else fetch_candles
            candles = fetcher(
                address=trade["token_address"],
                chain=trade.get("chain", "sol"),
                start=start,
                end=end,
                resolution=args.resolution,
            )
            if not candles:
                print(f"Skipping {trade['trade_id']}: no candle data", file=sys.stderr)
                skipped += 1
                continue
            output = args.output_dir / f"{trade['trade_id'].replace(':', '_')}.svg"
            render_trade_chart(candles, trade, output)
            rendered += 1
            print(f"Rendered {output} ({len(candles)} candles)")
        except (RuntimeError, KeyError, ValueError) as exc:
            print(f"Skipping {trade.get('trade_id', 'unknown')}: {exc}", file=sys.stderr)
            skipped += 1

    print(f"Charts rendered: {rendered}; skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
