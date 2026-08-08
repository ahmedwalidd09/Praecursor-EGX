from datetime import datetime, timezone
from pathlib import Path
import csv
import sqlite3
import tempfile
import unittest

from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.storage.price_cache import PriceCache
from praecursor.storage.signal_history import SignalHistoryStore


class TestAccuracyTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_praecursor.db"
        self.archive_csv_path = Path(self.temp_dir.name) / "accuracy_history_archive.csv"

        # Initialize schemas for signals, outcomes, and price cache
        self.store = SignalHistoryStore(self.db_path)
        self.cache = PriceCache(self.db_path)
        self.cache.initialize()  # Create source_prices table
        self.tracker = AccuracyTracker(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_scanner_run(self, conn, run_id, generated_at, source_name="mubasher"):
        conn.execute("""
            INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count)
            VALUES (?, ?, ?, '[]', 8, 0)
        """, (run_id, generated_at, source_name))

    def _create_scanner_signal(self, conn, run_id, generated_at, rank, symbol, latest_close, target_price, label="Watchlist Tomorrow"):
        conn.execute("""
            INSERT INTO scanner_signals (
                run_id, generated_at, rank, symbol, company, opportunity_score,
                final_predictor_score, predictor_label, latest_close, consensus_confidence,
                data_quality_score, next_day_score, next_day_label, swing_score,
                swing_label, swing_stop_loss, next_day_target
            ) VALUES (?, ?, ?, ?, ?, 80.0, 80.0, 'Strong', ?, 100.0, 100.0, 80.0, ?, 80.0, 'Swing', 0.0, ?)
        """, (run_id, generated_at, rank, symbol, f"{symbol} Co", latest_close, label, target_price))

    def _create_source_price(self, conn, symbol, trade_date, high, close):
        conn.execute("""
            INSERT INTO source_prices (ticker, trade_date, source, open, high, low, close, volume, confidence, collected_at)
            VALUES (?, ?, 'mubasher', ?, ?, ?, ?, 10000, 1.0, '2026-08-01T12:00:00Z')
        """, (symbol, trade_date, close, high, min(close, high), close))

    def test_intraday_high_hits_target_even_when_close_is_lower(self):
        """Verify candidate target hit when intraday high reaches target price even if close is lower."""
        with sqlite3.connect(self.db_path) as conn:
            self._create_scanner_run(conn, run_id=1, generated_at="2026-08-01T12:00:00Z")
            # Candidate target = 107.5 (+7.5% from latest_close 100.0)
            self._create_scanner_signal(conn, run_id=1, generated_at="2026-08-01T12:00:00Z", rank=1, symbol="TEST_HIT", latest_close=100.0, target_price=107.5)
            # Next day candle: high = 108.0 (>= 107.5 target), but close = 101.0 (< 107.5 target)
            self._create_source_price(conn, symbol="TEST_HIT", trade_date="2026-08-02", high=108.0, close=101.0)
            conn.commit()

        self.tracker.update_historical_outcomes()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            outcome = conn.execute("SELECT * FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'TEST_HIT'").fetchone()

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["next_day_hit"], 1, "Intraday high >= target price must log as HIT even when close is lower")

    def test_intraday_high_misses_target_even_if_over_2_point_5_percent(self):
        """Verify candidate target miss when intraday high fails to reach target price, even if gain > 2.5%."""
        with sqlite3.connect(self.db_path) as conn:
            self._create_scanner_run(conn, run_id=1, generated_at="2026-08-01T12:00:00Z")
            # Target = 107.5 (+7.5% from latest_close 100.0)
            self._create_scanner_signal(conn, run_id=1, generated_at="2026-08-01T12:00:00Z", rank=1, symbol="TEST_MISS", latest_close=100.0, target_price=107.5)
            # Next day candle: high = 104.0 (+4.0% gain > 2.5%, but < 107.5 target), close = 103.0
            self._create_source_price(conn, symbol="TEST_MISS", trade_date="2026-08-02", high=104.0, close=103.0)
            conn.commit()

        self.tracker.update_historical_outcomes()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            outcome = conn.execute("SELECT * FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'TEST_MISS'").fetchone()

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["next_day_hit"], 0, "Intraday high < target price must log as MISS even if high is > 2.5% above close")

    def test_running_updater_multiple_times_appends_and_maintains_baseline_count(self):
        """Verify running updater multiple times appends to history archive and maintains baseline count (16 records)."""
        with sqlite3.connect(self.db_path) as conn:
            # Day 1: 2026-08-01 (Run 1) -> 8 candidate signals
            self._create_scanner_run(conn, run_id=1, generated_at="2026-08-01T12:00:00Z")
            for r in range(1, 9):
                sym = f"SYM_D1_{r}"
                self._create_scanner_signal(conn, run_id=1, generated_at="2026-08-01T12:00:00Z", rank=r, symbol=sym, latest_close=100.0, target_price=105.0)
                # 4 hits (high 106.0), 4 misses (high 103.0)
                high_val = 106.0 if r <= 4 else 103.0
                self._create_source_price(conn, symbol=sym, trade_date="2026-08-02", high=high_val, close=101.0)

            # Day 2: 2026-08-02 (Run 2) -> 8 candidate signals
            self._create_scanner_run(conn, run_id=2, generated_at="2026-08-02T12:00:00Z")
            for r in range(1, 9):
                sym = f"SYM_D2_{r}"
                self._create_scanner_signal(conn, run_id=2, generated_at="2026-08-02T12:00:00Z", rank=r, symbol=sym, latest_close=50.0, target_price=53.0)
                high_val = 54.0 if r <= 4 else 51.0
                self._create_source_price(conn, symbol=sym, trade_date="2026-08-03", high=high_val, close=50.5)

            conn.commit()

        # Execute tracker update first time
        self.tracker.update_historical_outcomes()
        self.tracker.export_accuracy_history_archive(self.archive_csv_path)

        with sqlite3.connect(self.db_path) as conn:
            count1 = conn.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]

        self.assertEqual(count1, 16, f"Expected 16 outcomes across 2 runs (8 each), got {count1}")

        # Execute tracker update a second time
        self.tracker.update_historical_outcomes()
        self.tracker.export_accuracy_history_archive(self.archive_csv_path)

        with sqlite3.connect(self.db_path) as conn:
            count2 = conn.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]

        self.assertEqual(count2, 16, "Re-running updater must maintain baseline count without creating duplicates")

        # Verify CSV export
        self.assertTrue(self.archive_csv_path.exists(), "Archive CSV file should be created")
        with open(self.archive_csv_path, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 16, f"CSV archive should contain exactly 16 records, got {len(reader)}")
        # Check cumulative accuracy metrics progression
        last_row = reader[-1]
        self.assertEqual(int(last_row["cumulative_total"]), 16)
        self.assertEqual(int(last_row["cumulative_hits"]), 8)
        self.assertEqual(float(last_row["cumulative_accuracy_pct"]), 50.0)


if __name__ == "__main__":
    unittest.main()
