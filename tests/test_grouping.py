import unittest

from app.trade_review import group_activities


TOKEN = "TOKEN"


def activity(event_type, ts, qty, quote, tx, cost_usd):
    return {
        "event_type": event_type,
        "timestamp": ts,
        "tx_hash": tx,
        "token": {"address": TOKEN, "symbol": "TEST"},
        "token_amount": str(qty),
        "quote_amount": str(quote),
        "cost_usd": str(cost_usd),
        "price_usd": str(cost_usd / qty),
        "gas_usd": "0.10",
        "dex_usd": "0.20",
    }


class GroupActivitiesTests(unittest.TestCase):
    def test_groups_multiple_buys_and_partial_sells_into_one_trade(self):
        activities = [
            activity("buy", 100, 100, 1, "b1", 100),
            activity("buy", 110, 50, 0.6, "b2", 60),
            activity("sell", 120, 75, 1.2, "s1", 120),
            activity("sell", 130, 75, 1.5, "s2", 150),
        ]

        trades = group_activities(activities)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade["status"], "closed")
        self.assertEqual(trade["buy_count"], 2)
        self.assertEqual(trade["sell_count"], 2)
        self.assertEqual(trade["quantity_bought"], 150.0)
        self.assertEqual(trade["quantity_sold"], 150.0)
        self.assertEqual(trade["gross_pnl_usd"], 110.0)
        self.assertEqual(trade["net_pnl_usd"], 108.8)
        self.assertTrue(trade["has_multiple_entries"])
        self.assertTrue(trade["has_partial_exits"])

    def test_starts_a_new_trade_after_position_is_flat(self):
        activities = [
            activity("buy", 100, 10, 1, "b1", 10),
            activity("sell", 110, 10, 1.2, "s1", 12),
            activity("buy", 200, 20, 2, "b2", 20),
            activity("sell", 210, 20, 1.8, "s2", 18),
        ]

        trades = group_activities(activities)

        self.assertEqual(len(trades), 2)
        self.assertEqual([t["net_pnl_usd"] for t in trades], [1.4, -2.6])

    def test_keeps_open_position_as_open_trade(self):
        activities = [activity("buy", 100, 10, 1, "b1", 10)]

        trades = group_activities(activities)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["status"], "open")
        self.assertEqual(trades[0]["quantity_sold"], 0.0)


if __name__ == "__main__":
    unittest.main()
