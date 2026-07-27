import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.backtesting.engine import Backtester
from praecursor.backtesting.reports import BacktestCSVReportWriter
from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.data.data_manager import DataManager
from praecursor.storage.price_cache import PriceCache


class BacktesterTests(unittest.TestCase):
    def test_backtester_generates_signals_summary_and_reports(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            db_path = directory_path / "backtest.db"
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

            writer = BacktestCSVReportWriter()
            signals_path = writer.write_signals(result, directory_path / "signals.csv")
            summary_path = writer.write_summary(result, directory_path / "summary.csv")
            symbol_summary_path = writer.write_symbol_summary(result, directory_path / "symbol_summary.csv")
            markdown_path = writer.write_markdown(result, directory_path / "summary.md")

            self.assertTrue(signals_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(symbol_summary_path.exists())
            self.assertTrue(markdown_path.exists())

        self.assertGreater(len(result.signals), 0)
        self.assertGreater(len(result.summary), 0)
        self.assertGreater(len(result.symbol_summary), 0)
        self.assertGreater(len(result.best_signals), 0)
        self.assertGreater(len(result.worst_signals), 0)
        self.assertEqual(result.errors, {})
        self.assertIn(5, result.signals[0].forward_returns)


if __name__ == "__main__":
    unittest.main()
