from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from praecursor.storage.database import connect

SIGNAL_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS scanner_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    symbols TEXT NOT NULL,
    success_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    report_path TEXT,
    markdown_report_path TEXT,
    archive_report_path TEXT,
    archive_markdown_report_path TEXT
);

CREATE TABLE IF NOT EXISTS scanner_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    rank INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    company TEXT NOT NULL,
    opportunity_score REAL NOT NULL,
    final_predictor_score REAL NOT NULL,
    predictor_label TEXT NOT NULL,
    latest_close REAL NOT NULL,
    consensus_confidence REAL NOT NULL,
    data_quality_score REAL NOT NULL,
    previous_rank INTEGER,
    rank_change INTEGER,
    score_components TEXT,
    next_day_score REAL DEFAULT 0,
    next_day_label TEXT DEFAULT '',
    next_day_target REAL DEFAULT 0,
    swing_score REAL DEFAULT 0,
    swing_label TEXT DEFAULT '',
    swing_stop_loss REAL DEFAULT 0,
    indicator_values_json TEXT DEFAULT NULL,
    FOREIGN KEY(run_id) REFERENCES scanner_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_scanner_signals_symbol_run
ON scanner_signals (symbol, run_id);

CREATE TABLE IF NOT EXISTS scanner_signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    
    -- Next-Day Outcome
    next_day_label TEXT NOT NULL,
    next_day_hit INTEGER, -- 1 for Hit, 0 for Miss, NULL for Pending
    next_day_return REAL,
    next_day_max_return REAL,
    
    -- Swing Outcome
    swing_label TEXT NOT NULL,
    swing_hit INTEGER, -- 1 for Hit, 0 for Miss, NULL for Pending
    swing_max_return REAL,
    swing_days_held INTEGER,
    
    FOREIGN KEY(run_id) REFERENCES scanner_runs(id),
    UNIQUE(run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_outcomes_signal_date
ON scanner_signal_outcomes (signal_date);
"""


class SignalHistoryStore:
    """Persist scanner runs and ranked opportunity signals."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path
        self.initialize()

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(SIGNAL_HISTORY_SCHEMA)
            
            # Safe migrations for new columns
            new_columns = [
                "next_day_score REAL DEFAULT 0",
                "next_day_label TEXT DEFAULT ''",
                "next_day_target REAL DEFAULT 0",
                "swing_score REAL DEFAULT 0",
                "swing_label TEXT DEFAULT ''",
                "swing_stop_loss REAL DEFAULT 0",
                "indicator_values_json TEXT DEFAULT NULL",
            ]
            for col in new_columns:
                try:
                    connection.execute(f"ALTER TABLE scanner_signals ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass # Column already exists

            outcome_columns = [
                "next_day_max_return REAL DEFAULT 0"
            ]
            for col in outcome_columns:
                try:
                    connection.execute(f"ALTER TABLE scanner_signal_outcomes ADD COLUMN {col}")
                except sqlite3.OperationalError:
                    pass # Column already exists
                    
            connection.commit()

    def latest_ranks(self) -> dict[str, int]:
        """Return symbol -> rank for the most recent stored scanner run."""
        try:
            with closing(self._connect()) as connection:
                connection.row_factory = sqlite3.Row
                latest_run = connection.execute(
                    "SELECT id FROM scanner_runs ORDER BY id DESC LIMIT 1"
                ).fetchone()

                if latest_run is None:
                    return {}

                rows = connection.execute(
                    """
                    SELECT symbol, rank
                    FROM scanner_signals
                    WHERE run_id = ?
                    """,
                    (latest_run["id"],),
                ).fetchall()

            return {row["symbol"]: int(row["rank"]) for row in rows}
        except sqlite3.OperationalError:
            self.initialize()
            return {}

    def save_run(self, result: Any) -> int:
        """Save a completed ScannerRunResult and return scanner_runs.id."""
        generated_at = result.generated_at.isoformat()

        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO scanner_runs (
                    generated_at,
                    source_name,
                    symbols,
                    success_count,
                    error_count,
                    report_path,
                    markdown_report_path,
                    archive_report_path,
                    archive_markdown_report_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generated_at,
                    result.source_name,
                    json.dumps(result.symbols),
                    result.success_count,
                    result.error_count,
                    str(result.report_path) if result.report_path else None,
                    str(result.markdown_report_path) if result.markdown_report_path else None,
                    str(result.archive_report_path) if result.archive_report_path else None,
                    str(result.archive_markdown_report_path) if result.archive_markdown_report_path else None,
                ),
            )
            run_id = int(cursor.lastrowid)

            rows = []
            for rank, symbol_result in enumerate(result.symbol_results, start=1):
                score = symbol_result.opportunity_score
                consensus_confidence = (
                    symbol_result.consensus_result.confidence_percent
                    if symbol_result.consensus_result
                    else 0.0
                )
                # Extract next-day target price from prediction
                nd_target = 0.0
                if hasattr(symbol_result, 'next_day_prediction') and symbol_result.next_day_prediction:
                    nd_target = float(symbol_result.next_day_prediction.target_price)
                    
                components_json = None
                if hasattr(score, 'components'):
                    try:
                        components_json = json.dumps([{"name": c.name, "score": c.score, "max_score": c.max_score} for c in score.components])
                    except Exception:
                        pass

                swing_score = float(getattr(symbol_result, 'swing_score', 0.0))
                swing_label = str(getattr(symbol_result, 'swing_label', ''))
                swing_stop_loss = float(getattr(symbol_result, 'swing_stop_loss', 0.0))

                indicator_values_json = None
                if hasattr(score, 'indicator_values'):
                    try:
                        indicator_values_json = json.dumps(score.indicator_values)
                    except Exception:
                        pass

                rows.append(
                    (
                        run_id,
                        generated_at,
                        rank,
                        score.symbol,
                        score.company,
                        float(score.score_percent),
                        float(symbol_result.final_predictor_score),
                        symbol_result.predictor_label,
                        float(score.latest_close),
                        float(consensus_confidence),
                        float(symbol_result.data_quality_score),
                        symbol_result.previous_rank,
                        symbol_result.rank_change,
                        float(symbol_result.next_day_score),
                        symbol_result.next_day_label,
                        nd_target,
                        swing_score,
                        swing_label,
                        swing_stop_loss,
                        components_json,
                        indicator_values_json,
                    )
                )

            connection.executemany(
                """
                INSERT INTO scanner_signals (
                    run_id,
                    generated_at,
                    rank,
                    symbol,
                    company,
                    opportunity_score,
                    final_predictor_score,
                    predictor_label,
                    latest_close,
                    consensus_confidence,
                    data_quality_score,
                    previous_rank,
                    rank_change,
                    next_day_score,
                    next_day_label,
                    next_day_target,
                    swing_score,
                    swing_label,
                    swing_stop_loss,
                    score_components,
                    indicator_values_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()

        return run_id

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
