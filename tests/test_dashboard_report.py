import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.data.data_manager import DataManager
from praecursor.reporting.dashboard import ScannerDashboardWriter
from praecursor.storage.price_cache import PriceCache
from praecursor.workflows.scanner import ScannerWorkflow


class DashboardReportTests(unittest.TestCase):
    def test_dashboard_writer_creates_html(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            cache = PriceCache(database_path=directory_path / "dashboard.db")
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
            output_path = ScannerDashboardWriter().write(result, directory_path / "dashboard2.html")
            html = output_path.read_text(encoding="utf-8")

        self.assertIn("Praecursor-EGX", html)
        self.assertIn("Next-Day Candidates", html)
        self.assertIn("Swing Candidates", html)


if __name__ == "__main__":
    unittest.main()
