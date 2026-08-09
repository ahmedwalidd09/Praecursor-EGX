"""
Adversarial empirical test suite written by challenger_2.
Verifies network isolation guard, target evaluation logic, and duplicate candidate prevention during CSV export.
"""

from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import socket
import sys
import tempfile
import unittest

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.storage.price_cache import PriceCache
from praecursor.storage.signal_history import SignalHistoryStore


class TestChallenger2Empirical(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_praecursor.db"
        self.archive_csv_path = Path(self.temp_dir.name) / "accuracy_history_archive.csv"
        SignalHistoryStore(self.db_path).initialize()
        PriceCache(self.db_path).initialize()
        self.tracker = AccuracyTracker(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_scanner_run(self, conn, run_id, generated_at):
        conn.execute("""
            INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count)
            VALUES (?, ?, 'mubasher', '[]', 8, 0)
        """, (run_id, generated_at))

    def _create_scanner_signal(self, conn, run_id, generated_at, rank, symbol, latest_close, target_price):
        conn.execute("""
            INSERT INTO scanner_signals (
                run_id, generated_at, rank, symbol, company, opportunity_score,
                final_predictor_score, predictor_label, latest_close, consensus_confidence,
                data_quality_score, next_day_score, next_day_label, swing_score,
                swing_label, swing_stop_loss, next_day_target
            ) VALUES (?, ?, ?, ?, ?, 80.0, 80.0, 'Strong', ?, 100.0, 100.0, 80.0, 'Bullish', 80.0, 'Swing', 0.0, ?)
        """, (run_id, generated_at, rank, symbol, f"{symbol} Co", latest_close, target_price))

    def _create_source_price(self, conn, symbol, trade_date, high, close):
        conn.execute("""
            INSERT INTO source_prices (ticker, trade_date, source, open, high, low, close, volume, confidence, collected_at)
            VALUES (?, ?, 'mubasher', ?, ?, ?, ?, 10000, 1.0, '2026-08-01T12:00:00Z')
        """, (symbol, trade_date, close, high, min(close, high), close))

    # --- 1. Test Network Isolation Guard ---
    def test_outbound_socket_connection_raises_runtime_error(self):
        """Verify outbound network connections raise RuntimeError when isolation is active."""
        orig_socket_connect = socket.socket.connect
        def guarded_connect(sock_self, address):
            host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
            if host in ("127.0.0.1", "localhost", "::1"):
                return orig_socket_connect(sock_self, address)
            raise RuntimeError(
                f"Network access disabled during automated test runs: attempted connection to {address}."
            )

        socket.socket.connect = guarded_connect
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(RuntimeError) as cm:
                    sock.connect(("8.8.8.8", 80))
                self.assertIn("Network access disabled during automated test runs", str(cm.exception))
            finally:
                sock.close()
        finally:
            socket.socket.connect = orig_socket_connect

    def test_loopback_connection_bypasses_guard(self):
        """Verify loopback localhost connections do NOT trigger network isolation RuntimeError."""
        orig_socket_connect = socket.socket.connect
        def guarded_connect(sock_self, address):
            host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
            if host in ("127.0.0.1", "localhost", "::1"):
                return orig_socket_connect(sock_self, address)
            raise RuntimeError(
                f"Network access disabled during automated test runs: attempted connection to {address}."
            )

        socket.socket.connect = guarded_connect
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises((ConnectionRefusedError, OSError)) as cm:
                    sock.connect(("127.0.0.1", 65530))
                self.assertNotIsInstance(cm.exception, RuntimeError)
            finally:
                sock.close()
        finally:
            socket.socket.connect = orig_socket_connect

    # --- 2. Test accuracy_tracker.py Target Evaluation Logic ---
    def test_intraday_high_reaching_target_is_hit_even_if_close_is_lower(self):
        """Verify intraday high >= target evaluates to 1 (HIT) even when close is lower."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            self._create_scanner_run(conn, run_id=1, generated_at="2026-08-01T12:00:00Z")
            self._create_scanner_signal(conn, run_id=1, generated_at="2026-08-01T12:00:00Z", rank=1, symbol="HIGH_HIT", latest_close=100.0, target_price=105.0)
            self._create_source_price(conn, symbol="HIGH_HIT", trade_date="2026-08-02", high=105.0, close=85.0)
            conn.commit()

        self.tracker.update_historical_outcomes()

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            outcome = conn.execute("SELECT * FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'HIGH_HIT'").fetchone()

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["next_day_hit"], 1, "Intraday high >= target price MUST be recorded as HIT (1)")

    def test_intraday_high_below_target_is_miss(self):
        """Verify intraday high < target evaluates to 0 (MISS)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            self._create_scanner_run(conn, run_id=1, generated_at="2026-08-01T12:00:00Z")
            self._create_scanner_signal(conn, run_id=1, generated_at="2026-08-01T12:00:00Z", rank=1, symbol="HIGH_MISS", latest_close=100.0, target_price=105.0)
            self._create_source_price(conn, symbol="HIGH_MISS", trade_date="2026-08-02", high=104.0, close=104.0)
            conn.commit()

        self.tracker.update_historical_outcomes()

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            outcome = conn.execute("SELECT * FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'HIGH_MISS'").fetchone()

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["next_day_hit"], 0, "Intraday high < target price MUST be recorded as MISS (0)")

    # --- 3. Test Duplicate Candidate Prevention During CSV Export ---
    def test_csv_export_prevents_duplicate_candidates(self):
        """Verify CSV export maintains seen set and avoids duplicate (signal_date, symbol) rows."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count)
                VALUES (1, '2026-08-01T12:00:00Z', 'mubasher', '[]', 1, 0)
            """)
            conn.execute("""
                INSERT INTO scanner_signals (
                    run_id, generated_at, rank, symbol, company, opportunity_score,
                    final_predictor_score, predictor_label, latest_close, consensus_confidence,
                    data_quality_score, next_day_score, next_day_label, swing_score,
                    swing_label, swing_stop_loss, next_day_target
                ) VALUES (1, '2026-08-01T12:00:00Z', 1, 'DUP_CANDIDATE', 'Dup Co', 80.0, 80.0, 'Strong', 100.0, 100.0, 100.0, 80.0, 'Bullish', 80.0, 'Swing', 0.0, 105.0)
            """)
            conn.execute("""
                INSERT INTO scanner_signal_outcomes (
                    run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, next_day_max_return, swing_label
                ) VALUES (1, 'DUP_CANDIDATE', '2026-08-01', 'Bullish', 1, 2.0, 5.0, '')
            """)
            conn.commit()

        self.tracker.export_accuracy_history_archive(self.archive_csv_path)
        self.tracker.export_accuracy_history_archive(self.archive_csv_path)

        self.assertTrue(self.archive_csv_path.exists())
        with open(self.archive_csv_path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 1, f"Expected 1 record in archive CSV, got {len(rows)}")
        self.assertEqual(rows[0]["symbol"], "DUP_CANDIDATE")
        self.assertEqual(int(rows[0]["cumulative_total"]), 1)
        self.assertEqual(int(rows[0]["cumulative_hits"]), 1)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestChallenger2Empirical)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("EMPIRICAL_TEST_VERDICT: PASS")
        sys.exit(0)
    else:
        print("EMPIRICAL_TEST_VERDICT: FAIL")
        sys.exit(1)
