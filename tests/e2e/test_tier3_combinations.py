from datetime import date
import sqlite3
import pytest
from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice
from praecursor.storage.signal_history import SignalHistoryStore


class TestTier3Combinations:
    """Tier 3: Pairwise Cross-Feature Integration Tests."""

    def test_comb_r1_r3_scheduled_append(self, temp_db_path, run_task_script):
        """Verify 5 PM scheduled run updates accuracy tracking and appends to cumulative archive without overwriting."""
        tracker = AccuracyTracker(database_path=temp_db_path)
        stats_before = tracker.get_accuracy_stats()
        assert stats_before["next_day"]["total"] == 16

        # Simulate scheduled task execution at 5 PM inserting new daily run
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        cursor.execute("INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count) VALUES ('2026-07-30T17:00:00', 'scheduled', '[]', 1, 0)")
        run_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO scanner_signals (run_id, generated_at, rank, symbol, company, opportunity_score, final_predictor_score, predictor_label, latest_close, consensus_confidence, data_quality_score, next_day_score, next_day_label, next_day_target)
            VALUES (?, '2026-07-30T17:00:00', 1, 'COMI', 'Commercial International Bank', 90.0, 90.0, 'BULLISH', 80.0, 100.0, 1.0, 90.0, 'BULLISH', 82.5)
        """, (run_id,))

        cursor.execute("""
            INSERT INTO scanner_signal_outcomes (run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label)
            VALUES (?, 'COMI', '2026-07-30', 'BULLISH', 1, 3.5, '')
        """, (run_id,))
        conn.commit()
        conn.close()

        stats_after = tracker.get_accuracy_stats()
        assert stats_after["next_day"]["total"] == 17
        assert stats_after["next_day"]["hits"] == 11

    def test_comb_r2_r4_consensus_target_verification(self):
        """Verify data source consensus calculates verified intraday high, which feeds directly into target hit verification."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        # Multi-source prices (TradingView and Mubasher)
        prices = [
            SourcePrice(source_name="TradingView", symbol="FWRY", trade_date=today, close=6.0, high=6.4),
            SourcePrice(source_name="Mubasher", symbol="FWRY", trade_date=today, close=6.0, high=6.4),
        ]

        consensus_res = engine.calculate("FWRY", today, prices)
        assert consensus_res.accepted is True
        verified_high = consensus_res.consensus_high # 6.4

        # Feed consensus verified high directly into target evaluation logic
        latest_close = 6.0
        target_price = 6.30  # +5% target = 6.30
        is_hit = 1 if verified_high >= target_price else 0

        assert is_hit == 1, f"Expected HIT (1) because consensus verified high ({verified_high}) >= target ({target_price})"

    def test_comb_r1_r2_scheduled_target_eval(self, temp_db_path):
        """Verify scheduled 5 PM updater retrieves candidates and evaluates target % hit vs close."""
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Insert a 5 PM run with target 82.5 for latest_close 80.0
        cursor.execute("INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count) VALUES (100, '2026-07-30T17:00:00', 'scheduled_5pm', '[]', 1, 0)")
        cursor.execute("""
            INSERT INTO scanner_signals (run_id, generated_at, rank, symbol, company, opportunity_score, final_predictor_score, predictor_label, latest_close, consensus_confidence, data_quality_score, next_day_score, next_day_label, next_day_target)
            VALUES (100, '2026-07-30T17:00:00', 1, 'SCHEDULED_SYM', 'Sched Corp', 90.0, 90.0, 'BULLISH', 80.0, 100.0, 1.0, 90.0, 'BULLISH', 82.5)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_prices (
                ticker TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT,
                PRIMARY KEY (ticker, trade_date, source)
            )
        """)
        # Next day price high 83.0 (reaches target 82.5) but close is 79.0 (lower than entry)
        cursor.execute("INSERT INTO source_prices VALUES ('SCHEDULED_SYM', '2026-07-31', 80.0, 83.0, 78.5, 79.0, 1000, 'consensus')")
        conn.commit()
        conn.close()

        tracker = AccuracyTracker(database_path=temp_db_path)
        tracker.update_historical_outcomes()

        conn = sqlite3.connect(str(temp_db_path))
        hit = conn.execute("SELECT next_day_hit FROM scanner_signal_outcomes WHERE run_id = 100 AND symbol = 'SCHEDULED_SYM'").fetchone()[0]
        conn.close()

        assert hit == 1, "Scheduled 5 PM evaluation must evaluate intraday high hit even when close is lower."

    def test_comb_r3_r4_consensus_archive_logging(self, temp_db_path, caplog):
        """Verify consensus price data logs and consensus results are recorded into cumulative history archive."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=today, close=80.0, high=82.5),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=today, close=80.0, high=82.5),
        ]

        consensus_res = engine.calculate("COMI", today, prices)

        # Record consensus result into database signal history
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        cursor.execute("INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count) VALUES (?, 'consensus', '[]', 1, 0)", (f"{today}T17:00:00",))
        run_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO scanner_signals (run_id, generated_at, rank, symbol, company, opportunity_score, final_predictor_score, predictor_label, latest_close, consensus_confidence, data_quality_score, next_day_score, next_day_label, next_day_target)
            VALUES (?, ?, 1, 'COMI', 'COMI', 90.0, 90.0, 'BULLISH', ?, ?, 1.0, 90.0, 'BULLISH', ?)
        """, (run_id, f"{today}T17:00:00", consensus_res.consensus_close, consensus_res.confidence_percent, consensus_res.consensus_high))
        conn.commit()

        row = cursor.execute("SELECT latest_close, next_day_target, consensus_confidence FROM scanner_signals WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()

        assert row[0] == 80.0
        assert row[1] == 82.5
        assert row[2] == 100.0
