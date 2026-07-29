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
            "| Rank | Symbol | Previous | Change | Opportunity Score | Final Score | Label | Next-Day Score | Next-Day Label | Swing Score | Swing Label | Latest Close | EMA20 | EMA50 | EMA200 | RSI14 | MACD Hist | Momentum20 | RelVol20 | Breakout20 | Breakout50 | NearHigh250% | ATR% | Consensus | Consensus Confidence | Data Quality | H/L Quality |",
            "| ---: | --- | ---: | --- | ---: | ---: | --- | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"
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
                f"{result.previous_rank if result.previous_rank is not None else 'new'} | "
                f"{result.rank_change_text} | "
                f"{score.total_score:.0f}/{score.max_score:.0f} | "
                f"{result.final_predictor_score:.0f}/100 | "
                f"{result.predictor_label} | "
                f"{result.next_day_score:.0f}/100 | "
                f"{result.next_day_label} | "
                f"{result.swing_score:.0f}/100 | "
                f"{result.swing_label} | "
                f"{score.latest_close:.2f} | "
                f"{self._format_value(score.indicator_values.get('EMA20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('EMA50', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('EMA200', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('RSI14', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('MACDHistogram', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('Momentum20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('RelVolume20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('Breakout20', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('Breakout50', float('nan')))} | "
                f"{self._format_value(score.indicator_values.get('NearCloseHigh250Percent', float('nan')))} | "
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
                    f"- Final predictor score: **{result.final_predictor_score:.0f}/100**",
                    f"- Predictor label: **{result.predictor_label}**",
                    f"- Predictor reasons: {result.predictor_reasons_text}",
                    f"- Next-day score: **{result.next_day_score:.0f}/100**",
                    f"- Next-day label: **{result.next_day_label}**",
                    f"- Next-day reasons: {result.next_day_reasons_text}",
                    f"- Swing score: **{result.swing_score:.0f}/100**",
                    f"- Swing label: **{result.swing_label}**",
                    f"- Swing reasons: {result.swing_reasons_text}",
                    f"- Previous rank: **{result.previous_rank if result.previous_rank is not None else 'new'}**",
                    f"- Rank change: **{result.rank_change_text}**",
                    f"- Latest close: **{score.latest_close:.2f}**",
                    f"- Average volume 20: **{self._format_value(score.indicator_values.get('AvgVolume20', float('nan')))}**",
                    f"- Relative volume 20: **{self._format_value(score.indicator_values.get('RelVolume20', float('nan')))}**",
                    f"- MACD histogram: **{self._format_value(score.indicator_values.get('MACDHistogram', float('nan')))}**",
                    f"- Momentum20: **{self._format_value(score.indicator_values.get('Momentum20', float('nan')))}%**",
                    f"- Trend strength: **{self._format_value(score.indicator_values.get('TrendStrength', float('nan')))} / 100**",
                    f"- Breakout20: **{self._format_value(score.indicator_values.get('Breakout20', float('nan')))}**",
                    f"- Breakout50: **{self._format_value(score.indicator_values.get('Breakout50', float('nan')))}**",
                    f"- CloseHigh250: **{self._format_value(score.indicator_values.get('CloseHigh250', float('nan')))}**",
                    f"- NearCloseHigh250Percent: **{self._format_value(score.indicator_values.get('NearCloseHigh250Percent', float('nan')))}%**",
                    f"- Volume confirmed breakout: **{self._format_value(score.indicator_values.get('VolumeConfirmedBreakout', float('nan')))}**",
                    f"- RSI rebound: **{self._format_value(score.indicator_values.get('RSIRebound', float('nan')))}**",
                    f"- EMA20 reclaim: **{self._format_value(score.indicator_values.get('EMA20Reclaim', float('nan')))}**",
                    f"- MACD histogram improvement: **{self._format_value(score.indicator_values.get('MACDHistogramImprovement', float('nan')))}**",
                    f"- Volume spike from weakness: **{self._format_value(score.indicator_values.get('VolumeSpikeFromWeakness', float('nan')))}**",
                    f"- Momentum5: **{self._format_value(score.indicator_values.get('Momentum5', float('nan')))}%**",
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
                        f"- Consensus sources used: **{result.consensus_source_names_text}**",
                        f"- Confidence vs 5-source target: **{consensus.confidence_percent:.0f}% ({consensus.confidence_label})**",
                    ]
                )
            elif result.consensus_error:
                lines.append(f"- Consensus error: {result.consensus_error}")

            if result.consensus_source_errors:
                lines.append(f"- Consensus source errors: {result.consensus_source_errors_text}")

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
