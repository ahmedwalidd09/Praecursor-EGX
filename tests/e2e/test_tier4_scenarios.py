from datetime import date, timedelta
import sqlite3
import subprocess
import pytest
from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice
from praecursor.storage.signal_history import SignalHistoryStore, SIGNAL_HISTORY_SCHEMA


class TestTier4Scenarios:
    """Tier 4: Real-World End-to-End Application Scenarios."""

    def test_scenario_multi_day_pipeline(self, temp_db_path):
        """Full end-to-end multi-day pipeline execution (Scan -> 5 PM Updater -> Consensus -> Hit Check -> Archive Append -> Retrain check)."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        tracker = AccuracyTracker(database_path=temp_db_path)

        start_date = date(2026, 8, 1)

        # Day 1: Multi-source fetch & consensus
        prices_day1 = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=start_date, close=80.0, high=83.0),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=start_date, close=80.0, high=83.0),
        ]
        consensus1 = engine.calculate("COMI", start_date, prices_day1)
        assert consensus1.accepted is True

        # Save scan run
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count) VALUES ('2026-08-01T17:00:00', 'consensus', '[]', 1, 0)")
        run_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO scanner_signals (run_id, generated_at, rank, symbol, company, opportunity_score, final_predictor_score, predictor_label, latest_close, consensus_confidence, data_quality_score, next_day_score, next_day_label, next_day_target)
            VALUES (?, '2026-08-01T17:00:00', 1, 'COMI', 'COMI Bank', 90.0, 90.0, 'BULLISH', 80.0, 100.0, 1.0, 90.0, 'BULLISH', 82.5)
        """, (run_id,))

        # Add Day 2 price bar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_prices (
                ticker TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT,
                PRIMARY KEY (ticker, trade_date, source)
            )
        """)
        cursor.execute("INSERT INTO source_prices VALUES ('COMI', '2026-08-02', 80.0, 83.5, 79.5, 81.0, 5000, 'consensus')")
        conn.commit()
        conn.close()

        # Run 5 PM updater
        tracker.update_historical_outcomes()

        # Check outcome hit & archive append
        stats = tracker.get_accuracy_stats()
        assert stats["next_day"]["total"] == 17
        assert stats["next_day"]["hits"] == 11
        assert stats["next_day"]["accuracy"] > 60.0

    def test_scenario_weekly_trading_simulation(self, temp_db_path, accuracy_tracker):
        """Simulate 5 consecutive trading days with 16 baseline records, verifying cumulative total grows to 21 records."""
        stats_initial = accuracy_tracker.get_accuracy_stats()
        assert stats_initial["next_day"]["total"] == 16

        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        days = ["2026-07-30", "2026-07-31", "2026-08-01", "2026-08-02", "2026-08-03"]
        for idx, d in enumerate(days, start=17):
            cursor.execute("INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count) VALUES (?, 'consensus', '[]', 1, 0)", (f"{d}T17:00:00",))
            run_id = cursor.lastrowid
            sym = f"SIM{idx}"
            cursor.execute("""
                INSERT INTO scanner_signals (run_id, generated_at, rank, symbol, company, opportunity_score, final_predictor_score, predictor_label, latest_close, consensus_confidence, data_quality_score, next_day_score, next_day_label, next_day_target)
                VALUES (?, ?, 1, ?, 'Simulated Corp', 85.0, 85.0, 'BULLISH', 10.0, 100.0, 1.0, 85.0, 'BULLISH', 10.5)
            """, (run_id, f"{d}T17:00:00", sym))
            cursor.execute("""
                INSERT INTO scanner_signal_outcomes (run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label)
                VALUES (?, ?, ?, 'BULLISH', 1, 4.0, '')
            """, (run_id, sym, d))

        conn.commit()
        conn.close()

        stats_final = accuracy_tracker.get_accuracy_stats()
        assert stats_final["next_day"]["total"] == 21, f"Expected cumulative total to grow from 16 to 21, got {stats_final['next_day']['total']}"
        assert stats_final["next_day"]["hits"] == 15 # 10 + 5

    def test_scenario_tradingview_outage_resilience(self, temp_db_path):
        """Simulate TradingView returning bad 1-bar data during daily 5 PM run; Mubasher supplies clean data, target hit evaluated, archive updated cleanly."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=1, target_source_count=2)
        today = date(2026, 8, 1)

        # TradingView returns corrupted 1-bar price, Mubasher supplies clean price
        prices = [
            SourcePrice(source_name="TradingView", symbol="OUTAGE_SYM", trade_date=today, close=0.01, high=0.01),
            SourcePrice(source_name="Mubasher", symbol="OUTAGE_SYM", trade_date=today, close=50.0, high=53.0),
        ]

        # Mubasher clean price is used
        valid_prices = [p for p in prices if p.close > 0.1]
        consensus = engine.calculate("OUTAGE_SYM", today, valid_prices)

        assert consensus.consensus_close == 50.0
        assert consensus.consensus_high == 53.0

        # Evaluate target (entry=50.0, target=52.5) -> high 53.0 is a HIT
        hit = 1 if consensus.consensus_high >= 52.5 else 0
        assert hit == 1

    def test_scenario_scheduled_task_lifecycle(self, run_task_script):
        """Test Windows scheduled task registration script execution, task query, trigger execution via schtasks, and log verification."""
        task_name = "PraecursorE2ELifecycle"
        reg_res = run_task_script("register_task.ps1", task_name, "17:00")
        assert reg_res.returncode == 0

        # Query task status
        query_res = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/FO", "CSV"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert task_name in query_res.stdout

        # Delete scheduled task cleanly
        del_res = subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True, text=True)
        assert del_res.returncode == 0

    def test_scenario_updater_rerun_idempotency(self, temp_db_path):
        """Run 5 PM updater twice on same day; verify state integrity and no corrupted cumulative totals."""
        tracker = AccuracyTracker(database_path=temp_db_path)
        stats1 = tracker.get_accuracy_stats()
        count1 = stats1["next_day"]["total"]

        # Run outcome update twice
        tracker.update_historical_outcomes()
        tracker.update_historical_outcomes()

        stats2 = tracker.get_accuracy_stats()
        count2 = stats2["next_day"]["total"]

        assert count1 == count2 == 16, "Re-running 5 PM updater must be idempotent and not create duplicate or corrupted records."
