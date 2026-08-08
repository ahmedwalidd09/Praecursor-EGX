from dataclasses import dataclass
from datetime import datetime
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

from praecursor.notifications.telegram import TelegramClient, TelegramReportFormatter, TelegramSettings
from praecursor.storage.signal_history import SignalHistoryStore
from praecursor.workflows.scanner import ScannerWorkflow


@dataclass
class MinimalOppScore:
    latest_close: float


@dataclass
class MinimalResultRow:
    symbol: str
    next_day_score: float
    next_day_label: str
    opportunity_score: MinimalOppScore


@dataclass
class MinimalRunResult:
    generated_at: datetime
    success_count: int
    error_count: int
    next_day_results: list
    report_path: str = None
    markdown_report_path: str = None
    next_day_report_path: str = None
    dashboard_report_path: str = None


def load_latest_scan_result() -> MinimalRunResult | None:
    """Fetch latest scanner run results directly from the signal history database."""
    store = SignalHistoryStore()
    try:
        with store._connect() as conn:
            conn.row_factory = sqlite3.Row
            latest_run = conn.execute("SELECT * FROM scanner_runs ORDER BY id DESC LIMIT 1").fetchone()
            if not latest_run:
                return None

            run_id = latest_run["id"]
            gen_at_str = latest_run["generated_at"]
            if isinstance(gen_at_str, str):
                generated_at = datetime.fromisoformat(gen_at_str.replace('Z', '+00:00'))
            else:
                generated_at = datetime.now()
            success_count = latest_run["success_count"]
            error_count = latest_run["error_count"]

            rows = conn.execute("SELECT * FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (run_id,)).fetchall()

            next_day_list = []
            for r in rows:
                row = dict(r)
                item = MinimalResultRow(
                    symbol=row["symbol"],
                    next_day_score=row.get("next_day_score", 0.0) or 0.0,
                    next_day_label=row.get("next_day_label", "") or "",
                    opportunity_score=MinimalOppScore(latest_close=row["latest_close"]),
                )
                next_day_list.append(item)

            next_day_list = sorted(next_day_list, key=lambda x: x.next_day_score, reverse=True)

            return MinimalRunResult(
                generated_at=generated_at,
                success_count=success_count,
                error_count=error_count,
                next_day_results=next_day_list,
                report_path=latest_run["report_path"],
                markdown_report_path=latest_run["markdown_report_path"],
                dashboard_report_path="reports/dashboard.html",
            )
    except Exception as e:
        return None


def main() -> int:
    args = parse_args()
    result = None

    if args.use_latest:
        result = load_latest_scan_result()
        if result is None:
            print("Warning: No scanner runs found in database. Exiting cleanly.")
            return 0
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)
    elif args.run_scanner:
        result = ScannerWorkflow().run(symbols=parse_symbols(args.symbols))
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)
    elif args.message:
        message = args.message
    else:
        result = load_latest_scan_result()
        if result is None:
            print("Warning: No scanner runs found in database. Exiting cleanly.")
            return 0
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)

    if args.dry_run:
        print(message)
        return 0

    client = TelegramClient(TelegramSettings.from_environment())
    client.send_message(message)
    print("Telegram message sent.")

    if args.send_files and result is not None:
        send_report_files(client, result)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Praecursor-EGX scanner report to Telegram.")
    parser.add_argument("--use-latest", action="store_true", help="Send summary from latest database scan run.")
    parser.add_argument("--run-scanner", action="store_true", help="Run scanner first and send its summary.")
    parser.add_argument("--symbols", help="Comma-separated symbols for scanner run, e.g. COMI,SWDY.")
    parser.add_argument("--message", help="Send a custom Telegram message instead of scanner output.")
    parser.add_argument("--top", type=int, default=5, help="Number of candidates per section. Default: 5.")
    parser.add_argument("--send-files", action="store_true", help="Also send CSV/HTML/Markdown report files.")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending to Telegram.")
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def send_report_files(client: TelegramClient, result) -> None:
    paths = [
        result.next_day_report_path,
        result.report_path,
        result.markdown_report_path,
        result.dashboard_report_path,
    ]
    for path in paths:
        if path and Path(path).exists():
            client.send_document(Path(path), caption=f"Praecursor-EGX report: {Path(path).name}")
            print(f"Telegram file sent: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
