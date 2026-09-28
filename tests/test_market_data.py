import unittest

from app.market_data import normalize_candles


class MarketDataTests(unittest.TestCase):
    def test_normalizes_gmgn_millisecond_candles(self):
        payload = {"list": [{"time": 1700000000000, "open": "1", "close": "2", "high": "3", "low": "0.5"}]}

        candles = normalize_candles(payload)

        self.assertEqual(candles[0]["time"], 1700000000)
        self.assertEqual(candles[0]["open"], 1.0)
        self.assertEqual(candles[0]["close"], 2.0)


if __name__ == "__main__":
    unittest.main()
