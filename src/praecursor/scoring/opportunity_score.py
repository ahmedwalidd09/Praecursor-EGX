from dataclasses import dataclass, field
from math import isnan

from praecursor.core.stock import Stock
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.atr import ATRIndicator, ATRPercentIndicator
from praecursor.scoring.average_volume import AverageVolumeIndicator
from praecursor.scoring.breakout import CloseBreakoutIndicator, CloseHighIndicator, NearCloseHighIndicator, VolumeConfirmedBreakoutIndicator
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.macd import MACDHistogramIndicator, MACDLineIndicator, MACDSignalIndicator
from praecursor.scoring.price_momentum import PriceMomentumIndicator
from praecursor.scoring.relative_volume import RelativeVolumeIndicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.rsi import RSIIndicator
from praecursor.scoring.trend_strength import TrendStrengthIndicator


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

    Current model:
    - Trend structure: 25 points
    - RSI momentum: 20 points
    - MACD confirmation: 15 points
    - 20-bar price momentum: 10 points
    - Relative volume confirmation: 10 points
    - Close-based breakout setup: 20 points
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
        self.analyzer.add_indicator(MACDLineIndicator())
        self.analyzer.add_indicator(MACDSignalIndicator())
        self.analyzer.add_indicator(MACDHistogramIndicator())
        self.analyzer.add_indicator(PriceMomentumIndicator(20))
        self.analyzer.add_indicator(TrendStrengthIndicator())
        self.analyzer.add_indicator(ATRIndicator(14))
        self.analyzer.add_indicator(ATRPercentIndicator(14))
        self.analyzer.add_indicator(CloseBreakoutIndicator(20))
        self.analyzer.add_indicator(CloseBreakoutIndicator(50))
        self.analyzer.add_indicator(CloseHighIndicator(250))
        self.analyzer.add_indicator(NearCloseHighIndicator(250))
        self.analyzer.add_indicator(VolumeConfirmedBreakoutIndicator())

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
        breakout20 = indicator_values.get("Breakout20", float("nan"))
        breakout50 = indicator_values.get("Breakout50", float("nan"))
        near_close_high250 = indicator_values.get("NearCloseHigh250Percent", float("nan"))
        volume_confirmed_breakout = indicator_values.get("VolumeConfirmedBreakout", float("nan"))
        macd = indicator_values.get("MACD", float("nan"))
        macd_histogram = indicator_values.get("MACDHistogram", float("nan"))
        momentum20 = indicator_values.get("Momentum20", float("nan"))

        return [
            self._score_close_above_ema20(latest_close, ema20),
            self._score_ema20_above_ema50(ema20, ema50),
            self._score_ema50_above_ema200(ema50, ema200),
            self._score_rsi14(rsi14),
            self._score_macd(macd, macd_histogram),
            self._score_momentum20(momentum20),
            self._score_relative_volume20(relative_volume20),
            self._score_breakout_setup(
                breakout20,
                breakout50,
                near_close_high250,
                volume_confirmed_breakout,
            ),
        ]

    def _score_close_above_ema20(self, latest_close: float, ema20: float) -> ScoreComponent:
        max_score = 8.0

        if self._missing(ema20):
            return ScoreComponent("Close > EMA20", 0.0, max_score, "EMA20 is unavailable.")

        if latest_close > ema20:
            return ScoreComponent("Close > EMA20", max_score, max_score, "Price is above short-term trend.")

        return ScoreComponent("Close > EMA20", 0.0, max_score, "Price is not above short-term trend.")

    def _score_ema20_above_ema50(self, ema20: float, ema50: float) -> ScoreComponent:
        max_score = 8.0

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
        max_score = 9.0

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
        max_score = 20.0

        if self._missing(rsi14):
            return ScoreComponent("RSI14 momentum", 0.0, max_score, "RSI14 is unavailable.")

        if 50 <= rsi14 <= 70:
            return ScoreComponent("RSI14 momentum", 20.0, max_score, "RSI is in a healthy bullish range.")

        if 70 < rsi14 <= 75:
            return ScoreComponent(
                "RSI14 momentum",
                13.0,
                max_score,
                "RSI shows strong momentum but is becoming extended.",
            )

        if rsi14 > 75:
            return ScoreComponent(
                "RSI14 momentum",
                5.0,
                max_score,
                "RSI is overextended; risk of pullback is higher.",
            )

        if 40 <= rsi14 < 50:
            return ScoreComponent("RSI14 momentum", 6.0, max_score, "RSI is neutral to slightly weak.")

        return ScoreComponent("RSI14 momentum", 0.0, max_score, "RSI is weak.")

    def _score_macd(self, macd: float, macd_histogram: float) -> ScoreComponent:
        max_score = 15.0

        if self._missing(macd) or self._missing(macd_histogram):
            return ScoreComponent("MACD confirmation", 0.0, max_score, "MACD is unavailable.")

        if macd > 0 and macd_histogram > 0:
            return ScoreComponent(
                "MACD confirmation",
                15.0,
                max_score,
                "MACD is positive and histogram confirms bullish momentum.",
            )

        if macd_histogram > 0:
            return ScoreComponent(
                "MACD confirmation",
                10.0,
                max_score,
                "MACD histogram is positive, but MACD line is not yet above zero.",
            )

        if macd > 0:
            return ScoreComponent(
                "MACD confirmation",
                5.0,
                max_score,
                "MACD is positive, but histogram is not confirming acceleration.",
            )

        return ScoreComponent("MACD confirmation", 0.0, max_score, "MACD is not bullish.")

    def _score_momentum20(self, momentum20: float) -> ScoreComponent:
        max_score = 10.0

        if self._missing(momentum20):
            return ScoreComponent("Momentum20", 0.0, max_score, "20-bar momentum is unavailable.")

        if momentum20 >= 10:
            return ScoreComponent("Momentum20", 10.0, max_score, "20-bar price momentum is strong.")

        if momentum20 >= 3:
            return ScoreComponent("Momentum20", 8.0, max_score, "20-bar price momentum is positive.")

        if momentum20 >= 0:
            return ScoreComponent("Momentum20", 4.0, max_score, "20-bar price momentum is mildly positive.")

        return ScoreComponent("Momentum20", 0.0, max_score, "20-bar price momentum is negative.")

    def _score_relative_volume20(self, relative_volume20: float) -> ScoreComponent:
        max_score = 10.0

        if self._missing(relative_volume20):
            return ScoreComponent("Relative Volume20", 0.0, max_score, "Relative volume is unavailable.")

        if relative_volume20 >= 1.5:
            return ScoreComponent(
                "Relative Volume20",
                10.0,
                max_score,
                "Volume is strongly above its 20-day average.",
            )

        if relative_volume20 >= 1.0:
            return ScoreComponent(
                "Relative Volume20",
                7.0,
                max_score,
                "Volume is above or near its 20-day average.",
            )

        if relative_volume20 >= 0.75:
            return ScoreComponent(
                "Relative Volume20",
                4.0,
                max_score,
                "Volume is slightly below its 20-day average.",
            )

        return ScoreComponent(
            "Relative Volume20",
            0.0,
            max_score,
            "Volume is weak relative to recent activity.",
        )

    def _score_breakout_setup(
        self,
        breakout20: float,
        breakout50: float,
        near_close_high250: float,
        volume_confirmed_breakout: float,
    ) -> ScoreComponent:
        max_score = 20.0

        if self._missing(breakout20) or self._missing(breakout50) or self._missing(near_close_high250):
            return ScoreComponent("Breakout setup", 0.0, max_score, "Breakout indicators are unavailable.")

        score = 0.0
        reasons: list[str] = []

        if breakout20 == 1.0:
            score += 7.0
            reasons.append("latest close broke above the previous 20-bar closing high")

        if breakout50 == 1.0:
            score += 7.0
            reasons.append("latest close broke above the previous 50-bar closing high")

        if near_close_high250 >= -3.0:
            score += 4.0
            reasons.append("close is within 3% of its 250-bar closing high")
        elif near_close_high250 >= -7.0:
            score += 2.0
            reasons.append("close is within 7% of its 250-bar closing high")

        if not self._missing(volume_confirmed_breakout) and volume_confirmed_breakout == 1.0:
            score += 2.0
            reasons.append("breakout is volume-confirmed")

        if not reasons:
            return ScoreComponent("Breakout setup", 0.0, max_score, "No close-based breakout setup is present.")

        return ScoreComponent("Breakout setup", min(score, max_score), max_score, "; ".join(reasons) + ".")

    def _missing(self, value: float) -> bool:
        return isnan(value)
