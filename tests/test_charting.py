import tempfile
import unittest
from pathlib import Path

from app.charting import render_trade_chart


class ChartingTests(unittest.TestCase):
    def test_renders_svg_with_candles_and_trade_markers(self):
        candles = [
            {"time": 100, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1},
            {"time": 130, "open": 1.1, "high": 1.4, "low": 1.0, "close": 1.3},
            {"time": 160, "open": 1.3, "high": 1.35, "low": 1.05, "close": 1.1},
        ]
        trade = {
            "symbol": "TEST",
            "opened_at": 115,
            "closed_at": 155,
            "average_entry_usd": 1.05,
            "average_exit_usd": 1.25,
            "net_pnl_usd": 2.5,
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trade.svg"
            render_trade_chart(candles, trade, output)
            svg = output.read_text()

        self.assertIn("TEST", svg)
        self.assertIn("Entry", svg)
        self.assertIn("Exit", svg)
        self.assertIn("<svg", svg)
        self.assertGreater(svg.count("<line"), 2)


if __name__ == "__main__":
    unittest.main()
