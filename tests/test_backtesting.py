import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.backtesting.engine import Backtester
from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.data.data_manager import DataManager
from praecursor.storage.price_cache import PriceCache


class BacktesterTests(unittest.TestCase):
    def test_backtester_generates_signals_and_summary(self):
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "backtest.db"
            cache = PriceCache(database_path=db_path)
            manager = DataManager(
                sources=[FakeMarketDataSource()],
                minimum_bars=260,
                price_cache=cache,
            )
            manager.fetch_history("COMI", date(2025, 1, 1), date(2026, 7, 27))

            result = Backtester(
                price_cache=cache,
                source_name="fake_market_data",
                minimum_history_bars=260,
                horizons=(5, 10, 20),
            ).run(["COMI"], date(2025, 1, 1), date(2026, 7, 27))

        self.assertGreater(len(result.signals), 0)
        self.assertGreater(len(result.summary), 0)
        self.assertEqual(result.errors, {})
        self.assertIn(5, result.signals[0].forward_returns)


if __name__ == "__main__":
    unittest.main()
