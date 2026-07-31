import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.data.data_manager import DataManager
from praecursor.notifications.telegram import TelegramReportFormatter
from praecursor.storage.price_cache import PriceCache
from praecursor.workflows.scanner import ScannerWorkflow


class TelegramFormatterTests(unittest.TestCase):
    def test_formatter_contains_candidate_sections(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            cache = PriceCache(database_path=directory_path / "telegram.db")
            DataManager([FakeMarketDataSource()], minimum_bars=200, price_cache=cache).fetch_history(
                "COMI",
                date(2025, 1, 1),
                date(2026, 7, 27),
            )
            result = ScannerWorkflow(
                lookback_days=450,
                minimum_bars=200,
                source_name="fake_market_data",
                market_data_source=FakeMarketDataSource(),
                price_cache=cache,
                enable_consensus=False,
                enable_history=False,
            ).run(
                symbols=["COMI"],
                end_date=date(2026, 7, 27),
                report_path=directory_path / "ranking.csv",
                next_day_report_path=directory_path / "next.csv",
                swing_report_path=directory_path / "swing.csv",
                markdown_report_path=directory_path / "ranking.md",
                dashboard_report_path=directory_path / "dashboard.html",
            )

        message = TelegramReportFormatter().format_scanner_result(result, top_n=3)
        self.assertIn("Praecursor-EGX Scan", message)
        self.assertIn("Next-Day Candidates", message)
        self.assertIn("Swing Candidates", message)
        self.assertIn("COMI", message)


if __name__ == "__main__":
    unittest.main()
