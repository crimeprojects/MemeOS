"""GMGN and Birdeye market-data adapters."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def normalize_candles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candles = []
    for raw in payload.get("list", []):
        timestamp = int(float(raw["time"]))
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        candles.append(
            {
                "time": timestamp,
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "volume": float(raw.get("volume", 0)),
            }
        )
    return sorted(candles, key=lambda candle: candle["time"])


def normalize_birdeye_candles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candles = []
    for raw in (payload.get("data") or {}).get("items", []):
        candles.append(
            {
                "time": int(raw["unix_time"]),
                "open": float(raw["o"]),
                "high": float(raw["h"]),
                "low": float(raw["l"]),
                "close": float(raw["c"]),
                "volume": float(raw.get("v", 0)),
            }
        )
    return sorted(candles, key=lambda candle: candle["time"])


def fetch_candles(
    address: str,
    chain: str,
    start: int,
    end: int,
    resolution: str = "30s",
) -> list[dict[str, Any]]:
    command = [
        "gmgn-cli", "market", "kline",
        "--chain", chain,
        "--address", address,
        "--resolution", resolution,
        "--from", str(max(0, start)),
        "--to", str(max(start + 1, end)),
        "--raw",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "GMGN K-line request failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GMGN K-line returned invalid JSON: {exc}") from exc
    if payload.get("code") not in (None, 0):
        raise RuntimeError(payload.get("message") or f"GMGN K-line error code {payload['code']}")
    return normalize_candles(payload)


def _birdeye_key() -> str:
    if os.environ.get("BIRDEYE_API_KEY"):
        return os.environ["BIRDEYE_API_KEY"]
    env_path = Path.home() / ".config/birdeye/.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("BIRDEYE_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("BIRDEYE_API_KEY is not configured")


def fetch_birdeye_candles(
    address: str,
    chain: str,
    start: int,
    end: int,
    resolution: str = "15s",
) -> list[dict[str, Any]]:
    chain_header = {"sol": "solana", "solana": "solana"}.get(chain, chain)
    params = urllib.parse.urlencode(
        {
            "address": address,
            "type": resolution,
            "time_from": max(0, start),
            "time_to": max(start + 1, end),
            "currency": "usd",
            "mode": "range",
        }
    )
    request = urllib.request.Request(
        "https://public-api.birdeye.so/defi/v3/ohlcv?" + params,
        headers={"X-API-KEY": _birdeye_key(), "x-chain": chain_header},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        raise RuntimeError(f"Birdeye OHLCV request failed: {exc}") from exc
    if not payload.get("success"):
        raise RuntimeError(payload.get("message") or "Birdeye OHLCV request failed")
    return normalize_birdeye_candles(payload)
