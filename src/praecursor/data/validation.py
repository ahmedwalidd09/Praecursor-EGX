from dataclasses import dataclass, field
from datetime import date

from praecursor.core.price_bar import PriceBar


@dataclass
class ValidationResult:
    """Result returned after checking price data quality."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Data is valid when there are no blocking errors."""
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class PriceBarValidator:
    """Validate daily OHLCV price bars before analysis or caching."""

    def validate(
        self,
        price_bars: list[PriceBar],
        symbol: str = "",
        minimum_bars: int = 1,
    ) -> ValidationResult:
        result = ValidationResult()
        label = symbol or "Unknown symbol"

        if not price_bars:
            result.add_error(f"{label}: no price bars were provided.")
            return result

        if len(price_bars) < minimum_bars:
            result.add_error(
                f"{label}: expected at least {minimum_bars} price bars, "
                f"but received {len(price_bars)}."
            )

        self._validate_dates(price_bars, label, result)
        self._validate_ohlcv(price_bars, label, result)

        return result

    def _validate_dates(
        self,
        price_bars: list[PriceBar],
        label: str,
        result: ValidationResult,
    ) -> None:
        seen_dates: set[date] = set()
        previous_date: date | None = None

        for bar in price_bars:
            trade_date = bar.date.date()

            if trade_date in seen_dates:
                result.add_error(f"{label}: duplicate price bar for {trade_date}.")

            seen_dates.add(trade_date)

            if previous_date is not None and trade_date < previous_date:
                result.add_error(
                    f"{label}: price bars are not sorted oldest to newest "
                    f"near {trade_date}."
                )

            previous_date = trade_date

    def _validate_ohlcv(
        self,
        price_bars: list[PriceBar],
        label: str,
        result: ValidationResult,
    ) -> None:
        for bar in price_bars:
            trade_date = bar.date.date()

            if bar.open <= 0:
                result.add_error(f"{label} {trade_date}: open price must be positive.")

            if bar.high <= 0:
                result.add_error(f"{label} {trade_date}: high price must be positive.")

            if bar.low <= 0:
                result.add_error(f"{label} {trade_date}: low price must be positive.")

            if bar.close <= 0:
                result.add_error(f"{label} {trade_date}: close price must be positive.")

            if bar.high < bar.low:
                result.add_error(f"{label} {trade_date}: high price is below low price.")

            if bar.high < bar.open:
                result.add_error(f"{label} {trade_date}: high price is below open price.")

            if bar.high < bar.close:
                result.add_error(f"{label} {trade_date}: high price is below close price.")

            if bar.low > bar.open:
                result.add_error(f"{label} {trade_date}: low price is above open price.")

            if bar.low > bar.close:
                result.add_error(f"{label} {trade_date}: low price is above close price.")

            if bar.volume < 0:
                result.add_error(f"{label} {trade_date}: volume cannot be negative.")

            if bar.volume == 0:
                result.add_warning(f"{label} {trade_date}: volume is zero.")
