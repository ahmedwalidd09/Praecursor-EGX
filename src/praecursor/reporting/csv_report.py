import csv
from math import isnan
from pathlib import Path

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
        "trend_notes",
        "momentum_notes",
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
            "trend_notes": self._build_trend_notes(score),
            "momentum_notes": self._build_momentum_notes(score),
        }

    def _build_trend_notes(self, score: OpportunityScore) -> str:
        trend_components = [
            component
            for component in score.components
            if component.name != "RSI14 momentum"
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

    def _format_number(self, value: float) -> str:
        if isnan(value):
            return "N/A"

        return f"{value:.2f}"
