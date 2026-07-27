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
    FOREIGN KEY(run_id) REFERENCES scanner_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_scanner_signals_symbol_run
ON scanner_signals (symbol, run_id);
"""


class SignalHistoryStore:
    """Persist scanner runs and ranked opportunity signals."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SIGNAL_HISTORY_SCHEMA)
            connection.commit()

    def latest_ranks(self) -> dict[str, int]:
        """Return symbol -> rank for the most recent stored scanner run."""
        with self._connect() as connection:
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

    def save_run(self, result: Any) -> int:
        """Save a completed ScannerRunResult and return scanner_runs.id."""
        generated_at = result.generated_at.isoformat()

        with self._connect() as connection:
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
                rows.append(
                    (
                        run_id,
                        generated_at,
                        rank,
                        score.symbol,
                        score.company,
                        score.score_percent,
                        symbol_result.final_predictor_score,
                        symbol_result.predictor_label,
                        score.latest_close,
                        consensus_confidence,
                        symbol_result.data_quality_score,
                        symbol_result.previous_rank,
                        symbol_result.rank_change,
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
                    rank_change
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()

        return run_id

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
