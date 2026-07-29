import csv
from pathlib import Path

from praecursor.backtesting.engine import (
    BacktestDataIssue,
    BacktestLabelExample,
    BacktestResult,
    BacktestScoreBucketSummaryRow,
    BacktestSignal,
    BacktestSummaryRow,
    BacktestSymbolSummaryRow,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BACKTEST_SIGNALS_REPORT = ROOT / "reports" / "backtest_signals.csv"
DEFAULT_BACKTEST_SUMMARY_REPORT = ROOT / "reports" / "backtest_summary.csv"
DEFAULT_BACKTEST_SYMBOL_SUMMARY_REPORT = ROOT / "reports" / "backtest_symbol_summary.csv"
DEFAULT_BACKTEST_SCORE_BUCKET_REPORT = ROOT / "reports" / "backtest_score_buckets.csv"
DEFAULT_BACKTEST_BEST_REPORT = ROOT / "reports" / "backtest_best_signals.csv"
DEFAULT_BACKTEST_WORST_REPORT = ROOT / "reports" / "backtest_worst_signals.csv"
DEFAULT_BACKTEST_LABEL_EXAMPLES_REPORT = ROOT / "reports" / "backtest_label_examples.csv"
DEFAULT_BACKTEST_MISSED_MOVERS_REPORT = ROOT / "reports" / "backtest_missed_movers.csv"
DEFAULT_BACKTEST_OVEREXTENSION_REPORT = ROOT / "reports" / "backtest_overextension.csv"
DEFAULT_BACKTEST_DATA_ISSUES_REPORT = ROOT / "reports" / "backtest_data_issues.csv"
DEFAULT_BACKTEST_MARKDOWN_REPORT = ROOT / "reports" / "backtest_summary.md"


class BacktestCSVReportWriter:
    """Write backtest signal and summary reports."""

    def write_all(self, result: BacktestResult) -> dict[str, Path]:
        return {
            "signals": self.write_signals(result),
            "summary": self.write_summary(result),
            "symbol_summary": self.write_symbol_summary(result),
            "score_buckets": self.write_score_buckets(result),
            "best_signals": self.write_signal_examples(result.best_signals, result, DEFAULT_BACKTEST_BEST_REPORT),
            "worst_signals": self.write_signal_examples(result.worst_signals, result, DEFAULT_BACKTEST_WORST_REPORT),
            "label_examples": self.write_label_examples(result),
            "missed_movers": self.write_signal_examples(result.missed_movers, result, DEFAULT_BACKTEST_MISSED_MOVERS_REPORT),
            "overextension": self.write_signal_examples(result.overextension_signals, result, DEFAULT_BACKTEST_OVEREXTENSION_REPORT),
            "data_issues": self.write_data_issues(result),
            "markdown": self.write_markdown(result),
        }

    def write_signals(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_SIGNALS_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._signal_fieldnames(result)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for signal in result.signals:
                writer.writerow(self._signal_row(signal, result.horizons))
        return output_path

    def write_summary(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_SUMMARY_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._summary_fieldnames(result)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for summary_row in result.summary:
                writer.writerow(self._summary_row(summary_row, result.horizons))
        return output_path

    def write_symbol_summary(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_SYMBOL_SUMMARY_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._symbol_summary_fieldnames(result)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for summary_row in result.symbol_summary:
                writer.writerow(self._symbol_summary_row(summary_row, result.horizons))
        return output_path

    def write_score_buckets(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_SCORE_BUCKET_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._score_bucket_fieldnames(result)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for summary_row in result.score_bucket_summary:
                writer.writerow(self._score_bucket_row(summary_row, result.horizons))
        return output_path

    def write_signal_examples(self, signals: list[BacktestSignal], result: BacktestResult, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._signal_fieldnames(result)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for signal in signals:
                writer.writerow(self._signal_row(signal, result.horizons))
        return output_path

    def write_label_examples(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_LABEL_EXAMPLES_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["example_label", "example_type", *self._signal_fieldnames(result)]
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for example in result.label_examples:
                row = self._signal_row(example.signal, result.horizons)
                writer.writerow({"example_label": example.label, "example_type": example.example_type, **row})
        return output_path

    def write_data_issues(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_DATA_ISSUES_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["symbol", "issue", "detail"])
            writer.writeheader()
            for issue in result.data_issues:
                writer.writerow(self._data_issue_row(issue))
        return output_path

    def write_markdown(self, result: BacktestResult, output_path: Path = DEFAULT_BACKTEST_MARKDOWN_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._markdown_content(result), encoding="utf-8")
        return output_path

    def _signal_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = [
            "symbol",
            "company",
            "signal_date",
            "label",
            "score_bucket",
            "opportunity_score",
            "next_day_score",
            "swing_label",
            "swing_score",
            "entry_close",
            "rsi14",
            "rel_volume20",
            "macd_histogram",
            "momentum20",
            "breakout20",
            "breakout50",
            "rsi_rebound",
            "ema20_reclaim",
            "macd_histogram_improvement",
            "volume_spike_from_weakness",
            "momentum5",
        ]
        fields.extend([f"return_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _summary_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = ["label", "signal_count", "warning"]
        fields.extend([f"avg_return_{horizon}_bars" for horizon in result.horizons])
        fields.extend([f"win_rate_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _symbol_summary_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = ["symbol", "company", "signal_count"]
        fields.extend([f"avg_return_{horizon}_bars" for horizon in result.horizons])
        fields.extend([f"win_rate_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _score_bucket_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = ["bucket", "signal_count", "warning"]
        fields.extend([f"avg_return_{horizon}_bars" for horizon in result.horizons])
        fields.extend([f"win_rate_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _signal_row(self, signal: BacktestSignal, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {
            "symbol": signal.symbol,
            "company": signal.company,
            "signal_date": signal.signal_date.isoformat(),
            "label": signal.label,
            "score_bucket": signal.score_bucket,
            "opportunity_score": self._format_number(signal.opportunity_score),
            "next_day_score": self._format_number(signal.next_day_score),
            "swing_label": signal.swing_label,
            "swing_score": self._format_number(signal.swing_score),
            "entry_close": self._format_number(signal.entry_close),
            "rsi14": self._format_number(signal.indicator_values.get("RSI14", float("nan"))),
            "rel_volume20": self._format_number(signal.indicator_values.get("RelVolume20", float("nan"))),
            "macd_histogram": self._format_number(signal.indicator_values.get("MACDHistogram", float("nan"))),
            "momentum20": self._format_number(signal.indicator_values.get("Momentum20", float("nan"))),
            "breakout20": self._format_number(signal.indicator_values.get("Breakout20", float("nan"))),
            "breakout50": self._format_number(signal.indicator_values.get("Breakout50", float("nan"))),
            "rsi_rebound": self._format_number(signal.indicator_values.get("RSIRebound", float("nan"))),
            "ema20_reclaim": self._format_number(signal.indicator_values.get("EMA20Reclaim", float("nan"))),
            "macd_histogram_improvement": self._format_number(signal.indicator_values.get("MACDHistogramImprovement", float("nan"))),
            "volume_spike_from_weakness": self._format_number(signal.indicator_values.get("VolumeSpikeFromWeakness", float("nan"))),
            "momentum5": self._format_number(signal.indicator_values.get("Momentum5", float("nan"))),
        }
        for horizon in horizons:
            row[f"return_{horizon}_bars"] = self._format_number(signal.forward_returns[horizon])
        return row

    def _summary_row(self, summary: BacktestSummaryRow, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {"label": summary.label, "signal_count": str(summary.signal_count), "warning": summary.warning or ""}
        for horizon in horizons:
            row[f"avg_return_{horizon}_bars"] = self._format_number(summary.average_returns[horizon])
        for horizon in horizons:
            row[f"win_rate_{horizon}_bars"] = self._format_number(summary.win_rates[horizon])
        return row

    def _symbol_summary_row(self, summary: BacktestSymbolSummaryRow, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {"symbol": summary.symbol, "company": summary.company, "signal_count": str(summary.signal_count)}
        for horizon in horizons:
            row[f"avg_return_{horizon}_bars"] = self._format_number(summary.average_returns[horizon])
        for horizon in horizons:
            row[f"win_rate_{horizon}_bars"] = self._format_number(summary.win_rates[horizon])
        return row

    def _score_bucket_row(self, summary: BacktestScoreBucketSummaryRow, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {"bucket": summary.bucket, "signal_count": str(summary.signal_count), "warning": summary.warning or ""}
        for horizon in horizons:
            row[f"avg_return_{horizon}_bars"] = self._format_number(summary.average_returns[horizon])
        for horizon in horizons:
            row[f"win_rate_{horizon}_bars"] = self._format_number(summary.win_rates[horizon])
        return row

    def _data_issue_row(self, issue: BacktestDataIssue) -> dict[str, str]:
        return {"symbol": issue.symbol, "issue": issue.issue, "detail": issue.detail}

    def _markdown_content(self, result: BacktestResult) -> str:
        lines = [
            "# Praecursor-EGX Backtest Summary",
            "",
            f"- Source: {result.source_name}",
            f"- Symbols: {', '.join(result.symbols)}",
            f"- Date range: {result.start_date} to {result.end_date}",
            f"- Horizons: {', '.join(str(horizon) for horizon in result.horizons)} bars",
            f"- Signals: {len(result.signals)}",
            f"- Errors: {len(result.errors)}",
            "",
            "## Calibration notes",
            "",
        ]
        if result.calibration_notes:
            lines.extend([f"- {note}" for note in result.calibration_notes])
        else:
            lines.append("- No calibration warnings generated.")
        lines.extend(["", "## Summary by label", ""])
        lines.extend(self._markdown_summary_table(result.summary, result.horizons, "Label"))
        lines.extend(["", "## Summary by score bucket", ""])
        lines.extend(self._markdown_bucket_table(result.score_bucket_summary, result.horizons))
        lines.extend(["", "## Summary by symbol", ""])
        lines.extend(self._markdown_symbol_table(result.symbol_summary, result.horizons))
        lines.extend(["", "## Missed next-day movers", ""])
        lines.extend(self._markdown_signal_table(result.missed_movers[:10], result.horizons))
        lines.extend(["", "## Overextension follow-through", ""])
        lines.extend(self._markdown_signal_table(result.overextension_signals[:10], result.horizons))
        lines.extend(["", "## Best signals", ""])
        lines.extend(self._markdown_signal_table(result.best_signals, result.horizons))
        lines.extend(["", "## Worst signals", ""])
        lines.extend(self._markdown_signal_table(result.worst_signals, result.horizons))
        if result.data_issues:
            lines.extend(["", "## Data issues", ""])
            for issue in result.data_issues:
                lines.append(f"- {issue.symbol}: {issue.issue} — {issue.detail}")
        if result.errors:
            lines.extend(["", "## Errors", ""])
            for symbol, error in result.errors.items():
                lines.append(f"- {symbol}: {error}")
        return "\n".join(lines)

    def _markdown_summary_table(self, rows: list[BacktestSummaryRow], horizons: tuple[int, ...], first_column: str) -> list[str]:
        header = f"| {first_column} | Signals | " + " | ".join(f"Avg {h} bars | Win {h} bars" for h in horizons) + " | Warning |"
        separator = "| --- | ---: | " + " | ".join("---: | ---:" for _ in horizons) + " | --- |"
        lines = [header, separator]
        for row in rows:
            cells = [row.label, str(row.signal_count)]
            for horizon in horizons:
                cells.append(f"{row.average_returns[horizon]:.2f}%")
                cells.append(f"{row.win_rates[horizon]:.0f}%")
            cells.append(row.warning or "")
            lines.append("| " + " | ".join(cells) + " |")
        return lines

    def _markdown_bucket_table(self, rows: list[BacktestScoreBucketSummaryRow], horizons: tuple[int, ...]) -> list[str]:
        header = "| Bucket | Signals | " + " | ".join(f"Avg {h} bars | Win {h} bars" for h in horizons) + " | Warning |"
        separator = "| --- | ---: | " + " | ".join("---: | ---:" for _ in horizons) + " | --- |"
        lines = [header, separator]
        for row in rows:
            cells = [row.bucket, str(row.signal_count)]
            for horizon in horizons:
                cells.append(f"{row.average_returns[horizon]:.2f}%")
                cells.append(f"{row.win_rates[horizon]:.0f}%")
            cells.append(row.warning or "")
            lines.append("| " + " | ".join(cells) + " |")
        return lines

    def _markdown_symbol_table(self, rows: list[BacktestSymbolSummaryRow], horizons: tuple[int, ...]) -> list[str]:
        header = "| Symbol | Signals | " + " | ".join(f"Avg {h} bars | Win {h} bars" for h in horizons) + " |"
        separator = "| --- | ---: | " + " | ".join("---: | ---:" for _ in horizons) + " |"
        lines = [header, separator]
        for row in rows:
            cells = [row.symbol, str(row.signal_count)]
            for horizon in horizons:
                cells.append(f"{row.average_returns[horizon]:.2f}%")
                cells.append(f"{row.win_rates[horizon]:.0f}%")
            lines.append("| " + " | ".join(cells) + " |")
        return lines

    def _markdown_signal_table(self, signals: list[BacktestSignal], horizons: tuple[int, ...]) -> list[str]:
        header = "| Symbol | Date | Next-Day Label | Next-Day Score | Swing Label | Swing Score | " + " | ".join(f"Return {h}" for h in horizons) + " |"
        separator = "| --- | --- | --- | ---: | --- | ---: | " + " | ".join("---:" for _ in horizons) + " |"
        lines = [header, separator]
        for signal in signals:
            cells = [signal.symbol, signal.signal_date.isoformat(), signal.label, f"{signal.next_day_score:.0f}", signal.swing_label, f"{signal.swing_score:.0f}"]
            for horizon in horizons:
                cells.append(f"{signal.forward_returns[horizon]:.2f}%")
            lines.append("| " + " | ".join(cells) + " |")
        return lines

    def _format_number(self, value: float) -> str:
        if value != value:
            return "N/A"
        return f"{value:.2f}"
