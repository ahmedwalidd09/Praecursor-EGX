from dataclasses import dataclass, field
from datetime import date, timedelta

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.scoring.next_day import calculate_next_day_prediction
from praecursor.scoring.opportunity_score import OpportunityScore, OpportunityScorer
from praecursor.scoring.swing import calculate_swing_prediction
from praecursor.storage.price_cache import PriceCache


@dataclass(frozen=True)
class BacktestSignal:
    """One historical signal and its future returns."""

    symbol: str
    company: str
    signal_date: date
    label: str
    opportunity_score: float
    next_day_score: float
    swing_label: str
    swing_score: float
    entry_close: float
    forward_returns: dict[int, float]
    indicator_values: dict[str, float]

    @property
    def score_bucket(self) -> str:
        return score_bucket(self.opportunity_score)


@dataclass(frozen=True)
class BacktestSummaryRow:
    """Aggregated performance for one label."""

    label: str
    signal_count: int
    average_returns: dict[int, float]
    win_rates: dict[int, float]
    warning: str | None = None


@dataclass(frozen=True)
class BacktestSymbolSummaryRow:
    """Aggregated performance for one symbol."""

    symbol: str
    company: str
    signal_count: int
    average_returns: dict[int, float]
    win_rates: dict[int, float]


@dataclass(frozen=True)
class BacktestScoreBucketSummaryRow:
    """Aggregated performance for one opportunity-score bucket."""

    bucket: str
    signal_count: int
    average_returns: dict[int, float]
    win_rates: dict[int, float]
    warning: str | None = None


@dataclass(frozen=True)
class BacktestDataIssue:
    """Potential data-quality issue detected during backtesting."""

    symbol: str
    issue: str
    detail: str


