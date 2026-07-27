from math import isnan
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARKDOWN_REPORT = ROOT / "reports" / "opportunity_ranking.md"


class ScannerMarkdownReportWriter:
    """Write a readable Markdown scanner report."""

    def write(self, results: list[Any], output_path: Path = DEFAULT_MARKDOWN_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build_content(results), encoding="utf-8")
        return output_path

    def _build_content(self, results: list[Any]) -> str:
        lines = [
            "# Praecursor-EGX Opportunity Ranking",
            "",
            "| Rank | Symbol | Score | Latest Close | EMA20 | EMA50 | EMA200 | RSI14 | MACD Hist | Momentum20 | RelVol20 | ATR% | Consensus | Consensus Confidence | Data Quality | H/L Quality |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"
        ]

        for rank, result in enumerate(results, start=1):
            score = result.opportunity_score
            consensus = result.consensus_result
            consensus_status = "Accepted" if consensus and consensus.accepted else "Not accepted"
            confidence = f"{consensus.confidence_percent:.0f}% ({consensus.confidence_label})" if consensus else "N/A"
            data_quality = f"{result.data_quality_score:.0f}% ({result.data_quality_label})"
            high_low_quality = f"{result.high_low_quality_score:.0f}% ({result.high_low_quality_label})"

            lines.append(
                "| "
                f"{rank} | "
                f"{score.symbol} | "
                f"{score.total_score:.0f}/{score.max_score:.0f} | "
                f"{score.latest_close:.2f} | "
                f"{self._format_value(score.indicator_values.get('EMA20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('EMA50', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('EMA200', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('RSI14', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('MACDHistogram', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('Momentum20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('RelVolume20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('ATRPercent14', float('nan')))} | "
                f"{consensus_status} | "
                f"{confidence} | "
                f"{data_quality} | "
                f"{high_low_quality} |"
            )

        lines.extend(["", "## Details", ""])

        for rank, result in enumerate(results, start=1):
            score = result.opportunity_score
            consensus = result.consensus_result
            lines.extend(
                [
                    f"### #{rank} {score.symbol} - {score.company}",
                    "",
                    f"- Opportunity score: **{score.total_score:.0f}/{score.max_score:.0f} ({score.score_percent:.0f}%)**",
                    f"- Latest close: **{score.latest_close:.2f}**",
                    f"- Average volume 20: **{self._format_value(score.indicator_values.get('AvgVolume20', float('nan')))}**",
                    f"- Relative volume 20: **{self._format_value(score.indicator_values.get('RelVolume20', float('nan')))}**",
                    f"- MACD histogram: **{self._format_value(score.indicator_values.get('MACDHistogram', float('nan')))}**",
                    f"- Momentum20: **{self._format_value(score.indicator_values.get('Momentum20', float('nan')))}%**",
                    f"- Trend strength: **{self._format_value(score.indicator_values.get('TrendStrength', float('nan')))} / 100**",
                    f"- ATR14: **{self._format_value(score.indicator_values.get('ATR14', float('nan')))}**",
                    f"- ATRPercent14: **{self._format_value(score.indicator_values.get('ATRPercent14', float('nan')))}%**",
                    f"- ATR reliability: **{result.atr_reliability_label}**",
                    f"- Data quality: **{result.data_quality_score:.0f}% ({result.data_quality_label})** based on {result.warning_count} warning(s)",
                    f"- High/low quality: **{result.high_low_quality_score:.0f}% ({result.high_low_quality_label})** based on {result.high_low_warning_count} high/low warning(s)",
                ]
            )

            if consensus:
                lines.extend(
                    [
                        f"- Consensus close: **{consensus.consensus_close:.2f}** on {consensus.trade_date}",
                        f"- Consensus agreement: **{consensus.agreeing_source_count}/{consensus.source_count} sources ({consensus.agreement_percent:.0f}%)**",
                        f"- Confidence vs 5-source target: **{consensus.confidence_percent:.0f}% ({consensus.confidence_label})**",
                    ]
                )
            elif result.consensus_error:
                lines.append(f"- Consensus error: {result.consensus_error}")

            lines.append("- Components:")
            for component in score.components:
                lines.append(
                    f"  - {component.name}: {component.score:.0f}/{component.max_score:.0f} - {component.reason}"
                )

            lines.append("")

        return "\n".join(lines)

    def _format_value(self, value: float) -> str:
        if isnan(value):
            return "N/A"

        return f"{value:.2f}"
