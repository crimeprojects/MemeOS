"""Normalize GMGN wallet activity into candidate position trades."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _token_key(activity: dict[str, Any]) -> str:
    token = activity.get("token") or {}
    return str(token.get("address") or token.get("symbol") or "unknown")


def _timestamp(value: Any) -> int:
    return int(_float(value))


def _new_trade(activity: dict[str, Any], sequence: int) -> dict[str, Any]:
    token = activity.get("token") or {}
    return {
        "trade_id": f"{_token_key(activity)}:{sequence}",
        "token_address": token.get("address"),
        "symbol": token.get("symbol"),
        "chain": activity.get("chain", "sol"),
        "status": "open",
        "opened_at": _timestamp(activity.get("timestamp")),
        "closed_at": None,
        "quantity_bought": 0.0,
        "quantity_sold": 0.0,
        "buy_cost_usd": 0.0,
        "sell_income_usd": 0.0,
        "fees_usd": 0.0,
        "gross_pnl_usd": 0.0,
        "net_pnl_usd": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "has_multiple_entries": False,
        "has_partial_exits": False,
        "buy_tx_hashes": [],
        "sell_tx_hashes": [],
        "unmatched_sell_quantity": 0.0,
    }


def _add_fee(activity: dict[str, Any]) -> float:
    return _float(activity.get("gas_usd")) + _float(activity.get("dex_usd"))


def group_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group chronological buys/sells by token into position lifecycles.

    This is deliberately conservative: it groups consecutive inventory into one
    trade and starts a new trade only after the position reaches zero. Sells
    without a matching buy in the supplied window are retained as unmatched.
    """
    ordered = sorted(activities, key=lambda item: _timestamp(item.get("timestamp")))
    active: dict[str, dict[str, Any]] = {}
    lots: dict[str, deque[dict[str, float]]] = {}
    completed: list[dict[str, Any]] = []
    sequence: dict[str, int] = {}

    for activity in ordered:
        event = str(activity.get("event_type", "")).lower()
        if event not in {"buy", "sell"}:
            continue
        key = _token_key(activity)
        qty = _float(activity.get("token_amount"))
        value = _float(activity.get("cost_usd"))
        if qty <= 0:
            continue

        if event == "buy":
            if key not in active:
                sequence[key] = sequence.get(key, 0) + 1
                active[key] = _new_trade(activity, sequence[key])
                lots[key] = deque()
            trade = active[key]
            trade["quantity_bought"] += qty
            trade["buy_cost_usd"] += value
            trade["buy_count"] += 1
            trade["has_multiple_entries"] = trade["buy_count"] > 1
            trade["fees_usd"] += _add_fee(activity)
            trade["buy_tx_hashes"].append(activity.get("tx_hash"))
            lots[key].append({"quantity": qty, "cost_usd": value})
            continue

        trade = active.get(key)
        if trade is None:
            # Preserve data quality issues for later reconciliation.
            sequence[key] = sequence.get(key, 0) + 1
            trade = _new_trade(activity, sequence[key])
            trade["status"] = "unmatched_sell"
            trade["unmatched_sell_quantity"] = qty
            trade["quantity_sold"] = qty
            trade["sell_income_usd"] = value
            trade["sell_count"] = 1
            trade["fees_usd"] = _add_fee(activity)
            trade["sell_tx_hashes"].append(activity.get("tx_hash"))
            trade["closed_at"] = _timestamp(activity.get("timestamp"))
            trade["gross_pnl_usd"] = value
            trade["net_pnl_usd"] = value - trade["fees_usd"]
            completed.append(trade)
            continue

        trade["quantity_sold"] += qty
        trade["sell_income_usd"] += value
        trade["sell_count"] += 1
        trade["has_partial_exits"] = trade["sell_count"] > 1
        trade["fees_usd"] += _add_fee(activity)
        trade["sell_tx_hashes"].append(activity.get("tx_hash"))

        remaining = qty
        while remaining > 1e-12 and lots[key]:
            lot = lots[key][0]
            consumed = min(remaining, lot["quantity"])
            lot["quantity"] -= consumed
            remaining -= consumed
            if lot["quantity"] <= 1e-12:
                lots[key].popleft()

        if remaining > 1e-12:
            trade["unmatched_sell_quantity"] += remaining

        open_quantity = sum(lot["quantity"] for lot in lots[key])
        if open_quantity <= 1e-12:
            trade["status"] = "closed"
            trade["closed_at"] = _timestamp(activity.get("timestamp"))
            trade["gross_pnl_usd"] = trade["sell_income_usd"] - trade["buy_cost_usd"]
            trade["net_pnl_usd"] = trade["gross_pnl_usd"] - trade["fees_usd"]
            completed.append(trade)
            del active[key]
            del lots[key]

    for trade in active.values():
        trade["gross_pnl_usd"] = trade["sell_income_usd"] - trade["buy_cost_usd"]
        trade["net_pnl_usd"] = trade["gross_pnl_usd"] - trade["fees_usd"]
        completed.append(trade)

    for trade in completed:
        trade["duration_seconds"] = (
            (trade["closed_at"] or int(datetime.now(timezone.utc).timestamp()))
            - trade["opened_at"]
        )
        trade["average_entry_usd"] = (
            trade["buy_cost_usd"] / trade["quantity_bought"]
            if trade["quantity_bought"]
            else None
        )
        trade["average_exit_usd"] = (
            trade["sell_income_usd"] / trade["quantity_sold"]
            if trade["quantity_sold"]
            else None
        )

    return sorted(completed, key=lambda item: item["opened_at"])
