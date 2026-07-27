import csv
from math import isnan
from pathlib import Path
from typing import Any

from praecursor.scoring.opportunity_score import OpportunityScore

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RANKING_REPORT = ROOT / "reports" / "opportunity_ranking.csv"


class OpportunityRankingCSVWriter:
    """Write ranked opportunity scores to a CSV report."""

    FIELDNAMES = [
        "rank",
        "symbol",
        "company",
        "score",
        "score_percent",
        "latest_close",
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "avg_volume20",
        "rel_volume20",
        "macd",
        "macd_signal",
        "macd_histogram",
        "momentum20",
        "trend_strength",
        "atr14",
        "atr_percent14",
        "breakout20",
        "breakout50",
        "close_high250",
        "near_close_high250_percent",
        "volume_confirmed_breakout",
        "trend_notes",
        "momentum_notes",
        "macd_notes",
        "price_momentum_notes",
        "breakout_notes",
        "volume_notes",
    ]

    def write(
        self,
        scores: list[OpportunityScore],
        output_path: Path = DEFAULT_RANKING_REPORT,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
            writer.writeheader()

            for rank, score in enumerate(scores, start=1):
                writer.writerow(self._build_row(rank, score))

        return output_path

    def _build_row(self, rank: int, score: OpportunityScore) -> dict[str, str | int]:
        return {
            "rank": rank,
            "symbol": score.symbol,
            "company": score.company,
            "score": self._format_number(score.total_score),
            "score_percent": self._format_number(score.score_percent),
            "latest_close": self._format_number(score.latest_close),
            "ema20": self._format_number(score.indicator_values.get("EMA20", float("nan"))),
            "ema50": self._format_number(score.indicator_values.get("EMA50", float("nan"))),
            "ema200": self._format_number(score.indicator_values.get("EMA200", float("nan"))),
            "rsi14": self._format_number(score.indicator_values.get("RSI14", float("nan"))),
            "avg_volume20": self._format_number(score.indicator_values.get("AvgVolume20", float("nan"))),
            "rel_volume20": self._format_number(score.indicator_values.get("RelVolume20", float("nan"))),
            "macd": self._format_number(score.indicator_values.get("MACD", float("nan"))),
            "macd_signal": self._format_number(score.indicator_values.get("MACDSignal", float("nan"))),
            "macd_histogram": self._format_number(score.indicator_values.get("MACDHistogram", float("nan"))),
            "momentum20": self._format_number(score.indicator_values.get("Momentum20", float("nan"))),
            "trend_strength": self._format_number(score.indicator_values.get("TrendStrength", float("nan"))),
            "atr14": self._format_number(score.indicator_values.get("ATR14", float("nan"))),
            "atr_percent14": self._format_number(score.indicator_values.get("ATRPercent14", float("nan"))),
            "breakout20": self._format_number(score.indicator_values.get("Breakout20", float("nan"))),
            "breakout50": self._format_number(score.indicator_values.get("Breakout50", float("nan"))),
            "close_high250": self._format_number(score.indicator_values.get("CloseHigh250", float("nan"))),
            "near_close_high250_percent": self._format_number(score.indicator_values.get("NearCloseHigh250Percent", float("nan"))),
            "volume_confirmed_breakout": self._format_number(score.indicator_values.get("VolumeConfirmedBreakout", float("nan"))),
            "trend_notes": self._build_trend_notes(score),
            "momentum_notes": self._build_momentum_notes(score),
            "macd_notes": self._build_macd_notes(score),
            "price_momentum_notes": self._build_price_momentum_notes(score),
            "breakout_notes": self._build_breakout_notes(score),
            "volume_notes": self._build_volume_notes(score),
        }

    def _build_trend_notes(self, score: OpportunityScore) -> str:
        trend_component_names = {"Close > EMA20", "EMA20 > EMA50", "EMA50 > EMA200"}
        trend_components = [
            component
            for component in score.components
            if component.name in trend_component_names
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in trend_components
        )

    def _build_momentum_notes(self, score: OpportunityScore) -> str:
        momentum_components = [
            component
            for component in score.components
            if component.name == "RSI14 momentum"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in momentum_components
        )

    def _build_macd_notes(self, score: OpportunityScore) -> str:
        macd_components = [
            component
            for component in score.components
            if component.name == "MACD confirmation"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in macd_components
        )

    def _build_price_momentum_notes(self, score: OpportunityScore) -> str:
        price_momentum_components = [
            component
            for component in score.components
            if component.name == "Momentum20"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in price_momentum_components
        )

    def _build_breakout_notes(self, score: OpportunityScore) -> str:
        breakout_components = [
            component
            for component in score.components
            if component.name == "Breakout setup"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in breakout_components
        )

    def _build_volume_notes(self, score: OpportunityScore) -> str:
        volume_components = [
            component
            for component in score.components
            if component.name == "Relative Volume20"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in volume_components
        )

    def _format_number(self, value: float) -> str:
        if isnan(value):
            return "N/A"

        return f"{value:.2f}"


class ScannerCSVReportWriter:
    """Write scanner results, including consensus metadata, to CSV."""

    FIELDNAMES = [
        "rank",
        "symbol",
        "company",
        "score",
        "score_percent",
        "latest_close",
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "avg_volume20",
        "rel_volume20",
        "macd",
        "macd_signal",
        "macd_histogram",
        "momentum20",
        "trend_strength",
        "atr14",
        "atr_percent14",
        "breakout20",
        "breakout50",
        "close_high250",
        "near_close_high250_percent",
        "volume_confirmed_breakout",
        "consensus_accepted",
        "consensus_close",
        "consensus_trade_date",
        "consensus_sources",
        "consensus_agreeing_sources",
        "consensus_agreement_percent",
        "consensus_confidence_percent",
        "consensus_confidence_label",
        "consensus_error",
        "data_quality_score",
        "data_quality_label",
        "high_low_warning_count",
        "high_low_quality_score",
        "high_low_quality_label",
        "atr_reliability_label",
        "primary_downloaded_bars",
        "consensus_downloaded_bars",
        "warning_count",
        "trend_notes",
        "momentum_notes",
        "macd_notes",
        "price_momentum_notes",
        "breakout_notes",
        "volume_notes",
    ]

    def write(
        self,
        results: list[Any],
        output_path: Path = DEFAULT_RANKING_REPORT,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
            writer.writeheader()

            for rank, result in enumerate(results, start=1):
                writer.writerow(self._build_row(rank, result))

        return output_path

    def _build_row(self, rank: int, result: Any) -> dict[str, str | int | bool]:
        score = result.opportunity_score
        consensus = result.consensus_result

        return {
            "rank": rank,
            "symbol": score.symbol,
            "company": score.company,
            "score": self._format_number(score.total_score),
            "score_percent": self._format_number(score.score_percent),
            "latest_close": self._format_number(score.latest_close),
            "ema20": self._format_number(score.indicator_values.get("EMA20", float("nan"))),
            "ema50": self._format_number(score.indicator_values.get("EMA50", float("nan"))),
            "ema200": self._format_number(score.indicator_values.get("EMA200", float("nan"))),
            "rsi14": self._format_number(score.indicator_values.get("RSI14", float("nan"))),
            "avg_volume20": self._format_number(score.indicator_values.get("AvgVolume20", float("nan"))),
            "rel_volume20": self._format_number(score.indicator_values.get("RelVolume20", float("nan"))),
            "macd": self._format_number(score.indicator_values.get("MACD", float("nan"))),
            "macd_signal": self._format_number(score.indicator_values.get("MACDSignal", float("nan"))),
            "macd_histogram": self._format_number(score.indicator_values.get("MACDHistogram", float("nan"))),
            "momentum20": self._format_number(score.indicator_values.get("Momentum20", float("nan"))),
            "trend_strength": self._format_number(score.indicator_values.get("TrendStrength", float("nan"))),
            "atr14": self._format_number(score.indicator_values.get("ATR14", float("nan"))),
            "atr_percent14": self._format_number(score.indicator_values.get("ATRPercent14", float("nan"))),
            "breakout20": self._format_number(score.indicator_values.get("Breakout20", float("nan"))),
            "breakout50": self._format_number(score.indicator_values.get("Breakout50", float("nan"))),
            "close_high250": self._format_number(score.indicator_values.get("CloseHigh250", float("nan"))),
            "near_close_high250_percent": self._format_number(score.indicator_values.get("NearCloseHigh250Percent", float("nan"))),
            "volume_confirmed_breakout": self._format_number(score.indicator_values.get("VolumeConfirmedBreakout", float("nan"))),
            "consensus_accepted": consensus.accepted if consensus else False,
            "consensus_close": self._format_number(consensus.consensus_close) if consensus else "N/A",
            "consensus_trade_date": consensus.trade_date.isoformat() if consensus else "N/A",
            "consensus_sources": consensus.source_count if consensus else 0,
            "consensus_agreeing_sources": consensus.agreeing_source_count if consensus else 0,
            "consensus_agreement_percent": self._format_number(consensus.agreement_percent) if consensus else "N/A",
            "consensus_confidence_percent": self._format_number(consensus.confidence_percent) if consensus else "N/A",
            "consensus_confidence_label": consensus.confidence_label if consensus else "low",
            "consensus_error": result.consensus_error or "",
            "data_quality_score": self._format_number(result.data_quality_score),
            "data_quality_label": result.data_quality_label,
            "high_low_warning_count": result.high_low_warning_count,
            "high_low_quality_score": self._format_number(result.high_low_quality_score),
            "high_low_quality_label": result.high_low_quality_label,
            "atr_reliability_label": result.atr_reliability_label,
            "primary_downloaded_bars": result.downloaded_bars,
            "consensus_downloaded_bars": result.consensus_downloaded_bars,
            "warning_count": result.warning_count,
            "trend_notes": self._build_trend_notes(score),
            "momentum_notes": self._build_momentum_notes(score),
            "macd_notes": self._build_macd_notes(score),
            "price_momentum_notes": self._build_price_momentum_notes(score),
            "breakout_notes": self._build_breakout_notes(score),
            "volume_notes": self._build_volume_notes(score),
        }

    def _build_trend_notes(self, score: OpportunityScore) -> str:
        return OpportunityRankingCSVWriter()._build_trend_notes(score)

    def _build_momentum_notes(self, score: OpportunityScore) -> str:
        return OpportunityRankingCSVWriter()._build_momentum_notes(score)

    def _build_macd_notes(self, score: OpportunityScore) -> str:
        macd_components = [
            component
            for component in score.components
            if component.name == "MACD confirmation"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in macd_components
        )

    def _build_price_momentum_notes(self, score: OpportunityScore) -> str:
        price_momentum_components = [
            component
            for component in score.components
            if component.name == "Momentum20"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in price_momentum_components
        )

    def _build_breakout_notes(self, score: OpportunityScore) -> str:
        breakout_components = [
            component
            for component in score.components
            if component.name == "Breakout setup"
        ]

        return "; ".join(
            f"{component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            for component in breakout_components
        )

    def _build_volume_notes(self, score: OpportunityScore) -> str:
        return OpportunityRankingCSVWriter()._build_volume_notes(score)

    def _format_number(self, value: float) -> str:
        return OpportunityRankingCSVWriter()._format_number(value)
