import math
import sqlite3
import pytest
from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.storage.signal_history import SignalHistoryStore


def create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close):
    """Helper to set up a clean single-signal scenario in a sqlite database and update outcomes."""
    db_file = tmp_path / "target_eval_test.db"
    store = SignalHistoryStore(db_file)
    store.initialize()

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count)
        VALUES (1, '2026-08-01T17:00:00', 'test', '["TEST"]', 1, 0)
    """)

    cursor.execute("""
        INSERT INTO scanner_signals (
            run_id, generated_at, rank, symbol, company, opportunity_score,
            final_predictor_score, predictor_label, latest_close, consensus_confidence,
            data_quality_score, next_day_score, next_day_label, next_day_target
        ) VALUES (1, '2026-08-01T17:00:00', 1, 'TEST', 'Test Corp', 90.0, 90.0, 'BULLISH', ?, 100.0, 1.0, 90.0, 'BULLISH', ?)
    """, (latest_close, target_price))

    # Insert next day candle in source_prices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_prices (
            ticker TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            source TEXT,
            PRIMARY KEY (ticker, trade_date, source)
        )
    """)

    cursor.execute("""
        INSERT INTO source_prices (ticker, trade_date, open, high, low, close, volume, source)
        VALUES ('TEST', '2026-08-02', ?, ?, ?, ?, 1000, 'test')
    """, (latest_close, next_high, min(latest_close, next_close), next_close))

    conn.commit()
    conn.close()

    tracker = AccuracyTracker(database_path=db_file)
    tracker.update_historical_outcomes()

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    outcome = cursor.execute("SELECT next_day_hit, next_day_return FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'TEST'").fetchone()
    conn.close()

    return outcome


class TestR2TargetVerificationTier1:
    """Tier 1: Feature Coverage for R2 Intraday Target Verification."""

    def test_r2_intraday_high_hits_target_close_lower(self, tmp_path):
        """Verify intraday high >= target % counts as HIT even if close < target."""
        latest_close = 100.0
        target_price = 105.0  # +5% target
        next_high = 106.0    # Reached +6% intraday
        next_close = 98.0    # Closed at -2%

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1, f"Expected HIT (1) because intraday high ({next_high}) >= target ({target_price}), even though close ({next_close}) was lower."

    def test_r2_intraday_high_hits_exact_target(self, tmp_path):
        """Verify intraday high == target % counts as HIT."""
        latest_close = 50.0
        target_price = 53.0  # +6%
        next_high = 53.0    # Exactly hit target
        next_close = 52.0

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1, f"Expected HIT (1) for exact target match high ({next_high}) == target ({target_price})"

    def test_r2_intraday_high_exceeds_target(self, tmp_path):
        """Verify intraday high > target % counts as HIT."""
        latest_close = 10.0
        target_price = 10.5 # +5%
        next_high = 11.2   # +12%
        next_close = 11.0

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1, "Expected HIT (1) when high exceeds target."

    def test_r2_intraday_high_below_target_close_below(self, tmp_path):
        """Verify intraday high < target % and close < target % counts as MISS."""
        latest_close = 100.0
        target_price = 108.0 # +8%
        next_high = 101.5   # Only +1.5% high
        next_close = 99.0   # Closed at -1%

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 0, f"Expected MISS (0) when high ({next_high}) < target ({target_price}) and close < target"

    def test_r2_intraday_high_below_target_close_above(self, tmp_path):
        """Verify target hit rules when close is above entry but high didn't reach target."""
        latest_close = 100.0
        target_price = 110.0 # +10% target
        next_high = 102.0    # +2% high (below 2.5% solid gain threshold & below target)
        next_close = 101.5   # Closed +1.5%

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 0, "Expected MISS (0) because high did not reach target or solid gain threshold."


class TestR2TargetVerificationTier2:
    """Tier 2: Boundary & Corner Cases for R2 Intraday Target Verification."""

    def test_r2_floating_point_target_precision(self, tmp_path):
        """Verify target % comparison with floating point precision (7.5000001% vs 7.5%)."""
        latest_close = 100.0
        target_price = 107.5000001
        next_high = 107.5000001
        next_close = 105.0

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1

    def test_r2_zero_atr_target(self, tmp_path):
        """Verify target verification handling when ATR or target calculation is 0 or undefined."""
        latest_close = 50.0
        target_price = 0.0  # Undefined/zero target falls back to latest_close or solid gain
        next_high = 52.0    # +4% (solid gain >= 2.5%)
        next_close = 51.5

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1

    def test_r2_circuit_breaker_high(self, tmp_path):
        """Verify target verification when intraday high reaches +20% limit up circuit breaker."""
        latest_close = 100.0
        target_price = 115.0 # +15%
        next_high = 120.0    # Max +20% limit up
        next_close = 120.0

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 1

    def test_r2_zero_high_volume(self, tmp_path):
        """Verify handling of stock with 0 intraday volume or stagnant high."""
        latest_close = 100.0
        target_price = 105.0
        next_high = 100.0    # Stagnant high
        next_close = 100.0

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, next_close)
        assert outcome is not None
        hit_status, ret = outcome
        assert hit_status == 0

    def test_r2_negative_or_nan_prices(self, tmp_path):
        """Verify graceful rejection/handling of NaN or negative intraday high values."""
        latest_close = 100.0
        target_price = 105.0
        next_high = None     # Missing or NaN high

        outcome = create_test_db_for_target_eval(tmp_path, latest_close, target_price, next_high, 100.0)
        # Should remain pending (None outcome record or hit_status is None)
        assert outcome is None
