import csv
from pathlib import Path

from praecursor.backtesting.engine import BacktestResult, BacktestSignal, BacktestSummaryRow

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BACKTEST_SIGNALS_REPORT = ROOT / "reports" / "backtest_signals.csv"
DEFAULT_BACKTEST_SUMMARY_REPORT = ROOT / "reports" / "backtest_summary.csv"


class BacktestCSVReportWriter:
    """Write backtest signal and summary CSV reports."""

    def write_signals(
        self,
        result: BacktestResult,
        output_path: Path = DEFAULT_BACKTEST_SIGNALS_REPORT,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._signal_fieldnames(result)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for signal in result.signals:
                writer.writerow(self._signal_row(signal, result.horizons))

        return output_path

    def write_summary(
        self,
        result: BacktestResult,
        output_path: Path = DEFAULT_BACKTEST_SUMMARY_REPORT,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._summary_fieldnames(result)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for summary_row in result.summary:
                writer.writerow(self._summary_row(summary_row, result.horizons))

        return output_path

    def _signal_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = [
            "symbol",
            "company",
            "signal_date",
            "label",
            "opportunity_score",
            "entry_close",
            "rsi14",
            "rel_volume20",
            "macd_histogram",
            "momentum20",
            "breakout20",
            "breakout50",
        ]
        fields.extend([f"return_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _summary_fieldnames(self, result: BacktestResult) -> list[str]:
        fields = ["label", "signal_count"]
        fields.extend([f"avg_return_{horizon}_bars" for horizon in result.horizons])
        fields.extend([f"win_rate_{horizon}_bars" for horizon in result.horizons])
        return fields

    def _signal_row(self, signal: BacktestSignal, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {
            "symbol": signal.symbol,
            "company": signal.company,
            "signal_date": signal.signal_date.isoformat(),
            "label": signal.label,
            "opportunity_score": self._format_number(signal.opportunity_score),
            "entry_close": self._format_number(signal.entry_close),
            "rsi14": self._format_number(signal.indicator_values.get("RSI14", float("nan"))),
            "rel_volume20": self._format_number(signal.indicator_values.get("RelVolume20", float("nan"))),
            "macd_histogram": self._format_number(signal.indicator_values.get("MACDHistogram", float("nan"))),
            "momentum20": self._format_number(signal.indicator_values.get("Momentum20", float("nan"))),
            "breakout20": self._format_number(signal.indicator_values.get("Breakout20", float("nan"))),
            "breakout50": self._format_number(signal.indicator_values.get("Breakout50", float("nan"))),
        }

        for horizon in horizons:
            row[f"return_{horizon}_bars"] = self._format_number(signal.forward_returns[horizon])

        return row

    def _summary_row(self, summary: BacktestSummaryRow, horizons: tuple[int, ...]) -> dict[str, str]:
        row = {
            "label": summary.label,
            "signal_count": str(summary.signal_count),
        }

        for horizon in horizons:
            row[f"avg_return_{horizon}_bars"] = self._format_number(summary.average_returns[horizon])

        for horizon in horizons:
            row[f"win_rate_{horizon}_bars"] = self._format_number(summary.win_rates[horizon])

        return row

    def _format_number(self, value: float) -> str:
        if value != value:
            return "N/A"

        return f"{value:.2f}"
