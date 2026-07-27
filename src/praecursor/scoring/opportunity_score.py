from dataclasses import dataclass, field
from math import isnan

from praecursor.core.stock import Stock
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.average_volume import AverageVolumeIndicator
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.relative_volume import RelativeVolumeIndicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.rsi import RSIIndicator


@dataclass(frozen=True)
class ScoreComponent:
    """One explainable part of the opportunity score."""

    name: str
    score: float
    max_score: float
    reason: str


@dataclass(frozen=True)
class OpportunityScore:
    """Final opportunity score for one stock."""

    symbol: str
    company: str
    latest_close: float
    total_score: float
    max_score: float
    indicator_values: dict[str, float]
    components: list[ScoreComponent] = field(default_factory=list)

    @property
    def score_percent(self) -> float:
        if self.max_score == 0:
            return 0.0

        return (self.total_score / self.max_score) * 100


class OpportunityScorer:
    """
    Calculate an explainable opportunity score.

    Current first practical model:
    - Trend: 45 points
    - Momentum: 35 points
    - Volume confirmation: 20 points

    The model is intentionally transparent and will evolve as more validated
    sources and indicators are added.
    """

    MAX_SCORE = 100.0

    def __init__(self):
        self.analyzer = Analyzer()
        self.analyzer.add_indicator(EMAIndicator(20))
        self.analyzer.add_indicator(EMAIndicator(50))
        self.analyzer.add_indicator(EMAIndicator(200))
        self.analyzer.add_indicator(RSIIndicator(14))
        self.analyzer.add_indicator(AverageVolumeIndicator(20))
        self.analyzer.add_indicator(RelativeVolumeIndicator(20))

    def score(self, stock: Stock) -> OpportunityScore:
        latest_close = stock.latest().close
        indicator_values = self._calculate_indicators(stock)
        components = self._build_components(latest_close, indicator_values)
        total_score = sum(component.score for component in components)

        return OpportunityScore(
            symbol=stock.symbol,
            company=stock.company,
            latest_close=latest_close,
            total_score=total_score,
            max_score=self.MAX_SCORE,
            indicator_values=indicator_values,
            components=components,
        )

    def _calculate_indicators(self, stock: Stock) -> dict[str, float]:
        results: list[IndicatorResult] = self.analyzer.analyze(stock)
        return {result.name: result.value for result in results}

    def _build_components(
        self,
        latest_close: float,
        indicator_values: dict[str, float],
    ) -> list[ScoreComponent]:
        ema20 = indicator_values.get("EMA20", float("nan"))
        ema50 = indicator_values.get("EMA50", float("nan"))
        ema200 = indicator_values.get("EMA200", float("nan"))
        rsi14 = indicator_values.get("RSI14", float("nan"))
        relative_volume20 = indicator_values.get("RelVolume20", float("nan"))

        return [
            self._score_close_above_ema20(latest_close, ema20),
            self._score_ema20_above_ema50(ema20, ema50),
            self._score_ema50_above_ema200(ema50, ema200),
            self._score_rsi14(rsi14),
            self._score_relative_volume20(relative_volume20),
        ]

    def _score_close_above_ema20(self, latest_close: float, ema20: float) -> ScoreComponent:
        max_score = 15.0

        if self._missing(ema20):
            return ScoreComponent("Close > EMA20", 0.0, max_score, "EMA20 is unavailable.")

        if latest_close > ema20:
            return ScoreComponent(
                "Close > EMA20",
                max_score,
                max_score,
                "Price is above short-term trend.",
            )

        return ScoreComponent(
            "Close > EMA20",
            0.0,
            max_score,
            "Price is not above short-term trend.",
        )

    def _score_ema20_above_ema50(self, ema20: float, ema50: float) -> ScoreComponent:
        max_score = 15.0

        if self._missing(ema20) or self._missing(ema50):
            return ScoreComponent("EMA20 > EMA50", 0.0, max_score, "EMA20 or EMA50 is unavailable.")

        if ema20 > ema50:
            return ScoreComponent(
                "EMA20 > EMA50",
                max_score,
                max_score,
                "Short-term trend is above medium-term trend.",
            )

        return ScoreComponent(
            "EMA20 > EMA50",
            0.0,
            max_score,
            "Short-term trend is not above medium-term trend.",
        )

    def _score_ema50_above_ema200(self, ema50: float, ema200: float) -> ScoreComponent:
        max_score = 15.0

        if self._missing(ema50) or self._missing(ema200):
            return ScoreComponent("EMA50 > EMA200", 0.0, max_score, "EMA50 or EMA200 is unavailable.")

        if ema50 > ema200:
            return ScoreComponent(
                "EMA50 > EMA200",
                max_score,
                max_score,
                "Medium-term trend is above long-term trend.",
            )

        return ScoreComponent(
            "EMA50 > EMA200",
            0.0,
            max_score,
            "Medium-term trend is not above long-term trend.",
        )

    def _score_rsi14(self, rsi14: float) -> ScoreComponent:
        max_score = 35.0

        if self._missing(rsi14):
            return ScoreComponent("RSI14 momentum", 0.0, max_score, "RSI14 is unavailable.")

        if 50 <= rsi14 <= 70:
            return ScoreComponent(
                "RSI14 momentum",
                35.0,
                max_score,
                "RSI is in a healthy bullish range.",
            )

        if 70 < rsi14 <= 75:
            return ScoreComponent(
                "RSI14 momentum",
                22.0,
                max_score,
                "RSI shows strong momentum but is becoming extended.",
            )

        if rsi14 > 75:
            return ScoreComponent(
                "RSI14 momentum",
                8.0,
                max_score,
                "RSI is overextended; risk of pullback is higher.",
            )

        if 40 <= rsi14 < 50:
            return ScoreComponent(
                "RSI14 momentum",
                10.0,
                max_score,
                "RSI is neutral to slightly weak.",
            )

        return ScoreComponent(
            "RSI14 momentum",
            0.0,
            max_score,
            "RSI is weak.",
        )

    def _score_relative_volume20(self, relative_volume20: float) -> ScoreComponent:
        max_score = 20.0

        if self._missing(relative_volume20):
            return ScoreComponent("Relative Volume20", 0.0, max_score, "Relative volume is unavailable.")

        if relative_volume20 >= 1.5:
            return ScoreComponent(
                "Relative Volume20",
                20.0,
                max_score,
                "Volume is strongly above its 20-day average.",
            )

        if relative_volume20 >= 1.0:
            return ScoreComponent(
                "Relative Volume20",
                15.0,
                max_score,
                "Volume is above or near its 20-day average.",
            )

        if relative_volume20 >= 0.75:
            return ScoreComponent(
                "Relative Volume20",
                8.0,
                max_score,
                "Volume is slightly below its 20-day average.",
            )

        return ScoreComponent(
            "Relative Volume20",
            0.0,
            max_score,
            "Volume is weak relative to recent activity.",
        )

    def _missing(self, value: float) -> bool:
        return isnan(value)
