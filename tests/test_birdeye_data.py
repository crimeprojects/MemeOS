import unittest

from app.market_data import normalize_birdeye_candles


class BirdeyeDataTests(unittest.TestCase):
    def test_normalizes_birdeye_15s_candles(self):
        payload = {
            "success": True,
            "data": {
                "items": [
                    {"unix_time": 1700000000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}
                ]
            },
        }

        candles = normalize_birdeye_candles(payload)

        self.assertEqual(candles[0]["time"], 1700000000)
        self.assertEqual(candles[0]["open"], 1.0)
        self.assertEqual(candles[0]["close"], 1.5)
