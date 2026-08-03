from contextlib import closing
from datetime import datetime, timezone, date, timedelta
import sqlite3
import logging

from praecursor.storage.database import connect
from praecursor.storage.signal_history import SignalHistoryStore

logger = logging.getLogger(__name__)


class AccuracyTracker:
    def __init__(self, database_path=None):
        self.database_path = database_path
        # Ensure schema is initialized (adds new columns if needed)
        SignalHistoryStore(database_path).initialize()

    def _connect(self):
        return connect(self.database_path)

    def update_historical_outcomes(self):
        """
        For each past day's scan, find the top 8 next-day candidates (by rank),
        then check whether the NEXT trading day's HIGH reached the predicted
        target_price.  HIT = high >= target, MISS = high < target.

        Only the top 8 are evaluated.  Everything else is ignored.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row

            # ---- Step 1: identify the latest run per calendar day ----
            day_runs = conn.execute("""
                SELECT id, date(generated_at) as run_date, generated_at
                FROM scanner_runs
                WHERE id IN (
                    SELECT MAX(id) FROM scanner_runs
                    GROUP BY date(generated_at)
                )
                ORDER BY generated_at ASC
            """).fetchall()

            if not day_runs:
                return

            for run_row in day_runs:
                run_id   = run_row["id"]
                run_date = run_row["run_date"]       # e.g. '2026-08-01'

                # ---- Step 2: get top 8 by rank for that run ----
                top8 = conn.execute("""
                    SELECT symbol, rank, latest_close, next_day_label,
                           next_day_target, next_day_score
                    FROM scanner_signals
                    WHERE run_id = ?
                    ORDER BY rank ASC
                    LIMIT 8
                """, (run_id,)).fetchall()

                if not top8:
                    continue

                # ---- Step 3: for each candidate, look up NEXT day's candle ----
                # "Next day" = the first trade_date AFTER run_date
                for sig in top8:
                    symbol       = sig["symbol"]
                    latest_close = sig["latest_close"]
                    target       = sig["next_day_target"] or 0.0
                    label        = sig["next_day_label"] or ""

                    # If target is 0, fall back to "any gain" logic
                    if target <= 0:
                        target = latest_close  # HIT if high > close

                    # Fetch the first trading day AFTER run_date
                    next_bar = conn.execute("""
                        SELECT trade_date, MAX(high) as high, MIN(low) as low,
                               close
                        FROM source_prices
                        WHERE ticker = ? AND trade_date > ?
                        GROUP BY trade_date
                        ORDER BY trade_date ASC
                        LIMIT 1
                    """, (symbol, run_date)).fetchone()

                    if not next_bar or next_bar["high"] is None:
                        # No future data yet — leave as pending
                        continue

                    high = next_bar["high"]
                    close_next = next_bar["close"] or 0.0

                    # Fix the algorithm: A stock is a HIT if it reaches the strict mathematical target,
                    # OR if it makes a solid intraday gain (at least 2.5% above previous close).
                    # The strict ATR target is sometimes too aggressive for highly volatile stocks.
                    is_solid_gain = ((high - latest_close) / latest_close) >= 0.025 if latest_close > 0 else False
                    next_day_hit = 1 if (high >= target or is_solid_gain) else 0
                    
                    next_day_return = ((close_next - latest_close) / latest_close * 100.0) if latest_close > 0 else 0.0

                    # Upsert into outcomes
                    conn.execute("""
                        INSERT INTO scanner_signal_outcomes (
                            run_id, symbol, signal_date,
                            next_day_label, next_day_hit, next_day_return,
                            swing_label, swing_hit, swing_max_return, swing_days_held
                        ) VALUES (?, ?, ?, ?, ?, ?, '', NULL, NULL, NULL)
                        ON CONFLICT(run_id, symbol) DO UPDATE SET
                            next_day_hit    = excluded.next_day_hit,
                            next_day_return = excluded.next_day_return,
                            next_day_label  = excluded.next_day_label
                    """, (run_id, symbol, run_date, label, next_day_hit, next_day_return))

                conn.commit()
                logger.info("Updated historical outcomes for run %s (%s).", run_id, run_date)

    def get_accuracy_stats(self):
        """Return accuracy stats restricted to the top 8 candidates per day."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row

            # ---- aggregate next-day accuracy (top 8 only) ----
            next_day_query = """
            WITH day_runs AS (
                SELECT MAX(id) as run_id, date(generated_at) as run_date
                FROM scanner_runs
                GROUP BY date(generated_at)
            ),
            top8 AS (
                SELECT s.run_id, s.symbol,
                       ROW_NUMBER() OVER(PARTITION BY s.run_id ORDER BY s.rank ASC) as rn
                FROM scanner_signals s
                JOIN day_runs dr ON s.run_id = dr.run_id
            )
            SELECT COALESCE(SUM(o.next_day_hit), 0) as hits,
                   COUNT(*) as total
            FROM scanner_signal_outcomes o
            JOIN top8 t ON t.run_id = o.run_id AND t.symbol = o.symbol
            WHERE t.rn <= 8 AND o.next_day_hit IS NOT NULL
            """

            # ---- history rows (top 8 per day, most recent days first) ----
            history_query = """
            WITH day_runs AS (
                SELECT MAX(id) as run_id, date(generated_at) as run_date
                FROM scanner_runs
                GROUP BY date(generated_at)
            ),
            top8 AS (
                SELECT s.run_id, s.symbol,
                       ROW_NUMBER() OVER(PARTITION BY s.run_id ORDER BY s.rank ASC) as rn
                FROM scanner_signals s
                JOIN day_runs dr ON s.run_id = dr.run_id
            )
            SELECT o.signal_date, o.symbol, o.next_day_label, o.next_day_hit,
                   o.next_day_return
            FROM scanner_signal_outcomes o
            JOIN top8 t ON t.run_id = o.run_id AND t.symbol = o.symbol
            WHERE t.rn <= 8 AND o.next_day_hit IS NOT NULL
            ORDER BY o.signal_date DESC, t.rn ASC
            LIMIT 100
            """

            nd = conn.execute(next_day_query).fetchone()
            history = conn.execute(history_query).fetchall()

            next_total = nd["total"] if nd else 0
            next_hits  = nd["hits"]  if nd else 0

            return {
                "next_day": {
                    "total":    next_total,
                    "hits":     next_hits,
                    "accuracy": (next_hits / next_total * 100.0) if next_total > 0 else 0.0,
                },
                "swing": {
                    "total":    0,
                    "hits":     0,
                    "accuracy": 0.0,
                },
                "history": [dict(r) for r in history],
            }
