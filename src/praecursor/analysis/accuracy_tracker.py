"""
Accuracy Tracker for Praecursor-EGX.
Resolves and calculates empirical accuracy metrics from signal outcomes.
"""

from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import logging
import math
from pathlib import Path
import csv
import sqlite3
from statistics import median
from typing import Any

from praecursor.storage.database import DATABASE, connect

logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).resolve().parents[3] / "database" / "praecursor.db"


def _parse_signal_date(gen_at_val: Any) -> date:
    """Parse generated_at safely, converting UTC to Cairo local date if timezone-aware."""
    if not gen_at_val:
        return date.today()
    if isinstance(gen_at_val, datetime):
        dt = gen_at_val
    elif isinstance(gen_at_val, date):
        return gen_at_val
    else:
        val_str = str(gen_at_val).strip()
        try:
            clean_str = val_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
        except Exception:
            try:
                return datetime.strptime(val_str[:10], "%Y-%m-%d").date()
            except Exception:
                return date.today()

    if dt.tzinfo is not None:
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo("Africa/Cairo"))
        except Exception:
            dt = dt.astimezone(timezone(timedelta(hours=3)))
    return dt.date()


class AccuracyTracker:
    def __init__(self, db_path: Path | str | None = None, database_path: Path | str | None = None):
        target = db_path if db_path is not None else database_path
        if target is None:
            self.db_path = DATABASE_PATH
        else:
            self.db_path = Path(target)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def evaluate_outcomes(self, as_of_date: str | None = None) -> int:
        """Resolve pending signals against subsequent price bars."""
        if not self.db_path.exists():
            logger.warning(f"[AUTO-OUTCOME] Database not found at {self.db_path}")
            return 0

        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if required tables exist
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scanner_signals', 'scanner_signal_outcomes', 'source_prices')"
            )
            existing_tables = {row["name"] for row in cursor.fetchall()}
            if not {"scanner_signals", "scanner_signal_outcomes", "source_prices"}.issubset(existing_tables):
                return 0

            # Ensure columns exist
            cursor.execute("PRAGMA table_info(scanner_signal_outcomes)")
            cols = [r["name"] for r in cursor.fetchall()]
            if "next_day_return" not in cols:
                cursor.execute("ALTER TABLE scanner_signal_outcomes ADD COLUMN next_day_return REAL")
            if "next_day_max_return" not in cols:
                cursor.execute("ALTER TABLE scanner_signal_outcomes ADD COLUMN next_day_max_return REAL")
            conn.commit()

            query = """
            SELECT s.run_id, s.symbol, s.next_day_target, s.generated_at, s.next_day_label, s.latest_close
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
                label = sig["next_day_label"] or ""
                entry_price = float(sig["latest_close"]) if sig["latest_close"] else 0.0

                if entry_price <= 0.0 or math.isnan(entry_price):
                    continue

                signal_dt = _parse_signal_date(sig["generated_at"])
                run_date = signal_dt.isoformat()

                # Find latest known trade_date on or before signal generation to anchor reference date
                base_row = conn.execute(
                    """
                    SELECT date(trade_date) as base_date
                    FROM source_prices
                    WHERE ticker = ? AND date(trade_date) <= ? AND close > 0
                    ORDER BY date(trade_date) DESC LIMIT 1
                    """,
                    (symbol, run_date),
                ).fetchone()
                ref_date = base_row["base_date"] if base_row else run_date

                # Find the earliest subsequent trading date strictly after the reference date
                next_date_row = conn.execute(
                    """
                    SELECT date(trade_date) as next_trade_date
                    FROM source_prices
                    WHERE ticker = ? AND date(trade_date) > ? AND close > 0 AND high > 0
                    ORDER BY date(trade_date) ASC LIMIT 1
                    """,
                    (symbol, ref_date),
                ).fetchone()

                if not next_date_row:
                    continue

                next_date = next_date_row["next_trade_date"]

                # Fetch all available price bars for that ticker on the next trade date
                price_rows = conn.execute(
                    """
                    SELECT open, high, low, close
                    FROM source_prices
                    WHERE ticker = ? AND date(trade_date) = ? AND close > 0
                    """,
                    (symbol, next_date),
                ).fetchall()

                if not price_rows:
                    continue

                valid_highs = []
                valid_closes = []
                valid_opens = []

                for pr in price_rows:
                    try:
                        c = float(pr["close"]) if pr["close"] is not None else None
                        h = float(pr["high"]) if pr["high"] is not None else None
                        o = float(pr["open"]) if pr["open"] is not None else None
                        if c is not None and not math.isnan(c) and c > 0:
                            valid_closes.append(c)
                        if h is not None and not math.isnan(h) and h > 0:
                            valid_highs.append(h)
                        if o is not None and not math.isnan(o) and o > 0:
                            valid_opens.append(o)
                    except (ValueError, TypeError):
                        continue

                if not valid_closes or not valid_highs:
                    continue

                close = median(valid_closes)
                raw_high = max(valid_highs)
                raw_open = valid_opens[0] if valid_opens else close

                # High/low bounds normalization: high cannot be lower than close or open
                high = max(raw_high, close, raw_open)

                # Determine effective target and adjust for corporate actions / stock splits
                effective_entry = entry_price
                if target > 0:
                    effective_target = target
                else:
                    effective_target = entry_price * 1.025

                # Detect split-unadjusted high/low bounds:
                # EGX daily price circuit breaker limit is +-20%.
                # Moves beyond +-35% indicate stock splits or capital changes.
                ratio = close / entry_price
                if ratio < 0.65 and close > 0:
                    # Forward stock split (2:1, 3:1, 4:1, 5:1, 10:1, 20:1)
                    inv_ratio = entry_price / close
                    factor = round(inv_ratio)
                    if factor in (2, 3, 4, 5, 8, 10, 20) and abs(inv_ratio - factor) / factor < 0.20:
                        effective_entry = entry_price / factor
                        effective_target = effective_target / factor
                elif ratio > 1.50 and entry_price > 0:
                    # Reverse stock split (1:2, 1:3, 1:4, 1:5, 1:10)
                    factor = round(ratio)
                    if factor in (2, 3, 4, 5, 8, 10, 20) and abs(ratio - factor) / factor < 0.20:
                        effective_entry = entry_price * factor
                        effective_target = effective_target * factor

                hit = 1 if (effective_target > 0 and high >= effective_target) else 0

                ret = (close - effective_entry) / effective_entry * 100.0 if effective_entry > 0 else 0.0
                max_ret = (high - effective_entry) / effective_entry * 100.0 if effective_entry > 0 else 0.0

                conn.execute(
                    """
                    INSERT INTO scanner_signal_outcomes (run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, next_day_max_return, swing_label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '')
                    ON CONFLICT(run_id, symbol) DO UPDATE SET
                        next_day_hit = excluded.next_day_hit,
                        next_day_return = excluded.next_day_return,
                        next_day_max_return = excluded.next_day_max_return
                    """,
                    (run_id, symbol, run_date, label, hit, ret, max_ret),
                )
                resolved += 1

            conn.commit()
            return resolved

    def update_historical_outcomes(self) -> int:
        return self.evaluate_outcomes()

    def get_accuracy_stats(self) -> dict:
        """Return structured accuracy statistics and historical outcomes."""
        default_result = {
            "next_day": {
                "total": 0,
                "hits": 0,
                "accuracy": 0.0,
                "avg_return": 0.0,
                "avg_max_return": 0.0,
            },
            "history": [],
        }
        if not self.db_path.exists():
            return default_result

        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scanner_signal_outcomes'")
            if not cursor.fetchone():
                return default_result

            rows = conn.execute(
                """
                SELECT run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, next_day_max_return, swing_label
                FROM scanner_signal_outcomes
                WHERE next_day_hit IS NOT NULL
                ORDER BY signal_date ASC, run_id ASC
                """
            ).fetchall()

            if not rows:
                return default_result

            history = [dict(r) for r in rows]
            total = len(history)
            hits = sum(1 for r in history if r.get("next_day_hit") == 1)
            accuracy = (hits / total * 100.0) if total > 0 else 0.0

            valid_returns = [float(r["next_day_return"]) for r in history if r.get("next_day_return") is not None]
            avg_return = (sum(valid_returns) / len(valid_returns)) if valid_returns else 0.0

            valid_max_returns = [float(r["next_day_max_return"]) for r in history if r.get("next_day_max_return") is not None]
            avg_max_return = (sum(valid_max_returns) / len(valid_max_returns)) if valid_max_returns else 0.0

            return {
                "next_day": {
                    "total": total,
                    "hits": hits,
                    "accuracy": accuracy,
                    "avg_return": avg_return,
                    "avg_max_return": avg_max_return,
                },
                "history": history,
            }

    def export_accuracy_history_archive(self, csv_path: Path | str) -> Path:
        """Export cumulative accuracy archive to CSV."""
        out_path = Path(csv_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT 
                    s.run_id, s.symbol, s.company, date(s.generated_at) as signal_date,
                    s.opportunity_score, s.next_day_score, s.next_day_label,
                    s.latest_close, s.next_day_target,
                    o.next_day_hit
                FROM scanner_signals s
                JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
                WHERE o.next_day_hit IS NOT NULL
                ORDER BY s.run_id ASC, s.rank ASC
                """
            ).fetchall()

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

            fieldnames = [
                "signal_date", "run_id", "symbol", "company",
                "opportunity_score", "next_day_score", "next_day_label",
                "latest_close", "next_day_target", "next_day_hit",
                "cumulative_total", "cumulative_hits", "cumulative_accuracy_pct"
            ]
            with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                if records:
                    writer.writerows(records)

        return out_path

    def get_summary(self) -> dict:
        """Return aggregate summary metrics."""
        stats = self.get_accuracy_stats()
        nd = stats["next_day"]
        return {
            "total_signals": nd["total"],
            "hits": nd["hits"],
            "win_rate": nd["accuracy"],
            "avg_return": nd["avg_return"],
            "avg_max_return": nd["avg_max_return"],
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

