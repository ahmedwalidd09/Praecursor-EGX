from dataclasses import dataclass, field
from datetime import date

from praecursor.core.stock import Stock
from praecursor.core.price_bar import PriceBar
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.scoring.opportunity_score import OpportunityScore, OpportunityScorer
from praecursor.storage.price_cache import PriceCache


@dataclass(frozen=True)
class BacktestSignal:
    """One historical signal and its future returns."""

    symbol: str
    company: str
    signal_date: date
    label: str
    opportunity_score: float
    entry_close: float
    forward_returns: dict[int, float]
    indicator_values: dict[str, float]


@dataclass(frozen=True)
class BacktestSummaryRow:
    """Aggregated performance for one label."""

    label: str
    signal_count: int
    average_returns: dict[int, float]
    win_rates: dict[int, float]


@dataclass(frozen=True)
class BacktestResult:
    """Full result from one backtest run."""

    source_name: str
    symbols: list[str]
    start_date: date
    end_date: date
    horizons: tuple[int, ...]
    signals: list[BacktestSignal] = field(default_factory=list)
    summary: list[BacktestSummaryRow] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class Backtester:
    """
    Run a simple historical forward-return backtest.

    This initial backtest evaluates technical signals from cached historical
    prices. It does not use historical consensus because consensus was not
    collected historically for every date.
    """

    def __init__(
        self,
        price_cache: PriceCache | None = None,
        symbol_mapper: SymbolMapper | None = None,
        scorer: OpportunityScorer | None = None,
        source_name: str = "yahoo_finance",
        minimum_history_bars: int = 260,
        horizons: tuple[int, ...] = (5, 10, 20),
    ):
        self.price_cache = price_cache or PriceCache()
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.scorer = scorer or OpportunityScorer()
        self.source_name = source_name
        self.minimum_history_bars = minimum_history_bars
        self.horizons = horizons

    def run(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        signals: list[BacktestSignal] = []
        errors: dict[str, str] = {}

        for symbol in symbols:
            try:
                price_bars = self.price_cache.load(
                    symbol,
                    self.source_name,
                    start_date,
                    end_date,
                )

                if len(price_bars) < self.minimum_history_bars + max(self.horizons):
                    errors[symbol] = (
                        f"Not enough cached bars for backtest: {len(price_bars)} bars found, "
                        f"need at least {self.minimum_history_bars + max(self.horizons)}."
                    )
                    continue

                signals.extend(self._generate_signals(symbol, price_bars))
            except Exception as error:
                errors[symbol] = str(error)

        summary = self._summarize(signals)

        return BacktestResult(
            source_name=self.source_name,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            horizons=self.horizons,
            signals=signals,
            summary=summary,
            errors=errors,
        )

    def _generate_signals(self, symbol: str, price_bars: list[PriceBar]) -> list[BacktestSignal]:
        company = self.symbol_mapper.get_company_name(symbol)
        signals: list[BacktestSignal] = []
        max_horizon = max(self.horizons)
        last_signal_index = len(price_bars) - max_horizon - 1

        for index in range(self.minimum_history_bars - 1, last_signal_index + 1):
            historical_stock = Stock(
                symbol=symbol,
                company=company,
                history=list(price_bars[: index + 1]),
            )
            opportunity_score = self.scorer.score(historical_stock)
            entry_close = price_bars[index].close
            forward_returns = self._calculate_forward_returns(price_bars, index, entry_close)

            signals.append(
                BacktestSignal(
                    symbol=symbol,
                    company=company,
                    signal_date=price_bars[index].date.date(),
                    label=self._label_signal(opportunity_score),
                    opportunity_score=opportunity_score.score_percent,
                    entry_close=entry_close,
                    forward_returns=forward_returns,
                    indicator_values=opportunity_score.indicator_values,
                )
            )

        return signals

    def _calculate_forward_returns(
        self,
        price_bars: list[PriceBar],
        index: int,
        entry_close: float,
    ) -> dict[int, float]:
        returns: dict[int, float] = {}

        for horizon in self.horizons:
            future_close = price_bars[index + horizon].close
            returns[horizon] = ((future_close / entry_close) - 1) * 100

        return returns

    def _label_signal(self, score: OpportunityScore) -> str:
        if self._is_extended_breakout(score):
            return "Extended Breakout"

        if score.score_percent >= 75:
            return "Strong Candidate"

        if score.score_percent >= 60:
            return "Watchlist"

        return "Avoid"

    def _is_extended_breakout(self, score: OpportunityScore) -> bool:
        rsi14 = score.indicator_values.get("RSI14")
        breakout20 = score.indicator_values.get("Breakout20")
        breakout50 = score.indicator_values.get("Breakout50")
        relative_volume20 = score.indicator_values.get("RelVolume20")

        if rsi14 is None or rsi14 != rsi14:
            return False

        return (
            rsi14 > 75
            and breakout20 == 1.0
            and breakout50 == 1.0
            and relative_volume20 is not None
            and relative_volume20 == relative_volume20
            and relative_volume20 >= 1.0
        )

    def _summarize(self, signals: list[BacktestSignal]) -> list[BacktestSummaryRow]:
        labels = sorted({signal.label for signal in signals})
        summary_rows: list[BacktestSummaryRow] = []

        for label in labels:
            label_signals = [signal for signal in signals if signal.label == label]
            average_returns: dict[int, float] = {}
            win_rates: dict[int, float] = {}

            for horizon in self.horizons:
                horizon_returns = [signal.forward_returns[horizon] for signal in label_signals]
                average_returns[horizon] = sum(horizon_returns) / len(horizon_returns)
                wins = [value for value in horizon_returns if value > 0]
                win_rates[horizon] = (len(wins) / len(horizon_returns)) * 100

            summary_rows.append(
                BacktestSummaryRow(
                    label=label,
                    signal_count=len(label_signals),
                    average_returns=average_returns,
                    win_rates=win_rates,
                )
            )

        return summary_rows
