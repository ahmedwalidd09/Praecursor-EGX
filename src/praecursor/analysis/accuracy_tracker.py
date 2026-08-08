import csv
from contextlib import closing
from datetime import datetime, timezone, date, timedelta
import logging
from pathlib import Path
import sqlite3

from praecursor.storage.database import connect
from praecursor.storage.price_cache import PriceCache
from praecursor.storage.signal_history import SignalHistoryStore

logger = logging.getLogger(__name__)


class AccuracyTracker:
    def __init__(self, database_path=None):
        self.database_path = database_path
        # Ensure schema is initialized (adds new columns if needed)
        SignalHistoryStore(database_path).initialize()
        PriceCache(database_path).initialize()

    def _connect(self):
        return connect(self.database_path)

    def update_historical_outcomes(self):
        """
        For each past day's scan, find the top 8 next-day candidates (by rank),
        then check whether the NEXT trading day's HIGH reached the predicted
        target_price. HIT = high >= target, MISS = high < target.

        Only the top 8 are evaluated. Everything else is ignored.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row

            # ---- Step 1: identify the latest run per calendar day ----
            day_runs = conn.execute("""
                SELECT id, date(generated_at) as run_date, generated_at
                FROM scanner_runs
                WHERE id IN (
                    SELECT MIN(id) FROM scanner_runs
                    GROUP BY date(generated_at)
                )
                ORDER BY generated_at ASC
            """).fetchall()

            if day_runs:
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

                        # If target is 0, fall back to latest_close (HIT if high >= close)
                        if target <= 0:
                            target = latest_close

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

                        # Intraday target verification logic (R2):
                        # Candidate target hit: next_day_hit = 1 if high >= target_price else 0
                        # Strict target verification: intraday high reaching target is recorded as a HIT
                        # even if closing price close < target. Removed 2.5% solid gain fallback.
                        next_day_hit = 1 if high >= target else 0

                        next_day_return = ((close_next - latest_close) / latest_close * 100.0) if latest_close > 0 else 0.0
                        next_day_max_return = ((high - latest_close) / latest_close * 100.0) if latest_close > 0 else 0.0

                        # Upsert into outcomes
                        conn.execute("""
                            INSERT INTO scanner_signal_outcomes (
                                run_id, symbol, signal_date,
                                next_day_label, next_day_hit, next_day_return,
                                next_day_max_return,
                                swing_label, swing_hit, swing_max_return, swing_days_held
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, '', NULL, NULL, NULL)
                            ON CONFLICT(run_id, symbol) DO UPDATE SET
                                next_day_hit        = excluded.next_day_hit,
                                next_day_return     = excluded.next_day_return,
                                next_day_max_return = excluded.next_day_max_return,
                                next_day_label      = excluded.next_day_label
                        """, (run_id, symbol, run_date, label, next_day_hit, next_day_return, next_day_max_return))

                    conn.commit()
                    logger.info("Updated historical outcomes for run %s (%s).", run_id, run_date)

        # Automatically export cumulative history archive CSV (R3)
        self.export_accuracy_history_archive()

    def export_accuracy_history_archive(self, export_path=None):
        """
        Cumulative Historical Archive (R3):
        Generate reports/archive/accuracy_history_archive.csv maintaining running total
        accuracy metrics across multiple runs without overwriting prior records.
        """
        if export_path is None:
            root = Path(__file__).resolve().parents[3]
            export_path = root / "reports" / "archive" / "accuracy_history_archive.csv"
        else:
            export_path = Path(export_path)

        export_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            query = """
            WITH day_runs AS (
                SELECT MIN(id) as run_id, date(generated_at) as run_date
                FROM scanner_runs
                GROUP BY date(generated_at)
            ),
            top8 AS (
                SELECT s.run_id, s.symbol, s.next_day_target, s.latest_close,
                       ROW_NUMBER() OVER(PARTITION BY s.run_id ORDER BY s.rank ASC) as rn
                FROM scanner_signals s
                JOIN day_runs dr ON s.run_id = dr.run_id
            )
            SELECT o.signal_date, o.run_id, o.symbol,
                   COALESCE(t.latest_close, 0.0) as latest_close,
                   COALESCE(t.next_day_target, 0.0) as next_day_target,
                   o.next_day_label, o.next_day_hit, o.next_day_return,
                   COALESCE(o.next_day_max_return, 0.0) as next_day_max_return
            FROM scanner_signal_outcomes o
            LEFT JOIN top8 t ON t.run_id = o.run_id AND t.symbol = o.symbol
            WHERE o.next_day_hit IS NOT NULL
            ORDER BY o.signal_date ASC, o.run_id ASC, o.id ASC
            """
            rows = conn.execute(query).fetchall()

        fieldnames = [
            "signal_date",
            "run_id",
            "symbol",
            "latest_close",
            "next_day_target",
            "next_day_label",
            "next_day_hit",
            "next_day_return",
            "next_day_max_return",
            "cumulative_total",
            "cumulative_hits",
            "cumulative_accuracy_pct"
        ]

        running_total = 0
        running_hits = 0

        with open(export_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for r in rows:
                hit = r["next_day_hit"]
                running_total += 1
                if hit == 1:
                    running_hits += 1

                accuracy_pct = (running_hits / running_total * 100.0) if running_total > 0 else 0.0

                writer.writerow({
                    "signal_date": r["signal_date"],
                    "run_id": r["run_id"],
                    "symbol": r["symbol"],
                    "latest_close": r["latest_close"],
                    "next_day_target": r["next_day_target"],
                    "next_day_label": r["next_day_label"],
                    "next_day_hit": hit,
                    "next_day_return": r["next_day_return"],
                    "next_day_max_return": r["next_day_max_return"],
                    "cumulative_total": running_total,
                    "cumulative_hits": running_hits,
                    "cumulative_accuracy_pct": round(accuracy_pct, 2)
                })

        logger.info("Exported accuracy history archive to %s (%d records)", export_path, running_total)
        return export_path

    def get_accuracy_stats(self):
        """Return accuracy stats restricted to the top 8 candidates per day."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row

            # ---- aggregate next-day accuracy (top 8 only) ----
            next_day_query = """
            WITH day_runs AS (
                SELECT MIN(id) as run_id, date(generated_at) as run_date
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
                SELECT MIN(id) as run_id, date(generated_at) as run_date
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

