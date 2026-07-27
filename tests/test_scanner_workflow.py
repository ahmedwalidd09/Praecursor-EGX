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


if __name__ == "__main__":
    unittest.main()
