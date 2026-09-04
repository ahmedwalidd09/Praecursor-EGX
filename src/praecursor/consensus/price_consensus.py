import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import median

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourcePrice:
    """One source's price observation for one symbol and date."""

    source_name: str
    symbol: str
    trade_date: date
    close: float
    high: float | None = None
    volume: int | None = None


@dataclass(frozen=True)
class SourceAgreement:
    """Agreement result for one source compared with consensus."""

    source_name: str
    close: float
    difference_percent: float
    agrees: bool
    high: float | None = None
    high_difference_percent: float | None = None
    agrees_close: bool = True
    agrees_high: bool = True


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
    consensus_high: float = 0.0
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

    @property
    def confidence_label(self) -> str:
        """
        Human-readable consensus confidence.

        Current project policy:
        - 2 agreeing sources is accepted but still medium confidence.
        - 3+ agreeing sources against a 5-source target becomes high confidence.
        """
        if not self.accepted:
            return "low"

        if self.agreeing_source_count >= 3 and self.confidence_percent >= 60:
            return "high"

        if self.agreeing_source_count >= 2:
            return "medium"

        return "low"


class PriceConsensusEngine:
    """
    Compare prices from independent sources and calculate consensus.

    Numeric market data rarely matches exactly across sources. We therefore
    compare each close and high price with the median close and high, treating
    it as agreement when the percentage difference is inside a tolerance.
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
        """Calculate high and close price consensus for one symbol and date."""
        normalized_symbol = symbol.strip().upper()
        relevant_prices, warnings = self._filter_prices(normalized_symbol, trade_date, prices)

        if not relevant_prices:
            raise ValueError(f"No source prices provided for {normalized_symbol} on {trade_date}.")

        consensus_close = float(median([price.close for price in relevant_prices]))
        valid_highs = [p.high for p in relevant_prices if p.high is not None and p.high > 0]
        consensus_high = max(float(median(valid_highs)), consensus_close) if valid_highs else consensus_close

        logger.info(
            "Comparing multi-source price data for %s on %s across %d sources (TradingView, Mubasher, etc.):",
            normalized_symbol,
            trade_date,
            len(relevant_prices),
        )
        for price in relevant_prices:
            high_str = f"{price.high:.2f}" if price.high is not None else "N/A"
            logger.info(
                "  [Source: %s] High: %s, Close: %.2f",
                price.source_name,
                high_str,
                price.close,
            )

        agreements = [self._calculate_agreement(price, consensus_close, consensus_high) for price in relevant_prices]

        logger.info(
            "Calculated Consensus for %s (%s): Consensus High = %.2f, Consensus Close = %.2f",
            normalized_symbol,
            trade_date,
            consensus_high,
            consensus_close,
        )
        for ag in agreements:
            high_diff_str = f"{ag.high_difference_percent:.2f}%" if ag.high_difference_percent is not None else "N/A"
            logger.info(
                "  Agreement [%s]: Close Diff = %.2f%% (Agrees: %s), High Diff = %s (Agrees: %s) -> Overall Agrees: %s",
                ag.source_name,
                ag.difference_percent,
                ag.agrees_close,
                high_diff_str,
                ag.agrees_high,
                ag.agrees,
            )

        agreeing_source_count = sum(1 for agreement in agreements if agreement.agrees)
        accepted = agreeing_source_count >= self.minimum_agreeing_sources

        logger.info(
            "Consensus Decision for %s on %s: Accepted = %s (%d/%d agreeing sources, minimum required: %d)",
            normalized_symbol,
            trade_date,
            accepted,
            agreeing_source_count,
            len(relevant_prices),
            self.minimum_agreeing_sources,
        )

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
            consensus_high=consensus_high,
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

        target_dt = trade_date.date() if isinstance(trade_date, datetime) else trade_date

        for price in prices:
            if price.symbol.strip().upper() != symbol:
                warnings.append(
                    f"Ignored {price.source_name}: expected symbol {symbol}, got {price.symbol}."
                )
                continue

            price_dt = price.trade_date.date() if isinstance(price.trade_date, datetime) else price.trade_date
            if price_dt != target_dt:
                warnings.append(
                    f"Ignored {price.source_name}: expected date {trade_date}, got {price.trade_date}."
                )
                continue

            if price.close <= 0:
                warnings.append(f"Ignored {price.source_name}: close price must be positive.")
                continue

            # Normalize high to be at least close if high is provided
            norm_high = price.high
            if norm_high is not None and norm_high > 0 and norm_high < price.close:
                norm_high = price.close
                warnings.append(
                    f"Adjusted {price.source_name} high ({price.high}) to close ({price.close})."
                )
                price = SourcePrice(
                    source_name=price.source_name,
                    symbol=price.symbol,
                    trade_date=price.trade_date,
                    close=price.close,
                    high=norm_high,
                    volume=price.volume,
                )

            source_key = price.source_name.strip().lower()

            if source_key in seen_sources:
                warnings.append(f"Ignored duplicate source price from {price.source_name}.")
                continue

            seen_sources.add(source_key)
            relevant_prices.append(price)

        return relevant_prices, warnings

    def _calculate_agreement(
        self, price: SourcePrice, consensus_close: float, consensus_high: float
    ) -> SourceAgreement:
        close_diff = self._percent_difference(price.close, consensus_close)
        agrees_close = close_diff <= self.tolerance_percent

        if price.high is not None and price.high > 0:
            high_diff: float | None = self._percent_difference(price.high, consensus_high)
            agrees_high = high_diff <= self.tolerance_percent
        else:
            high_diff = None
            agrees_high = True

        agrees = agrees_close and agrees_high

        return SourceAgreement(
            source_name=price.source_name,
            close=price.close,
            difference_percent=close_diff,
            agrees=agrees,
            high=price.high,
            high_difference_percent=high_diff,
            agrees_close=agrees_close,
            agrees_high=agrees_high,
        )

    def _percent_difference(self, value: float, reference: float) -> float:
        if reference == 0:
            return 0.0

        return abs(value - reference) / reference * 100

