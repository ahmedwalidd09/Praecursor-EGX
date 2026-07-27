from dataclasses import dataclass, field
from datetime import datetime, timezone

from praecursor.core.price_bar import PriceBar


@dataclass
class CollectionResult:
    """
    Normalized output from one market data source.

    A collector may read data from Yahoo Finance, EGX, Mubasher,
    StockAnalysis, CSV, or any future source. No matter where the data
    came from, it should return this same shape.
    """

    symbol: str
    source_name: str
    price_bars: list[PriceBar] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
