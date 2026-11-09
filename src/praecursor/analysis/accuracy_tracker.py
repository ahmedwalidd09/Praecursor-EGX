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
        if not self.db_path.exists():
            return 0
        from praecursor.analysis.verified_history import resolve_history
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"source_prices", "scanner_signals"}.issubset(names):
                return 0
            return resolve_history(conn, as_of_date)

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
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verified_outcomes'")
            if not cursor.fetchone():
                return default_result

            rows = conn.execute(
                """
                SELECT run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, next_day_max_return, swing_label
                FROM verified_outcomes
                WHERE next_day_hit IS NOT NULL
                ORDER BY signal_date ASC, run_id ASC
                """
            ).fetchall()

            if not rows:
                return default_result

            history = list({(r["signal_date"], r["symbol"]): dict(r) for r in reversed(rows)}.values())
            history.sort(key=lambda r: (r["signal_date"], r["symbol"]))
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
                    s.run_id, s.symbol, s.company, o.signal_date,
                    s.opportunity_score, s.next_day_score, s.next_day_label,
                    s.latest_close, s.next_day_target,
                    o.next_day_hit
                FROM scanner_signals s
                JOIN verified_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
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
            "target_touch_rate": nd["accuracy"],
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

