import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.storage.price_cache import PriceCache
from praecursor.workflows.scanner import ScannerWorkflow


class ScannerWorkflowTests(unittest.TestCase):
    def test_workflow_saves_history_and_rank_changes(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            db_path = directory_path / "scanner.db"
            workflow = ScannerWorkflow(
                lookback_days=450,
                minimum_bars=200,
                source_name="fake_market_data",
                market_data_source=FakeMarketDataSource(),
                price_cache=PriceCache(database_path=db_path),
                enable_consensus=False,
                enable_archive_reports=True,
            )

            first_result = workflow.run(
                symbols=["COMI", "HRHO"],
                end_date=date(2026, 7, 27),
                report_path=directory_path / "ranking.csv",
                markdown_report_path=directory_path / "ranking.md",
            )
            second_result = workflow.run(
                symbols=["COMI", "HRHO"],
                end_date=date(2026, 7, 27),
                report_path=directory_path / "ranking2.csv",
                markdown_report_path=directory_path / "ranking2.md",
            )

            self.assertEqual(first_result.history_run_id, 1)
            self.assertEqual(second_result.history_run_id, 2)
            self.assertEqual(second_result.symbol_results[0].previous_rank, 1)
            self.assertEqual(second_result.symbol_results[0].rank_change_text, "unchanged")
            self.assertTrue(second_result.report_path.exists())
            self.assertTrue(second_result.markdown_report_path.exists())
            self.assertTrue(second_result.archive_report_path.exists())
            self.assertTrue(second_result.archive_markdown_report_path.exists())

    def test_scanner_consensus_logging_and_cache_override(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            db_path = directory_path / "scanner.db"
            cache = PriceCache(database_path=db_path)

            source_tv = FakeMarketDataSource(source_name="TradingView")
            source_mubasher = FakeMarketDataSource(source_name="Mubasher")

            workflow = ScannerWorkflow(
                lookback_days=450,
                minimum_bars=200,
                source_name="TradingView",
                market_data_source=source_tv,
                consensus_data_sources=[source_tv, source_mubasher],
                price_cache=cache,
                enable_consensus=True,
                enable_archive_reports=False,
            )

            with self.assertLogs("praecursor.workflows.scanner", level="INFO") as cm:
                result = workflow.run(
                    symbols=["COMI"],
                    end_date=date(2026, 7, 27),
                    report_path=directory_path / "ranking.csv",
                    markdown_report_path=directory_path / "ranking.md",
                )

            self.assertEqual(len(result.symbol_results), 1)
            symbol_res = result.symbol_results[0]
            self.assertIsNotNone(symbol_res.consensus_result)
            self.assertTrue(symbol_res.consensus_result.accepted)
            self.assertGreater(symbol_res.consensus_result.consensus_high, 0)
            self.assertGreater(symbol_res.consensus_result.consensus_close, 0)

            log_output = "\n".join(cm.output)
            self.assertIn("TradingView", log_output)
            self.assertIn("Mubasher", log_output)
            self.assertIn("Fetching price data for COMI from consensus data sources", log_output)

            # Also test direct PriceCache.override_consensus_prices SQL execution on db
            cache.override_consensus_prices("COMI", "TradingView", date(2026, 7, 27), 150.0, 145.0)
            loaded_bars = cache.load("COMI", "TradingView", date(2026, 7, 27), date(2026, 7, 27))
            self.assertEqual(len(loaded_bars), 1)
            self.assertEqual(loaded_bars[0].high, 150.0)
            self.assertEqual(loaded_bars[0].close, 145.0)


if __name__ == "__main__":
    unittest.main()
