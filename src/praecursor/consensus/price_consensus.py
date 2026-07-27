from dataclasses import dataclass, field
from datetime import date
from statistics import median


@dataclass(frozen=True)
class SourcePrice:
    """One source's price observation for one symbol and date."""

    source_name: str
    symbol: str
    trade_date: date
    close: float
    volume: int | None = None


@dataclass(frozen=True)
class SourceAgreement:
    """Agreement result for one source compared with consensus."""

    source_name: str
    close: float
    difference_percent: float
    agrees: bool


@dataclass(frozen=True)
class PriceConsensusResult:
    """Consensus result for one symbol and trade date."""

    symbol: str
    trade_date: date
    consensus_close: float
    source_count: int
    agreeing_source_count: int
    target_source_count: int
    tolerance_percent: float
    minimum_agreeing_sources: int
    accepted: bool
    agreements: list[SourceAgreement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def agreement_percent(self) -> float:
        if self.source_count == 0:
            return 0.0

        return (self.agreeing_source_count / self.source_count) * 100

    @property
    def confidence_percent(self) -> float:
        if self.target_source_count == 0:
            return 0.0

        return min((self.agreeing_source_count / self.target_source_count) * 100, 100.0)


class PriceConsensusEngine:
    """
    Compare prices from independent sources and calculate consensus.

    Numeric market data rarely matches exactly across sources. We therefore
    compare each close price with the median close and treat it as agreement
    when the percentage difference is inside a tolerance.
    """

    def __init__(
        self,
        tolerance_percent: float = 0.5,
        minimum_agreeing_sources: int = 3,
        target_source_count: int = 5,
    ):
        if tolerance_percent < 0:
            raise ValueError("tolerance_percent cannot be negative.")

        if minimum_agreeing_sources < 1:
            raise ValueError("minimum_agreeing_sources must be at least 1.")

        if target_source_count < 1:
            raise ValueError("target_source_count must be at least 1.")

        self.tolerance_percent = tolerance_percent
        self.minimum_agreeing_sources = minimum_agreeing_sources
        self.target_source_count = target_source_count

    def calculate(self, symbol: str, trade_date: date, prices: list[SourcePrice]) -> PriceConsensusResult:
        """Calculate close-price consensus for one symbol and date."""
        normalized_symbol = symbol.strip().upper()
        relevant_prices, warnings = self._filter_prices(normalized_symbol, trade_date, prices)

        if not relevant_prices:
            raise ValueError(f"No source prices provided for {normalized_symbol} on {trade_date}.")

        consensus_close = float(median([price.close for price in relevant_prices]))
        agreements = [self._calculate_agreement(price, consensus_close) for price in relevant_prices]
        agreeing_source_count = sum(1 for agreement in agreements if agreement.agrees)
        accepted = agreeing_source_count >= self.minimum_agreeing_sources

        if len(relevant_prices) < self.minimum_agreeing_sources:
            warnings.append(
                f"Only {len(relevant_prices)} source(s) available; "
                f"{self.minimum_agreeing_sources} agreeing sources are required for acceptance."
            )

        if not accepted:
            warnings.append(
                f"Consensus not accepted: {agreeing_source_count} agreeing source(s), "
                f"minimum required is {self.minimum_agreeing_sources}."
            )

        return PriceConsensusResult(
            symbol=normalized_symbol,
            trade_date=trade_date,
            consensus_close=consensus_close,
            source_count=len(relevant_prices),
            agreeing_source_count=agreeing_source_count,
            target_source_count=self.target_source_count,
            tolerance_percent=self.tolerance_percent,
            minimum_agreeing_sources=self.minimum_agreeing_sources,
            accepted=accepted,
            agreements=agreements,
            warnings=warnings,
        )

    def _filter_prices(
        self,
        symbol: str,
        trade_date: date,
        prices: list[SourcePrice],
    ) -> tuple[list[SourcePrice], list[str]]:
        relevant_prices: list[SourcePrice] = []
        warnings: list[str] = []
        seen_sources: set[str] = set()

        for price in prices:
            if price.symbol.strip().upper() != symbol:
                warnings.append(
                    f"Ignored {price.source_name}: expected symbol {symbol}, got {price.symbol}."
                )
                continue

            if price.trade_date != trade_date:
                warnings.append(
                    f"Ignored {price.source_name}: expected date {trade_date}, got {price.trade_date}."
                )
                continue

            if price.close <= 0:
                warnings.append(f"Ignored {price.source_name}: close price must be positive.")
                continue

            source_key = price.source_name.strip().lower()

            if source_key in seen_sources:
                warnings.append(f"Ignored duplicate source price from {price.source_name}.")
                continue

            seen_sources.add(source_key)
            relevant_prices.append(price)

        return relevant_prices, warnings

    def _calculate_agreement(self, price: SourcePrice, consensus_close: float) -> SourceAgreement:
        difference_percent = self._percent_difference(price.close, consensus_close)

        return SourceAgreement(
            source_name=price.source_name,
            close=price.close,
            difference_percent=difference_percent,
            agrees=difference_percent <= self.tolerance_percent,
        )

    def _percent_difference(self, value: float, reference: float) -> float:
        if reference == 0:
            return 0.0

        return abs(value - reference) / reference * 100
