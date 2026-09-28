"""Dependency-free SVG trade charts for local review and Notion upload."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


WIDTH = 1200
HEIGHT = 700
LEFT = 80
RIGHT = 30
TOP = 70
BOTTOM = 70


def _value(candle: dict[str, Any], *names: str) -> float:
    for name in names:
        if name in candle and candle[name] is not None:
            return float(candle[name])
    raise ValueError(f"Candle is missing any of {names}: {candle}")


def _timestamp(candle: dict[str, Any]) -> int:
    return int(_value(candle, "time", "timestamp", "unix_time"))


def render_trade_chart(
    candles: list[dict[str, Any]], trade: dict[str, Any], output: str | Path
) -> Path:
    """Render OHLC candles and average entry/exit markers as an SVG."""
    if not candles:
        raise ValueError("Cannot render a chart without candles")
    candles = sorted(candles, key=_timestamp)
    timestamps = [_timestamp(candle) for candle in candles]
    lows = [_value(candle, "low", "l") for candle in candles]
    highs = [_value(candle, "high", "h") for candle in candles]
    prices = lows + highs
    low, high = min(prices), max(prices)
    if high == low:
        high += 1
        low -= 1
    x0, x1 = LEFT, WIDTH - RIGHT
    y0, y1 = TOP, HEIGHT - BOTTOM
    t0, t1 = min(timestamps), max(timestamps)
    if t1 == t0:
        t1 += 1

    def x(timestamp: float) -> float:
        return x0 + (float(timestamp) - t0) / (t1 - t0) * (x1 - x0)

    def y(price: float) -> float:
        return y1 - (float(price) - low) / (high - low) * (y1 - y0)

    candle_width = max(2.0, (x1 - x0) / max(len(candles) * 2.5, 1))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        f'<text x="{LEFT}" y="32" fill="#f9fafb" font-size="22" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{escape(str(trade.get("symbol") or "Trade"))} trade review</text>',
        f'<text x="{LEFT}" y="55" fill="#9ca3af" font-size="13" font-family="-apple-system,BlinkMacSystemFont,sans-serif">Net P&amp;L: ${float(trade.get("net_pnl_usd") or 0):.2f} · {len(candles)} candles</text>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#4b5563"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#4b5563"/>',
    ]

    for candle in candles:
        ts = _timestamp(candle)
        op = _value(candle, "open", "o")
        cl = _value(candle, "close", "c")
        hi = _value(candle, "high", "h")
        lo = _value(candle, "low", "l")
        color = "#22c55e" if cl >= op else "#ef4444"
        cx = x(ts)
        body_top = y(max(op, cl))
        body_height = max(1.0, abs(y(op) - y(cl)))
        parts.append(f'<line x1="{cx:.2f}" y1="{y(hi):.2f}" x2="{cx:.2f}" y2="{y(lo):.2f}" stroke="{color}" stroke-width="1.5"/>')
        parts.append(f'<rect x="{cx - candle_width / 2:.2f}" y="{body_top:.2f}" width="{candle_width:.2f}" height="{body_height:.2f}" fill="{color}" opacity="0.9"/>')

    markers = [(trade.get("opened_at"), trade.get("average_entry_usd"), "Entry", "#60a5fa"), (trade.get("closed_at"), trade.get("average_exit_usd"), "Exit", "#fbbf24")]
    for timestamp, price, label, color in markers:
        if timestamp is None or price is None:
            continue
        mx, my = x(float(timestamp)), y(float(price))
        parts.append(f'<line x1="{mx:.2f}" y1="{y0}" x2="{mx:.2f}" y2="{y1}" stroke="{color}" stroke-dasharray="6 4" stroke-width="2"/>')
        parts.append(f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="6" fill="{color}" stroke="#111827" stroke-width="2"/>')
        parts.append(f'<text x="{mx + 8:.2f}" y="{max(y0 + 16, my - 10):.2f}" fill="{color}" font-size="14" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{label}</text>')

    parts.append(f'<text x="{x0}" y="{HEIGHT - 22}" fill="#9ca3af" font-size="12" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{t0}</text>')
    parts.append(f'<text x="{x1 - 90}" y="{HEIGHT - 22}" fill="#9ca3af" font-size="12" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{t1}</text>')
    parts.append('</svg>')
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts))
    return destination
