from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import sqlite3

from praecursor.collectors.collection_result import CollectionResult
from praecursor.core.price_bar import PriceBar
from praecursor.storage.database import DATABASE, connect
from praecursor.storage.schema import PRICE_CACHE_SCHEMA


class PriceCache:
    """SQLite cache for validated source-specific price bars."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path
        self.initialize()

    @property
    def path(self) -> Path:
        """Actual SQLite database path used by this cache."""
        return self.database_path or DATABASE

    def initialize(self) -> None:
        """Create the cache table if it does not already exist."""
        with closing(self._connect()) as connection:
            connection.executescript(PRICE_CACHE_SCHEMA)
            connection.commit()

    def save(self, result: CollectionResult) -> int:
        """
        Save a collection result into SQLite.

        If the same ticker, trade date, and source already exist, the row is
        updated instead of duplicated.
        """
        if not result.price_bars:
            return 0

        rows = [
            (
                result.symbol,
                bar.date.date().isoformat(),
                result.source_name,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                int(bar.volume),
                result.confidence,
                result.collected_at.isoformat(),
            )
            for bar in result.price_bars
        ]

        with closing(self._connect()) as connection:
            connection.executemany(
                """
                INSERT INTO source_prices (
                    ticker,
                    trade_date,
                    source,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    confidence,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, trade_date, source) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    confidence = excluded.confidence,
                    collected_at = excluded.collected_at
                """,
                rows,
            )
            connection.commit()

        return len(rows)

    def load(
        self,
        symbol: str,
        source_name: str,
        start_date: date,
        end_date: date,
    ) -> list[PriceBar]:
        """Load cached bars for one symbol and source."""
        start_text = start_date.isoformat()
        end_text = end_date.isoformat()

        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT trade_date, open, high, low, close, volume
                FROM source_prices
                WHERE ticker = ?
                  AND source = ?
                  AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date ASC
                """,
                (symbol, source_name, start_text, end_text),
            ).fetchall()

        return [self._row_to_price_bar(row) for row in rows]

    def count(self, symbol: str, source_name: str) -> int:
        """Count cached rows for one symbol and source."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM source_prices
                WHERE ticker = ? AND source = ?
                """,
                (symbol, source_name),
            ).fetchone()

        return int(row[0])

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def _row_to_price_bar(self, row: sqlite3.Row) -> PriceBar:
        return PriceBar(
            date=datetime.strptime(row["trade_date"], "%Y-%m-%d"),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row["volume"]),
        )