@dataclass(frozen=True)
class BacktestLabelExample:
    """Best/worst signal example scoped to one label."""

    label: str
    example_type: str
    signal: BacktestSignal


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
    symbol_summary: list[BacktestSymbolSummaryRow] = field(default_factory=list)
    score_bucket_summary: list[BacktestScoreBucketSummaryRow] = field(default_factory=list)
    best_signals: list[BacktestSignal] = field(default_factory=list)
    worst_signals: list[BacktestSignal] = field(default_factory=list)
    label_examples: list[BacktestLabelExample] = field(default_factory=list)
    missed_movers: list[BacktestSignal] = field(default_factory=list)
    overextension_signals: list[BacktestSignal] = field(default_factory=list)
    data_issues: list[BacktestDataIssue] = field(default_factory=list)
    calibration_notes: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class Backtester:
    """
    Run a simple historical forward-return backtest.

    This evaluates technical signals from cached historical prices. It does not
    use historical consensus because consensus was not collected historically
    for every date.
    """

    def __init__(
        self,
        price_cache: PriceCache | None = None,
        symbol_mapper: SymbolMapper | None = None,
        scorer: OpportunityScorer | None = None,
        source_name: str = "yahoo_finance",
        minimum_history_bars: int = 260,
        horizons: tuple[int, ...] = (1, 2, 5, 10, 20),
        minimum_signals_per_label: int = 10,
        example_horizon: int | None = None,
        best_worst_limit: int = 10,
        missed_move_threshold: float = 5.0,
        flat_return_threshold_percent: float = 80.0,
        zero_volume_threshold_percent: float = 20.0,
    ):
        self.price_cache = price_cache or PriceCache()
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.scorer = scorer or OpportunityScorer()
        self.source_name = source_name
        self.minimum_history_bars = minimum_history_bars
        self.horizons = horizons
        self.minimum_signals_per_label = minimum_signals_per_label
        self.example_horizon = example_horizon or max(horizons)
        self.best_worst_limit = best_worst_limit
        self.missed_move_threshold = missed_move_threshold
        self.flat_return_threshold_percent = flat_return_threshold_percent
        self.zero_volume_threshold_percent = zero_volume_threshold_percent

    def run(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        signals: list[BacktestSignal] = []
        errors: dict[str, str] = {}
        data_issues: list[BacktestDataIssue] = []

        for symbol in symbols:
            try:
                price_bars = self.price_cache.load(
                    symbol,
                    self.source_name,
                    start_date,
                    end_date,
                )
                data_issues.extend(self._detect_data_issues(symbol, price_bars, end_date))

                if len(price_bars) < self.minimum_history_bars + max(self.horizons):
                    errors[symbol] = (
                        f"Not enough cached bars for backtest: {len(price_bars)} bars found, "
                        f"need at least {self.minimum_history_bars + max(self.horizons)}."
                    )
                    continue

                signals.extend(self._generate_signals(symbol, price_bars))
            except Exception as error:
                errors[symbol] = str(error)

        summary = self._summarize_by_label(signals)
        symbol_summary = self._summarize_by_symbol(signals)
        score_bucket_summary = self._summarize_by_score_bucket(signals)
        best_signals = self._best_signals(signals)
        worst_signals = self._worst_signals(signals)
        label_examples = self._label_examples(signals)
        missed_movers = self._missed_movers(signals)
        overextension_signals = self._overextension_signals(signals)
        calibration_notes = self._calibration_notes(summary, score_bucket_summary, data_issues)

        return BacktestResult(
            source_name=self.source_name,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            horizons=self.horizons,
            signals=signals,
            summary=summary,
            symbol_summary=symbol_summary,
            score_bucket_summary=score_bucket_summary,
            best_signals=best_signals,
            worst_signals=worst_signals,
            label_examples=label_examples,
            missed_movers=missed_movers,
            overextension_signals=overextension_signals,
            data_issues=data_issues,
            calibration_notes=calibration_notes,
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
            next_day_prediction = calculate_next_day_prediction(
                opportunity_score=opportunity_score,
                consensus_accepted=True,
                consensus_confidence=40.0,
                data_quality_score=100.0,
            )
            swing_prediction = calculate_swing_prediction(
                opportunity_score=opportunity_score,
                consensus_accepted=True,
                consensus_confidence=40.0,
                data_quality_score=100.0,
            )
            entry_close = price_bars[index].close
            forward_returns = self._calculate_forward_returns(price_bars, index, entry_close)

            signals.append(
                BacktestSignal(
                    symbol=symbol,
                    company=company,
                    signal_date=price_bars[index].date.date(),
                    label=next_day_prediction.label,
                    opportunity_score=opportunity_score.score_percent,
                    next_day_score=next_day_prediction.score,
                    swing_label=swing_prediction.label,
                    swing_score=swing_prediction.score,
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
        return calculate_next_day_prediction(
            opportunity_score=score,
            consensus_accepted=True,
            consensus_confidence=40.0,
            data_quality_score=100.0,
        ).label

    def _summarize_by_label(self, signals: list[BacktestSignal]) -> list[BacktestSummaryRow]:
        labels = sorted({signal.label for signal in signals})
        return [
            self._summary_row_for_label(label, [signal for signal in signals if signal.label == label])
            for label in labels
        ]

    def _summary_row_for_label(self, label: str, signals: list[BacktestSignal]) -> BacktestSummaryRow:
        average_returns, win_rates = self._aggregate_returns(signals)
        warning = None

        if len(signals) < self.minimum_signals_per_label:
            warning = (
                f"Low sample size: {len(signals)} signal(s), "
                f"minimum recommended is {self.minimum_signals_per_label}."
            )

        return BacktestSummaryRow(
            label=label,
            signal_count=len(signals),
            average_returns=average_returns,
            win_rates=win_rates,
            warning=warning,
        )

    def _summarize_by_symbol(self, signals: list[BacktestSignal]) -> list[BacktestSymbolSummaryRow]:
        symbols = sorted({signal.symbol for signal in signals})
        rows: list[BacktestSymbolSummaryRow] = []

        for symbol in symbols:
            symbol_signals = [signal for signal in signals if signal.symbol == symbol]
            average_returns, win_rates = self._aggregate_returns(symbol_signals)
            rows.append(
                BacktestSymbolSummaryRow(
                    symbol=symbol,
                    company=symbol_signals[0].company,
                    signal_count=len(symbol_signals),
                    average_returns=average_returns,
                    win_rates=win_rates,
                )
            )

        return rows

    def _summarize_by_score_bucket(self, signals: list[BacktestSignal]) -> list[BacktestScoreBucketSummaryRow]:
        buckets = ["0-20", "20-40", "40-60", "60-80", "80-100"]
        rows: list[BacktestScoreBucketSummaryRow] = []

        for bucket in buckets:
            bucket_signals = [signal for signal in signals if signal.score_bucket == bucket]
            if not bucket_signals:
                continue
            average_returns, win_rates = self._aggregate_returns(bucket_signals)
            warning = None
            if len(bucket_signals) < self.minimum_signals_per_label:
                warning = f"Low sample size: {len(bucket_signals)} signal(s)."
            rows.append(
                BacktestScoreBucketSummaryRow(
                    bucket=bucket,
                    signal_count=len(bucket_signals),
                    average_returns=average_returns,
                    win_rates=win_rates,
                    warning=warning,
                )
            )

        return rows

    def _aggregate_returns(self, signals: list[BacktestSignal]) -> tuple[dict[int, float], dict[int, float]]:
        average_returns: dict[int, float] = {}
        win_rates: dict[int, float] = {}

        for horizon in self.horizons:
            horizon_returns = [signal.forward_returns[horizon] for signal in signals]
            average_returns[horizon] = sum(horizon_returns) / len(horizon_returns)
            wins = [value for value in horizon_returns if value > 0]
            win_rates[horizon] = (len(wins) / len(horizon_returns)) * 100

        return average_returns, win_rates

    def _best_signals(self, signals: list[BacktestSignal]) -> list[BacktestSignal]:
        return sorted(
            signals,
            key=lambda signal: signal.forward_returns[self.example_horizon],
            reverse=True,
        )[: self.best_worst_limit]

    def _worst_signals(self, signals: list[BacktestSignal]) -> list[BacktestSignal]:
        return sorted(
            signals,
            key=lambda signal: signal.forward_returns[self.example_horizon],
        )[: self.best_worst_limit]

    def _label_examples(self, signals: list[BacktestSignal]) -> list[BacktestLabelExample]:
        examples: list[BacktestLabelExample] = []
        labels = sorted({signal.label for signal in signals})

        for label in labels:
            label_signals = [signal for signal in signals if signal.label == label]
            best = sorted(
                label_signals,
                key=lambda signal: signal.forward_returns[self.example_horizon],
                reverse=True,
            )[: self.best_worst_limit]
            worst = sorted(
                label_signals,
                key=lambda signal: signal.forward_returns[self.example_horizon],
            )[: self.best_worst_limit]
            examples.extend([BacktestLabelExample(label, "best", signal) for signal in best])
            examples.extend([BacktestLabelExample(label, "worst", signal) for signal in worst])

        return examples

    def _missed_movers(self, signals: list[BacktestSignal]) -> list[BacktestSignal]:
        first_horizon = min(self.horizons)
        weak_labels = {"Avoid Tomorrow", "Watchlist Tomorrow"}
        return [
            signal
            for signal in signals
            if signal.label in weak_labels
            and signal.forward_returns[first_horizon] >= self.missed_move_threshold
        ]

    def _overextension_signals(self, signals: list[BacktestSignal]) -> list[BacktestSignal]:
        return [
            signal
            for signal in signals
            if signal.indicator_values.get("RSI14", 0) > 75
            and signal.indicator_values.get("Breakout20") == 1.0
        ]

    def _detect_data_issues(
        self,
        symbol: str,
        price_bars: list[PriceBar],
        requested_end_date: date,
    ) -> list[BacktestDataIssue]:
        issues: list[BacktestDataIssue] = []

        if not price_bars:
            issues.append(BacktestDataIssue(symbol, "missing_data", "No cached bars found."))
            return issues

        latest_date = price_bars[-1].date.date()
        if latest_date < requested_end_date - timedelta(days=10):
            issues.append(
                BacktestDataIssue(
                    symbol,
                    "stale_data",
                    f"Latest cached bar is {latest_date}, requested end date is {requested_end_date}.",
                )
            )

        close_changes = [
            abs((price_bars[index].close / price_bars[index - 1].close) - 1)
            for index in range(1, len(price_bars))
            if price_bars[index - 1].close > 0
        ]
        if close_changes:
            flat_ratio = sum(1 for change in close_changes if change < 0.0001) / len(close_changes) * 100
            if flat_ratio >= self.flat_return_threshold_percent:
                issues.append(
                    BacktestDataIssue(
                        symbol,
                        "mostly_flat_prices",
                        f"{flat_ratio:.0f}% of consecutive closes are effectively unchanged.",
                    )
                )

        zero_volume_ratio = sum(1 for bar in price_bars if bar.volume == 0) / len(price_bars) * 100
        if zero_volume_ratio >= self.zero_volume_threshold_percent:
            issues.append(
                BacktestDataIssue(
                    symbol,
                    "zero_volume",
                    f"{zero_volume_ratio:.0f}% of bars have zero volume.",
                )
            )

        return issues

    def _calibration_notes(
        self,
        summary: list[BacktestSummaryRow],
        score_bucket_summary: list[BacktestScoreBucketSummaryRow],
        data_issues: list[BacktestDataIssue],
    ) -> list[str]:
        notes: list[str] = []
        first_horizon = min(self.horizons)
        longer_horizon = max(self.horizons)

        if summary:
            best_avg = max(summary, key=lambda row: row.average_returns[first_horizon])
            best_win = max(summary, key=lambda row: row.win_rates[first_horizon])
            notes.append(
                f"Best {first_horizon}-bar average return label: {best_avg.label} "
                f"({best_avg.average_returns[first_horizon]:.2f}%)."
            )
            notes.append(
                f"Best {first_horizon}-bar win-rate label: {best_win.label} "
                f"({best_win.win_rates[first_horizon]:.0f}%)."
            )

            avoid_rows = [row for row in summary if row.label == "Avoid Tomorrow"]
            if avoid_rows and avoid_rows[0].average_returns[longer_horizon] > 0:
                notes.append(
                    "Avoid Tomorrow has positive longer-horizon returns; consider splitting early reversal cases."
                )

        if score_bucket_summary:
            best_bucket = max(score_bucket_summary, key=lambda row: row.average_returns[first_horizon])
            notes.append(
                f"Best {first_horizon}-bar score bucket: {best_bucket.bucket} "
                f"({best_bucket.average_returns[first_horizon]:.2f}%)."
            )

        if data_issues:
            notes.append(f"Detected {len(data_issues)} potential data issue(s); inspect backtest_data_issues.csv.")

        for row in summary:
            if row.warning:
                notes.append(f"{row.label}: {row.warning}")

        return notes


def score_bucket(score: float) -> str:
    if score < 20:
        return "0-20"
    if score < 40:
        return "20-40"
    if score < 60:
        return "40-60"
    if score < 80:
        return "60-80"
    return "80-100"
