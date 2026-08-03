from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3

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
    swing_score: float
    swing_label: str
    opportunity_score: MinimalOppScore


@dataclass
class MinimalRunResult:
    generated_at: datetime
    success_count: int
    error_count: int
    next_day_results: list
    swing_results: list
    report_path: str = None
    markdown_report_path: str = None
    next_day_report_path: str = None
    swing_report_path: str = None
    dashboard_report_path: str = None


def load_latest_scan_result() -> MinimalRunResult | None:
    """Fetch latest scanner run results directly from the signal history database."""
    store = SignalHistoryStore()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        latest_run = conn.execute("SELECT * FROM scanner_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not latest_run:
            return None

        run_id = latest_run["id"]
        generated_at = datetime.fromisoformat(latest_run["generated_at"])
        success_count = latest_run["success_count"]
        error_count = latest_run["error_count"]

        rows = conn.execute("SELECT * FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (run_id,)).fetchall()

        next_day_list = []
        swing_list = []
        for r in rows:
            row = dict(r)
            item = MinimalResultRow(
                symbol=row["symbol"],
                next_day_score=row.get("next_day_score", 0.0),
                next_day_label=row.get("next_day_label", ""),
                swing_score=row.get("swing_score", 0.0),
                swing_label=row.get("swing_label", ""),
                opportunity_score=MinimalOppScore(latest_close=row["latest_close"]),
            )
            next_day_list.append(item)
            swing_list.append(item)

        next_day_list = sorted(next_day_list, key=lambda x: x.next_day_score, reverse=True)
        swing_list = sorted(swing_list, key=lambda x: x.swing_score, reverse=True)

        return MinimalRunResult(
            generated_at=generated_at,
            success_count=success_count,
            error_count=error_count,
            next_day_results=next_day_list,
            swing_results=swing_list,
            report_path=latest_run["report_path"],
            markdown_report_path=latest_run["markdown_report_path"],
            dashboard_report_path="reports/dashboard.html",
        )


def main() -> int:
    args = parse_args()
    result = None

    if args.use_latest:
        result = load_latest_scan_result()
        if result is None:
            raise SystemExit("No scanner runs found in database.")
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)
    elif args.run_scanner:
        result = ScannerWorkflow().run(symbols=parse_symbols(args.symbols))
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)
    elif args.message:
        message = args.message
    else:
        result = load_latest_scan_result()
        if result is None:
            raise SystemExit("Use --use-latest, --run-scanner, or --message.")
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
        result.swing_report_path,
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
