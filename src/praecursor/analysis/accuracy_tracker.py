"""
Accuracy Tracker for Praecursor-EGX.
Resolves and calculates empirical accuracy metrics from signal outcomes.
"""

from datetime import datetime, timezone
import logging
import math
from pathlib import Path
import csv
import sqlite3
import pandas as pd

logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).resolve().parents[3] / "database" / "praecursor.db"


class AccuracyTracker:
    def __init__(self, db_path: Path | str | None = None, database_path: Path | str | None = None):
        target = db_path if db_path is not None else database_path
        if target is None:
            self.db_path = DATABASE_PATH
        else:
            self.db_path = Path(target)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def evaluate_outcomes(self, as_of_date: str | None = None) -> int:
        """Resolve pending signals against subsequent price bars."""
        if not self.db_path.exists():
            logger.warning(f"[AUTO-OUTCOME] Database not found at {self.db_path}")
            return 0

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scanner_signals', 'scanner_signal_outcomes', 'source_prices')")
            existing_tables = {row['name'] for row in cursor.fetchall()}
            if not {'scanner_signals', 'scanner_signal_outcomes', 'source_prices'}.issubset(existing_tables):
                return 0
            
            # Ensure columns exist
            cursor.execute("PRAGMA table_info(scanner_signal_outcomes)")
            cols = [r['name'] for r in cursor.fetchall()]
            if "next_day_return" not in cols:
                cursor.execute("ALTER TABLE scanner_signal_outcomes ADD COLUMN next_day_return REAL")
            if "next_day_max_return" not in cols:
                cursor.execute("ALTER TABLE scanner_signal_outcomes ADD COLUMN next_day_max_return REAL")
            conn.commit()

            query = """
            SELECT s.run_id, s.symbol, s.next_day_target, date(s.generated_at) as run_date, s.next_day_label, s.latest_close
            FROM scanner_signals s
            LEFT JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
            WHERE (o.next_day_hit IS NULL)
            """
            pending = conn.execute(query).fetchall()
            resolved = 0
            for sig in pending:
                run_id = sig["run_id"]
                symbol = sig["symbol"]
                target = float(sig["next_day_target"]) if sig["next_day_target"] is not None else 0.0
                run_date = sig["run_date"]
                label = sig["next_day_label"]
                entry_price = float(sig["latest_close"]) if sig["latest_close"] else 0.0

                price_row = conn.execute("""
                    SELECT date(trade_date) as trade_date, open, high, low, close
                    FROM source_prices
                    WHERE ticker = ? AND date(trade_date) > ?
                    ORDER BY trade_date ASC LIMIT 1
                """, (symbol, run_date)).fetchone()

                if not price_row:
                    continue

                if price_row["high"] is None or price_row["close"] is None:
                    continue

                try:
                    high = float(price_row["high"])
                    close = float(price_row["close"])
                except (TypeError, ValueError):
                    continue

                if math.isnan(high) or math.isnan(close):
                    continue

                if target > 0:
                    effective_target = target
                elif entry_price > 0:
                    effective_target = entry_price * 1.025
                else:
                    effective_target = 0.0

                hit = 1 if (effective_target > 0 and high >= effective_target) else 0

                ret = (close - entry_price) / entry_price * 100.0 if entry_price > 0 else 0.0
                max_ret = (high - entry_price) / entry_price * 100.0 if entry_price > 0 else 0.0

                conn.execute("""
                    INSERT INTO scanner_signal_outcomes (run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, next_day_max_return, swing_label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '')
                    ON CONFLICT(run_id, symbol) DO UPDATE SET
                        next_day_hit = excluded.next_day_hit,
                        next_day_return = excluded.next_day_return,
                        next_day_max_return = excluded.next_day_max_return
                """, (run_id, symbol, run_date, label, hit, ret, max_ret))
                resolved += 1

            conn.commit()
            return resolved

    def update_historical_outcomes(self) -> int:
        return self.evaluate_outcomes()

    def export_accuracy_history_archive(self, csv_path: Path | str) -> Path:
        """Export cumulative accuracy archive to CSV."""
        out_path = Path(csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT 
                    s.run_id, s.symbol, s.company, date(s.generated_at) as signal_date,
                    s.opportunity_score, s.next_day_score, s.next_day_label,
                    s.latest_close, s.next_day_target,
                    o.next_day_hit
                FROM scanner_signals s
                JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
                WHERE o.next_day_hit IS NOT NULL
                ORDER BY s.run_id ASC, s.rank ASC
            """).fetchall()

            records = []
            cum_total = 0
            cum_hits = 0
            seen = set()

            for r in rows:
                key = (r["signal_date"], r["symbol"])
                if key in seen:
                    continue
                seen.add(key)

                hit = int(r["next_day_hit"])
                cum_total += 1
                cum_hits += hit
                acc = (cum_hits / cum_total * 100.0) if cum_total > 0 else 0.0

                records.append({
                    "signal_date": r["signal_date"],
                    "run_id": r["run_id"],
                    "symbol": r["symbol"],
                    "company": r["company"] or r["symbol"],
                    "opportunity_score": r["opportunity_score"] or 0.0,
                    "next_day_score": r["next_day_score"] or 0.0,
                    "next_day_label": r["next_day_label"] or "",
                    "latest_close": r["latest_close"] or 0.0,
                    "next_day_target": r["next_day_target"] or 0.0,
                    "next_day_hit": hit,
                    "cumulative_total": cum_total,
                    "cumulative_hits": cum_hits,
                    "cumulative_accuracy_pct": round(acc, 2),
                })

            if records:
                fieldnames = list(records[0].keys())
                with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)

        return out_path

    def get_summary(self) -> dict:
        """Return aggregate summary metrics."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN next_day_hit = 1 THEN 1 ELSE 0 END) as hits,
                    AVG(next_day_return) as avg_return,
                    AVG(next_day_max_return) as avg_max_return
                FROM scanner_signal_outcomes
                WHERE next_day_hit IS NOT NULL
            """).fetchone()

            total = row[0] or 0
            hits = row[1] or 0
            win_rate = (hits / total * 100.0) if total > 0 else 0.0
            return {
                "total_signals": total,
                "hits": hits,
                "win_rate": win_rate,
                "avg_return": row[2] or 0.0,
                "avg_max_return": row[3] or 0.0,
            }


def track_outcomes_from_db(db_path: Path | str | None = None) -> int:
    """Auto-backfill outcomes for all prior predictions from the database."""
    try:
        resolved_db_path = Path(db_path) if db_path is not None else DATABASE_PATH
        if not resolved_db_path.exists():
            logger.warning(f"[AUTO-OUTCOME] Database not found at {resolved_db_path}")
            return 0

        tracker = AccuracyTracker(db_path=resolved_db_path)
        backfilled = tracker.evaluate_outcomes()
        if backfilled > 0:
            logger.info(f"[AUTO-OUTCOME] Backfilled {backfilled} prediction outcomes from prior scans.")
        return backfilled
    except Exception as e:
        logger.warning(f"[AUTO-OUTCOME] Could not backfill outcomes: {e}")
        return 0

